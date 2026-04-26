/**
 * Display-name mapping for raw DuckDB columns.
 * The UI must never show raw column names; always look them up here.
 */
export const COLUMN_LABELS: Record<string, string> = {
  player_uid: "Player ID",
  player_name: "Player",
  season: "Season",
  team_name: "Team",
  league_id: "League",
  model_position: "Position",
  api_position: "Position",
  player_age: "Age",
  player_photo_url: "Photo",

  target_market_value_eur: "Market Value",
  last_market_value_eur: "Last Market Value",
  predicted_market_value_eur: "Projected End-of-Season Value",
  projected_change_pct: "Projected Change %",

  api_minutes: "Minutes",
  api_appearances: "Appearances",
  api_starts: "Starts",
  api_goals_total: "Goals",
  api_goals_assists: "Assists",
  api_passes_total: "Passes",
  api_passes_key: "Key Passes",
  api_dribbles_attempts: "Dribbles Attempted",
  api_dribbles_success: "Dribbles Completed",
  api_duels_total: "Duels",
  api_duels_won: "Duels Won",
  api_tackles_total: "Tackles",
  api_cards_yellow: "Yellow Cards",
  api_cards_red: "Red Cards",
  api_shots_total: "Shots",
  api_shots_on: "Shots on Target",

  goals_assists_per90: "Goals + Assists / 90",
  api_passes_key_per90: "Key Passes / 90",
  api_tackles_total_per90: "Tackles / 90",
  api_duels_won_per90: "Duels Won / 90",
  api_shots_total_per90: "Shots / 90",
  api_shots_on_per90: "Shots on Target / 90",

  understat_goals: "Goals (xG src)",
  understat_assists: "Assists (xG src)",
  understat_xg: "xG",
  understat_xa: "xA",
  understat_shots: "Shots (xG src)",
  understat_key_passes: "Key Passes (xG src)",
  understat_goals_per90: "Goals / 90",
  understat_assists_per90: "Assists / 90",
  xg_per90: "xG / 90",
  xa_per90: "xA / 90",
  xg_xa_per90: "xG + xA / 90",
  understat_shots_per90: "Shots / 90",

  dribble_success_rate: "Dribble Success %",
  duel_win_rate: "Duel Win %",
  cards_per90: "Cards / 90",

  saves: "Saves",
  goals_conceded: "Goals Conceded",
  saves_per90: "Saves / 90",
  goals_conceded_per90: "Goals Conceded / 90",
  save_rate: "Save %",
  api_passes_total_per90: "Passes / 90",
  api_dribbles_attempts_per90: "Dribbles Attempted / 90",
  goal_conversion_rate: "Goal Conversion %",
};

export function label(key: string): string {
  return COLUMN_LABELS[key] ?? key;
}

export const LEAGUE_NAMES: Record<number, string> = {
  39: "Premier League",
  61: "Ligue 1",
  78: "Bundesliga",
  135: "Serie A",
  140: "La Liga",
};

export const LEAGUE_COUNTRIES: Record<number, string> = {
  39: "England",
  61: "France",
  78: "Germany",
  135: "Italy",
  140: "Spain",
};

export const POSITION_LABELS: Record<string, string> = {
  G: "Goalkeeper",
  D: "Defender",
  M: "Midfielder",
  F: "Forward",
};

export function positionLabel(code: string | null | undefined): string {
  if (!code) return "—";
  return POSITION_LABELS[code] ?? code;
}

export function leagueLabel(id: number | null | undefined): string {
  if (id == null) return "—";
  return LEAGUE_NAMES[id] ?? `League ${id}`;
}
