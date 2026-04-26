#!/usr/bin/env python3
"""Fetch fixture-level player stats from API-FOOTBALL and aggregate them.

Usage:
  1) Set API key in API_KEY below, or export API_FOOTBALL_KEY.
  2) One league-season:
      python3 api_football_fixture_players_flow.py --league 39 --season 2012
  3) Only see how many requests this will make:
      python3 api_football_fixture_players_flow.py --league 39 --season 2012 --count-only

Outputs for league=39, season=2012:
  - data/api_football/per_fixture/fixtures/league_39/fixtures_39_2012.json
  - data/api_football/per_fixture/fixture_players_raw/league_39/fixture_players_raw_39_2012.json
  - data/api_football/per_fixture/fixture_player_stats/league_39/fixture_player_stats_39_2012.csv
  - data/api_football/per_fixture/player_stats_from_fixtures/league_39/player_stats_from_fixtures_39_2012.csv
  - data/api_football/per_fixture/player_stats_from_fixtures/all_leagues/player_stats_from_fixtures_all_2011_2025.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from math import ceil
from pathlib import Path
from typing import Any

BASE_URL = "https://v3.football.api-sports.io"
# Prefer API_FOOTBALL_KEY in your environment. This fallback matches the existing script.
API_KEY = "be97036a0785b65d465be5facd7be4c7"
COMPLETED_STATUSES = "FT-AET-PEN"
TOP5_LEAGUE_IDS = [39, 135, 140, 78, 61]
PER_FIXTURE_ROOT = Path("data") / "api_football" / "per_fixture"


PLAYER_MATCH_FIELDS = [
    "league_id",
    "season",
    "fixture_id",
    "fixture_date",
    "fixture_status",
    "round",
    "home_team_id",
    "home_team_name",
    "away_team_id",
    "away_team_name",
    "team_id",
    "team_name",
    "opponent_team_id",
    "opponent_team_name",
    "is_home",
    "player_id",
    "player_name",
    "number",
    "position",
    "rating",
    "captain",
    "substitute",
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
    "passes_accuracy",
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

SUM_FIELDS = [
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


def per_fixture_output_dir(kind: str, league: int) -> Path:
    path = PER_FIXTURE_ROOT / kind / f"league_{league}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_api_key() -> str:
    env_key = os.getenv("API_FOOTBALL_KEY", "").strip()
    file_key = API_KEY.strip()

    if env_key:
        return env_key
    if file_key and file_key != "YOUR_API_KEY_HERE":
        return file_key

    raise RuntimeError(
        "API key not set. Set API_FOOTBALL_KEY env var or replace API_KEY in script."
    )


def build_headers(api_key: str) -> dict[str, str]:
    return {"x-apisports-key": api_key}


def call_api(
    endpoint: str,
    params: dict[str, Any],
    api_key: str,
    max_retries: int = 5,
    retry_wait_seconds: float = 2.0,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{BASE_URL}/{endpoint}?{query}" if query else f"{BASE_URL}/{endpoint}"
    req = urllib.request.Request(url, headers=build_headers(api_key), method="GET")

    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload)
        except urllib.error.HTTPError as exc:
            attempt += 1
            status = exc.code
            body = exc.read().decode("utf-8", errors="replace")

            if status in (429, 499, 500, 502, 503, 504) and attempt <= max_retries:
                wait_s = retry_wait_seconds * attempt
                print(f"HTTP {status} on {endpoint}. Retrying in {wait_s:.1f}s...")
                time.sleep(wait_s)
                continue

            raise RuntimeError(
                f"API request failed for {url} with status {status}. Response body: {body}"
            ) from exc
        except urllib.error.URLError as exc:
            attempt += 1
            if attempt <= max_retries:
                wait_s = retry_wait_seconds * attempt
                print(f"Network error on {endpoint}: {exc}. Retrying in {wait_s:.1f}s...")
                time.sleep(wait_s)
                continue
            raise RuntimeError(f"Network error calling {url}: {exc}") from exc


def write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_csv(path: str, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if not rows:
        raise RuntimeError(f"No rows to write to {path}.")

    columns = fieldnames or list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clean_number(value: Any) -> int | float | None:
    num = as_float(value)
    if num is None:
        return None
    if num.is_integer():
        return int(num)
    return num


def get_nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def fetch_fixtures(
    league: int,
    season: int,
    api_key: str,
    status: str = COMPLETED_STATUSES,
) -> list[dict[str, Any]]:
    data = call_api(
        "fixtures",
        {"league": league, "season": season, "status": status},
        api_key,
    )
    errors = data.get("errors")
    if errors:
        raise RuntimeError(f"fixtures endpoint returned errors: {errors}")
    return data.get("response", [])


def fixture_metadata(fixture: dict[str, Any], league: int, season: int) -> dict[str, Any]:
    fixture_obj = fixture.get("fixture", {})
    league_obj = fixture.get("league", {})
    teams = fixture.get("teams", {})
    home = teams.get("home", {})
    away = teams.get("away", {})

    return {
        "league_id": league_obj.get("id", league),
        "season": league_obj.get("season", season),
        "fixture_id": fixture_obj.get("id"),
        "fixture_date": fixture_obj.get("date"),
        "fixture_status": get_nested(fixture_obj, "status", "short"),
        "round": league_obj.get("round"),
        "home_team_id": home.get("id"),
        "home_team_name": home.get("name"),
        "away_team_id": away.get("id"),
        "away_team_name": away.get("name"),
    }


def fetch_fixture_players(fixture_id: int, api_key: str) -> list[dict[str, Any]]:
    data = call_api("fixtures/players", {"fixture": fixture_id}, api_key)
    errors = data.get("errors")
    if errors:
        raise RuntimeError(f"fixtures/players returned errors for {fixture_id}: {errors}")
    return data.get("response", [])


def chunked(values: list[Any], size: int) -> list[list[Any]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def fetch_fixtures_by_ids(
    fixture_ids: list[int],
    api_key: str,
    throttle_seconds: float,
) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    chunks = chunked(fixture_ids, 20)

    for i, ids_group in enumerate(chunks, start=1):
        ids_param = "-".join(str(fixture_id) for fixture_id in ids_group)
        print(f"[{i}/{len(chunks)}] Fetching fixture bundle for ids={ids_param}...")
        data = call_api("fixtures", {"ids": ids_param}, api_key)
        errors = data.get("errors")
        if errors:
            raise RuntimeError(f"fixtures?ids returned errors for {ids_param}: {errors}")
        fixtures.extend(data.get("response", []))

        if i < len(chunks):
            time.sleep(throttle_seconds)

    return fixtures


def flatten_fixture_players(
    fixture: dict[str, Any],
    fixture_players_payload: list[dict[str, Any]],
    league: int,
    season: int,
) -> list[dict[str, Any]]:
    meta = fixture_metadata(fixture, league, season)
    rows: list[dict[str, Any]] = []

    for team_entry in fixture_players_payload:
        team = team_entry.get("team", {})
        team_id = team.get("id")
        is_home = team_id == meta["home_team_id"]
        opponent_id = meta["away_team_id"] if is_home else meta["home_team_id"]
        opponent_name = meta["away_team_name"] if is_home else meta["home_team_name"]

        for player_entry in team_entry.get("players", []) or []:
            player = player_entry.get("player", {})
            stats_list = player_entry.get("statistics", []) or [{}]

            for stat in stats_list:
                games = stat.get("games", {})
                shots = stat.get("shots", {})
                goals = stat.get("goals", {})
                passes = stat.get("passes", {})
                tackles = stat.get("tackles", {})
                duels = stat.get("duels", {})
                dribbles = stat.get("dribbles", {})
                fouls = stat.get("fouls", {})
                cards = stat.get("cards", {})
                penalty = stat.get("penalty", {})

                row = {
                    **meta,
                    "team_id": team_id,
                    "team_name": team.get("name"),
                    "opponent_team_id": opponent_id,
                    "opponent_team_name": opponent_name,
                    "is_home": is_home,
                    "player_id": player.get("id"),
                    "player_name": player.get("name"),
                    "number": games.get("number"),
                    "position": games.get("position"),
                    "rating": as_float(games.get("rating")),
                    "captain": games.get("captain"),
                    "substitute": games.get("substitute"),
                    "minutes": clean_number(games.get("minutes")),
                    "offsides": clean_number(stat.get("offsides")),
                    "shots_total": clean_number(shots.get("total")),
                    "shots_on": clean_number(shots.get("on")),
                    "goals_total": clean_number(goals.get("total")),
                    "goals_conceded": clean_number(goals.get("conceded")),
                    "goals_assists": clean_number(goals.get("assists")),
                    "goals_saves": clean_number(goals.get("saves")),
                    "passes_total": clean_number(passes.get("total")),
                    "passes_key": clean_number(passes.get("key")),
                    "passes_accuracy": clean_number(passes.get("accuracy")),
                    "tackles_total": clean_number(tackles.get("total")),
                    "tackles_blocks": clean_number(tackles.get("blocks")),
                    "tackles_interceptions": clean_number(tackles.get("interceptions")),
                    "duels_total": clean_number(duels.get("total")),
                    "duels_won": clean_number(duels.get("won")),
                    "dribbles_attempts": clean_number(dribbles.get("attempts")),
                    "dribbles_success": clean_number(dribbles.get("success")),
                    "dribbles_past": clean_number(dribbles.get("past")),
                    "fouls_drawn": clean_number(fouls.get("drawn")),
                    "fouls_committed": clean_number(fouls.get("committed")),
                    "cards_yellow": clean_number(cards.get("yellow")),
                    "cards_red": clean_number(cards.get("red")),
                    "penalty_won": clean_number(penalty.get("won")),
                    "penalty_commited": clean_number(penalty.get("commited")),
                    "penalty_scored": clean_number(penalty.get("scored")),
                    "penalty_missed": clean_number(penalty.get("missed")),
                    "penalty_saved": clean_number(penalty.get("saved")),
                }
                rows.append(row)

    return rows


def aggregate_player_rows(match_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for row in match_rows:
        grouped[(row["player_id"], row["team_id"], row["season"])].append(row)

    aggregate_rows: list[dict[str, Any]] = []
    for (_player_id, _team_id, _season), rows in grouped.items():
        first = rows[0]
        played_rows = [r for r in rows if (as_float(r.get("minutes")) or 0) > 0]
        starts = sum(1 for r in rows if r.get("substitute") is False and (as_float(r.get("minutes")) or 0) > 0)
        sub_apps = sum(1 for r in played_rows if r.get("substitute") is True)

        agg: dict[str, Any] = {
            "player_id": first["player_id"],
            "player_name": first["player_name"],
            "team_id": first["team_id"],
            "team_name": first["team_name"],
            "league_id": first["league_id"],
            "season": first["season"],
            "position": most_common([r.get("position") for r in rows]),
            "squad_rows": len(rows),
            "appearances": len(played_rows),
            "starts": starts,
            "sub_appearances": sub_apps,
        }

        for field in SUM_FIELDS:
            values = [as_float(r.get(field)) for r in rows]
            agg[field] = clean_number(sum(v for v in values if v is not None))

        rating_minutes = [
            (as_float(r.get("rating")), as_float(r.get("minutes")) or 0)
            for r in rows
            if as_float(r.get("rating")) is not None
        ]
        rating_weight = sum(minutes for _rating, minutes in rating_minutes)
        if rating_weight:
            agg["avg_rating"] = round(
                sum((rating or 0) * minutes for rating, minutes in rating_minutes) / rating_weight,
                3,
            )
        else:
            ratings = [as_float(r.get("rating")) for r in rows if as_float(r.get("rating")) is not None]
            agg["avg_rating"] = round(sum(ratings) / len(ratings), 3) if ratings else None

        total_minutes = as_float(agg.get("minutes")) or 0
        for field in [
            "goals_total",
            "goals_assists",
            "shots_total",
            "shots_on",
            "passes_key",
            "tackles_total",
            "duels_won",
            "cards_yellow",
            "cards_red",
        ]:
            value = as_float(agg.get(field))
            agg[f"{field}_per90"] = round(value * 90 / total_minutes, 3) if value is not None and total_minutes else None

        aggregate_rows.append(agg)

    return sorted(
        aggregate_rows,
        key=lambda r: (
            str(r.get("team_name") or ""),
            -(as_float(r.get("minutes")) or 0),
            str(r.get("player_name") or ""),
        ),
    )


def most_common(values: list[Any]) -> Any:
    counts: dict[Any, int] = {}
    for value in values:
        if value in (None, ""):
            continue
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: item[1])[0]


def aggregate_fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "player_id",
        "player_name",
        "team_id",
        "team_name",
        "league_id",
        "season",
        "position",
        "squad_rows",
        "appearances",
        "starts",
        "sub_appearances",
        "minutes",
        "avg_rating",
    ]
    per90 = [f"{field}_per90" for field in [
        "goals_total",
        "goals_assists",
        "shots_total",
        "shots_on",
        "passes_key",
        "tackles_total",
        "duels_won",
        "cards_yellow",
        "cards_red",
    ]]
    remaining = [key for key in rows[0].keys() if key not in preferred and key not in per90]
    return preferred + remaining + per90


def merged_fixture_stats_path(league_ids: list[int], seasons: list[int]) -> Path:
    start_season = min(seasons)
    end_season = max(seasons)
    if len(league_ids) > 1:
        output_dir = PER_FIXTURE_ROOT / "player_stats_from_fixtures" / "all_leagues"
        filename = f"player_stats_from_fixtures_all_{start_season}_{end_season}.csv"
    else:
        output_dir = per_fixture_output_dir("player_stats_from_fixtures", league_ids[0])
        filename = (
            f"player_stats_from_fixtures_{league_ids[0]}_all_"
            f"{start_season}_{end_season}.csv"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / filename


def merge_existing_aggregated_fixture_stats(
    league_ids: list[int],
    seasons: list[int],
) -> Path:
    source_files = [
        PER_FIXTURE_ROOT
        / "player_stats_from_fixtures"
        / f"league_{league}"
        / f"player_stats_from_fixtures_{league}_{season}.csv"
        for league in league_ids
        for season in seasons
    ]
    existing_files = [path for path in source_files if path.exists()]
    missing_files = [path for path in source_files if not path.exists()]

    if not existing_files:
        raise RuntimeError("No existing aggregated fixture files found to merge.")

    rows: list[dict[str, Any]] = []
    fieldnames: list[str] = []
    seen_fields: set[str] = set()

    for path in existing_files:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for field in reader.fieldnames or []:
                if field not in seen_fields:
                    fieldnames.append(field)
                    seen_fields.add(field)
            rows.extend(reader)

    def sort_value(row: dict[str, Any], field: str) -> tuple[int, Any]:
        value = row.get(field)
        numeric = as_float(value)
        if numeric is not None:
            return (0, numeric)
        return (1, value or "")

    rows = sorted(
        rows,
        key=lambda row: (
            sort_value(row, "league_id"),
            sort_value(row, "season"),
            sort_value(row, "team_id"),
            sort_value(row, "player_id"),
        ),
    )

    output_path = merged_fixture_stats_path(league_ids, seasons)
    write_csv(output_path, rows, fieldnames)
    print(f"Merged {len(existing_files)} files -> {output_path}")
    print(f"Merged rows: {len(rows):,}")
    if missing_files:
        print(f"Skipped missing files: {len(missing_files)}")
    return output_path


def run_fixture_players_flow(
    league: int,
    season: int,
    fixtures: list[dict[str, Any]],
    api_key: str,
    throttle_seconds: float,
    limit_fixtures: int | None,
    fetch_mode: str,
) -> None:
    fixtures = sorted(fixtures, key=lambda f: get_nested(f, "fixture", "date") or "")
    if limit_fixtures is not None:
        fixtures = fixtures[:limit_fixtures]

    fixtures_dir = per_fixture_output_dir("fixtures", league)
    raw_dir = per_fixture_output_dir("fixture_players_raw", league)
    match_stats_dir = per_fixture_output_dir("fixture_player_stats", league)
    aggregate_dir = per_fixture_output_dir("player_stats_from_fixtures", league)

    fixtures_json = fixtures_dir / f"fixtures_{league}_{season}.json"
    write_json(fixtures_json, fixtures)
    print(f"Saved {len(fixtures)} fixtures -> {fixtures_json}")

    raw_by_fixture: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []

    if fetch_mode == "bulk":
        fixture_ids = [
            int(fixture_id)
            for fixture_id in (get_nested(fixture, "fixture", "id") for fixture in fixtures)
            if fixture_id is not None
        ]
        fixture_bundles = fetch_fixtures_by_ids(fixture_ids, api_key, throttle_seconds)

        for fixture in fixture_bundles:
            fixture_id = get_nested(fixture, "fixture", "id")
            payload = fixture.get("players", []) or []
            raw_by_fixture.append({"fixture_id": fixture_id, "response": payload})
            all_rows.extend(flatten_fixture_players(fixture, payload, league, season))
    elif fetch_mode == "per-fixture":
        for i, fixture in enumerate(fixtures, start=1):
            fixture_id = get_nested(fixture, "fixture", "id")
            if fixture_id is None:
                continue

            print(f"[{i}/{len(fixtures)}] Fetching fixture players for fixture={fixture_id}...")
            payload = fetch_fixture_players(int(fixture_id), api_key)
            raw_by_fixture.append({"fixture_id": fixture_id, "response": payload})
            all_rows.extend(flatten_fixture_players(fixture, payload, league, season))

            if i < len(fixtures):
                time.sleep(throttle_seconds)
    else:
        raise RuntimeError(f"Unknown fetch mode: {fetch_mode}")

    raw_json = raw_dir / f"fixture_players_raw_{league}_{season}.json"
    write_json(raw_json, raw_by_fixture)
    print(f"Saved raw fixture-player payloads -> {raw_json}")

    if not all_rows:
        print("No fixture player rows found, so no CSV files were written.")
        return

    match_csv = match_stats_dir / f"fixture_player_stats_{league}_{season}.csv"
    write_csv(match_csv, all_rows, PLAYER_MATCH_FIELDS)
    print(f"Saved player-match rows ({len(all_rows):,}) -> {match_csv}")

    aggregate_rows = aggregate_player_rows(all_rows)
    aggregate_csv = aggregate_dir / f"player_stats_from_fixtures_{league}_{season}.csv"
    write_csv(aggregate_csv, aggregate_rows, aggregate_fieldnames(aggregate_rows))
    print(f"Saved aggregated player stats ({len(aggregate_rows):,}) -> {aggregate_csv}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download fixture-level player stats and aggregate them by player/team."
    )
    parser.add_argument("--league", type=int, default=39, help="League ID (default: 39)")
    parser.add_argument("--season", type=int, default=2012, help="Season year (default: 2012)")
    parser.add_argument(
        "--batch-top5",
        action="store_true",
        help="Run for default top 5 league IDs (39, 135, 140, 78, 61)",
    )
    parser.add_argument(
        "--league-ids",
        type=str,
        default="",
        help="Comma-separated league IDs for batch mode, e.g. 39,135,140,78,61",
    )
    parser.add_argument(
        "--start-season",
        type=int,
        default=None,
        help="Start season year for batch mode (inclusive)",
    )
    parser.add_argument(
        "--end-season",
        type=int,
        default=None,
        help="End season year for batch mode (inclusive)",
    )
    parser.add_argument(
        "--status",
        type=str,
        default=COMPLETED_STATUSES,
        help=f"Fixture statuses to fetch (default: {COMPLETED_STATUSES})",
    )
    parser.add_argument(
        "--throttle-seconds",
        type=float,
        default=0.1,
        help="Delay between player-data calls to reduce 429 risk (default: 0.1)",
    )
    parser.add_argument(
        "--limit-fixtures",
        type=int,
        default=None,
        help="Fetch only the first N fixtures, useful for testing.",
    )
    parser.add_argument(
        "--fetch-mode",
        choices=["bulk", "per-fixture"],
        default="bulk",
        help="bulk uses fixtures?ids chunks of 20; per-fixture uses fixtures/players one match at a time.",
    )
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="Fetch fixture IDs and print expected request count only.",
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="Merge existing player_stats_from_fixtures CSVs without calling the API.",
    )
    args = parser.parse_args()

    if args.batch_top5:
        league_ids = TOP5_LEAGUE_IDS
    elif args.league_ids.strip():
        league_ids = [int(x.strip()) for x in args.league_ids.split(",") if x.strip()]
    else:
        league_ids = [args.league]

    if (args.start_season is None) != (args.end_season is None):
        raise RuntimeError("Use both --start-season and --end-season together.")

    if args.start_season is not None and args.end_season is not None:
        if args.start_season > args.end_season:
            raise RuntimeError("--start-season must be <= --end-season")
        seasons = list(range(args.start_season, args.end_season + 1))
    else:
        seasons = [args.season]

    combinations = [(league, season) for league in league_ids for season in seasons]

    if args.merge_existing:
        merge_existing_aggregated_fixture_stats(league_ids, seasons)
        return

    api_key = resolve_api_key()

    if args.count_only:
        fixtures_requests_total = 0
        player_data_requests_total = 0

        print("Counting fixture-player requests...")
        for league, season in combinations:
            print(f"Fetching fixture IDs for league={league}, season={season}...")
            fixtures = fetch_fixtures(league, season, api_key, status=args.status)
            fixture_count = len(fixtures)
            if args.limit_fixtures is not None:
                fixture_count = min(fixture_count, args.limit_fixtures)

            player_data_requests = (
                ceil(fixture_count / 20) if args.fetch_mode == "bulk" else fixture_count
            )
            fixtures_requests_total += 1
            player_data_requests_total += player_data_requests
            print(
                f"league={league} season={season} | fixtures={fixture_count} | "
                f"player_data_requests={player_data_requests}"
            )

        print("\n=== Request Count Summary ===")
        print(f"combinations: {len(combinations)}")
        print(f"fixtures requests: {fixtures_requests_total}")
        print(f"player-data requests via {args.fetch_mode}: {player_data_requests_total}")
        print(f"total requests: {fixtures_requests_total + player_data_requests_total}")
        return

    for league, season in combinations:
        print(
            f"\n=== league={league} season={season} ===\n"
            f"Fetching fixtures for league={league}, season={season}, status={args.status}..."
        )
        fixtures = fetch_fixtures(league, season, api_key, status=args.status)
        run_fixture_players_flow(
            league=league,
            season=season,
            fixtures=fixtures,
            api_key=api_key,
            throttle_seconds=args.throttle_seconds,
            limit_fixtures=args.limit_fixtures,
            fetch_mode=args.fetch_mode,
        )

    if len(combinations) > 1 and args.limit_fixtures is None:
        merge_existing_aggregated_fixture_stats(league_ids, seasons)


if __name__ == "__main__":
    main()
