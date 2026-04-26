#!/usr/bin/env python3
"""Build a player-season regression dataset with market value target.

The script merges:
- API-Football player stats (auto-picks per_fixture or per_season by null completeness)
- Understat player-season data
- Transfermarkt market values from DuckDB

Output:
- data/merged/player_season_regression_dataset.csv
"""

from __future__ import annotations

import argparse
import csv
import glob
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
API_FIXTURE_GLOB = (
    ROOT / "data" / "api_football" / "per_fixture" / "player_stats_from_fixtures" / "league_*" / "*.csv"
)
API_SEASON_GLOB = (
    ROOT / "data" / "api_football" / "per_season" / "player_stats" / "league_*" / "*.csv"
)
UNDERSTAT_CSV = ROOT / "data" / "understat_player_season.csv"
TRANSFERMARKT_DUCKDB = ROOT / "data" / "transfermarkt-datasets.duckdb"
OUTPUT_CSV = ROOT / "data" / "merged" / "player_season_regression_dataset.csv"
OUTPUT_ALL3_CSV = ROOT / "data" / "merged" / "player_season_regression_dataset_all3.csv"


LEAGUE_ID_TO_UNDERSTAT = {
    "39": "ENG-Premier League",
    "61": "FRA-Ligue 1",
    "78": "GER-Bundesliga",
    "135": "ITA-Serie A",
    "140": "ESP-La Liga",
}

COMPLETENESS_COLUMNS = [
    "position",
    "minutes",
    "appearances",
    "goals_total",
    "goals_assists",
    "shots_total",
    "shots_on",
    "cards_yellow",
    "cards_red",
]

