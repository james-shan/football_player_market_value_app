#!/usr/bin/env python3
"""Compile merged player datasets into a DuckDB analytics database.

This script ingests:
1) player_market_value_predictions_2025_26.csv
2) player_season_regression_dataset_all3.csv
3) player_stats_2025_26_null_market_value.csv

and creates:
- raw_* tables (one per CSV)
- dim_players (transfer-safe player identity dimension, with photo URL)
- fact_player_team_seasons (player x season x team granular, NOT unique on player+season)
- fact_player_seasons (player x season aggregated, UNIQUE on (player_uid, season))
- vw_player_latest_projection (lightweight projection view)

Uniqueness rules:
- fact_player_seasons is unique on (player_uid, season).
- For transferred players within a season, the row with the most minutes is kept.
- Only the 2025 prediction with uses_last_market_value = TRUE is attached.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_CSV = (
    ROOT / "data" / "merged" / "player_market_value_predictions_2025_26.csv"
)
DEFAULT_REGRESSION_CSV = (
    ROOT / "data" / "merged" / "player_season_regression_dataset_all3.csv"
)
DEFAULT_STATS_CSV = (
    ROOT / "data" / "merged" / "player_stats_2025_26_null_market_value.csv"
)
DEFAULT_OUTPUT_DUCKDB = ROOT / "data" / "merged" / "player_analytics.duckdb"
DEFAULT_TRANSFERMARKT_DUCKDB = ROOT / "data" / "transfermarkt-datasets.duckdb"

CURRENT_SEASON = 2025


def _assert_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")


def _quoted(path: Path) -> str:
    """Return a SQL-safe single-quoted path."""
    return str(path).replace("'", "''")


def build_duckdb(
    predictions_csv: Path,
    regression_csv: Path,
    stats_csv: Path,
    output_duckdb: Path,
    transfermarkt_duckdb: Path | None,
) -> None:
    _assert_exists(predictions_csv, "Predictions CSV")
    _assert_exists(regression_csv, "Regression CSV")
    _assert_exists(stats_csv, "Stats CSV")
    if transfermarkt_duckdb is not None:
        _assert_exists(transfermarkt_duckdb, "Transfermarkt DuckDB")

    output_duckdb.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(output_duckdb))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS analytics;")

        con.execute(
            f"""
            CREATE OR REPLACE TABLE analytics.raw_player_market_value_predictions AS
            SELECT *
            FROM read_csv_auto('{_quoted(predictions_csv)}', header=true, sample_size=-1);
            """
        )

        con.execute(
            f"""
            CREATE OR REPLACE TABLE analytics.raw_player_season_regression_dataset AS
            SELECT *
            FROM read_csv_auto('{_quoted(regression_csv)}', header=true, sample_size=-1);
            """
        )

        con.execute(
            f"""
            CREATE OR REPLACE TABLE analytics.raw_player_stats_2025_26 AS
            SELECT *
            FROM read_csv_auto('{_quoted(stats_csv)}', header=true, sample_size=-1);
            """
        )

        if transfermarkt_duckdb is not None:
            con.execute(
                f"ATTACH '{_quoted(transfermarkt_duckdb)}' AS transfermarkt_db (READ_ONLY);"
            )
            con.execute(
                """
                CREATE OR REPLACE TABLE analytics.raw_transfermarkt_player_images AS
                SELECT DISTINCT
                  p.player_id AS transfermarkt_player_id,
                  p.name AS player_name,
                  p.image_url AS player_photo_url
                FROM transfermarkt_db.players p
                WHERE p.image_url IS NOT NULL AND TRIM(p.image_url) <> '';
                """
            )
        else:
            con.execute(
                """
                CREATE OR REPLACE TABLE analytics.raw_transfermarkt_player_images AS
                SELECT
                  CAST(NULL AS BIGINT) AS transfermarkt_player_id,
                  CAST(NULL AS VARCHAR) AS player_name,
                  CAST(NULL AS VARCHAR) AS player_photo_url
                WHERE 1 = 0;
                """
            )

        # Predictions: keep only the model variant that uses last market value.
        con.execute(
            """
            CREATE OR REPLACE TABLE analytics.fact_predictions_2025_26 AS
            SELECT
              player_season_uid,
              player_name,
              season,
              team_name,
              model_position,
              last_market_value_eur AS prediction_last_market_value_eur,
              predicted_market_value_eur,
              selected_model_spec,
              selected_algorithm,
              uses_last_market_value
            FROM analytics.raw_player_market_value_predictions
            WHERE uses_last_market_value = TRUE;
            """
        )

        # Identity dimension. Prefer api_player_id, then understat, then name hash.
        con.execute(
            """
            CREATE OR REPLACE TABLE analytics.dim_players AS
            WITH unioned AS (
              SELECT
                CAST(api_player_id AS VARCHAR) AS api_player_id,
                CAST(understat_player_id AS VARCHAR) AS understat_player_id,
                CAST(player_name AS VARCHAR) AS player_name
              FROM analytics.raw_player_stats_2025_26

              UNION ALL

              SELECT
                CAST(api_player_id AS VARCHAR) AS api_player_id,
                CAST(understat_player_id AS VARCHAR) AS understat_player_id,
                CAST(player_name AS VARCHAR) AS player_name
              FROM analytics.raw_player_season_regression_dataset
            ),
            image_choice AS (
              SELECT
                lower(trim(player_name)) AS norm_player_name,
                player_photo_url,
                ROW_NUMBER() OVER (
                  PARTITION BY lower(trim(player_name))
                  ORDER BY transfermarkt_player_id
                ) AS rn
              FROM analytics.raw_transfermarkt_player_images
            ),
            dedup AS (
              SELECT DISTINCT
                NULLIF(TRIM(api_player_id), '') AS api_player_id,
                NULLIF(TRIM(understat_player_id), '') AS understat_player_id,
                NULLIF(TRIM(player_name), '') AS player_name
              FROM unioned
              WHERE
                NULLIF(TRIM(api_player_id), '') IS NOT NULL
                OR NULLIF(TRIM(understat_player_id), '') IS NOT NULL
                OR NULLIF(TRIM(player_name), '') IS NOT NULL
            ),
            keyed AS (
              SELECT
                CASE
                  WHEN api_player_id IS NOT NULL THEN 'api:' || api_player_id
                  WHEN understat_player_id IS NOT NULL THEN 'understat:' || understat_player_id
                  ELSE 'name_md5:' || md5(lower(player_name))
                END AS player_uid,
                api_player_id,
                understat_player_id,
                player_name,
                ic.player_photo_url
              FROM dedup
              LEFT JOIN image_choice ic
                ON lower(trim(dedup.player_name)) = ic.norm_player_name
               AND ic.rn = 1
            ),
            ranked_uid AS (
              SELECT
                keyed.*,
                ROW_NUMBER() OVER (
                  PARTITION BY player_uid
                  ORDER BY
                    CASE WHEN player_photo_url IS NOT NULL THEN 0 ELSE 1 END,
                    LENGTH(player_name) DESC,
                    player_name
                ) AS row_rank
              FROM keyed
            )
            SELECT
              player_uid,
              api_player_id,
              understat_player_id,
              player_name,
              player_photo_url
            FROM ranked_uid
            WHERE row_rank = 1;
            """
        )

        # Per-team granular fact table. NOT unique on (player_uid, season) by design,
        # because a player can appear with multiple clubs in the same season.
        # Built by unioning historical regression rows with current 2025 stat rows.
        con.execute(
            """
            CREATE OR REPLACE TABLE analytics.fact_player_team_seasons AS
            WITH historical AS (
              SELECT
                CASE
                  WHEN NULLIF(TRIM(CAST(api_player_id AS VARCHAR)), '') IS NOT NULL
                    THEN 'api:' || TRIM(CAST(api_player_id AS VARCHAR))
                  WHEN NULLIF(TRIM(CAST(understat_player_id AS VARCHAR)), '') IS NOT NULL
                    THEN 'understat:' || TRIM(CAST(understat_player_id AS VARCHAR))
                  ELSE 'name_md5:' || md5(lower(COALESCE(CAST(player_name AS VARCHAR), '')))
                END AS player_uid,
                CAST(season AS BIGINT) AS season,
                CAST(player_name AS VARCHAR) AS player_name,
                CAST(team_name AS VARCHAR) AS team_name,
                CAST(league_id AS BIGINT) AS league_id,
                CAST(NULL AS VARCHAR) AS model_position,
                CAST(api_position AS VARCHAR) AS api_position,
                CAST(transfermarkt_age_at_season AS DOUBLE) AS player_age,
                CAST(target_market_value_eur AS DOUBLE) AS target_market_value_eur,
                CAST(last_market_value_eur AS DOUBLE) AS last_market_value_eur,
                CAST(api_minutes AS DOUBLE) AS api_minutes,
                CAST(api_appearances AS DOUBLE) AS api_appearances,
                CAST(api_starts AS DOUBLE) AS api_starts,
                CAST(api_goals_total AS DOUBLE) AS api_goals_total,
                CAST(api_goals_assists AS DOUBLE) AS api_goals_assists,
                CAST(api_shots_total AS DOUBLE) AS api_shots_total,
                CAST(api_shots_on AS DOUBLE) AS api_shots_on,
                CAST(api_passes_total AS DOUBLE) AS api_passes_total,
                CAST(api_passes_key AS DOUBLE) AS api_passes_key,
                CAST(api_tackles_total AS DOUBLE) AS api_tackles_total,
                CAST(api_dribbles_attempts AS DOUBLE) AS api_dribbles_attempts,
                CAST(api_dribbles_success AS DOUBLE) AS api_dribbles_success,
                CAST(api_duels_total AS DOUBLE) AS api_duels_total,
                CAST(api_duels_won AS DOUBLE) AS api_duels_won,
                CAST(api_cards_yellow AS DOUBLE) AS api_cards_yellow,
                CAST(api_cards_red AS DOUBLE) AS api_cards_red,
                CAST(api_goals_total_per90 AS DOUBLE) AS api_goals_total_per90,
                CAST(api_goals_assists_per90 AS DOUBLE) AS api_goals_assists_per90,
                CAST(api_shots_total_per90 AS DOUBLE) AS api_shots_total_per90,
                CAST(api_shots_on_per90 AS DOUBLE) AS api_shots_on_per90,
                CAST(api_passes_key_per90 AS DOUBLE) AS api_passes_key_per90,
                CAST(api_tackles_total_per90 AS DOUBLE) AS api_tackles_total_per90,
                CAST(api_duels_won_per90 AS DOUBLE) AS api_duels_won_per90,
                CAST(api_cards_yellow_per90 AS DOUBLE) AS api_cards_yellow_per90,
                CAST(api_cards_red_per90 AS DOUBLE) AS api_cards_red_per90,
                CAST(understat_minutes AS DOUBLE) AS understat_minutes,
                CAST(understat_xg AS DOUBLE) AS understat_xg,
                CAST(understat_xa AS DOUBLE) AS understat_xa,
                CAST(understat_assists AS DOUBLE) AS understat_assists,
                CAST(understat_goals AS DOUBLE) AS understat_goals,
                CAST(understat_shots AS DOUBLE) AS understat_shots,
                CAST(understat_key_passes AS DOUBLE) AS understat_key_passes,
                'historical'::VARCHAR AS source
              FROM analytics.raw_player_season_regression_dataset
            ),
            current AS (
              SELECT
                CASE
                  WHEN NULLIF(TRIM(CAST(api_player_id AS VARCHAR)), '') IS NOT NULL
                    THEN 'api:' || TRIM(CAST(api_player_id AS VARCHAR))
                  WHEN NULLIF(TRIM(CAST(understat_player_id AS VARCHAR)), '') IS NOT NULL
                    THEN 'understat:' || TRIM(CAST(understat_player_id AS VARCHAR))
                  ELSE 'name_md5:' || md5(lower(COALESCE(CAST(player_name AS VARCHAR), '')))
                END AS player_uid,
                CAST(season AS BIGINT) AS season,
                CAST(player_name AS VARCHAR) AS player_name,
                CAST(team_name AS VARCHAR) AS team_name,
                CAST(league_id AS BIGINT) AS league_id,
                CAST(model_position AS VARCHAR) AS model_position,
                CAST(api_position AS VARCHAR) AS api_position,
                CAST(player_age AS DOUBLE) AS player_age,
                TRY_CAST(target_market_value_eur AS DOUBLE) AS target_market_value_eur,
                CAST(last_market_value_eur AS DOUBLE) AS last_market_value_eur,
                CAST(api_minutes AS DOUBLE) AS api_minutes,
                CAST(api_appearances AS DOUBLE) AS api_appearances,
                CAST(api_starts AS DOUBLE) AS api_starts,
                CAST(api_goals_total AS DOUBLE) AS api_goals_total,
                CAST(api_goals_assists AS DOUBLE) AS api_goals_assists,
                CAST(api_shots_total AS DOUBLE) AS api_shots_total,
                CAST(api_shots_on AS DOUBLE) AS api_shots_on,
                CAST(api_passes_total AS DOUBLE) AS api_passes_total,
                CAST(api_passes_key AS DOUBLE) AS api_passes_key,
                CAST(api_tackles_total AS DOUBLE) AS api_tackles_total,
                CAST(api_dribbles_attempts AS DOUBLE) AS api_dribbles_attempts,
                CAST(api_dribbles_success AS DOUBLE) AS api_dribbles_success,
                CAST(api_duels_total AS DOUBLE) AS api_duels_total,
                CAST(api_duels_won AS DOUBLE) AS api_duels_won,
                CAST(api_cards_yellow AS DOUBLE) AS api_cards_yellow,
                CAST(api_cards_red AS DOUBLE) AS api_cards_red,
                CAST(api_goals_total_per90 AS DOUBLE) AS api_goals_total_per90,
                CAST(api_goals_assists_per90 AS DOUBLE) AS api_goals_assists_per90,
                CAST(api_shots_total_per90 AS DOUBLE) AS api_shots_total_per90,
                CAST(api_shots_on_per90 AS DOUBLE) AS api_shots_on_per90,
                CAST(api_passes_key_per90 AS DOUBLE) AS api_passes_key_per90,
                CAST(api_tackles_total_per90 AS DOUBLE) AS api_tackles_total_per90,
                CAST(api_duels_won_per90 AS DOUBLE) AS api_duels_won_per90,
                CAST(api_cards_yellow_per90 AS DOUBLE) AS api_cards_yellow_per90,
                CAST(api_cards_red_per90 AS DOUBLE) AS api_cards_red_per90,
                CAST(understat_minutes AS DOUBLE) AS understat_minutes,
                CAST(understat_xg AS DOUBLE) AS understat_xg,
                CAST(understat_xa AS DOUBLE) AS understat_xa,
                CAST(understat_assists AS DOUBLE) AS understat_assists,
                CAST(understat_goals AS DOUBLE) AS understat_goals,
                CAST(understat_shots AS DOUBLE) AS understat_shots,
                CAST(understat_key_passes AS DOUBLE) AS understat_key_passes,
                'current'::VARCHAR AS source
              FROM analytics.raw_player_stats_2025_26
            ),
            combined AS (
              SELECT * FROM historical
              UNION ALL
              SELECT * FROM current
            )
            SELECT
              c.*,
              CASE
                WHEN c.understat_minutes IS NOT NULL AND c.understat_minutes > 0
                  THEN c.understat_xg / c.understat_minutes * 90.0
              END AS understat_xg_per90,
              CASE
                WHEN c.understat_minutes IS NOT NULL AND c.understat_minutes > 0
                  THEN c.understat_xa / c.understat_minutes * 90.0
              END AS understat_xa_per90,
              CASE
                WHEN c.understat_minutes IS NOT NULL AND c.understat_minutes > 0
                  THEN (COALESCE(c.understat_xg, 0) + COALESCE(c.understat_xa, 0))
                       / c.understat_minutes * 90.0
              END AS xg_xa_per90,
              c.api_goals_assists_per90 AS goals_assists_per90,
              CASE
                WHEN c.api_duels_total IS NOT NULL AND c.api_duels_total > 0
                  THEN c.api_duels_won / c.api_duels_total
              END AS duel_win_rate,
              CASE
                WHEN c.api_dribbles_attempts IS NOT NULL AND c.api_dribbles_attempts > 0
                  THEN c.api_dribbles_success / c.api_dribbles_attempts
              END AS dribble_success_rate,
              CASE
                WHEN c.api_minutes IS NOT NULL AND c.api_minutes > 0
                  THEN (COALESCE(c.api_cards_yellow, 0) + COALESCE(c.api_cards_red, 0))
                       / c.api_minutes * 90.0
              END AS cards_per90
            FROM combined c;
            """
        )

        # Player-season fact, UNIQUE on (player_uid, season).
        # For transferred players, choose the row with the most minutes.
        # Predictions only join for the current 2025 season.
        con.execute(
            f"""
            CREATE OR REPLACE TABLE analytics.fact_player_seasons AS
            WITH ranked AS (
              SELECT
                fts.*,
                ROW_NUMBER() OVER (
                  PARTITION BY fts.player_uid, fts.season
                  ORDER BY
                    COALESCE(fts.api_minutes, -1) DESC,
                    COALESCE(fts.api_appearances, -1) DESC,
                    fts.team_name NULLS LAST
                ) AS row_rank
              FROM analytics.fact_player_team_seasons fts
            ),
            picked AS (
              SELECT * FROM ranked WHERE row_rank = 1
            ),
            season_teams AS (
              SELECT
                player_uid,
                season,
                STRING_AGG(DISTINCT team_name, ' / ' ORDER BY team_name) AS season_team_names,
                COUNT(DISTINCT team_name) AS season_team_count,
                SUM(COALESCE(api_minutes, 0)) AS season_total_minutes
              FROM analytics.fact_player_team_seasons
              GROUP BY player_uid, season
            )
            SELECT
              p.player_uid,
              p.season,
              p.player_name,
              p.team_name AS primary_team_name,
              st.season_team_names,
              st.season_team_count,
              p.league_id,
              p.model_position,
              p.api_position,
              p.player_age,
              p.target_market_value_eur,
              p.last_market_value_eur,
              p.api_minutes,
              p.api_appearances,
              p.api_starts,
              p.api_goals_total,
              p.api_goals_assists,
              p.api_shots_total,
              p.api_shots_on,
              p.api_passes_total,
              p.api_passes_key,
              p.api_tackles_total,
              p.api_dribbles_attempts,
              p.api_dribbles_success,
              p.api_duels_total,
              p.api_duels_won,
              p.api_cards_yellow,
              p.api_cards_red,
              p.api_goals_total_per90,
              p.api_goals_assists_per90,
              p.api_shots_total_per90,
              p.api_shots_on_per90,
              p.api_passes_key_per90,
              p.api_tackles_total_per90,
              p.api_duels_won_per90,
              p.api_cards_yellow_per90,
              p.api_cards_red_per90,
              p.understat_minutes,
              p.understat_xg,
              p.understat_xa,
              p.understat_goals,
              p.understat_assists,
              p.understat_shots,
              p.understat_key_passes,
              p.understat_xg_per90,
              p.understat_xa_per90,
              p.xg_xa_per90,
              p.goals_assists_per90,
              p.duel_win_rate,
              p.dribble_success_rate,
              p.cards_per90,
              CASE WHEN p.season = {CURRENT_SEASON}
                   THEN pred.predicted_market_value_eur END AS predicted_market_value_eur,
              CASE WHEN p.season = {CURRENT_SEASON}
                   THEN pred.selected_model_spec END AS selected_model_spec,
              CASE WHEN p.season = {CURRENT_SEASON}
                   THEN pred.selected_algorithm END AS selected_algorithm,
              CASE WHEN p.season = {CURRENT_SEASON}
                   THEN pred.uses_last_market_value END AS uses_last_market_value,
              dp.player_photo_url,
              p.source
            FROM picked p
            LEFT JOIN season_teams st
              ON st.player_uid = p.player_uid AND st.season = p.season
            LEFT JOIN analytics.fact_predictions_2025_26 pred
              ON pred.player_name = p.player_name
             AND pred.season = p.season
             AND COALESCE(pred.team_name, '') = COALESCE(p.team_name, '')
            LEFT JOIN analytics.dim_players dp
              ON dp.player_uid = p.player_uid;
            """
        )

        con.execute(
            """
            CREATE OR REPLACE VIEW analytics.vw_player_latest_projection AS
            SELECT
              player_uid,
              player_name,
              season,
              primary_team_name AS team_name,
              model_position,
              last_market_value_eur,
              predicted_market_value_eur,
              player_photo_url
            FROM analytics.fact_player_seasons
            WHERE season = (SELECT MAX(season) FROM analytics.fact_player_seasons);
            """
        )

        # Verify uniqueness invariants.
        dup_count = con.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT player_uid, season
              FROM analytics.fact_player_seasons
              GROUP BY 1, 2
              HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        if dup_count > 0:
            raise RuntimeError(
                f"fact_player_seasons not unique on (player_uid, season): "
                f"{dup_count} duplicate keys."
            )

        if transfermarkt_duckdb is not None:
            con.execute("DETACH transfermarkt_db;")
    finally:
        con.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a DuckDB analytics database from merged player CSV datasets."
        )
    )
    parser.add_argument(
        "--predictions-csv",
        type=Path,
        default=DEFAULT_PREDICTIONS_CSV,
        help="Path to player_market_value_predictions CSV.",
    )
    parser.add_argument(
        "--regression-csv",
        type=Path,
        default=DEFAULT_REGRESSION_CSV,
        help="Path to player_season_regression_dataset CSV.",
    )
    parser.add_argument(
        "--stats-csv",
        type=Path,
        default=DEFAULT_STATS_CSV,
        help="Path to player_stats CSV.",
    )
    parser.add_argument(
        "--output-duckdb",
        type=Path,
        default=DEFAULT_OUTPUT_DUCKDB,
        help="Output DuckDB path.",
    )
    parser.add_argument(
        "--transfermarkt-duckdb",
        type=Path,
        default=DEFAULT_TRANSFERMARKT_DUCKDB,
        help="Transfermarkt DuckDB used for player photos.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_duckdb(
        predictions_csv=args.predictions_csv,
        regression_csv=args.regression_csv,
        stats_csv=args.stats_csv,
        output_duckdb=args.output_duckdb,
        transfermarkt_duckdb=args.transfermarkt_duckdb,
    )
    print(f"Built DuckDB: {args.output_duckdb}")


if __name__ == "__main__":
    main()
