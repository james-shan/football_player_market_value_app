import "server-only";
import { query } from "./db";
import { LEAGUE_NAMES } from "./labels";
import type {
  CohortRow,
  CurrentMappingRow,
  PlayerProfile,
  PlayerSeasonRow,
  SquadRow,
} from "./types";

export type { CohortRow, CurrentMappingRow, PlayerSeasonRow, PlayerProfile, SquadRow };

export const CURRENT_SEASON = 2025;

const LEAGUE_IDS = Object.keys(LEAGUE_NAMES).map((k) => Number(k));
const LEAGUE_LIST = LEAGUE_IDS.join(",");

/**
 * Canonical league per team derived from the 2025 fact rows.
 *
 * Some entries in `analytics.fact_player_seasons` carry a `league_id` that
 * does not match the player's `primary_team_name` (data noise from the
 * upstream multi-source join). We assign each team its modal league and use
 * that as the authoritative league for filter dropdowns and squad slicing,
 * so the Club selector always lists the correct teams for the chosen league.
 */
const TEAM_TO_LEAGUE_CTE = `
team_to_league AS (
  SELECT primary_team_name AS team_name, league_id
  FROM (
    SELECT primary_team_name, league_id, COUNT(*) AS n,
           ROW_NUMBER() OVER (
             PARTITION BY primary_team_name
             ORDER BY COUNT(*) DESC, league_id
           ) AS rn
    FROM analytics.fact_player_seasons
    WHERE season = ${CURRENT_SEASON}
      AND uses_last_market_value = TRUE
      AND league_id IN (${LEAGUE_LIST})
      AND primary_team_name IS NOT NULL
    GROUP BY primary_team_name, league_id
  )
  WHERE rn = 1
)`;

/**
 * Goalkeeper-specific stats live in the raw tables, not in fact_player_seasons.
 * We splice them in via api_player_id-derived player_uid joins so the unified
 * row always exposes saves / goals conceded / save% for keepers.
 */
const GK_HISTORICAL_CTE = `
gk_hist AS (
  SELECT
    'api:' || TRIM(CAST(api_player_id AS VARCHAR)) AS player_uid,
    season,
    api_goals_conceded AS goals_conceded,
    api_goals_saves AS saves
  FROM analytics.raw_player_season_regression_dataset
  WHERE api_player_id IS NOT NULL
    AND season < ${CURRENT_SEASON}
)`;

const GK_CURRENT_CTE = `
gk_cur AS (
  SELECT
    'api:' || TRIM(CAST(api_player_id AS VARCHAR)) AS player_uid,
    season,
    api_goals_conceded AS goals_conceded,
    api_goals_saves AS saves
  FROM analytics.raw_player_stats_2025_26
  WHERE api_player_id IS NOT NULL
    AND season = ${CURRENT_SEASON}
)`;

/**
 * Per-player, per-season unified projection: pulls every season from
 * analytics.fact_player_seasons (which already contains both historical
 * actuals and the 2025-26 projection rows), enriches with goalkeeper-only
 * raw stats, and computes a few derived metrics we use throughout the UI
 * (per-90 passes, save rate, etc.).
 */
const UNIFIED_SEASONS_CTE = `
unified AS (
  SELECT
    f.player_uid,
    f.player_name,
    f.season,
    f.primary_team_name AS team_name,
    f.season_team_names,
    f.season_team_count,
    COALESCE(t.league_id, f.league_id) AS league_id,
    f.model_position,
    f.api_position,
    f.player_age,
    f.target_market_value_eur,
    f.last_market_value_eur,
    f.predicted_market_value_eur,
    (f.season = ${CURRENT_SEASON} AND f.uses_last_market_value = TRUE) AS is_projection,
    f.api_minutes,
    f.api_appearances,
    f.api_starts,
    f.api_goals_total,
    f.api_goals_assists,
    f.api_passes_total,
    f.api_passes_key,
    f.api_dribbles_attempts,
    f.api_dribbles_success,
    f.api_duels_total,
    f.api_duels_won,
    f.api_tackles_total,
    f.api_cards_yellow,
    f.api_cards_red,
    f.api_shots_total,
    f.api_shots_on,
    f.api_goals_total_per90,
    f.api_goals_assists_per90,
    f.goals_assists_per90,
    f.api_passes_key_per90,
    f.api_tackles_total_per90,
    f.api_duels_won_per90,
    f.api_shots_total_per90,
    f.api_shots_on_per90,
    f.api_cards_yellow_per90,
    f.api_cards_red_per90,
    f.understat_goals,
    f.understat_assists,
    f.understat_xg,
    f.understat_xa,
    f.understat_shots,
    f.understat_key_passes,
    f.understat_xg_per90,
    f.understat_xa_per90,
    f.xg_xa_per90,
    f.duel_win_rate,
    f.dribble_success_rate,
    f.cards_per90,
    COALESCE(gh.goals_conceded, gc.goals_conceded) AS goals_conceded,
    COALESCE(gh.saves,          gc.saves)          AS saves
  FROM analytics.fact_player_seasons f
  LEFT JOIN team_to_league t ON t.team_name = f.primary_team_name
  LEFT JOIN gk_hist gh
    ON gh.player_uid = f.player_uid AND gh.season = f.season
  LEFT JOIN gk_cur gc
    ON gc.player_uid = f.player_uid AND gc.season = f.season
)`;

