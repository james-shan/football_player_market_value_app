/**
 * Position-specific UI configuration: which stat groups to show for the
 * season-by-season bar charts and which metrics to surface in the percentile
 * (vs same league + same position cohort) panel.
 *
 * The choices are informed by the model feature-importance CSV
 * (data/merged/player_market_value_feature_importance_top10.csv) but are
 * curated to be easy to read for a non-analyst audience: standard "shots,
 * passes, tackles, saves" type metrics rather than internal model features.
 */

export type StatKey =
  | "api_minutes"
  | "api_starts"
  | "api_appearances"
  | "api_goals_total_per90"
  | "understat_goals_per90"
  | "understat_assists_per90"
  | "goals_assists_per90"
  | "xg_per90"
  | "xa_per90"
  | "xg_xa_per90"
  | "api_shots_total_per90"
  | "api_shots_on_per90"
  | "api_passes_key_per90"
  | "api_passes_total_per90"
  | "api_tackles_total_per90"
  | "api_duels_won_per90"
  | "duel_win_rate"
  | "dribble_success_rate"
  | "api_dribbles_attempts_per90"
  | "cards_per90"
  // Goalkeeper-only enrichments (joined from raw_player_*).
  | "saves_per90"
  | "goals_conceded_per90"
  | "save_rate";

export type StatFormat = "rate" | "percent" | "count";

export type StatChartSeries = {
  key: StatKey;
  label: string;
  color: string;
};

export type StatChartGroup = {
  title: string;
  description: string;
  format: StatFormat;
  series: StatChartSeries[];
};

export type PercentileMetric = {
  key: StatKey;
  label: string;
  format: StatFormat;
  /** When true, lower raw values are better → percentile is inverted. */
  lowerIsBetter?: boolean;
};

export type PositionConfig = {
  positionLabel: string;
  charts: StatChartGroup[];
  percentiles: PercentileMetric[];
};

const COLORS = {
  emerald: "#10b981",
  indigo: "#6366f1",
  amber: "#f59e0b",
  pink: "#ec4899",
  cyan: "#22d3ee",
  rose: "#f43f5e",
};

const PLAYING_TIME: StatChartGroup = {
  title: "Playing Time",
  description: "Minutes, starts, and appearances by season",
  format: "count",
  series: [
    { key: "api_minutes", label: "Minutes", color: COLORS.emerald },
    { key: "api_starts", label: "Starts", color: COLORS.indigo },
    { key: "api_appearances", label: "Appearances", color: COLORS.amber },
  ],
};

const FORWARD: PositionConfig = {
  positionLabel: "Forward",
  charts: [
    PLAYING_TIME,
    {
      title: "Goal Output",
      description: "Goals, expected goals, and shots on target per 90",
      format: "rate",
      series: [
        { key: "understat_goals_per90", label: "Goals / 90", color: COLORS.emerald },
        { key: "xg_per90", label: "xG / 90", color: COLORS.indigo },
        { key: "api_shots_on_per90", label: "Shots on Tgt / 90", color: COLORS.amber },
      ],
    },
    {
      title: "Creation",
      description: "Assists, expected assists, and key passes per 90",
      format: "rate",
      series: [
        { key: "understat_assists_per90", label: "Assists / 90", color: COLORS.indigo },
        { key: "xa_per90", label: "xA / 90", color: COLORS.cyan },
        { key: "api_passes_key_per90", label: "Key Passes / 90", color: COLORS.pink },
      ],
    },
    {
      title: "On-the-Ball & Pressing",
      description: "Dribble success and duels won per 90",
      format: "rate",
      series: [
        { key: "api_duels_won_per90", label: "Duels Won / 90", color: COLORS.emerald },
        { key: "dribble_success_rate", label: "Dribble Success %", color: COLORS.amber },
      ],
    },
  ],
  percentiles: [
    { key: "understat_goals_per90", label: "Goals / 90", format: "rate" },
    { key: "xg_per90", label: "xG / 90", format: "rate" },
    { key: "goals_assists_per90", label: "G+A / 90", format: "rate" },
    { key: "xg_xa_per90", label: "xG+xA / 90", format: "rate" },
    { key: "api_shots_on_per90", label: "Shots on Tgt / 90", format: "rate" },
    { key: "dribble_success_rate", label: "Dribble Success %", format: "percent" },
  ],
};

