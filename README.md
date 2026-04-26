# Soccer Player Value Project (Technical README)

This repository contains a full pipeline to:

1. Collect and merge multi-source player-season data.
2. Build regression-ready modeling tables.
3. Train position-specific market value models.
4. Produce 2025-26 player projections and feature importance.
5. Build a DuckDB analytics database.
6. Serve an interactive Next.js dashboard.

If you want the methodology and modeling narrative (data collection/cleaning/filtering/modeling/results/benchmark/feature importance/app interpretation), read `README_METHODS_AND_RESULTS.md`.

## Repository Structure

- `scripts/`: data collection, merge, modeling, and DuckDB build scripts.
- `notebooks/`: feature engineering and results visualization notebooks.
- `data/`: raw/intermediate/final datasets and reports.
- `app/`, `components/`, `lib/`: Next.js analytics dashboard.

## End-to-End Pipeline Overview

### Step 1: Collect API-Football data

Two collection paths are supported:

- Per-season player endpoint pipeline: `scripts/api_football_players_flow.py`
- Per-fixture player endpoint pipeline: `scripts/api_football_fixture_players_flow.py`

Both scripts support:

- Single league-season runs.
- Batch runs across league lists and season ranges.
- `--count-only` mode to estimate API usage before downloading.
- Environment key override via `API_FOOTBALL_KEY`.

### Step 2: Merge API-Football + Understat + Transfermarkt

Script: `scripts/build_player_value_regression_dataset.py`

This stage:

- Auto-selects API source (`per_fixture` vs `per_season`) by null-completeness unless overridden.
- Normalizes player/team names for matching.
- Deduplicates player-season rows and aggregates transfer seasons.
- Merges Understat stats with fallback matching levels.
- Merges Transfermarkt season-end target values and lag market values.
- Forces season `2025` target to null (prediction-only season).

Outputs:

- `data/merged/player_season_regression_dataset.csv`
- `data/merged/player_season_regression_dataset_all3.csv`

### Step 3: Feature engineering and model tables

Notebook: `notebooks/regression_data_prep.ipynb`

Key outputs generated for model training/scoring:

- `data/merged/player_value_modeling_2015_16_to_2024_25.csv` (historical training/eval)
- `data/merged/player_stats_2025_26_null_market_value.csv` (2025 scoring table)

### Step 4: Train models and generate predictions

Script: `scripts/model_player_market_values_by_position.py`

This script:

- Trains per position (`D`, `F`, `G`, `M`), per setup (`uses_last_market_value` true/false).
- Evaluates 3 feature specs × 2 algorithms (`ridge`, `lightgbm`).
- Tunes hyperparameters on validation set.
- Selects best candidate by a configurable test metric (default `test_mae`).
- Refits selected models on all completed seasons.
- Scores prediction season (default `2025`).
- Exports top-10 transformed feature importances for selected models.

Outputs:

- `data/merged/player_market_value_model_comparison.csv`
- `data/merged/player_market_value_predictions_2025_26.csv`
- `data/merged/player_market_value_feature_importance_top10.csv`

### Step 5: Build analytics DuckDB for app

Script: `scripts/build_player_analytics_duckdb.py`

This stage builds:

- Raw imported tables from merged CSVs.
- `analytics.dim_players`
- `analytics.fact_player_team_seasons`
- `analytics.fact_player_seasons` (unique on player-season)
- `analytics.vw_player_latest_projection`

Output:

- `data/merged/player_analytics.duckdb`

### Step 6: Run dashboard app

The app queries `data/merged/player_analytics.duckdb` through `@duckdb/node-api`.

Pages:

- `/`: player explorer
- `/squad`: squad and league summary

## Environment Setup

### Python environment (pipeline)

Use your project Python environment (for example, conda env `compstats_proj`) and install required libraries if needed:

- `duckdb`
- `pandas`
- `numpy`
- `scikit-learn`
- `lightgbm`

### Node environment (app)

- Node.js 18.18+ (Node 20 LTS recommended)
- npm (lockfile is included)

## Data Pipeline Commands

Run from repository root.

### 1) API-Football collection (per-season route)

Single league-season:

```bash
python scripts/api_football_players_flow.py --league 39 --season 2021
```

