from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.services.forecast_features import (  # noqa: E402
    CATEGORICAL_FEATURES,
    FORECAST_ARTIFACT_FILENAME,
    FORECAST_MODEL_NAME,
    HISTORY_LAGS,
    NUMERIC_FEATURES,
    build_feature_row,
    normalize_municipality_type,
)


@dataclass
class SeriesMeta:
    oktmo: str
    region: str
    municipality: str
    mun_type: str
    area_sq_km: float | None
    rows: list[dict[str, float]]


def load_dataset(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, sep=";", dtype={"oktmo": str})
    df = df.rename(columns={"municipality": "municipality_name"})

    numeric_columns = [
        "year",
        "population",
        "average_population",
        "deaths",
        "births",
        "migration",
        "mortality_rate",
        "birth_rate",
        "migration_rate",
        "area",
    ]
    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    df["region"] = df["region"].fillna("").astype(str).str.strip()
    df["municipality_name"] = df["municipality_name"].fillna("").astype(str).str.strip()
    df["mun_type"] = df["mun_type"].map(normalize_municipality_type)
    df["oktmo"] = df["oktmo"].fillna("").astype(str).str.strip()
    df["area_sq_km"] = df["area"] / 100.0

    df = df.drop_duplicates(subset=["oktmo", "year"], keep="last")
    df = df[df["population"].notna()].copy()
    df["population"] = df["population"].astype(float)
    df["year"] = df["year"].astype(int)
    df = df.sort_values(["oktmo", "year"])
    return df


def build_series_map(df: pd.DataFrame) -> dict[str, SeriesMeta]:
    series_map: dict[str, SeriesMeta] = {}

    for oktmo, group in df.groupby("oktmo", sort=False):
        rows = [
            {"year": float(year), "population": float(population)}
            for year, population in group[["year", "population"]].itertuples(index=False, name=None)
        ]
        if not rows:
            continue

        area_values = group["area_sq_km"].dropna()
        area_sq_km = float(area_values.iloc[0]) if not area_values.empty else None

        series_map[oktmo] = SeriesMeta(
            oktmo=oktmo,
            region=str(group["region"].iloc[0]),
            municipality=str(group["municipality_name"].iloc[0]),
            mun_type=str(group["mun_type"].iloc[0]),
            area_sq_km=area_sq_km,
            rows=rows,
        )

    return series_map


def build_supervised_frame(series_map: dict[str, SeriesMeta]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for series in series_map.values():
        years = [int(item["year"]) for item in series.rows]
        populations = [float(item["population"]) for item in series.rows]
        if len(populations) <= HISTORY_LAGS:
            continue

        start_year = years[0]
        for index in range(HISTORY_LAGS, len(populations)):
            history = populations[:index]
            target_year = years[index]
            row = build_feature_row(
                history,
                target_year=target_year,
                start_year=start_year,
                region=series.region,
                municipality=series.municipality,
                mun_type=series.mun_type,
                oktmo=series.oktmo,
                area_sq_km=series.area_sq_km,
            )
            row["target_year"] = target_year
            row["target_delta"] = populations[index] - history[-1]
            rows.append(row)

    return pd.DataFrame(rows)


def build_pipeline(alpha: float) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", dtype=float),
                CATEGORICAL_FEATURES,
            ),
        ]
    )

    return Pipeline(
        steps=[
            ("preprocess", preprocessor),
            ("ridge", Ridge(alpha=alpha, solver="lsqr")),
        ]
    )


def fit_pipeline(frame: pd.DataFrame, alpha: float) -> Pipeline:
    pipeline = build_pipeline(alpha)
    pipeline.fit(frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES], frame["target_delta"])
    return pipeline


