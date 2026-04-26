#!/usr/bin/env python3
"""Train position-specific market value models and predict 2025-26 values.

Change the default file paths, season split, model grids, and selection metric
in the constants below or pass the matching CLI arguments.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
try:
    from sklearn.metrics import root_mean_squared_error
except ImportError:  # sklearn < 1.4
    root_mean_squared_error = None
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from lightgbm import LGBMRegressor


ROOT = Path(__file__).resolve().parents[1]

# Change these paths if you want to train or predict from different files.
TRAINING_DATA_PATH = ROOT / "data" / "merged" / "player_value_modeling_2015_16_to_2024_25.csv"
PREDICTION_DATA_PATH = ROOT / "data" / "merged" / "player_stats_2025_26_null_market_value.csv"
COMPARISON_OUTPUT_PATH = ROOT / "data" / "merged" / "player_market_value_model_comparison.csv"
PREDICTION_OUTPUT_PATH = ROOT / "data" / "merged" / "player_market_value_predictions_2025_26.csv"
FEATURE_IMPORTANCE_OUTPUT_PATH = ROOT / "data" / "merged" / "player_market_value_feature_importance_top10.csv"

# Change these seasons if you want a different season-based split.
# If left as None, the script uses the two most recent completed seasons in
# TRAINING_DATA_PATH as validation/test and all earlier seasons as train.
VALIDATION_SEASON: int | None = None
TEST_SEASON: int | None = None
PREDICTION_SEASON = 2025

# Change this to "test_rmse", "test_rmsle", or "test_r2" if desired.
SELECTION_METRIC = "test_mae"

CATEGORICAL_FEATURES = {"transfermarkt_match_level"}
IDENTIFIER_COLUMNS = [
    "player_season_uid",
    "player_name",
    "season",
    "team_name",
    "model_position",
    "last_market_value_eur",
]

MODEL_SPECS = {
    "model_1_simplified_performance": [
        "log_minutes",
        "minutes_share_3420",
        "start_rate",
        "player_age",
        "player_age_sq",
        "goals_assists_per90",
        "xg_xa_per90",
        "api_avg_rating",
        "transfermarkt_match_level",
    ],
    "model_2_full_performance_age_exposure": [
        "goals_assists_per90",
        "xg_xa_per90",
        "np_xg_xa_per90",
        "understat_xg_chain_per90",
        "understat_xg_buildup_per90",
        "api_avg_rating",
        "shot_on_target_rate",
        "goal_conversion_rate",
        "dribble_success_rate",
        "duel_win_rate",
        "log_minutes",
        "minutes_share_3420",
        "start_rate",
        "player_age",
        "player_age_sq",
        "age_peak_gap",
        "transfermarkt_match_level",
    ],
    "model_3_position_percentiles": [
        "goals_assists_per90_pos_season_pct",
        "xg_xa_per90_pos_season_pct",
        "np_xg_xa_per90_pos_season_pct",
        "understat_xg_chain_per90_pos_season_pct",
        "understat_xg_buildup_per90_pos_season_pct",
        "api_tackles_total_per90_pos_season_pct",
        "api_duels_won_per90_pos_season_pct",
        "api_passes_key_per90_pos_season_pct",
        "shot_on_target_rate_pos_season_pct",
        "duel_win_rate_pos_season_pct",
        "api_minutes_pos_season_pct",
        "api_avg_rating_pos_season_pct",
        "age_peak_gap",
        "is_u21",
        "is_over30",
        "transfermarkt_match_level",
    ],
}

# Change these grids to broaden or narrow validation-set hyperparameter tuning.
RIDGE_GRID = [
    {"regressor__alpha": alpha}
    for alpha in [0.1, 1.0, 10.0, 100.0]
]
LIGHTGBM_GRID = [
    {
        "regressor__n_estimators": n_estimators,
        "regressor__max_depth": max_depth,
        "regressor__num_leaves": num_leaves,
        "regressor__min_child_samples": min_child_samples,
        "regressor__learning_rate": learning_rate,
    }
    for n_estimators in [100, 200]
    for max_depth in [3, 5]
    for num_leaves in [7, 15]
    for min_child_samples in [30, 60]
    for learning_rate in [0.03, 0.05]
]


@dataclass(frozen=True)
class SplitConfig:
    train_seasons: list[int]
    validation_season: int
    test_season: int


@dataclass(frozen=True)
class Candidate:
    position: str
    model_spec: str
    algorithm: str
    uses_last_market_value: bool
    features: list[str]
    best_params: dict[str, Any]
    validation_metrics: dict[str, float]
    test_metrics: dict[str, float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train position-specific market value models and predict the 2025-26 outsample file."
    )
    parser.add_argument("--training-data", default=str(TRAINING_DATA_PATH))
    parser.add_argument("--prediction-data", default=str(PREDICTION_DATA_PATH))
    parser.add_argument("--comparison-output", default=str(COMPARISON_OUTPUT_PATH))
    parser.add_argument("--prediction-output", default=str(PREDICTION_OUTPUT_PATH))
    parser.add_argument("--validation-season", type=int, default=VALIDATION_SEASON)
    parser.add_argument("--test-season", type=int, default=TEST_SEASON)
    parser.add_argument("--prediction-season", type=int, default=PREDICTION_SEASON)
    parser.add_argument(
        "--selection-metric",
        choices=["test_mae", "test_rmse", "test_rmsle", "test_r2"],
        default=SELECTION_METRIC,
    )
    parser.add_argument(
        "--min-split-rows",
        type=int,
        default=20,
        help="Minimum train, validation, and test rows required for a position/setup.",
    )
    return parser.parse_args()


def make_one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def coerce_model_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    numeric_columns = {
        "season",
        "target_market_value_eur",
        "target_market_value_log",
        "last_market_value_eur",
        "last_market_value_log",
        "has_last_market_value",
    }
    for features in MODEL_SPECS.values():
        numeric_columns.update(col for col in features if col not in CATEGORICAL_FEATURES)
    numeric_columns.add("last_market_value_log")

    for col in sorted(numeric_columns & set(out.columns)):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in CATEGORICAL_FEATURES & set(out.columns):
        out[col] = out[col].astype("string")
    return out


def infer_split(
    df: pd.DataFrame,
    validation_season: int | None,
    test_season: int | None,
    prediction_season: int,
) -> SplitConfig:
    seasons = sorted(
        int(season)
        for season in df["season"].dropna().unique()
        if int(season) < prediction_season
    )
    if len(seasons) < 3:
        raise ValueError("Need at least three completed seasons for train/validation/test splitting.")

    test = test_season if test_season is not None else seasons[-1]
    validation = validation_season if validation_season is not None else seasons[seasons.index(test) - 1]
    train = [season for season in seasons if season < validation]
    if not train:
        raise ValueError("No training seasons remain before the validation season.")
    return SplitConfig(train_seasons=train, validation_season=validation, test_season=test)


def features_for_spec(model_spec: str, uses_last_market_value: bool) -> list[str]:
    features = list(MODEL_SPECS[model_spec])
    if uses_last_market_value:
        features.append("last_market_value_log")
    return features


def validate_required_columns(df: pd.DataFrame, prediction_df: pd.DataFrame) -> None:
    required = set(IDENTIFIER_COLUMNS) | {
        "target_market_value_eur",
        "target_market_value_log",
        "last_market_value_eur",
        "last_market_value_log",
        "has_last_market_value",
    }
    for features in MODEL_SPECS.values():
        required.update(features)
    missing_train = sorted(required - set(df.columns))
    prediction_required = (
        set(IDENTIFIER_COLUMNS)
        | set().union(*MODEL_SPECS.values())
        | {"has_last_market_value", "last_market_value_log"}
    )
    missing_prediction = sorted(prediction_required - set(prediction_df.columns))
    if missing_train:
        raise ValueError(f"Training data is missing required columns: {missing_train}")
    if missing_prediction:
        raise ValueError(f"Prediction data is missing required columns: {missing_prediction}")


def filter_setup_rows(df: pd.DataFrame, uses_last_market_value: bool) -> pd.DataFrame:
    eligible = df["target_market_value_log"].notna() & (df["target_market_value_eur"] > 0)
    if uses_last_market_value:
        eligible = (
            eligible
            & df["last_market_value_eur"].notna()
            & (df["last_market_value_eur"] > 0)
            & (df["has_last_market_value"] == 1)
        )
    return df[eligible].copy()


def target_for_setup(df: pd.DataFrame, uses_last_market_value: bool) -> pd.Series:
    # Keep a single target specification for all models.
    # uses_last_market_value only changes feature availability and eligible rows.
    return df["target_market_value_log"]


def market_value_predictions(df: pd.DataFrame, raw_predictions: np.ndarray, uses_last_market_value: bool) -> np.ndarray:
    # target_market_value_log is log1p(target_market_value_eur).
    predicted = np.expm1(raw_predictions)
    return np.clip(predicted, 0.0, None)


def metric_dict(y_true_eur: pd.Series | np.ndarray, y_pred_eur: np.ndarray) -> dict[str, float]:
    actual = np.asarray(y_true_eur, dtype=float)
    predicted = np.asarray(y_pred_eur, dtype=float)
    mask = np.isfinite(actual) & np.isfinite(predicted) & (actual >= 0) & (predicted >= 0)
    actual = actual[mask]
    predicted = predicted[mask]
    if len(actual) == 0:
        return {"mae": math.nan, "rmse": math.nan, "rmsle": math.nan, "r2": math.nan}
    if root_mean_squared_error is None:
        rmse = mean_squared_error(actual, predicted, squared=False)
        rmsle = mean_squared_error(np.log1p(actual), np.log1p(predicted), squared=False)
    else:
        rmse = root_mean_squared_error(actual, predicted)
        rmsle = root_mean_squared_error(np.log1p(actual), np.log1p(predicted))
    return {
        "mae": mean_absolute_error(actual, predicted),
        "rmse": rmse,
        "rmsle": rmsle,
        "r2": r2_score(actual, predicted) if len(actual) > 1 else math.nan,
    }


def make_preprocessor(features: list[str], algorithm: str) -> ColumnTransformer:
    categorical = [col for col in features if col in CATEGORICAL_FEATURES]
    numeric = [col for col in features if col not in CATEGORICAL_FEATURES]

    if algorithm == "ridge":
        numeric_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
    else:
        numeric_pipeline = Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))])

    transformers: list[tuple[str, Pipeline, list[str]]] = []
    if numeric:
        transformers.append(("numeric", numeric_pipeline, numeric))
    if categorical:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", make_one_hot_encoder()),
                    ]
                ),
                categorical,
            )
        )
    return ColumnTransformer(transformers=transformers, remainder="drop")


def make_pipeline(features: list[str], algorithm: str, random_state: int = 42) -> Pipeline:
    if algorithm == "ridge":
        regressor = Ridge()
    elif algorithm == "lightgbm":
        # Intentionally shallow/light configuration to reduce overfitting risk.
        regressor = LGBMRegressor(
            random_state=random_state,
            n_jobs=-1,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=0.5,
            objective="regression",
            verbosity=-1,
        )
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    return Pipeline(
        steps=[
            ("preprocess", make_preprocessor(features, algorithm)),
            ("regressor", regressor),
        ]
    )


def parameter_grid(algorithm: str) -> list[dict[str, Any]]:
    if algorithm == "ridge":
        return RIDGE_GRID
    if algorithm == "lightgbm":
        return LIGHTGBM_GRID
    raise ValueError(f"Unknown algorithm: {algorithm}")


def feature_importance_for_model(model: Pipeline, features: list[str], algorithm: str) -> pd.DataFrame:
    preprocess: ColumnTransformer = model.named_steps["preprocess"]
    transformed_features = preprocess.get_feature_names_out()
    regressor = model.named_steps["regressor"]

    if algorithm == "lightgbm":
        importance = np.asarray(regressor.feature_importances_, dtype=float)
    elif algorithm == "ridge":
        # Keep ridge compatible by exposing coefficient magnitude as importance proxy.
        importance = np.abs(np.asarray(regressor.coef_, dtype=float))
    else:
        raise ValueError(f"Unsupported algorithm for feature importance: {algorithm}")

    out = pd.DataFrame(
        {
            "transformed_feature": transformed_features,
            "importance": importance,
        }
    ).sort_values("importance", ascending=False)
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def fit_and_score_on_validation(
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    features: list[str],
    algorithm: str,
    uses_last_market_value: bool,
) -> tuple[dict[str, Any], dict[str, float]]:
    best_params: dict[str, Any] | None = None
    best_metrics: dict[str, float] | None = None
    best_mae = math.inf

    for params in parameter_grid(algorithm):
        model = make_pipeline(features, algorithm)
        model.set_params(**params)
        model.fit(train_df[features], target_for_setup(train_df, uses_last_market_value))
        raw_predictions = model.predict(validation_df[features])
        predicted_eur = market_value_predictions(validation_df, raw_predictions, uses_last_market_value)
        metrics = metric_dict(validation_df["target_market_value_eur"], predicted_eur)
        if metrics["mae"] < best_mae:
            best_mae = metrics["mae"]
            best_params = params
            best_metrics = metrics

    if best_params is None or best_metrics is None:
        raise RuntimeError("No validation candidate was fitted.")
    return best_params, best_metrics


def train_candidate(
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    test_df: pd.DataFrame,
    position: str,
    model_spec: str,
    algorithm: str,
    uses_last_market_value: bool,
) -> Candidate:
    features = features_for_spec(model_spec, uses_last_market_value)
    best_params, validation_metrics = fit_and_score_on_validation(
        train_df, validation_df, features, algorithm, uses_last_market_value
    )

    train_validation_df = pd.concat([train_df, validation_df], ignore_index=True)
    model = make_pipeline(features, algorithm)
    model.set_params(**best_params)
    model.fit(train_validation_df[features], target_for_setup(train_validation_df, uses_last_market_value))
    raw_test_predictions = model.predict(test_df[features])
    test_predictions = market_value_predictions(test_df, raw_test_predictions, uses_last_market_value)
    test_metrics = metric_dict(test_df["target_market_value_eur"], test_predictions)

    return Candidate(
        position=position,
        model_spec=model_spec,
        algorithm=algorithm,
        uses_last_market_value=uses_last_market_value,
        features=features,
        best_params=best_params,
        validation_metrics=validation_metrics,
        test_metrics=test_metrics,
    )


def candidate_to_row(candidate: Candidate, is_selected: bool) -> dict[str, Any]:
    row: dict[str, Any] = {
        "position": candidate.position,
        "model_spec": candidate.model_spec,
        "algorithm": candidate.algorithm,
        "uses_last_market_value": candidate.uses_last_market_value,
        "selected_for_position_setup": is_selected,
        "selected_hyperparameters": json.dumps(candidate.best_params, sort_keys=True),
    }
    for prefix, metrics in [
        ("validation", candidate.validation_metrics),
        ("test", candidate.test_metrics),
    ]:
        for metric_name, value in metrics.items():
            row[f"{prefix}_{metric_name}"] = value
    return row


def is_better(candidate: Candidate, incumbent: Candidate | None, selection_metric: str) -> bool:
    if incumbent is None:
        return True
    metric_name = selection_metric.removeprefix("test_")
    candidate_value = candidate.test_metrics[metric_name]
    incumbent_value = incumbent.test_metrics[metric_name]
    if selection_metric == "test_r2":
        return candidate_value > incumbent_value
    return candidate_value < incumbent_value


def train_all_candidates(
    df: pd.DataFrame,
    split: SplitConfig,
    min_split_rows: int,
    selection_metric: str,
) -> tuple[list[dict[str, Any]], dict[tuple[str, bool], Candidate]]:
    comparison_rows: list[dict[str, Any]] = []
    selected: dict[tuple[str, bool], Candidate] = {}
    candidates_by_key: dict[tuple[str, bool], list[Candidate]] = {}

    positions = sorted(str(position) for position in df["model_position"].dropna().unique())
    for position in positions:
        position_df = df[df["model_position"].astype(str) == position].copy()
        for uses_last_market_value in [False, True]:
            setup_df = filter_setup_rows(position_df, uses_last_market_value)
            train_df = setup_df[setup_df["season"].isin(split.train_seasons)].copy()
            validation_df = setup_df[setup_df["season"] == split.validation_season].copy()
            test_df = setup_df[setup_df["season"] == split.test_season].copy()

            if min(len(train_df), len(validation_df), len(test_df)) < min_split_rows:
                print(
                    f"Skipping {position}, uses_last_market_value={uses_last_market_value}: "
                    f"split sizes train={len(train_df)}, validation={len(validation_df)}, test={len(test_df)}",
                    flush=True,
                )
                continue

            key = (position, uses_last_market_value)
            candidates_by_key[key] = []
            print(
                f"Training {position}, uses_last_market_value={uses_last_market_value} "
                f"(train={len(train_df)}, validation={len(validation_df)}, test={len(test_df)})",
                flush=True,
            )
            for model_spec in MODEL_SPECS:
                for algorithm in ["ridge", "lightgbm"]:
                    print(f"  - {model_spec} / {algorithm}", flush=True)
                    candidate = train_candidate(
                        train_df=train_df,
                        validation_df=validation_df,
                        test_df=test_df,
                        position=position,
                        model_spec=model_spec,
                        algorithm=algorithm,
                        uses_last_market_value=uses_last_market_value,
                    )
                    candidates_by_key[key].append(candidate)
                    if is_better(candidate, selected.get(key), selection_metric):
                        selected[key] = candidate

    for key, candidates in candidates_by_key.items():
        selected_candidate = selected[key]
        for candidate in candidates:
            comparison_rows.append(
                candidate_to_row(candidate, is_selected=candidate == selected_candidate)
            )
    return comparison_rows, selected


def eligible_prediction_rows(prediction_df: pd.DataFrame, position: str, uses_last_market_value: bool) -> pd.DataFrame:
    out = prediction_df[prediction_df["model_position"].astype(str) == position].copy()
    if uses_last_market_value:
        out = out[
            (out["has_last_market_value"] == 1)
            & out["last_market_value_eur"].notna()
            & (out["last_market_value_eur"] > 0)
        ].copy()
    return out


def refit_and_predict(
    df: pd.DataFrame,
    prediction_df: pd.DataFrame,
    split: SplitConfig,
    selected: dict[tuple[str, bool], Candidate],
) -> pd.DataFrame:
    output_frames: list[pd.DataFrame] = []
    completed_training_df = df[df["season"].isin(split.train_seasons + [split.validation_season, split.test_season])].copy()

    for (position, uses_last_market_value), candidate in selected.items():
        setup_df = filter_setup_rows(
            completed_training_df[completed_training_df["model_position"].astype(str) == position],
            uses_last_market_value,
        )
        prediction_rows = eligible_prediction_rows(prediction_df, position, uses_last_market_value)
        if prediction_rows.empty:
            print(
                f"No prediction rows for {position}, uses_last_market_value={uses_last_market_value}",
                flush=True,
            )
            continue

        model = make_pipeline(candidate.features, candidate.algorithm)
        model.set_params(**candidate.best_params)
        model.fit(setup_df[candidate.features], target_for_setup(setup_df, uses_last_market_value))
        raw_predictions = model.predict(prediction_rows[candidate.features])
        predicted_eur = market_value_predictions(prediction_rows, raw_predictions, uses_last_market_value)

        out = prediction_rows[IDENTIFIER_COLUMNS].copy()
        out["predicted_market_value_eur"] = predicted_eur
        out["selected_model_spec"] = candidate.model_spec
        out["selected_algorithm"] = candidate.algorithm
        out["uses_last_market_value"] = uses_last_market_value
        output_frames.append(out)

    if not output_frames:
        return pd.DataFrame(
            columns=IDENTIFIER_COLUMNS
            + [
                "predicted_market_value_eur",
                "selected_model_spec",
                "selected_algorithm",
                "uses_last_market_value",
            ]
        )
    return pd.concat(output_frames, ignore_index=True).sort_values(
        ["model_position", "player_name", "uses_last_market_value"]
    )


def selected_feature_importance(
    df: pd.DataFrame,
    split: SplitConfig,
    selected: dict[tuple[str, bool], Candidate],
    top_n: int = 10,
) -> pd.DataFrame:
    output_rows: list[dict[str, Any]] = []
    completed_training_df = df[
        df["season"].isin(split.train_seasons + [split.validation_season, split.test_season])
    ].copy()

    for (position, uses_last_market_value), candidate in selected.items():
        setup_df = filter_setup_rows(
            completed_training_df[completed_training_df["model_position"].astype(str) == position],
            uses_last_market_value,
        )
        if setup_df.empty:
            continue

        model = make_pipeline(candidate.features, candidate.algorithm)
        model.set_params(**candidate.best_params)
        model.fit(setup_df[candidate.features], target_for_setup(setup_df, uses_last_market_value))
        importance_df = feature_importance_for_model(model, candidate.features, candidate.algorithm).head(top_n)
        for _, row in importance_df.iterrows():
            output_rows.append(
                {
                    "position": position,
                    "uses_last_market_value": uses_last_market_value,
                    "model_spec": candidate.model_spec,
                    "algorithm": candidate.algorithm,
                    "feature_rank": int(row["rank"]),
                    "feature": row["transformed_feature"],
                    "importance": float(row["importance"]),
                }
            )
    return pd.DataFrame(output_rows)


def main() -> None:
    args = parse_args()
    training_path = Path(args.training_data)
    prediction_path = Path(args.prediction_data)
    comparison_output_path = Path(args.comparison_output)
    prediction_output_path = Path(args.prediction_output)
    feature_importance_output_path = FEATURE_IMPORTANCE_OUTPUT_PATH

    df = coerce_model_columns(pd.read_csv(training_path))
    prediction_df = coerce_model_columns(pd.read_csv(prediction_path))
    validate_required_columns(df, prediction_df)

    split = infer_split(df, args.validation_season, args.test_season, args.prediction_season)
    print(
        "Season split: "
        f"train={split.train_seasons[0]}-{split.train_seasons[-1]}, "
        f"validation={split.validation_season}, test={split.test_season}, "
        f"prediction={args.prediction_season}",
        flush=True,
    )
    prediction_df = prediction_df[prediction_df["season"] == args.prediction_season].copy()

    comparison_rows, selected = train_all_candidates(
        df=df,
        split=split,
        min_split_rows=args.min_split_rows,
        selection_metric=args.selection_metric,
    )
    if comparison_rows:
        comparison_df = pd.DataFrame(comparison_rows).sort_values(
            ["position", "uses_last_market_value", "selected_for_position_setup", args.selection_metric],
            ascending=[True, True, False, args.selection_metric != "test_r2"],
        )
    else:
        comparison_df = pd.DataFrame(
            columns=[
                "position",
                "model_spec",
                "algorithm",
                "uses_last_market_value",
                "selected_for_position_setup",
                "selected_hyperparameters",
                "validation_mae",
                "validation_rmse",
                "validation_rmsle",
                "validation_r2",
                "test_mae",
                "test_rmse",
                "test_rmsle",
                "test_r2",
            ]
        )
    comparison_output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_df.to_csv(comparison_output_path, index=False)

    if not selected:
        print("No models selected. Check split sizes, data availability, or --min-split-rows.", flush=True)
        predictions_df = pd.DataFrame(
            columns=IDENTIFIER_COLUMNS
            + [
                "predicted_market_value_eur",
                "selected_model_spec",
                "selected_algorithm",
                "uses_last_market_value",
            ]
        )
        feature_importance_df = pd.DataFrame(
            columns=[
                "position",
                "uses_last_market_value",
                "model_spec",
                "algorithm",
                "feature_rank",
                "feature",
                "importance",
            ]
        )
    else:
        predictions_df = refit_and_predict(df, prediction_df, split, selected)
        feature_importance_df = selected_feature_importance(df, split, selected, top_n=10)

    prediction_output_path.parent.mkdir(parents=True, exist_ok=True)
    predictions_df.to_csv(prediction_output_path, index=False)

    feature_importance_output_path.parent.mkdir(parents=True, exist_ok=True)
    feature_importance_df.to_csv(feature_importance_output_path, index=False)

    print(f"Saved model comparison -> {comparison_output_path}", flush=True)
    print(f"Saved final predictions -> {prediction_output_path}", flush=True)
    print(f"Saved top-10 feature importance -> {feature_importance_output_path}", flush=True)
    print(f"Selected {len(selected)} position/setup models.", flush=True)


if __name__ == "__main__":
    main()
