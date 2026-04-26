# Player Market Value Study (Methods and Results)

This document explains the project from an analytical perspective: data collection, cleaning, filtering, modeling strategy, benchmarking, feature importance, and how the dashboard operationalizes the outputs.

For execution details (commands, setup, app runbook), use `README.md`.

## 1) Problem Definition

The project estimates end-of-season player market value using historical player-season performance and valuation data, then generates out-of-sample projections for season `2025` (representing 2025-26 in this pipeline).

The modeling objective is to produce:

- Reliable position-aware market value predictions.
- Transparent benchmark comparisons.
- Interpretable drivers via feature importance.
- A usable analytics product through a web app.

## 2) Data Collection

### 2.1 Sources

The pipeline integrates three football data sources:

- **API-Football**: player/team/league season and match-level performance statistics.
- **Understat**: expected metrics and chance-creation metrics (xG/xA/xG chain/build-up).
- **Transfermarkt DuckDB snapshot**: market valuation history and profile fields.

### 2.2 API-Football extraction modes

Two extraction methods are implemented:

- `per_season` route (`scripts/api_football_players_flow.py`)
- `per_fixture` route (`scripts/api_football_fixture_players_flow.py`)

Both support top-5 league batch runs (`39`, `61`, `78`, `135`, `140`) across a season range and include request counting before full pulls.

### 2.3 Why two API modes?

Per-season and per-fixture payloads can differ in completeness depending on endpoint behavior and historical season availability. The merge script can auto-select whichever source has lower missingness for key football stat columns.

## 3) Data Cleaning and Harmonization

Core cleaning and harmonization are implemented in `scripts/build_player_value_regression_dataset.py`.

### 3.1 Entity normalization

- Player and team names are normalized (lowercase, accent stripping, token cleanup, punctuation removal) to improve cross-source joins.
- League IDs are mapped to Understat league names for controlled matching.

### 3.2 Season parsing

- Multiple season formats are parsed into a common season start year.
- Understat season keys (e.g., `1516`, `1920`) are interpreted as season-start years.

### 3.3 Deduplication for transfers

Players may appear more than once in the same season when they move clubs.

- API rows are deduplicated at player-season level.
- Numeric volume metrics are aggregated.
- Rate/per-90 fields are recomputed from aggregated totals.
- Team names played in a season are preserved for traceability.

### 3.4 Transfermarkt target alignment

For season `x`, target valuation is selected from the valuation window immediately after season end (May-September of `x+1`), ensuring that target values are temporally aligned to the completed season.

Additional logic:

- A lag valuation (`last_market_value_eur`) is merged from the prior season.
- Match-level diagnostics are stored (`team_match`, `player_match`, ongoing fallbacks).
- For season `2025`, current target is intentionally set to null so it is treated as pure prediction data.

## 4) Filtering and Modeling Table Construction

The notebook `notebooks/regression_data_prep.ipynb` prepares model-ready tables.

### 4.1 Key modeling filters

- Position segmentation into model positions: `G`, `D`, `M`, `F`.
- Non-playing/irrelevant position labels (e.g., subs) are excluded.
- Null handling and column-level filtering are applied before final exports.
- Stable key `player_season_uid` is retained for prediction mapping.

### 4.2 Target and lag features

- Target: `target_market_value_eur`
- Modeling target: `target_market_value_log = log1p(target_market_value_eur)`
- Lag value:
  - `last_market_value_eur`
  - `last_market_value_log = log1p(last_market_value_eur)`
  - `has_last_market_value`

### 4.3 Final modeling datasets

- Historical training/eval set: `player_value_modeling_2015_16_to_2024_25.csv`
- Prediction-scoring set: `player_stats_2025_26_null_market_value.csv`

## 5) Modeling Framework

Modeling is implemented in `scripts/model_player_market_values_by_position.py`.

### 5.1 Candidate families

Candidates are trained separately for each position and each setup:

- Setup A: `uses_last_market_value = False`
- Setup B: `uses_last_market_value = True`

For each setup, the pipeline evaluates:

- 3 feature specifications:
  - `model_1_simplified_performance`
  - `model_2_full_performance_age_exposure`
  - `model_3_position_percentiles`
- 2 algorithms:
  - `ridge`
  - `lightgbm`

Total candidate space per position:

- `3 specs × 2 algorithms × 2 setups = 12` model variants.

### 5.2 Temporal split strategy