Top-5 leagues over range:

```bash
python scripts/api_football_players_flow.py --batch-top5 --start-season 2011 --end-season 2025
```

Count API requests only:

```bash
python scripts/api_football_players_flow.py --batch-top5 --start-season 2011 --end-season 2025 --count-only
```

### 2) API-Football collection (per-fixture route)

Single league-season:

```bash
python scripts/api_football_fixture_players_flow.py --league 39 --season 2012
```

Count API requests only:

```bash
python scripts/api_football_fixture_players_flow.py --league 39 --season 2012 --count-only
```

Batch top-5 + merge existing aggregated CSVs:

```bash
python scripts/api_football_fixture_players_flow.py --batch-top5 --start-season 2011 --end-season 2025
```

### 3) Build merged regression dataset

Auto-select API source by completeness:

```bash
python scripts/build_player_value_regression_dataset.py
```

Force source:

```bash
python scripts/build_player_value_regression_dataset.py --api-source per_fixture
```

### 4) Prepare model tables in notebook

Open and run:

- `notebooks/regression_data_prep.ipynb`

Ensure the notebook exports:

- `data/merged/player_value_modeling_2015_16_to_2024_25.csv`
- `data/merged/player_stats_2025_26_null_market_value.csv`

### 5) Train/evaluate models and predict 2025

Default:

```bash
python scripts/model_player_market_values_by_position.py
```

Common override pattern:

```bash
python scripts/model_player_market_values_by_position.py \
  --training-data data/merged/player_value_modeling_2015_16_to_2024_25.csv \
  --prediction-data data/merged/player_stats_2025_26_null_market_value.csv \
  --validation-season 2023 \
  --test-season 2024 \
  --prediction-season 2025 \
  --selection-metric test_mae \
  --min-split-rows 20
```

### 6) Build DuckDB analytics database

```bash
python scripts/build_player_analytics_duckdb.py
```

## Run the Dashboard

Install and start:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Production mode:

```bash
npm run build
npm start
```

## App Data Layer Notes

- Connection layer: `lib/db.ts`
- Query layer: `lib/queries.ts`
- Label mapping: `lib/labels.ts`
- Formatting helpers: `lib/format.ts`
- Position view config: `lib/positionConfig.ts`
- API routes:
  - `app/api/mapping/route.ts`
  - `app/api/player/[uid]/route.ts`
  - `app/api/cohort/[uid]/route.ts`
  - `app/api/squad/route.ts`

## Key Artifacts Produced

Core modeling and analytics outputs:

- `data/merged/player_value_modeling_2015_16_to_2024_25.csv`
- `data/merged/player_stats_2025_26_null_market_value.csv`
- `data/merged/player_market_value_model_comparison.csv`
- `data/merged/player_market_value_predictions_2025_26.csv`
- `data/merged/player_market_value_feature_importance_top10.csv`
- `data/merged/player_analytics.duckdb`

Supporting reports:

- `data/reports/player_value_data_dictionary.csv`
- `data/reports/player_value_numeric_distribution.csv`
- `data/reports/player_value_categorical_distribution.csv`
- `data/reports/player_value_source_summary.csv`
- `data/reports/player_value_data_report.md`

## Troubleshooting

- No selected models in training output:
  - Lower `--min-split-rows` or provide more seasons/rows per position/setup.
- LightGBM import error:
  - Install `lightgbm` in the same Python environment used to run scripts.
- App shows no data:
  - Rebuild `data/merged/player_analytics.duckdb` after generating predictions.
- API-Football throttling:
  - Use `--count-only` first and increase `--throttle-seconds`.

## Technical File Index

- API per-season fetch: `scripts/api_football_players_flow.py`
- API per-fixture fetch: `scripts/api_football_fixture_players_flow.py`
- Merge builder: `scripts/build_player_value_regression_dataset.py`
- Feature engineering: `notebooks/regression_data_prep.ipynb`
- Model training/prediction: `scripts/model_player_market_values_by_position.py`
- Results analysis: `notebooks/player_market_value_results_visualization.ipynb`
- DuckDB build: `scripts/build_player_analytics_duckdb.py`
- Dashboard: `app/`, `components/`, `lib/`