const DERIVED_METRICS_SQL = `
  s.api_minutes,
  s.api_appearances,
  s.api_starts,
  s.api_goals_total,
  s.api_goals_assists,
  s.api_passes_total,
  s.api_passes_key,
  s.api_dribbles_attempts,
  s.api_dribbles_success,
  s.api_duels_total,
  s.api_duels_won,
  s.api_tackles_total,
  s.api_cards_yellow,
  s.api_cards_red,
  s.api_shots_total,
  s.api_shots_on,
  s.api_passes_key_per90,
  s.api_tackles_total_per90,
  s.api_duels_won_per90,
  s.api_shots_total_per90,
  s.api_shots_on_per90,
  s.understat_goals,
  s.understat_assists,
  s.understat_xg,
  s.understat_xa,
  s.understat_shots,
  s.understat_key_passes,
  s.understat_xg_per90 AS xg_per90,
  s.understat_xa_per90 AS xa_per90,
  s.xg_xa_per90,
  s.goals_assists_per90,
  s.duel_win_rate,
  s.dribble_success_rate,
  s.cards_per90,
  s.goals_conceded,
  s.saves,
  CASE WHEN s.api_minutes > 0
       THEN COALESCE(s.understat_goals, s.api_goals_total, 0)::DOUBLE * 90.0 / s.api_minutes
       END AS understat_goals_per90,
  CASE WHEN s.api_minutes > 0
       THEN COALESCE(s.understat_assists, 0)::DOUBLE * 90.0 / s.api_minutes
       END AS understat_assists_per90,
  CASE WHEN s.api_minutes > 0
       THEN COALESCE(s.understat_shots, 0)::DOUBLE * 90.0 / s.api_minutes
       END AS understat_shots_per90,
  CASE WHEN s.api_minutes > 0
       THEN COALESCE(s.api_passes_total, 0)::DOUBLE * 90.0 / s.api_minutes
       END AS api_passes_total_per90,
  CASE WHEN s.api_minutes > 0
       THEN COALESCE(s.api_dribbles_attempts, 0)::DOUBLE * 90.0 / s.api_minutes
       END AS api_dribbles_attempts_per90,
  CASE WHEN s.api_minutes > 0
       THEN COALESCE(s.saves, 0)::DOUBLE * 90.0 / s.api_minutes
       END AS saves_per90,
  CASE WHEN s.api_minutes > 0
       THEN COALESCE(s.goals_conceded, 0)::DOUBLE * 90.0 / s.api_minutes
       END AS goals_conceded_per90,
  CASE WHEN COALESCE(s.saves, 0) + COALESCE(s.goals_conceded, 0) > 0
       THEN COALESCE(s.saves, 0)::DOUBLE
            / (COALESCE(s.saves, 0) + COALESCE(s.goals_conceded, 0))
       END AS save_rate,
  CASE WHEN COALESCE(s.api_shots_total, 0) > 0
       THEN COALESCE(s.api_goals_total, 0)::DOUBLE / s.api_shots_total
       END AS goal_conversion_rate
`;