Default split logic:

- Train: all completed seasons before validation.
- Validation: second-most-recent completed season.
- Test: most-recent completed season.
- Prediction: season `2025`.

This enforces chronological integrity and avoids leakage from future seasons.

### 5.3 Hyperparameter tuning and selection

- Hyperparameter search occurs on validation MAE.
- Final model selection per position/setup is based on configurable test metric (default `test_mae`).
- Supported selection metrics: `test_mae`, `test_rmse`, `test_rmsle`, `test_r2`.

### 5.4 Final refit and prediction

Selected models are retrained on all completed seasons (train + validation + test), then used to score the 2025 rows.

Predictions are transformed from log-space:

- `predicted_market_value_eur = expm1(prediction_log)`

## 6) Benchmarking

Benchmark analysis is performed in `notebooks/player_market_value_results_visualization.ipynb`.

The notebook includes a naive baseline:

- **Lag baseline**: predict current value as last known value.

This benchmark is compared against selected model outputs using standard regression metrics (including `R^2` and error analyses), enabling assessment of whether ML models materially outperform persistence.

## 7) Modeling Results Artifacts

Primary result files:

- `data/merged/player_market_value_model_comparison.csv`
  - Full candidate-by-candidate performance table.
  - Includes selected flags and tuned hyperparameters.
- `data/merged/player_market_value_predictions_2025_26.csv`
  - Final projected market values for prediction-season rows.
- `data/merged/player_market_value_feature_importance_top10.csv`
  - Top 10 transformed features for each selected position/setup model.

Notebook outputs provide:

- Position-by-position candidate performance summaries.
- Benchmark comparisons.
- Error distribution views.
- Projection summaries for 2025.

## 8) Feature Importance Interpretation

Importance is computed post-selection for each chosen model:

- LightGBM: tree feature importances (`feature_importances_`).
- Ridge: absolute coefficient magnitude as a linear importance proxy.

The exported ranking is model-specific and transformed-feature specific (e.g., one-hot encoded categories appear as separate transformed features). This is useful for identifying whether:

- Performance volume/exposure signals dominate.
- Age/trajectory terms matter by position.
- Lag value information carries predictive power.
- Percentile-based features improve robustness.

## 9) How the App Uses the Results

The application is built on top of `data/merged/player_analytics.duckdb`, generated by `scripts/build_player_analytics_duckdb.py`.

### 9.1 Data model in app-serving DB

Main entities include:

- `analytics.dim_players`
- `analytics.fact_player_team_seasons`
- `analytics.fact_player_seasons` (unique player-season, transfer-safe)
- `analytics.vw_player_latest_projection`

The 2025 projection attached in app-facing facts is the canonical model variant where:

- `uses_last_market_value = TRUE`

### 9.2 Product surfaces

- **Player Explorer (`/`)**
  - Historical market value + projected value timeline.
  - Position-aware percentile visuals.
  - Position-specific metric cards.
  - Season-level stats and export.
- **Squad Overview (`/squad`)**
  - Current vs projected squad value.
  - Top risers/fallers and positional value splits.
  - Distribution and ranking views for team-level decision support.

### 9.3 Why this matters analytically

The app bridges model outputs and practical interpretation:

- Scouting/valuation users can inspect individual projections with context.
- Team-level users can evaluate projected roster value movement.
- Analysts can validate whether model behavior aligns with football intuition.

## 10) Limitations and Practical Considerations

- Matching across public football datasets is inherently noisy due to name/team inconsistencies.
- Transfer seasons create multi-team rows that require aggregation assumptions.
- Market value reflects many off-pitch factors (contract length, injuries, transfer dynamics) that may be only partially captured by stat-based features.
- Feature importance reflects association under model structure, not strict causal effect.
- Prediction-year rows depend on the same pipeline assumptions used in historical alignment.

## 11) Reproducibility Checklist

To reproduce the full analytical outputs:

1. Collect API-Football data.
2. Prepare/refresh Understat and Transfermarkt inputs.
3. Run `scripts/build_player_value_regression_dataset.py`.
4. Run `notebooks/regression_data_prep.ipynb`.
5. Run `scripts/model_player_market_values_by_position.py`.
6. Run `scripts/build_player_analytics_duckdb.py`.
7. Validate in `notebooks/player_market_value_results_visualization.ipynb`.
8. Launch app and inspect both pages (`/`, `/squad`).