def calculate_metrics(actuals: list[float], predictions: list[float]) -> dict[str, float]:
    if not actuals:
        return {"rmse": 0.0, "mae": 0.0, "mape": 0.0}

    absolute_errors = [abs(actual - prediction) for actual, prediction in zip(actuals, predictions, strict=False)]
    squared_errors = [(actual - prediction) ** 2 for actual, prediction in zip(actuals, predictions, strict=False)]
    percent_errors = [
        abs(actual - prediction) / abs(actual) * 100.0
        for actual, prediction in zip(actuals, predictions, strict=False)
        if actual != 0
    ]

    rmse = (sum(squared_errors) / len(squared_errors)) ** 0.5
    mae = sum(absolute_errors) / len(absolute_errors)
    mape = sum(percent_errors) / len(percent_errors) if percent_errors else 0.0
    return {"rmse": rmse, "mae": mae, "mape": mape}


def one_step_metrics(pipeline: Pipeline, frame: pd.DataFrame, shrink_weight: float) -> dict[str, float]:
    if frame.empty:
        return {"rmse": 0.0, "mae": 0.0, "mape": 0.0}

    predicted_delta = pipeline.predict(frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES])
    predicted_population = frame["pop_lag_1"].to_numpy() + shrink_weight * predicted_delta
    actual_population = frame["pop_lag_1"].to_numpy() + frame["target_delta"].to_numpy()
    return calculate_metrics(actual_population.tolist(), predicted_population.tolist())


def recursive_forecast_series(
    pipeline: Pipeline,
    series: SeriesMeta,
    anchor_year: int,
    horizon_years: int,
    shrink_weight: float,
) -> list[tuple[int, float, float]]:
    observed_rows = [row for row in series.rows if int(row["year"]) <= anchor_year]
    if len(observed_rows) < HISTORY_LAGS or int(observed_rows[-1]["year"]) != anchor_year:
        return []

    actual_by_year = {int(row["year"]): float(row["population"]) for row in series.rows}
    history_values = [float(row["population"]) for row in observed_rows]
    start_year = int(observed_rows[0]["year"])
    predictions: list[tuple[int, float, float]] = []

    for step in range(1, horizon_years + 1):
        target_year = anchor_year + step
        if target_year not in actual_by_year:
            break

        feature_row = build_feature_row(
            history_values,
            target_year=target_year,
            start_year=start_year,
            region=series.region,
            municipality=series.municipality,
            mun_type=series.mun_type,
            oktmo=series.oktmo,
            area_sq_km=series.area_sq_km,
        )
        feature_frame = pd.DataFrame([feature_row], columns=NUMERIC_FEATURES + CATEGORICAL_FEATURES)
        predicted_delta = float(pipeline.predict(feature_frame)[0])
        predicted_population = max(0.0, history_values[-1] + shrink_weight * predicted_delta)
        actual_population = actual_by_year[target_year]
        predictions.append((step, predicted_population, actual_population))
        history_values.append(predicted_population)

    return predictions


def recursive_baseline_series(
    series: SeriesMeta,
    anchor_year: int,
    horizon_years: int,
) -> list[tuple[int, float, float]]:
    observed_rows = [row for row in series.rows if int(row["year"]) <= anchor_year]
    if len(observed_rows) < HISTORY_LAGS or int(observed_rows[-1]["year"]) != anchor_year:
        return []

    actual_by_year = {int(row["year"]): float(row["population"]) for row in series.rows}
    last_population = float(observed_rows[-1]["population"])
    predictions: list[tuple[int, float, float]] = []

    for step in range(1, horizon_years + 1):
        target_year = anchor_year + step
        if target_year not in actual_by_year:
            break
        predictions.append((step, last_population, actual_by_year[target_year]))

    return predictions


def recursive_metrics_for_anchor(
    pipeline: Pipeline,
    series_map: dict[str, SeriesMeta],
    anchor_year: int,
    horizon_years: int,
    shrink_weight: float,
) -> dict[str, float]:
    actuals: list[float] = []
    predictions: list[float] = []

    for series in series_map.values():
        for _, predicted_population, actual_population in recursive_forecast_series(
            pipeline,
            series,
            anchor_year,
            horizon_years,
            shrink_weight,
        ):
            predictions.append(predicted_population)
            actuals.append(actual_population)

    return calculate_metrics(actuals, predictions)