/** All current-season (2025) player rows used to drive filters/search. */
export async function getCurrentMapping(): Promise<CurrentMappingRow[]> {
  return query<CurrentMappingRow>(`
    WITH ${TEAM_TO_LEAGUE_CTE}
    SELECT
      f.player_uid,
      f.player_name,
      f.primary_team_name AS team_name,
      COALESCE(t.league_id, f.league_id) AS league_id,
      f.model_position,
      f.player_age,
      COALESCE(f.player_photo_url, dp.player_photo_url) AS player_photo_url,
      f.last_market_value_eur,
      f.predicted_market_value_eur
    FROM analytics.fact_player_seasons f
    LEFT JOIN team_to_league t ON t.team_name = f.primary_team_name
    LEFT JOIN analytics.dim_players dp USING (player_uid)
    WHERE f.season = ${CURRENT_SEASON}
      AND f.uses_last_market_value = TRUE
      AND f.predicted_market_value_eur IS NOT NULL
      AND COALESCE(t.league_id, f.league_id) IN (${LEAGUE_LIST})
    ORDER BY f.player_name
  `);
}

/** Full season history for one player_uid, including 2025 projection. */
export async function getPlayerSeasons(
  playerUid: string,
): Promise<PlayerSeasonRow[]> {
  return query<PlayerSeasonRow>(
    `
    WITH ${TEAM_TO_LEAGUE_CTE},
    ${GK_HISTORICAL_CTE},
    ${GK_CURRENT_CTE},
    ${UNIFIED_SEASONS_CTE}
    SELECT
      s.player_uid,
      s.player_name,
      s.season,
      s.team_name,
      s.season_team_names,
      s.season_team_count,
      s.league_id,
      s.model_position,
      s.api_position,
      s.player_age,
      s.target_market_value_eur,
      s.last_market_value_eur,
      s.predicted_market_value_eur,
      s.is_projection,
      ${DERIVED_METRICS_SQL}
    FROM unified s
    WHERE s.player_uid = ?
    ORDER BY s.season ASC
    `,
    [playerUid],
  );
}

export async function getPlayerProfile(
  playerUid: string,
): Promise<PlayerProfile | null> {
  const rows = await query<PlayerProfile>(
    `
    WITH ${TEAM_TO_LEAGUE_CTE}
    SELECT
      f.player_uid,
      f.player_name,
      f.primary_team_name AS team_name,
      COALESCE(t.league_id, f.league_id) AS league_id,
      f.model_position,
      f.api_position,
      f.player_age,
      COALESCE(f.player_photo_url, dp.player_photo_url) AS player_photo_url,
      f.last_market_value_eur,
      f.predicted_market_value_eur
    FROM analytics.fact_player_seasons f
    LEFT JOIN team_to_league t ON t.team_name = f.primary_team_name
    LEFT JOIN analytics.dim_players dp USING (player_uid)
    WHERE f.player_uid = ?
      AND f.season = ${CURRENT_SEASON}
      AND f.uses_last_market_value = TRUE
    LIMIT 1
    `,
    [playerUid],
  );
  if (rows.length) return rows[0];
  // Fallback: latest historical row (no projection available).
  const fallback = await query<PlayerProfile>(
    `
    WITH ${TEAM_TO_LEAGUE_CTE},
    last_hist AS (
      SELECT * FROM analytics.fact_player_seasons
      WHERE player_uid = ?
      ORDER BY season DESC
      LIMIT 1
    )
    SELECT
      h.player_uid,
      h.player_name,
      h.primary_team_name AS team_name,
      COALESCE(t.league_id, h.league_id) AS league_id,
      h.model_position,
      h.api_position,
      h.player_age,
      COALESCE(h.player_photo_url, dp.player_photo_url) AS player_photo_url,
      h.last_market_value_eur,
      h.predicted_market_value_eur
    FROM last_hist h
    LEFT JOIN team_to_league t ON t.team_name = h.primary_team_name
    LEFT JOIN analytics.dim_players dp USING (player_uid)
    `,
    [playerUid],
  );
  return fallback[0] ?? null;
}

/**
 * Cohort = all current-season players in the same league + position as the
 * supplied player. Used by the percentile chart to rank a player's stats
 * against their direct peers.
 */
