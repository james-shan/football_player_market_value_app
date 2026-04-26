# Player Market Value Modeling Pipeline

This repository builds position-specific player market value models and produces 2025-26 predictions from merged football data.

The end-to-end workflow is:

1. Build merged player-season dataset from API-Football + Understat + Transfermarkt.
2. Engineer model features and export modeling/prediction tables.
3. Train and evaluate candidate models by position and setup.
4. Select best model per position/setup.
5. Refit selected models on all available pre-2025 seasons.
6. Predict 2025-26 market values.
7. Export top-10 feature importance per selected model.
8. Visualize results, error distributions, and baseline comparisons in notebook.

---

## 1) Project Outputs

Main output files (written under `data/merged/`):

- `player_value_modeling_2015_16_to_2024_25.csv`
  - historical training/evaluation data (target available)
- `player_stats_2025_26_null_market_value.csv`
  - 2025-26 scoring data (target intentionally null)
- `player_market_value_model_comparison.csv`
  - all candidate model results and selected flags
- `player_market_value_predictions_2025_26.csv`
  - final 2025-26 predictions
- `player_market_value_feature_importance_top10.csv`
  - top-10 features per selected model (position/setup)

Optional reporting outputs:

- `data/reports/player_value_data_dictionary.csv`
- `data/reports/player_value_numeric_distribution.csv`
- `data/reports/player_value_categorical_distribution.csv`
- `data/reports/player_value_source_summary.csv`
- `data/reports/player_value_data_report.md`

---

## 2) Data Sources and Join Logic

Primary sources:

- **API-Football** (`api_*` columns): season and per-90 box stats, position, team context
- **Understat** (`understat_*` columns): xG/xA, chain/build-up metrics
- **Transfermarkt**:
  - current market value target (`target_market_value_eur`)
  - lag market value (`last_market_value_eur`)
  - age and matching metadata

Dataset creation script:

- `scripts/build_player_value_regression_dataset.py`

Feature engineering notebook:

- `notebooks/regression_data_prep.ipynb`

---

## 3) Modeling Tables and Key Rules

Prepared tables are generated in `notebooks/regression_data_prep.ipynb` with these key rules:

- Position segmentation is explicit via `model_position` (`D`, `F`, `G`, `M`; `SUB` removed).
- Stable row key:
  - `player_season_uid` for mapping predictions back to players/seasons.
- Null policy:
  - row-drop for non-target columns under configured threshold.
  - report columns above threshold.
- Required lag-value rule:
  - rows with missing `last_market_value_eur` are dropped when that policy is enabled.
- Two final exports:
  - historical 2015-2024 table with target
  - 2025 table with null target

Core target columns:

- `target_market_value_eur`
- `target_market_value_log = log1p(target_market_value_eur)`

Lag columns:

- `last_market_value_eur`
- `last_market_value_log = log1p(last_market_value_eur)`
- `has_last_market_value`

---

## 4) Training Script Overview

Training script:

- `scripts/model_player_market_values_by_position.py`

### 4.1 Candidate design

For each position (`D`, `F`, `G`, `M`) and each setup:

- `uses_last_market_value=False`
- `uses_last_market_value=True` (adds lag feature + stricter row eligibility)

the script trains candidate combinations across:

- 3 feature specs:
  - `model_1_simplified_performance`
  - `model_2_full_performance_age_exposure`
  - `model_3_position_percentiles`
- 2 algorithms:
  - `ridge`
  - `lightgbm` (shallow settings to reduce overfitting risk)

### 4.2 Target specification

All model setups use the same target:

- `target_market_value_log`

Predictions are converted back to EUR with:

- `predicted_market_value_eur = expm1(raw_prediction)`

### 4.3 Time split

If not overridden:

- Train: all completed seasons before validation
- Validation: second-most-recent completed season
- Test: most-recent completed season
- Prediction: configured prediction season (default `2025`)

### 4.4 Selection metric

Default selection metric:

- `test_mae`

Supported:

- `test_mae`, `test_rmse`, `test_rmsle`, `test_r2`

### 4.5 Refit before prediction

After selecting best candidate per position/setup, each selected model is **retrained on all available completed seasons**:

- `train + validation + test`

Then used to score 2025 rows.

---

## 5) LightGBM Anti-Overfit Setup

Current LightGBM base configuration:

- `subsample=0.8`
- `colsample_bytree=0.8`
- `reg_alpha=0.1`
- `reg_lambda=0.5`
- `objective="regression"`

Grid (shallow):

- `n_estimators`: 100, 200
- `max_depth`: 3, 5
- `num_leaves`: 7, 15
- `min_child_samples`: 30, 60
- `learning_rate`: 0.03, 0.05

---

## 6) Feature Importance Export

The script exports top-10 transformed features for each selected position/setup model:

- Output: `data/merged/player_market_value_feature_importance_top10.csv`
- Columns:
  - `position`
  - `uses_last_market_value`
  - `model_spec`
  - `algorithm`
  - `feature_rank`
  - `feature`
  - `importance`

Importance definition:

- LightGBM: `feature_importances_`
- Ridge: absolute coefficient magnitude (fallback proxy)

---

## 7) Visualization Notebook

Notebook:

- `notebooks/player_market_value_results_visualization.ipynb`

Includes:

- selected model summary tables
- candidate metric comparisons
- 2025 prediction summaries
- baseline (`predict next value = last value`) with `R^2`
- test-season error distribution in 2x2 grid by position

---

## 8) Run Instructions

Use your project environment (example shown with `compstats_proj`):