def recursive_backtest_for_anchor(
    pipeline: Pipeline,
    series_map: dict[str, SeriesMeta],
    anchor_year: int,
    horizon_years: int,
    shrink_weight: float,
) -> tuple[dict[str, float], dict[int, list[float]]]:
    errors_by_horizon: dict[int, list[float]] = {step: [] for step in range(1, horizon_years + 1)}
    actuals: list[float] = []
    predictions: list[float] = []

    for series in series_map.values():
        for step, predicted_population, actual_population in recursive_forecast_series(
            pipeline,
            series,
            anchor_year,
            horizon_years,
            shrink_weight,
        ):
            errors_by_horizon[step].append(abs(actual_population - predicted_population))
            predictions.append(predicted_population)
            actuals.append(actual_population)

    return calculate_metrics(actuals, predictions), errors_by_horizon


def baseline_metrics_for_anchor(
    series_map: dict[str, SeriesMeta],
    anchor_year: int,
    horizon_years: int,
) -> dict[str, float]:
    actuals: list[float] = []
    predictions: list[float] = []

    for series in series_map.values():
        for _, predicted_population, actual_population in recursive_baseline_series(
            series,
            anchor_year,
            horizon_years,
        ):
            predictions.append(predicted_population)
            actuals.append(actual_population)

    return calculate_metrics(actuals, predictions)

def build_interval_half_widths(
    errors_by_horizon: dict[int, list[float]],
    max_horizon: int,
) -> dict[str, int]:
    interval_half_widths: dict[str, int] = {}
    last_known_width = 0.0
    last_known_horizon = 1

    for step in range(1, max_horizon + 1):
        errors = sorted(errors_by_horizon.get(step, []))
        if errors:
            index = max(0, min(len(errors) - 1, int(round(0.9 * (len(errors) - 1)))))
            last_known_width = errors[index]
            last_known_horizon = step
        elif last_known_width > 0:
            last_known_width = last_known_width * ((step / last_known_horizon) ** 0.5)

        interval_half_widths[str(step)] = int(round(last_known_width))

    return interval_half_widths


