export type CurrentMappingRow = {
  player_uid: string;
  player_name: string;
  team_name: string | null;
  league_id: number | null;
  model_position: string | null;
  player_age: number | null;
  player_photo_url: string | null;
  last_market_value_eur: number | null;
  predicted_market_value_eur: number | null;
};

/**
 * One row per (player, season) used by the timeline, season table, and
 * position-specific charts. Pre-2025 rows are historical actuals; the
 * 2025 row (when present) is the model projection (`is_projection = true`).
 */
export type PlayerSeasonRow = {
  player_uid: string;
  player_name: string;
  season: number;
  team_name: string | null;
  season_team_names: string | null;
  season_team_count: number | null;
  league_id: number | null;
  model_position: string | null;
  api_position: string | null;
  player_age: number | null;
  target_market_value_eur: number | null;
  last_market_value_eur: number | null;
  predicted_market_value_eur: number | null;
  is_projection: boolean;

  api_minutes: number | null;
  api_appearances: number | null;
  api_starts: number | null;
  api_goals_total: number | null;
  api_goals_assists: number | null;
  api_passes_total: number | null;
  api_passes_key: number | null;
  api_dribbles_attempts: number | null;
  api_dribbles_success: number | null;
  api_duels_total: number | null;
  api_duels_won: number | null;
  api_tackles_total: number | null;
  api_cards_yellow: number | null;
  api_cards_red: number | null;
  api_shots_total: number | null;
  api_shots_on: number | null;

  api_passes_key_per90: number | null;
  api_tackles_total_per90: number | null;
  api_duels_won_per90: number | null;
  api_shots_total_per90: number | null;
  api_shots_on_per90: number | null;
  api_passes_total_per90: number | null;
  api_dribbles_attempts_per90: number | null;

  understat_goals: number | null;
  understat_assists: number | null;
  understat_xg: number | null;
  understat_xa: number | null;
  understat_shots: number | null;
  understat_key_passes: number | null;
  understat_goals_per90: number | null;
  understat_assists_per90: number | null;
  understat_shots_per90: number | null;
  xg_per90: number | null;
  xa_per90: number | null;
  xg_xa_per90: number | null;

  goals_assists_per90: number | null;
  duel_win_rate: number | null;
  dribble_success_rate: number | null;
  cards_per90: number | null;
  goal_conversion_rate: number | null;

  goals_conceded: number | null;
  saves: number | null;
  goals_conceded_per90: number | null;
  saves_per90: number | null;
  save_rate: number | null;
};

export type CohortRow = Omit<PlayerSeasonRow,
  | "season"
  | "season_team_names"
  | "season_team_count"
  | "api_position"
  | "player_age"
  | "target_market_value_eur"
  | "last_market_value_eur"
  | "predicted_market_value_eur"
  | "is_projection"
>;

export type PlayerProfile = {
  player_uid: string;
  player_name: string;
  team_name: string | null;
  league_id: number | null;
  model_position: string | null;
  api_position: string | null;
  player_age: number | null;
  player_photo_url: string | null;
  last_market_value_eur: number | null;
  predicted_market_value_eur: number | null;
};

export type SquadRow = CurrentMappingRow & {
  api_minutes: number | null;
  goals_assists_per90: number | null;
  xg_xa_per90: number | null;
  api_passes_key_per90: number | null;
  api_tackles_total_per90: number | null;
  duel_win_rate: number | null;
  projected_change_pct: number | null;
};
