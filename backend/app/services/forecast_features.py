from __future__ import annotations

from typing import Any

FORECAST_MODEL_NAME = "population_ridge_recursive_v1"
FORECAST_ARTIFACT_FILENAME = "population_forecast_ridge_v1.json"
HISTORY_LAGS = 7

NUMERIC_FEATURES = [
    "year",
    "year_index",
    "area_sq_km",
    "pop_lag_1",
    "pop_lag_2",
    "pop_lag_3",
    "pop_lag_4",
    "pop_lag_5",
    "pop_lag_6",
    "pop_lag_7",
    "pop_delta_1",
    "pop_delta_2",
    "pop_delta_3",
    "pop_delta_4",
    "pop_pct_1",
    "pop_pct_2",
    "pop_pct_3",
    "pop_roll_mean_3",
    "pop_roll_mean_5",
    "pop_roll_mean_7",
    "pop_roll_std_3",
    "pop_roll_std_5",
]

CATEGORICAL_FEATURES = [
    "region",
    "municipality",
    "mun_type",
    "oktmo",
]

MUN_TYPE_MAP = {
    "Городской округ": "городской_округ",
    "Муниципальный район": "муниципальный_район",
    "Муниципальный округ": "муниципальный_округ",
    "Административный район": "административный_район",
    "Город федерального значения": "город_фед_значения",
}


def normalize_municipality_type(value: str | None) -> str:
    if not value:
        return ""
    cleaned = value.strip()
    return MUN_TYPE_MAP.get(cleaned, cleaned)


def _safe_pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current - previous) / previous


def _rolling_mean(values: list[float]) -> float:
    return float(sum(values) / len(values))


def _rolling_std(values: list[float]) -> float:
    mean_value = _rolling_mean(values)
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return float(variance ** 0.5)


def build_numeric_feature_row(
    history_values: list[float],
    *,
    target_year: int,
    start_year: int,
    area_sq_km: float | None,
) -> dict[str, float]:
    if len(history_values) < HISTORY_LAGS:
        raise ValueError(f"Expected at least {HISTORY_LAGS} history points")

    history = [float(value) for value in history_values]
    features: dict[str, float] = {
        "year": float(target_year),
        "year_index": float(target_year - start_year),
        "area_sq_km": float(area_sq_km or 0.0),
    }

    for lag in range(1, HISTORY_LAGS + 1):
        features[f"pop_lag_{lag}"] = history[-lag]

    for lag in range(1, 5):
        current = history[-lag]
        previous = history[-lag - 1]
        features[f"pop_delta_{lag}"] = current - previous

    for lag in range(1, 4):
        current = history[-lag]
        previous = history[-lag - 1]
        features[f"pop_pct_{lag}"] = _safe_pct_change(current, previous)

    for window in (3, 5, 7):
        tail = history[-window:]
        features[f"pop_roll_mean_{window}"] = _rolling_mean(tail)

    for window in (3, 5):
        tail = history[-window:]
        features[f"pop_roll_std_{window}"] = _rolling_std(tail)

    return features


def build_feature_row(
    history_values: list[float],
    *,
    target_year: int,
    start_year: int,
    region: str | None,
    municipality: str | None,
    mun_type: str | None,
    oktmo: str | None,
    area_sq_km: float | None,
) -> dict[str, Any]:
    row: dict[str, Any] = build_numeric_feature_row(
        history_values,
        target_year=target_year,
        start_year=start_year,
        area_sq_km=area_sq_km,
    )
    row["region"] = (region or "").strip()
    row["municipality"] = (municipality or "").strip()
    row["mun_type"] = normalize_municipality_type(mun_type)
    row["oktmo"] = (oktmo or "").strip()
    return row