export async function getPlayerCohort(playerUid: string): Promise<{
  player: CohortRow | null;
  cohort: CohortRow[];
}> {
  const seedRows = await query<{
    league_id: number | null;
    model_position: string | null;
  }>(
    `
    WITH ${TEAM_TO_LEAGUE_CTE}
    SELECT
      COALESCE(t.league_id, f.league_id) AS league_id,
      f.model_position
    FROM analytics.fact_player_seasons f
    LEFT JOIN team_to_league t ON t.team_name = f.primary_team_name
    WHERE f.player_uid = ?
      AND f.season = ${CURRENT_SEASON}
      AND f.uses_last_market_value = TRUE
    LIMIT 1
    `,
    [playerUid],
  );
  const seed = seedRows[0];
  if (!seed || seed.league_id == null || !seed.model_position) {
    return { player: null, cohort: [] };
  }
  const cohort = await query<CohortRow>(
    `
    WITH ${TEAM_TO_LEAGUE_CTE},
    ${GK_HISTORICAL_CTE},
    ${GK_CURRENT_CTE},
    ${UNIFIED_SEASONS_CTE}
    SELECT
      s.player_uid,
      s.player_name,
      s.team_name,
      s.league_id,
      s.model_position,
      ${DERIVED_METRICS_SQL}
    FROM unified s
    WHERE s.season = ${CURRENT_SEASON}
      AND s.is_projection = TRUE
      AND s.league_id = ?
      AND s.model_position = ?
      AND s.predicted_market_value_eur IS NOT NULL
    `,
    [seed.league_id, seed.model_position],
  );
  const player = cohort.find((r) => r.player_uid === playerUid) ?? null;
  return { player, cohort };
}

export type SquadFilters = {
  leagueId?: number;
  team?: string;
  position?: string;
};

export async function getSquad(filters: SquadFilters): Promise<SquadRow[]> {
  const where: string[] = [
    `f.season = ${CURRENT_SEASON}`,
    `f.uses_last_market_value = TRUE`,
    `f.predicted_market_value_eur IS NOT NULL`,
    `COALESCE(t.league_id, f.league_id) IN (${LEAGUE_LIST})`,
  ];
  const params: (string | number)[] = [];
  if (filters.leagueId) {
    where.push(`COALESCE(t.league_id, f.league_id) = ?`);
    params.push(filters.leagueId);
  }
  if (filters.team) {
    where.push(`f.primary_team_name = ?`);
    params.push(filters.team);
  }
  if (filters.position) {
    where.push(`f.model_position = ?`);
    params.push(filters.position);
  }
  return query<SquadRow>(
    `
    WITH ${TEAM_TO_LEAGUE_CTE}
    SELECT
      f.player_uid,
      f.player_name,
      f.primary_team_name AS team_name,
      COALESCE(t.league_id, f.league_id) AS league_id,
      f.model_position,
      f.player_age,
      COALESCE(f.player_photo_url, dp.player_photo_url) AS player_photo_url,
      f.last_market_value_eur,
      f.predicted_market_value_eur,
      f.api_minutes,
      f.goals_assists_per90,
      f.xg_xa_per90,
      f.api_passes_key_per90,
      f.api_tackles_total_per90,
      f.duel_win_rate,
      CASE WHEN f.last_market_value_eur > 0
           THEN (f.predicted_market_value_eur - f.last_market_value_eur) / f.last_market_value_eur
           END AS projected_change_pct
    FROM analytics.fact_player_seasons f
    LEFT JOIN team_to_league t ON t.team_name = f.primary_team_name
    LEFT JOIN analytics.dim_players dp USING (player_uid)
    WHERE ${where.join(" AND ")}
    ORDER BY f.predicted_market_value_eur DESC NULLS LAST
    `,
    params,
  );
}

export async function getLeagueOptions(): Promise<
  { league_id: number; n_players: number }[]
> {
  return query(
    `
    WITH ${TEAM_TO_LEAGUE_CTE}
    SELECT COALESCE(t.league_id, f.league_id) AS league_id,
           COUNT(*) AS n_players
    FROM analytics.fact_player_seasons f
    LEFT JOIN team_to_league t ON t.team_name = f.primary_team_name
    WHERE f.season = ${CURRENT_SEASON}
      AND f.uses_last_market_value = TRUE
      AND f.predicted_market_value_eur IS NOT NULL
      AND COALESCE(t.league_id, f.league_id) IN (${LEAGUE_LIST})
    GROUP BY league_id
    ORDER BY league_id
    `,
  );
}