```bash
/Users/james/opt/anaconda3/envs/compstats_proj/bin/python "scripts/model_player_market_values_by_position.py"
```

Common overrides:

```bash
/Users/james/opt/anaconda3/envs/compstats_proj/bin/python "scripts/model_player_market_values_by_position.py" \
  --training-data "data/merged/player_value_modeling_2015_16_to_2024_25.csv" \
  --prediction-data "data/merged/player_stats_2025_26_null_market_value.csv" \
  --validation-season 2023 \
  --test-season 2024 \
  --prediction-season 2025 \
  --selection-metric test_mae \
  --min-split-rows 20
```

---

## 9) Troubleshooting

### Script exits with no selected models

Cause:

- split subset too small per position/setup.

Fix:

- lower `--min-split-rows`, or increase available seasons/rows.

The script now handles this case gracefully and still writes empty-structured outputs.

### Environment mismatch / command crashes

Use explicit interpreter path:

```bash
/Users/james/opt/anaconda3/envs/compstats_proj/bin/python "scripts/model_player_market_values_by_position.py"
```

### LightGBM import issue

Install in same environment:

```bash
pip install lightgbm
```

---

## 10) File Index

- Data merge script: `scripts/build_player_value_regression_dataset.py`
- Feature engineering notebook: `notebooks/regression_data_prep.ipynb`
- Training/prediction script: `scripts/model_player_market_values_by_position.py`
- Results notebook: `notebooks/player_market_value_results_visualization.ipynb`
- DuckDB build script: `scripts/build_player_analytics_duckdb.py`
- Dashboard app: `app/`, `components/`, `lib/`

---

## 11) Web Dashboard

A Next.js + DuckDB dashboard for exploring player history and 2025-26
projected market values lives in this same repository.

### 11.1 Prerequisites

- Node.js 18.18+ (Node 20 LTS recommended)
- The DuckDB analytics file at `data/merged/player_analytics.duckdb`
  - If missing, generate it with:
    ```bash
    python scripts/build_player_analytics_duckdb.py
    ```

### 11.2 Install and run

```bash
npm install
npm run dev
# open http://localhost:3000
```

For a production build:

```bash
npm run build
npm start
```

### 11.3 Pages

- `/` — **Player Explorer.** League → club → player filters, fuzzy search,
  player profile (photo, current team/league/position/age), market value
  timeline (historical actuals + 2025-26 projected end-of-season), a
  **percentile chart** that ranks the selected player's key stats against
  every other player in the same league + position (cohort size shown in
  the legend), **position-specific stat blocks** (e.g. *Shot Stopping* /
  *Distribution* for goalkeepers, *Goal Output* / *Creation* for forwards,
  *Defensive Actions* / *Attacking Contribution* for defenders, etc.), and a
  sortable season-by-season stats table with CSV export. Players without a
  2025-26 projection are excluded from the filters and search.
- `/squad` — **Club / League Overview.** Squad-level summary built from the
  current 2025 mapping: total current vs projected squad value, average
  projected change, top risers/fallers, current vs projected by position,
  projected change distribution, top-10 projected values, and a per-player
  squad table. Each team is assigned its modal league across the 2025 fact
  rows, so the Club selector only ever lists clubs that actually play in
  the chosen league.

### 11.4 Data layer

The dashboard reads `data/merged/player_analytics.duckdb` in read-only mode
through `@duckdb/node-api`. Source files of interest:

- `lib/db.ts` — singleton DuckDB connection.
- `lib/queries.ts` — SQL builders. Defines the unified player-season query
  used everywhere:
  - historical seasons (`< 2025`) come from
    `analytics.raw_player_season_regression_dataset`, with goalkeeper-only
    columns (`api_goals_conceded`, `api_goals_saves`) joined back in so GKs
    have full shot-stopping history.
  - 2025-26 projection rows come from `analytics.fact_player_seasons` filtered
    to `uses_last_market_value = TRUE` (the canonical projection per player)
    and `predicted_market_value_eur IS NOT NULL`. GK current-season saves /
    goals conceded are joined from `analytics.raw_player_stats_2025_26`.
  - A **canonical team→league** CTE picks each team's modal `league_id` from
    the 2025 fact rows. Every UI-facing query (mapping, squad, league
    options) maps team rows through it, eliminating cross-league bleed
    caused by inconsistent raw league codes.
- `lib/positionConfig.ts` — per-position chart layout (`Goalkeeper`,
  `Defender`, `Midfielder`, `Forward`) and the percentile-metric set used
  by the Player Explorer cohort visualization.
- `app/api/cohort/[uid]/route.ts` — returns the player's same-league,
  same-position cohort (current 2025 season only, projection-required) so
  the percentile chart can compute ranks client-side.
- `lib/labels.ts` — display-name mapping. Raw DuckDB columns are never shown
  in the UI; everything goes through this layer (e.g.
  `target_market_value_eur` → `Market Value`,
  `predicted_market_value_eur` → `Projected End-of-Season Value`,
  `goals_assists_per90` → `Goals + Assists / 90`,
  `xg_xa_per90` → `xG + xA / 90`,
  `duel_win_rate` → `Duel Win %`,
  `dribble_success_rate` → `Dribble Success %`).
- `lib/format.ts` — currency, percent, rate, and count formatting helpers.

### 11.5 Stack

- Next.js 16 (App Router) + React 19 + TypeScript
- Tailwind CSS for styling
- Recharts for charts
- TanStack Table for the stats grid
- Fuse.js for fuzzy player search
- Papa Parse for CSV export
- `@duckdb/node-api` (read-only) for the data backend