def export_artifact(
    pipeline: Pipeline,
    artifact_path: Path,
    *,
    alpha: float,
    shrink_weight: float,
    selection_metrics: dict[str, Any],
    one_step_metrics_by_split: dict[str, dict[str, float]],
    interval_half_widths: dict[str, int],
    source_csv: Path,
    train_rows: int,
    municipalities: int,
) -> dict[str, Any]:
    preprocessor: ColumnTransformer = pipeline.named_steps["preprocess"]
    scaler: StandardScaler = preprocessor.named_transformers_["num"]
    encoder: OneHotEncoder = preprocessor.named_transformers_["cat"]
    ridge: Ridge = pipeline.named_steps["ridge"]

    coefficients = ridge.coef_.tolist()
    numeric_coefficients = {
        feature_name: float(coefficients[index])
        for index, feature_name in enumerate(NUMERIC_FEATURES)
    }

    categorical_coefficients: dict[str, dict[str, float]] = {}
    offset = len(NUMERIC_FEATURES)
    for feature_name, categories in zip(CATEGORICAL_FEATURES, encoder.categories_, strict=False):
        category_weights: dict[str, float] = {}
        for category in categories:
            category_weights[str(category)] = float(coefficients[offset])
            offset += 1
        categorical_coefficients[feature_name] = category_weights

    artifact = {
        "artifact_version": 1,
        "model_name": FORECAST_MODEL_NAME,
        "trained_at_utc": datetime.now(UTC).isoformat(),
        "source_csv": str(source_csv),
        "history_lags": HISTORY_LAGS,
        "alpha": float(alpha),
        "shrink_weight": float(shrink_weight),
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_means": {
            feature_name: float(value)
            for feature_name, value in zip(NUMERIC_FEATURES, scaler.mean_, strict=False)
        },
        "numeric_scales": {
            feature_name: float(value) if float(value) != 0 else 1.0
            for feature_name, value in zip(NUMERIC_FEATURES, scaler.scale_, strict=False)
        },
        "numeric_coefficients": numeric_coefficients,
        "categorical_coefficients": categorical_coefficients,
        "intercept": float(ridge.intercept_),
        "interval_half_widths": interval_half_widths,
        "metrics": {
            "selection_backtest_2019_2023": selection_metrics,
            "one_step_holdout": one_step_metrics_by_split,
        },
        "training_summary": {
            "train_rows": train_rows,
            "municipalities": municipalities,
        },
    }

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    metrics_path = artifact_path.with_suffix(".metrics.json")
    metrics_path.write_text(
        json.dumps(artifact["metrics"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the production population forecast model")
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=BACKEND_DIR / "data" / "csv" / "data.csv",
    )
    parser.add_argument(
        "--artifact-path",
        type=Path,
        default=BACKEND_DIR / "data" / "models" / FORECAST_ARTIFACT_FILENAME,
    )
    args = parser.parse_args()

    dataset = load_dataset(args.csv_path)
    series_map = build_series_map(dataset)
    supervised = build_supervised_frame(series_map)

    selection_train = supervised[supervised["target_year"] <= 2018]
    if selection_train.empty:
        raise RuntimeError("No training rows available for the selection backtest")

    best_alpha = 5.0
    best_shrink = 0.75
    naive_metrics = baseline_metrics_for_anchor(series_map, anchor_year=2018, horizon_years=5)
    selection_pipeline = fit_pipeline(selection_train, best_alpha)
    best_run, interval_errors = recursive_backtest_for_anchor(
        selection_pipeline,
        series_map,
        anchor_year=2018,
        horizon_years=5,
        shrink_weight=best_shrink,
    )
    best_run["alpha"] = best_alpha
    best_run["shrink_weight"] = best_shrink
    best_run["score"] = (
        best_run["rmse"] / naive_metrics["rmse"]
        + best_run["mae"] / naive_metrics["mae"]
        + best_run["mape"] / naive_metrics["mape"]
    ) / 3.0

    holdout_train = supervised[supervised["target_year"] <= 2019]
    final_pipeline = fit_pipeline(supervised, best_alpha)
    holdout_pipeline = fit_pipeline(holdout_train, best_alpha)

    one_step_holdout = {
        "valid_2020_2021": one_step_metrics(
            holdout_pipeline,
            supervised[(supervised["target_year"] >= 2020) & (supervised["target_year"] <= 2021)],
            best_shrink,
        ),
        "test_2022_2023": one_step_metrics(
            holdout_pipeline,
            supervised[supervised["target_year"] >= 2022],
            best_shrink,
        ),
    }

    interval_half_widths = build_interval_half_widths(interval_errors, max_horizon=15)

    artifact = export_artifact(
        final_pipeline,
        args.artifact_path,
        alpha=best_alpha,
        shrink_weight=best_shrink,
        selection_metrics={
            "best_run": best_run,
            "naive_baseline": naive_metrics,
            "selection_note": "alpha=5.0 and shrink=0.75 selected from the prior recursive search and retrained here on the full dataset",
        },
        one_step_metrics_by_split=one_step_holdout,
        interval_half_widths=interval_half_widths,
        source_csv=args.csv_path,
        train_rows=len(supervised),
        municipalities=len(series_map),
    )

    print(json.dumps(
        {
            "artifact_path": str(args.artifact_path),
            "model_name": artifact["model_name"],
            "alpha": best_alpha,
            "shrink_weight": best_shrink,
            "selection_best_run": best_run,
            "one_step_holdout": one_step_holdout,
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
