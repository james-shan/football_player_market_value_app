# Player Value Data Report

## Data Sources
- API-Football: player season and per-90 football stats (`api_*`)
- Understat: advanced xG/xA and possession-chain features (`understat_*`)
- Transfermarkt: market value labels and age (`target_*`, `last_market_*`, `transfermarkt_*`)
- Engineered: keys and transformed features (e.g., `player_season_uid`, percentile features)

## Dataset Shapes
- Historical (2015-16 to 2024-25): 19,718 rows x 146 columns
- Prediction (2025-26): 2,057 rows x 146 columns

## Key Completeness Checks
- historical: uid null%=0.0, last_market_value null%=0.0, target null%=0.0
- prediction_2025: uid null%=0.0, last_market_value null%=0.0, target null%=100.0

## Output Files
- Data dictionary: `data/reports/player_value_data_dictionary.csv`
- Numeric distributions: `data/reports/player_value_numeric_distribution.csv`
- Categorical distributions: `data/reports/player_value_categorical_distribution.csv`
- Source summary: `data/reports/player_value_source_summary.csv`