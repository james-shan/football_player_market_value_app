#!/usr/bin/env python3
"""Fetch all teams and player season stats from API-FOOTBALL.

Usage:
  1) Set API key in API_KEY below, or export API_FOOTBALL_KEY.
  2) Single league-season run:
      python api_football_players_flow.py --league 39 --season 2021
  3) Batch run for top 5 leagues and season range:
      python api_football_players_flow.py --batch-top5 --start-season 2011 --end-season 2025
  4) Count-only mode (exact request count for players pages):
      python api_football_players_flow.py --batch-top5 --start-season 2011 --end-season 2025 --count-only

Outputs:
  - data/api_football/per_season/teams/league_39/teams_39_2021.json
  - data/api_football/per_season/players_raw/league_39/players_raw_39_2021.json
  - data/api_football/per_season/player_stats/league_39/player_stats_39_2021.csv
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
from pathlib import Path
from typing import Any

BASE_URL = "https://v3.football.api-sports.io"
# Replace this value or use the API_FOOTBALL_KEY environment variable.
API_KEY = "be97036a0785b65d465be5facd7be4c7"
TOP5_LEAGUE_IDS = [39, 135, 140, 78, 61]
PER_SEASON_ROOT = Path("data") / "api_football" / "per_season"


def per_season_output_dir(kind: str, league: int) -> Path:
    path = PER_SEASON_ROOT / kind / f"league_{league}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_headers(api_key: str) -> dict[str, str]:
    # API-FOOTBALL docs use x-apisports-key for direct API access.
    return {
        "x-apisports-key": api_key,
    }


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
            with urllib.request.urlopen(req, timeout=60) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload)
        except urllib.error.HTTPError as exc:
            attempt += 1
            status = exc.code
            body = exc.read().decode("utf-8", errors="replace")

            # Retry on rate limiting and transient upstream errors.
            if status in (429, 500, 502, 503, 504) and attempt <= max_retries:
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


def fetch_teams(league: int, season: int, api_key: str) -> list[dict[str, Any]]:
    data = call_api("teams", {"league": league, "season": season}, api_key)
    errors = data.get("errors")
    if errors:
        raise RuntimeError(f"teams endpoint returned errors: {errors}")
    return data.get("response", [])


def fetch_players_page(
    league: int,
    season: int,
    page: int,
    api_key: str,
) -> dict[str, Any]:
    data = call_api(
        "players",
        {"league": league, "season": season, "page": page},
        api_key,
    )
    errors = data.get("errors")
    if errors:
        raise RuntimeError(f"players endpoint returned errors on page {page}: {errors}")
    return data


def fetch_all_players(
    league: int,
    season: int,
    api_key: str,
    throttle_seconds: float = 0.6,
) -> list[dict[str, Any]]:
    all_players: list[dict[str, Any]] = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        data = fetch_players_page(league, season, page, api_key)

        paging = data.get("paging", {})
        current = int(paging.get("current", page))
        total_pages = int(paging.get("total", total_pages))

        page_rows = data.get("response", [])
        all_players.extend(page_rows)

        print(
            f"Fetched page {current}/{total_pages} | "
            f"page_rows={len(page_rows)} | cumulative={len(all_players)}"
        )

        page += 1
        if page <= total_pages:
            time.sleep(throttle_seconds)

    return all_players


def get_player_pages_count(league: int, season: int, api_key: str) -> int:
    data = fetch_players_page(league, season, 1, api_key)
    paging = data.get("paging", {})
    return int(paging.get("total", 1))


def flatten_player_stats(player_payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for entry in player_payload:
        player = entry.get("player", {})
        stats_list = entry.get("statistics", []) or [{}]

        for stat in stats_list:
            team = stat.get("team", {})
            league = stat.get("league", {})
            games = stat.get("games", {})
            substitutes = stat.get("substitutes", {})
            shots = stat.get("shots", {})
            goals = stat.get("goals", {})
            passes = stat.get("passes", {})
            tackles = stat.get("tackles", {})
            duels = stat.get("duels", {})
            dribbles = stat.get("dribbles", {})
            fouls = stat.get("fouls", {})
            cards = stat.get("cards", {})
            penalty = stat.get("penalty", {})

            rows.append(
                {
                    "player_id": player.get("id"),
                    "player_name": player.get("name"),
                    "firstname": player.get("firstname"),
                    "lastname": player.get("lastname"),
                    "age": player.get("age"),
                    "nationality": player.get("nationality"),
                    "height": player.get("height"),
                    "weight": player.get("weight"),
                    "injured": player.get("injured"),
                    "team_id": team.get("id"),
                    "team_name": team.get("name"),
                    "league_id": league.get("id"),
                    "league_name": league.get("name"),
                    "season": league.get("season"),
                    "appearances": games.get("appearences"),
                    "lineups": games.get("lineups"),
                    "minutes": games.get("minutes"),
                    "position": games.get("position"),
                    "rating": games.get("rating"),
                    "captain": games.get("captain"),
                    "sub_in": substitutes.get("in"),
                    "sub_out": substitutes.get("out"),
                    "sub_bench": substitutes.get("bench"),
                    "shots_total": shots.get("total"),
                    "shots_on": shots.get("on"),
                    "goals_total": goals.get("total"),
                    "goals_assists": goals.get("assists"),
                    "goals_conceded": goals.get("conceded"),
                    "goals_saves": goals.get("saves"),
                    "passes_total": passes.get("total"),
                    "passes_key": passes.get("key"),
                    "passes_accuracy": passes.get("accuracy"),
                    "tackles_total": tackles.get("total"),
                    "tackles_blocks": tackles.get("blocks"),
                    "tackles_interceptions": tackles.get("interceptions"),
                    "duels_total": duels.get("total"),
                    "duels_won": duels.get("won"),
                    "dribbles_attempts": dribbles.get("attempts"),
                    "dribbles_success": dribbles.get("success"),
                    "dribbles_past": dribbles.get("past"),
                    "fouls_drawn": fouls.get("drawn"),
                    "fouls_committed": fouls.get("committed"),
                    "cards_yellow": cards.get("yellow"),
                    "cards_yellowred": cards.get("yellowred"),
                    "cards_red": cards.get("red"),
                    "penalty_won": penalty.get("won"),
                    "penalty_commited": penalty.get("commited"),
                    "penalty_scored": penalty.get("scored"),
                    "penalty_missed": penalty.get("missed"),
                    "penalty_saved": penalty.get("saved"),
                }
            )

    return rows


def write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError("No rows to write to CSV.")

    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download API-FOOTBALL teams and player stats for one or many league-seasons."
    )
    parser.add_argument("--league", type=int, default=39, help="League ID (default: 39)")
    parser.add_argument("--season", type=int, default=2021, help="Season year (default: 2021)")
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
        "--count-only",
        action="store_true",
        help="Only compute exact request totals using players paging; do not download full data",
    )
    parser.add_argument(
        "--throttle-seconds",
        type=float,
        default=0.1,
        help="Delay between player page calls to reduce 429 risk (default: 0.6)",
    )
    args = parser.parse_args()

    api_key = resolve_api_key()

    league_ids: list[int]
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

    if args.count_only:
        players_requests_total = 0
        teams_requests_total = 0

        print("Counting exact requests from players paging...")
        for league, season in combinations:
            pages = get_player_pages_count(league, season, api_key)
            players_requests_total += pages
            teams_requests_total += 1
            print(
                f"league={league} season={season} | players_pages={pages} | "
                f"players_requests_so_far={players_requests_total}"
            )

        combos = len(combinations)
        print("\n=== Request Count Summary ===")
        print(f"combinations: {combos}")
        print(f"teams requests (1/combo): {teams_requests_total}")
        print(f"players requests (all pages): {players_requests_total}")
        print(f"total requests (teams + players): {teams_requests_total + players_requests_total}")
        return

    all_stats_rows: list[dict[str, Any]] = []

    for league, season in combinations:
        teams_dir = per_season_output_dir("teams", league)
        players_raw_dir = per_season_output_dir("players_raw", league)
        player_stats_dir = per_season_output_dir("player_stats", league)

        print(f"\n=== league={league} season={season} ===")
        print(f"Fetching teams for league={league}, season={season}...")
        teams = fetch_teams(league, season, api_key)
        teams_json = teams_dir / f"teams_{league}_{season}.json"
        write_json(teams_json, teams)
        print(f"Saved {len(teams)} teams -> {teams_json}")

        print(f"Fetching all players for league={league}, season={season}...")
        players_raw = fetch_all_players(
            league,
            season,
            api_key,
            throttle_seconds=args.throttle_seconds,
        )
        players_json = players_raw_dir / f"players_raw_{league}_{season}.json"
        write_json(players_json, players_raw)
        print(f"Saved raw players payload ({len(players_raw)} rows) -> {players_json}")

        player_stats = flatten_player_stats(players_raw)
        stats_csv = player_stats_dir / f"player_stats_{league}_{season}.csv"
        write_csv(stats_csv, player_stats)
        print(f"Saved flattened player stats ({len(player_stats)} rows) -> {stats_csv}")

        all_stats_rows.extend(player_stats)

    if len(combinations) > 1 and all_stats_rows:
        if len(league_ids) > 1:
            merged_dir = PER_SEASON_ROOT / "player_stats" / "all_leagues"
            merged_name_prefix = "player_stats_all"
        else:
            merged_dir = per_season_output_dir("player_stats", league_ids[0])
            merged_name_prefix = f"player_stats_{league_ids[0]}_all"

        merged_dir.mkdir(parents=True, exist_ok=True)
        if args.start_season is not None and args.end_season is not None:
            all_csv = merged_dir / f"{merged_name_prefix}_{args.start_season}_{args.end_season}.csv"
        else:
            all_csv = merged_dir / f"{merged_name_prefix}.csv"
        write_csv(all_csv, all_stats_rows)
        print(f"\nSaved merged player stats ({len(all_stats_rows)} rows) -> {all_csv}")


if __name__ == "__main__":
    main()