const MIDFIELDER: PositionConfig = {
  positionLabel: "Midfielder",
  charts: [
    PLAYING_TIME,
    {
      title: "Creation",
      description: "Assists, expected assists, and key passes per 90",
      format: "rate",
      series: [
        { key: "understat_assists_per90", label: "Assists / 90", color: COLORS.indigo },
        { key: "xa_per90", label: "xA / 90", color: COLORS.cyan },
        { key: "api_passes_key_per90", label: "Key Passes / 90", color: COLORS.pink },
      ],
    },
    {
      title: "Goal Threat",
      description: "Goals, expected goals, and shots per 90",
      format: "rate",
      series: [
        { key: "understat_goals_per90", label: "Goals / 90", color: COLORS.emerald },
        { key: "xg_per90", label: "xG / 90", color: COLORS.indigo },
        { key: "api_shots_total_per90", label: "Shots / 90", color: COLORS.amber },
      ],
    },
    {
      title: "Defensive Work & Duels",
      description: "Tackles, duels won, and dribble success",
      format: "rate",
      series: [
        { key: "api_tackles_total_per90", label: "Tackles / 90", color: COLORS.emerald },
        { key: "api_duels_won_per90", label: "Duels Won / 90", color: COLORS.indigo },
      ],
    },
  ],
  percentiles: [
    { key: "api_passes_key_per90", label: "Key Passes / 90", format: "rate" },
    { key: "xg_xa_per90", label: "xG+xA / 90", format: "rate" },
    { key: "goals_assists_per90", label: "G+A / 90", format: "rate" },
    { key: "dribble_success_rate", label: "Dribble Success %", format: "percent" },
    { key: "api_tackles_total_per90", label: "Tackles / 90", format: "rate" },
    { key: "duel_win_rate", label: "Duel Win %", format: "percent" },
  ],
};

const DEFENDER: PositionConfig = {
  positionLabel: "Defender",
  charts: [
    PLAYING_TIME,
    {
      title: "Defensive Actions",
      description: "Tackles and duels won per 90",
      format: "rate",
      series: [
        { key: "api_tackles_total_per90", label: "Tackles / 90", color: COLORS.emerald },
        { key: "api_duels_won_per90", label: "Duels Won / 90", color: COLORS.indigo },
      ],
    },
    {
      title: "Aerial / Ground Duels",
      description: "Share of duels won and dribbles successfully completed",
      format: "percent",
      series: [
        { key: "duel_win_rate", label: "Duel Win %", color: COLORS.emerald },
        { key: "dribble_success_rate", label: "Dribble Success %", color: COLORS.amber },
      ],
    },
    {
      title: "Attacking Contribution",
      description: "Goals, assists, and creation output per 90",
      format: "rate",
      series: [
        { key: "understat_goals_per90", label: "Goals / 90", color: COLORS.emerald },
        { key: "understat_assists_per90", label: "Assists / 90", color: COLORS.indigo },
        { key: "xg_xa_per90", label: "xG+xA / 90", color: COLORS.amber },
      ],
    },
    {
      title: "Passing Volume",
      description: "Total passes and key passes per 90",
      format: "rate",
      series: [
        { key: "api_passes_total_per90", label: "Passes / 90", color: COLORS.emerald },
        { key: "api_passes_key_per90", label: "Key Passes / 90", color: COLORS.pink },
      ],
    },
  ],
  percentiles: [
    { key: "api_tackles_total_per90", label: "Tackles / 90", format: "rate" },
    { key: "api_duels_won_per90", label: "Duels Won / 90", format: "rate" },
    { key: "duel_win_rate", label: "Duel Win %", format: "percent" },
    { key: "xg_xa_per90", label: "xG+xA / 90", format: "rate" },
    { key: "goals_assists_per90", label: "G+A / 90", format: "rate" },
    { key: "api_passes_total_per90", label: "Passes / 90", format: "rate" },
  ],
};

const GOALKEEPER: PositionConfig = {
  positionLabel: "Goalkeeper",
  charts: [
    PLAYING_TIME,
    {
      title: "Shot Stopping",
      description: "Saves and goals conceded per 90, save percentage",
      format: "rate",
      series: [
        { key: "saves_per90", label: "Saves / 90", color: COLORS.emerald },
        { key: "goals_conceded_per90", label: "Goals Conceded / 90", color: COLORS.rose },
      ],
    },
    {
      title: "Save Percentage",
      description: "Saves divided by total shots on target faced",
      format: "percent",
      series: [{ key: "save_rate", label: "Save %", color: COLORS.cyan }],
    },
    {
      title: "Distribution",
      description: "Total passes and key passes per 90",
      format: "rate",
      series: [
        { key: "api_passes_total_per90", label: "Passes / 90", color: COLORS.emerald },
        { key: "api_passes_key_per90", label: "Key Passes / 90", color: COLORS.pink },
      ],
    },
    {
      title: "Discipline",
      description: "Cards per 90 minutes",
      format: "rate",
      series: [{ key: "cards_per90", label: "Cards / 90", color: COLORS.amber }],
    },
  ],
  percentiles: [
    { key: "save_rate", label: "Save %", format: "percent" },
    {
      key: "goals_conceded_per90",
      label: "Goals Conceded / 90",
      format: "rate",
      lowerIsBetter: true,
    },
    { key: "saves_per90", label: "Saves / 90", format: "rate" },
    { key: "api_passes_total_per90", label: "Passes / 90", format: "rate" },
    { key: "api_minutes", label: "Minutes Played", format: "count" },
    { key: "duel_win_rate", label: "Duel Win %", format: "percent" },
  ],
};

export const POSITION_CONFIG: Record<string, PositionConfig> = {
  G: GOALKEEPER,
  D: DEFENDER,
  M: MIDFIELDER,
  F: FORWARD,
};

export function getPositionConfig(code: string | null | undefined): PositionConfig {
  if (code && POSITION_CONFIG[code]) return POSITION_CONFIG[code];
  return MIDFIELDER;
}