def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("&", " and ")
    text = re.sub(r"\b(fc|cf|ac|afc|sc|club)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def player_key_variants(normalized_player: str) -> list[str]:
    """Return candidate normalized player keys for cross-source matching.

    Understat sometimes includes extra surname tokens (e.g. 'mbappe lottin')
    while API-Football typically uses a shorter form (e.g. 'mbappe').
    We try the full normalized key first, then fall back to a short key built
    from the first two tokens.
    """
    key = (normalized_player or "").strip()
    if not key:
        return []
    tokens = key.split()
    if len(tokens) <= 2:
        return [key]
    short2 = " ".join(tokens[:2]).strip()
    # Keep ordering: most-specific first.
    out = [key]
    if short2 and short2 != key:
        out.append(short2)
    return out


def parse_season(value: Any) -> int | None:
    if value is None:
        return None
    text = re.sub(r"[^0-9]", "", str(value))
    if not text:
        return None
    if len(text) == 4:
        number = int(text)
        # True calendar year style, e.g. 2019, 2024.
        if 2000 <= number <= 2099:
            return number
        # Two-part season code style, e.g. 1516, 1920, 2223.
        left = int(text[:2])
        right = int(text[2:])
        if right == (left + 1) % 100:
            return 2000 + left
    if len(text) == 2:
        return 2000 + int(text)
    if len(text) == 8:
        return int(text[:4])
    return None


def parse_understat_season_candidates(value: Any) -> list[int]:
    """Return possible season start years for an Understat season key.

    Rules:
    - 1516 / 1920 / 2223 style -> single start year (2015 / 2019 / 2022)
    - 4-digit year YYYY -> season start YYYY (strict, no ambiguity)
    """
    if value is None:
        return []
    text = re.sub(r"[^0-9]", "", str(value))
    if not text:
        return []

    if len(text) == 4:
        left = int(text[:2])
        right = int(text[2:])
        if right == (left + 1) % 100:
            return [2000 + left]

        year = int(text)
        if 2000 <= year <= 2099:
            return [year]

    parsed = parse_season(value)
    return [parsed] if parsed is not None else []


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def age_on_date(dob_value: Any, ref_date: date) -> int | None:
    if dob_value in (None, ""):
        return None
    if isinstance(dob_value, datetime):
        dob = dob_value.date()
    elif isinstance(dob_value, date):
        dob = dob_value
    else:
        text = str(dob_value).strip()
        if not text:
            return None
        try:
            dob = datetime.fromisoformat(text.replace("Z", "")).date()
        except ValueError:
            try:
                dob = date.fromisoformat(text[:10])
            except ValueError:
                return None

    years = ref_date.year - dob.year
    if (ref_date.month, ref_date.day) < (dob.month, dob.day):
        years -= 1
    return years if years >= 0 else None


def pick_api_source(preferred: str | None) -> tuple[str, list[str], dict[str, float]]:
    sources = {
        "per_fixture": sorted(glob.glob(str(API_FIXTURE_GLOB))),
        "per_season": sorted(glob.glob(str(API_SEASON_GLOB))),
    }
    if preferred:
        if preferred not in sources:
            raise ValueError("api_source must be one of: per_fixture, per_season")
        return preferred, sources[preferred], {}

    scores: dict[str, float] = {}
    for source_name, paths in sources.items():
        if not paths:
            scores[source_name] = 1.0
            continue

        total = 0
        missing = 0
        for path in paths:
            with open(path, newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    total += len(COMPLETENESS_COLUMNS)
                    missing += sum(1 for col in COMPLETENESS_COLUMNS if row.get(col) in (None, ""))
        scores[source_name] = (missing / total) if total else 1.0

    chosen = min(scores, key=scores.get)
    return chosen, sources[chosen], scores


API_SUM_COLUMNS = [
    "squad_rows",
    "appearances",
    "starts",
    "sub_appearances",
    "minutes",
    "offsides",
    "shots_total",
    "shots_on",
    "goals_total",
    "goals_conceded",
    "goals_assists",
    "goals_saves",
    "passes_total",
    "passes_key",
    "tackles_total",
    "tackles_blocks",
    "tackles_interceptions",
    "duels_total",
    "duels_won",
    "dribbles_attempts",
    "dribbles_success",
    "dribbles_past",
    "fouls_drawn",
    "fouls_committed",
    "cards_yellow",
    "cards_red",
    "penalty_won",
    "penalty_commited",
    "penalty_scored",
    "penalty_missed",
    "penalty_saved",
]
API_PER90_BASES = [
    "goals_total",
    "goals_assists",
    "shots_total",
    "shots_on",
    "passes_key",
    "tackles_total",
    "duels_won",
    "cards_yellow",
    "cards_red",
]
API_WEIGHTED_AVG_COLUMNS = ["avg_rating", "passes_accuracy"]


def _format_number(value: float | int) -> str:
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.6g}"
    return str(value)


def _aggregate_api_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate multiple per-team rows of the same player+season into one row."""
    if len(group) == 1:
        return group[0]

    minutes_by_row = [as_float(row.get("minutes")) or 0.0 for row in group]
    primary_idx = max(range(len(group)), key=lambda i: minutes_by_row[i])
    primary = group[primary_idx]

    aggregated: dict[str, Any] = dict(primary)

    total_minutes = sum(minutes_by_row)

    for col in API_SUM_COLUMNS:
        if col not in primary:
            continue
        total = 0.0
        any_value = False
        for row in group:
            val = as_float(row.get(col))
            if val is not None:
                total += val
                any_value = True
        aggregated[col] = _format_number(total) if any_value else ""

    for col in API_WEIGHTED_AVG_COLUMNS:
        if col not in primary:
            continue
        weight_sum = 0.0
        weighted = 0.0
        any_value = False
        for row, minutes in zip(group, minutes_by_row):
            val = as_float(row.get(col))
            if val is None:
                continue
            any_value = True
            weight = minutes if minutes > 0 else 1.0
            weighted += val * weight
            weight_sum += weight
        if any_value and weight_sum > 0:
            aggregated[col] = f"{weighted / weight_sum:.3f}"
        else:
            aggregated[col] = ""

    aggregated_minutes = as_float(aggregated.get("minutes")) or 0.0
    for base in API_PER90_BASES:
        per90_col = f"{base}_per90"
        if per90_col not in primary:
            continue
        base_value = as_float(aggregated.get(base))
        if base_value is not None and aggregated_minutes > 0:
            aggregated[per90_col] = f"{base_value * 90 / aggregated_minutes:.3f}"
        else:
            aggregated[per90_col] = ""

    # Concatenate distinct teams played for during the season for traceability.
    team_names_seen: list[str] = []
    for row in group:
        name = (row.get("team_name") or "").strip()
        if name and name not in team_names_seen:
            team_names_seen.append(name)
    aggregated["team_name"] = team_names_seen[0] if team_names_seen else aggregated.get("team_name", "")
    aggregated["all_team_names_in_season"] = "|".join(team_names_seen)

    aggregated["norm_player"] = primary.get("norm_player", "")
    aggregated["norm_team"] = primary.get("norm_team", "")
    aggregated["understat_league"] = primary.get("understat_league", "")
    return aggregated


def deduplicate_api_rows_per_player_season(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, int], list[dict[str, Any]]] = defaultdict(list)
    no_id_rows: list[dict[str, Any]] = []
    for row in rows:
        player_id = str(row.get("player_id", "")).strip()
        if not player_id:
            no_id_rows.append(row)
            continue
        season = int(row["season"])
        grouped[(player_id, season)].append(row)

    deduped: list[dict[str, Any]] = []
    for group in grouped.values():
        deduped.append(_aggregate_api_group(group))
    deduped.extend(no_id_rows)
    return deduped


def read_api_rows(paths: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    api_columns_order: list[str] = []
    seen_columns: set[str] = set()
    for path in paths:
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for col in reader.fieldnames or []:
                if col not in seen_columns:
                    seen_columns.add(col)
                    api_columns_order.append(col)
            for row in reader:
                season = parse_season(row.get("season"))
                if season is None:
                    continue
                out: dict[str, Any] = dict(row)
                out["season"] = season
                out["norm_player"] = normalize_text(row.get("player_name"))
                out["norm_team"] = normalize_text(row.get("team_name"))
                out["understat_league"] = LEAGUE_ID_TO_UNDERSTAT.get(str(row.get("league_id")), "")
                rows.append(out)

    rows = deduplicate_api_rows_per_player_season(rows)
    if "all_team_names_in_season" not in api_columns_order:
        api_columns_order.append("all_team_names_in_season")
    return rows, api_columns_order


def load_per_season_height_weight() -> tuple[dict[tuple[int, str], dict[str, Any]], dict[tuple[int, str, str], dict[str, Any]]]:
    """Load height/weight from per-season stats keyed primarily by season+player_id."""
    bio_by_id: dict[tuple[int, str], dict[str, Any]] = {}
    bio_by_name_league: dict[tuple[int, str, str], dict[str, Any]] = {}
    for path in sorted(glob.glob(str(API_SEASON_GLOB))):
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                season = parse_season(row.get("season"))
                if season is None:
                    continue
                league_id = str(row.get("league_id", "")).strip()
                player_key = normalize_text(row.get("player_name"))
                if not player_key or not league_id:
                    continue
                player_id = str(row.get("player_id", "")).strip()
                minutes = as_float(row.get("minutes")) or 0.0
                bio_row = {
                    "api_height": row.get("height", ""),
                    "api_weight": row.get("weight", ""),
                    "_minutes": minutes,
                }
                if player_id:
                    key_id = (season, player_id)
                    existing_id = bio_by_id.get(key_id)
                    if existing_id is None or minutes > existing_id.get("_minutes", 0.0):
                        bio_by_id[key_id] = bio_row

                key_fallback = (season, player_key, league_id)
                existing_fallback = bio_by_name_league.get(key_fallback)
                if existing_fallback is None or minutes > existing_fallback.get("_minutes", 0.0):
                    bio_by_name_league[key_fallback] = bio_row
    return bio_by_id, bio_by_name_league


UNDERSTAT_SUM_COLUMNS = [
    "matches",
    "minutes",
    "goals",
    "xg",
    "np_goals",
    "np_xg",
    "assists",
    "xa",
    "shots",
    "key_passes",
    "yellow_cards",
    "red_cards",
    "xg_chain",
    "xg_buildup",
]


def _aggregate_understat_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    if len(group) == 1:
        return group[0]
    primary = max(group, key=lambda r: as_float(r.get("minutes")) or 0.0)
    aggregated = dict(primary)
    for col in UNDERSTAT_SUM_COLUMNS:
        if col not in primary:
            continue
        total = 0.0
        any_value = False
        for row in group:
            val = as_float(row.get(col))
            if val is not None:
                total += val
                any_value = True
        aggregated[col] = _format_number(total) if any_value else ""
    return aggregated


def build_understat_indices() -> tuple[dict[str, dict[tuple[Any, ...], dict[str, Any]]], list[str]]:
    if not UNDERSTAT_CSV.exists():
        return {"full": {}, "player_team": {}, "player_league": {}, "player_only": {}}, []

    grouped: dict[tuple[int, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    understat_columns: list[str] = []
    with open(UNDERSTAT_CSV, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        understat_columns = list(reader.fieldnames or [])
        for row in reader:
            seasons = parse_understat_season_candidates(row.get("season"))
            if not seasons:
                continue
            for season in seasons:
                player_norm = normalize_text(row.get("player"))
                team_norm = normalize_text(row.get("team"))
                league_key = str(row.get("league", ""))
                for player_key in player_key_variants(player_norm):
                    key = (season, player_key, team_norm, league_key)
                    grouped[key].append(row)

    # Keep row with the most minutes for each key (full key already includes team).
    best_full: dict[tuple[int, str, str, str], dict[str, Any]] = {}
    for key, candidates in grouped.items():
        best_full[key] = max(candidates, key=lambda item: as_float(item.get("minutes")) or 0.0)

    # Group by looser keys and aggregate (sum) across teams when player switched mid-season.
    pt_groups: dict[tuple[int, str, str], list[dict[str, Any]]] = defaultdict(list)
    pl_groups: dict[tuple[int, str, str], list[dict[str, Any]]] = defaultdict(list)
    po_groups: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for (season, player_key, team_key, league_key), row in best_full.items():
        pt_groups[(season, player_key, team_key)].append(row)
        pl_groups[(season, player_key, league_key)].append(row)
        po_groups[(season, player_key)].append(row)

    best_player_team = {key: _aggregate_understat_group(rows) for key, rows in pt_groups.items()}
    best_player_league = {key: _aggregate_understat_group(rows) for key, rows in pl_groups.items()}
    best_player_only = {key: _aggregate_understat_group(rows) for key, rows in po_groups.items()}

    return {
        "full": best_full,
        "player_team": best_player_team,
        "player_league": best_player_league,
        "player_only": best_player_only,
    }, understat_columns


def load_transfermarkt_values(
    duckdb_path: Path,
) -> tuple[
    dict[tuple[int, str, str], dict[str, Any]],
    dict[tuple[int, str], dict[str, Any]],
    dict[tuple[int, str, str], dict[str, Any]],
    dict[tuple[int, str], dict[str, Any]],
]:
    if not duckdb_path.exists():
        return {}, {}, {}, {}

    con = duckdb.connect(str(duckdb_path), read_only=True)
    query = """
        SELECT
            EXTRACT(year FROM pv.date)::INT AS valuation_year,
            p.name AS player_name,
            p.date_of_birth AS date_of_birth,
            p.height_in_cm AS height_in_cm,
            pv.current_club_name AS club_name,
            pv.market_value_in_eur AS market_value_in_eur,
            pv.date AS valuation_date
        FROM player_valuations pv
        JOIN players p ON p.player_id = pv.player_id
        WHERE p.name IS NOT NULL
          AND pv.market_value_in_eur IS NOT NULL
    """
    rows = con.execute(query).fetchall()
    con.close()

    by_player_team: dict[tuple[int, str, str], dict[str, Any]] = {}
    by_player_only: dict[tuple[int, str], dict[str, Any]] = {}
    ongoing_by_player_team: dict[tuple[int, str, str], dict[str, Any]] = {}
    ongoing_by_player_only: dict[tuple[int, str], dict[str, Any]] = {}

    for valuation_year, player_name, date_of_birth, height_in_cm, club_name, value, valuation_date in rows:
        # Season x (x-x+1) target must be from valuation posted after season end:
        # [May 1, Sep 30] of x+1.
        # Example: season 2021 target uses valuations in [2022-05-01, 2022-09-30].
        season = int(valuation_year) - 1
        player_key = normalize_text(player_name)
        team_key = normalize_text(club_name)
        season_start_date = date(int(season), 8, 1)
        age_at_season = age_on_date(date_of_birth, season_start_date)
        row = {
            "market_value_eur": int(value),
            "market_value_date": str(valuation_date),
            "transfermarkt_team_name": club_name,
            "transfermarkt_age_at_season": age_at_season,
            "transfermarkt_height_cm": int(height_in_cm) if height_in_cm is not None else None,
            # Weight is not available in this transfermarkt DuckDB snapshot.
            "transfermarkt_weight_kg": None,
        }
        valuation_dt = date.fromisoformat(str(valuation_date))
        season_window_start = date(int(season) + 1, 5, 1)
        season_window_end = date(int(season) + 1, 9, 30)
        if valuation_dt < season_window_start or valuation_dt > season_window_end:
            # Special handling for ongoing season 2025-26:
            # use latest available valuation in calendar year 2025 for merge metadata.
            if int(valuation_year) == 2025:
                ongoing_key_with_team = (2025, player_key, team_key)
                existing_ongoing_team = ongoing_by_player_team.get(ongoing_key_with_team)
                if existing_ongoing_team is None or row["market_value_date"] > existing_ongoing_team["market_value_date"]:
                    ongoing_by_player_team[ongoing_key_with_team] = row

                ongoing_key_player = (2025, player_key)
                existing_ongoing_player = ongoing_by_player_only.get(ongoing_key_player)
                if existing_ongoing_player is None or row["market_value_date"] > existing_ongoing_player["market_value_date"]:
                    ongoing_by_player_only[ongoing_key_player] = row
            continue

        key_with_team = (int(season), player_key, team_key)
        existing_team = by_player_team.get(key_with_team)
        # Pick earliest valuation after the cutoff (closest to season end).
        if existing_team is None or row["market_value_date"] < existing_team["market_value_date"]:
            by_player_team[key_with_team] = row

        key_player = (int(season), player_key)
        existing_player = by_player_only.get(key_player)
        if existing_player is None or row["market_value_date"] < existing_player["market_value_date"]:
            by_player_only[key_player] = row

    return by_player_team, by_player_only, ongoing_by_player_team, ongoing_by_player_only


def merge_rows(
    api_rows: list[dict[str, Any]],
    api_columns: list[str],
    per_season_bio_by_id: dict[tuple[int, str], dict[str, Any]],
    per_season_bio_by_name_league: dict[tuple[int, str, str], dict[str, Any]],
    understat_indices: dict[str, dict[tuple[Any, ...], dict[str, Any]]],
    understat_columns: list[str],
    tm_by_player_team: dict[tuple[int, str, str], dict[str, Any]],
    tm_by_player_only: dict[tuple[int, str], dict[str, Any]],
    tm_ongoing_by_player_team: dict[tuple[int, str, str], dict[str, Any]],
    tm_ongoing_by_player_only: dict[tuple[int, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []

    for row in api_rows:
        season = int(row["season"])
        pkey = row["norm_player"]
        tkey = row["norm_team"]
        league = row.get("understat_league", "")
        league_id_raw = str(row.get("league_id", "")).strip()
        player_id_raw = str(row.get("player_id", "")).strip()

        # API rows are deduped per (player_id, season). To preserve full-season stats
        # for players who switched teams mid-season, prefer aggregated indices first.
        understat: dict[str, Any] | None = None
        understat_match_level = ""
        for pk in player_key_variants(pkey):
            understat = understat_indices["player_league"].get((season, pk, league))
            understat_match_level = "player_league" if understat else ""
            if understat:
                break
            understat = understat_indices["player_only"].get((season, pk))
            understat_match_level = "player_only" if understat else ""
            if understat:
                break
            understat = understat_indices["player_team"].get((season, pk, tkey))
            understat_match_level = "player_team" if understat else ""
            if understat:
                break
            understat = understat_indices["full"].get((season, pk, tkey, league))
            understat_match_level = "full" if understat else ""
            if understat:
                break
        if understat is None:
            understat = {}
            understat_match_level = ""

        tm_key = (season, pkey, tkey)
        tm_source = "team_match"
        tm = tm_by_player_team.get(tm_key)
        if tm is None:
            tm_source = "player_match"
            tm = tm_by_player_only.get((season, pkey), {})
        if season == 2025 and not tm:
            tm_source = "ongoing_team_match"
            tm = tm_ongoing_by_player_team.get((season, pkey, tkey))
            if tm is None:
                tm_source = "ongoing_player_match"
                tm = tm_ongoing_by_player_only.get((season, pkey), {})
            if tm is None:
                tm_source = ""
                tm = {}

        prev_tm_key = (season - 1, pkey, tkey)
        prev_tm_source = "team_match"
        prev_tm = tm_by_player_team.get(prev_tm_key)
        if prev_tm is None:
            prev_tm_source = "player_match"
            prev_tm = tm_by_player_only.get((season - 1, pkey), {})

        out: dict[str, Any] = {}
        for col in api_columns:
            out[f"api_{col}"] = row.get(col, "")

        out["season"] = season
        out["player_name"] = row.get("player_name", "")
        out["team_name"] = row.get("team_name", "")
        out["league_id"] = row.get("league_id", "")
        out["understat_league"] = league
        bio = {}
        if player_id_raw:
            bio = per_season_bio_by_id.get((season, player_id_raw), {})
        if not bio:
            bio = per_season_bio_by_name_league.get((season, pkey, league_id_raw), {})
        out["api_height"] = bio.get("api_height", "")
        out["api_weight"] = bio.get("api_weight", "")

        for col in understat_columns:
            out[f"understat_{col}"] = understat.get(col, "")

        out["target_market_value_eur"] = tm.get("market_value_eur", "")
        out["market_value_date"] = tm.get("market_value_date", "")
        out["transfermarkt_team_name"] = tm.get("transfermarkt_team_name", "")
        out["transfermarkt_age_at_season"] = tm.get("transfermarkt_age_at_season", "")
        out["transfermarkt_match_level"] = tm_source if tm else ""
        out["last_market_value_eur"] = prev_tm.get("market_value_eur", "")
        out["last_market_value_date"] = prev_tm.get("market_value_date", "")
        out["last_transfermarkt_team_name"] = prev_tm.get("transfermarkt_team_name", "")
        out["last_transfermarkt_match_level"] = prev_tm_source if prev_tm else ""
        out["matched_last_transfermarkt"] = int(bool(prev_tm))
        out["understat_match_level"] = understat_match_level
        out["matched_understat"] = int(bool(understat))
        out["matched_transfermarkt"] = int(bool(tm))

        # Latest season is ongoing (25-26 / season=2025): keep Transfermarkt join,
        # but force current market value target to NA.
        if season == 2025:
            out["target_market_value_eur"] = ""

        merged.append(out)

    return merged


def write_output(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise RuntimeError("No rows generated. Check source files and key normalization.")

    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def verify_column_coverage(
    rows: list[dict[str, Any]],
    api_columns: list[str],
    understat_columns: list[str],
) -> None:
    if not rows:
        return
    output_columns = set(rows[0].keys())
    expected_api = {f"api_{col}" for col in api_columns}
    expected_understat = {f"understat_{col}" for col in understat_columns}

    missing_api = sorted(expected_api - output_columns)
    missing_understat = sorted(expected_understat - output_columns)
    if missing_api or missing_understat:
        details = []
        if missing_api:
            details.append(f"Missing API columns: {missing_api[:10]}{' ...' if len(missing_api) > 10 else ''}")
        if missing_understat:
            details.append(
                f"Missing Understat columns: {missing_understat[:10]}{' ...' if len(missing_understat) > 10 else ''}"
            )
        raise RuntimeError("Column coverage check failed. " + " | ".join(details))


def print_summary(
    rows: list[dict[str, Any]],
    all3_rows: list[dict[str, Any]],
    chosen_source: str,
    scores: dict[str, float],
    output_path: Path,
    output_all3_path: Path,
) -> None:
    total = len(rows)
    understat_matches = sum(int(r["matched_understat"]) for r in rows)
    transfer_matches = sum(int(r["matched_transfermarkt"]) for r in rows)
    target_non_null = sum(1 for r in rows if r["target_market_value_eur"] not in ("", None))
    seasons = sorted({int(r["season"]) for r in rows})

    if scores:
        print("API source completeness (lower is better):")
        for source_name, score in sorted(scores.items()):
            print(f"  - {source_name}: {score:.4f}")
    print(f"Chosen API source: {chosen_source}")
    print(f"Output rows: {total:,}")
    print(f"Seasons covered: {seasons[0]}-{seasons[-1]} ({len(seasons)} seasons)")
    print(f"Understat matches: {understat_matches:,} ({understat_matches / total:.1%})")
    print(f"Transfermarkt matches: {transfer_matches:,} ({transfer_matches / total:.1%})")
    print(f"Rows with target market value: {target_non_null:,} ({target_non_null / total:.1%})")
    if all3_rows:
        all3_seasons = sorted({int(r["season"]) for r in all3_rows})
        print(f"Rows matched in all 3 sources: {len(all3_rows):,} ({len(all3_rows) / total:.1%})")
        print(f"All-3 seasons covered: {all3_seasons[0]}-{all3_seasons[-1]} ({len(all3_seasons)} seasons)")
    else:
        print("Rows matched in all 3 sources: 0")
    print(f"Saved merged dataset -> {output_path}")
    print(f"Saved all-3 matched dataset -> {output_all3_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge API-Football, Understat, and Transfermarkt player values into a season-level dataset."
    )
    parser.add_argument(
        "--api-source",
        choices=["per_fixture", "per_season"],
        default=None,
        help="Force API source. Default auto-selects based on null completeness.",
    )
    parser.add_argument(
        "--duckdb-path",
        default=str(TRANSFERMARKT_DUCKDB),
        help="Path to transfermarkt DuckDB file.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_CSV),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--output-all3",
        default=str(OUTPUT_ALL3_CSV),
        help="Output CSV path for rows matched in all three sources.",
    )
    args = parser.parse_args()

    chosen_source, api_paths, scores = pick_api_source(args.api_source)
    if not api_paths:
        raise RuntimeError(f"No API CSV files found for source: {chosen_source}")

    api_rows, api_columns = read_api_rows(api_paths)
    per_season_bio_by_id, per_season_bio_by_name_league = load_per_season_height_weight()
    understat_indices, understat_columns = build_understat_indices()
    (
        tm_by_player_team,
        tm_by_player_only,
        tm_ongoing_by_player_team,
        tm_ongoing_by_player_only,
    ) = load_transfermarkt_values(Path(args.duckdb_path))
    merged_rows = merge_rows(
        api_rows,
        api_columns,
        per_season_bio_by_id,
        per_season_bio_by_name_league,
        understat_indices,
        understat_columns,
        tm_by_player_team,
        tm_by_player_only,
        tm_ongoing_by_player_team,
        tm_ongoing_by_player_only,
    )
    verify_column_coverage(merged_rows, api_columns, understat_columns)

    # Sanity check: each (api_player_id, season) appears at most once.
    seen_player_season: set[tuple[Any, int]] = set()
    for row in merged_rows:
        player_id = str(row.get("api_player_id", "")).strip()
        if not player_id:
            continue
        key = (player_id, int(row.get("season")))
        if key in seen_player_season:
            raise RuntimeError(
                f"Duplicate row detected for (player_id={player_id}, season={key[1]})"
            )
        seen_player_season.add(key)
    output_path = Path(args.output)
    output_all3_path = Path(args.output_all3)
    write_output(merged_rows, output_path)
    # "all3" is strict for completed seasons, but for ongoing season 2025
    # include API+Understat rows even though transfer value is intentionally blank.
    all3_rows = [
        row
        for row in merged_rows
        if row.get("matched_understat") == 1
        and (row.get("matched_transfermarkt") == 1 or int(row.get("season")) == 2025)
    ]
    write_output(all3_rows, output_all3_path)
    print_summary(merged_rows, all3_rows, chosen_source, scores, output_path, output_all3_path)


if __name__ == "__main__":
    main()
