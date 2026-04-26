from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import settings
from app.models.municipality import Municipality
from app.models.population import PopulationRecord
from app.models.region import Region
from app.services.forecast_features import (
    CATEGORICAL_FEATURES,
    FORECAST_ARTIFACT_FILENAME,
    FORECAST_MODEL_NAME,
    HISTORY_LAGS,
    NUMERIC_FEATURES,
    build_feature_row,
    normalize_municipality_type,
)

ScopeForecastType = Literal["country", "region", "municipality"]

DEFAULT_FORECAST_MODEL_NAME = FORECAST_MODEL_NAME
FALLBACK_LINEAR_MODEL_NAME = "linear_trend_fallback_v1"
FALLBACK_CONSTANT_MODEL_NAME = "constant_baseline_fallback_v1"

_ARTIFACT_CACHE: dict[str, Any] | None = None
_ARTIFACT_CACHE_MTIME: float | None = None
_ARTIFACT_CACHE_PATH: Path | None = None


@dataclass
class ScopeForecastResult:
    scope_type: ScopeForecastType
    scope_id: int | None
    scope_name: str
    model_name: str
    historical: list[dict[str, int]]
    forecast: list[dict[str, int]]
    municipalities_used: int = 1
    municipalities_total: int = 1

    @property
    def anchor_year(self) -> int | None:
        return self.historical[-1]["year"] if self.historical else None

    @property
    def anchor_population(self) -> int | None:
        return self.historical[-1]["population"] if self.historical else None


def _candidate_data_dirs() -> list[Path]:
    backend_dir = Path(__file__).resolve().parents[2]
    return [
        Path(settings.data_dir),
        backend_dir / "data",
        Path("/app/data"),
    ]


def _artifact_path() -> Path | None:
    for data_dir in _candidate_data_dirs():
        candidate = data_dir / "models" / FORECAST_ARTIFACT_FILENAME
        if candidate.is_file():
            return candidate
    return None


def _load_artifact() -> dict[str, Any] | None:
    global _ARTIFACT_CACHE, _ARTIFACT_CACHE_MTIME, _ARTIFACT_CACHE_PATH

    artifact_path = _artifact_path()
    if artifact_path is None:
        _ARTIFACT_CACHE = None
        _ARTIFACT_CACHE_MTIME = None
        _ARTIFACT_CACHE_PATH = None
        return None

    current_mtime = artifact_path.stat().st_mtime
    if (
        _ARTIFACT_CACHE is not None
        and _ARTIFACT_CACHE_PATH == artifact_path
        and _ARTIFACT_CACHE_MTIME == current_mtime
    ):
        return _ARTIFACT_CACHE

    _ARTIFACT_CACHE = json.loads(artifact_path.read_text(encoding="utf-8"))
    _ARTIFACT_CACHE_PATH = artifact_path
    _ARTIFACT_CACHE_MTIME = current_mtime
    return _ARTIFACT_CACHE


def _sanitize_history(historical_data: list[dict[str, Any]]) -> list[dict[str, int]]:
    deduped: dict[int, int] = {}
    for item in historical_data:
        year = item.get("year")
        population = item.get("population")
        if year is None or population is None:
            continue
        deduped[int(year)] = int(population)

    return [
        {"year": year, "population": population}
        for year, population in sorted(deduped.items())
    ]


def _truncate_history(
    historical_data: list[dict[str, Any]],
    anchor_year: int | None,
    *,
    require_exact_anchor: bool = False,
) -> list[dict[str, int]]:
    valid_history = _sanitize_history(historical_data)
    if anchor_year is None:
        return valid_history

    truncated = [item for item in valid_history if item["year"] <= anchor_year]
    if require_exact_anchor and truncated and truncated[-1]["year"] != anchor_year:
        return []
    return truncated


def _score_delta(artifact: dict[str, Any], feature_row: dict[str, Any]) -> float:
    intercept = float(artifact.get("intercept", 0.0))
    means = artifact.get("numeric_means", {})
    scales = artifact.get("numeric_scales", {})
    numeric_coefficients = artifact.get("numeric_coefficients", {})
    categorical_coefficients = artifact.get("categorical_coefficients", {})

    total = intercept

    for feature_name in NUMERIC_FEATURES:
        value = float(feature_row.get(feature_name, 0.0))
        mean_value = float(means.get(feature_name, 0.0))
        scale_value = float(scales.get(feature_name, 1.0)) or 1.0
        coefficient = float(numeric_coefficients.get(feature_name, 0.0))
        total += ((value - mean_value) / scale_value) * coefficient

    for feature_name in CATEGORICAL_FEATURES:
        category = str(feature_row.get(feature_name, ""))
        total += float(categorical_coefficients.get(feature_name, {}).get(category, 0.0))

    return total


def _interval_half_width(artifact: dict[str, Any], horizon_step: int) -> int:
    interval_map = artifact.get("interval_half_widths", {})
    if str(horizon_step) in interval_map:
        return int(interval_map[str(horizon_step)])

    numeric_keys = sorted(int(key) for key in interval_map.keys())
    if not numeric_keys:
        return 0

    last_key = numeric_keys[-1]
    last_width = int(interval_map[str(last_key)])
    return int(round(last_width * sqrt(horizon_step / last_key)))


def _artifact_forecast(
    historical_data: list[dict[str, int]],
    municipality_meta: dict[str, Any],
    horizon_years: int,
    artifact: dict[str, Any],
) -> list[dict[str, int]]:
    history_values = [float(item["population"]) for item in historical_data]
    start_year = int(historical_data[0]["year"])
    last_year = int(historical_data[-1]["year"])
    shrink_weight = float(artifact.get("shrink_weight", 1.0))

    region = municipality_meta.get("region") or ""
    municipality = municipality_meta.get("municipality") or ""
    mun_type = municipality_meta.get("mun_type") or ""
    oktmo = municipality_meta.get("oktmo") or ""
    area_sq_km = municipality_meta.get("area_sq_km")

    results: list[dict[str, int]] = []
    for step in range(1, horizon_years + 1):
        target_year = last_year + step
        feature_row = build_feature_row(
            history_values,
            target_year=target_year,
            start_year=start_year,
            region=str(region),
            municipality=str(municipality),
            mun_type=normalize_municipality_type(str(mun_type)),
            oktmo=str(oktmo),
            area_sq_km=float(area_sq_km) if area_sq_km is not None else None,
        )
        predicted_delta = _score_delta(artifact, feature_row)
        predicted_population = max(0, int(round(history_values[-1] + shrink_weight * predicted_delta)))
        half_width = _interval_half_width(artifact, step)
        history_values.append(float(predicted_population))

        results.append(
            {
                "year": target_year,
                "predicted_population": predicted_population,
                "confidence_lower": max(0, predicted_population - half_width),
                "confidence_upper": predicted_population + half_width,
            }
        )

    return results


def _constant_fallback(
    historical_data: list[dict[str, int]],
    horizon_years: int,
) -> list[dict[str, int]]:
    last_year = historical_data[-1]["year"]
    last_population = historical_data[-1]["population"]
    results: list[dict[str, int]] = []

    for step in range(1, horizon_years + 1):
        half_width = max(100, int(round(last_population * 0.02 * sqrt(step))))
        results.append(
            {
                "year": last_year + step,
                "predicted_population": last_population,
                "confidence_lower": max(0, last_population - half_width),
                "confidence_upper": last_population + half_width,
            }
        )

    return results


def _linear_trend_fallback(
    historical_data: list[dict[str, int]],
    horizon_years: int,
) -> list[dict[str, int]]:
    years = [float(item["year"]) for item in historical_data]
    populations = [float(item["population"]) for item in historical_data]
    n = len(years)

    if n < 2:
        return _constant_fallback(historical_data, horizon_years)

    mean_x = sum(years) / n
    mean_y = sum(populations) / n
    ss_xx = sum((year - mean_x) ** 2 for year in years)
    if ss_xx == 0:
        return _constant_fallback(historical_data, horizon_years)

    ss_xy = sum((year - mean_x) * (population - mean_y) for year, population in zip(years, populations, strict=False))
    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x

    residuals = [population - (intercept + slope * year) for year, population in zip(years, populations, strict=False)]
    residual_variance = sum(residual ** 2 for residual in residuals) / max(n - 2, 1)
    standard_error = residual_variance ** 0.5

    last_year = int(years[-1])
    results: list[dict[str, int]] = []

    for step in range(1, horizon_years + 1):
        forecast_year = last_year + step
        predicted = intercept + slope * forecast_year
        distance = abs(forecast_year - mean_x)
        margin = 1.96 * standard_error * sqrt(1 + 1 / n + distance**2 / ss_xx)
        predicted_population = max(0, int(round(predicted)))
        results.append(
            {
                "year": forecast_year,
                "predicted_population": predicted_population,
                "confidence_lower": max(0, int(round(predicted_population - margin))),
                "confidence_upper": max(0, int(round(predicted_population + margin))),
            }
        )

    return results


def generate_forecast(
    historical_data: list[dict[str, Any]],
    municipality_meta: dict[str, Any],
    horizon_years: int = 10,
) -> dict[str, Any]:
    valid_history = _sanitize_history(historical_data)
    if not valid_history:
        return {"model_name": FALLBACK_CONSTANT_MODEL_NAME, "forecast": []}

    artifact = _load_artifact()
    if artifact is not None and len(valid_history) >= HISTORY_LAGS:
        return {
            "model_name": str(artifact.get("model_name", FORECAST_MODEL_NAME)),
            "forecast": _artifact_forecast(valid_history, municipality_meta, horizon_years, artifact),
        }

    if len(valid_history) == 1:
        return {
            "model_name": FALLBACK_CONSTANT_MODEL_NAME,
            "forecast": _constant_fallback(valid_history, horizon_years),
        }

    return {
        "model_name": FALLBACK_LINEAR_MODEL_NAME,
        "forecast": _linear_trend_fallback(valid_history, horizon_years),
    }


async def get_scope_forecast(
    db: AsyncSession,
    scope_type: ScopeForecastType,
    scope_id: int | None,
    horizon_years: int = 10,
    anchor_year: int | None = None,
) -> ScopeForecastResult | None:
    if scope_type == "municipality":
        if scope_id is None:
            return None

        municipality_result = await db.execute(
            select(Municipality)
            .options(joinedload(Municipality.region))
            .where(Municipality.id == scope_id)
        )
        municipality = municipality_result.scalar_one_or_none()
        if not municipality:
            return None

        historical_result = await db.execute(
            select(PopulationRecord.year, PopulationRecord.population)
            .where(PopulationRecord.municipality_id == scope_id)
            .order_by(PopulationRecord.year)
        )
        historical_data = [
            {"year": year, "population": population}
            for year, population in historical_result.all()
        ]
        valid_history = _truncate_history(historical_data, anchor_year)
        if not valid_history:
            return None

        forecast_result = generate_forecast(
            valid_history,
            {
                "region": municipality.region.name if municipality.region else "",
                "municipality": municipality.name,
                "mun_type": municipality.municipality_type,
                "oktmo": municipality.oktmo_code or "",
                "area_sq_km": municipality.area_sq_km,
            },
            horizon_years,
        )
        return ScopeForecastResult(
            scope_type="municipality",
            scope_id=municipality.id,
            scope_name=municipality.name,
            model_name=forecast_result["model_name"],
            historical=valid_history,
            forecast=forecast_result["forecast"],
            municipalities_used=1,
            municipalities_total=1,
        )

    if scope_type == "region":
        if scope_id is None:
            return None
        scope_name = (await db.get(Region, scope_id))
        if not scope_name:
            return None
        municipality_query = (
            select(Municipality)
            .options(joinedload(Municipality.region))
            .where(Municipality.region_id == scope_id)
            .order_by(Municipality.id)
        )
        scope_label = scope_name.name
    else:
        municipality_query = select(Municipality).options(joinedload(Municipality.region)).order_by(Municipality.id)
        scope_label = "Россия"

    municipality_result = await db.execute(municipality_query)
    municipalities = municipality_result.scalars().all()
    if not municipalities:
        return None

    municipality_ids = [municipality.id for municipality in municipalities]
    population_rows = await db.execute(
        select(
            PopulationRecord.municipality_id,
            PopulationRecord.year,
            PopulationRecord.population,
        )
        .where(PopulationRecord.municipality_id.in_(municipality_ids))
        .order_by(PopulationRecord.municipality_id, PopulationRecord.year)
    )

    history_by_municipality: dict[int, list[dict[str, int | None]]] = defaultdict(list)
    for municipality_id, year, population in population_rows.all():
        history_by_municipality[municipality_id].append({"year": year, "population": population})

    history_totals: dict[int, int] = defaultdict(int)
    forecast_totals: dict[int, dict[str, int]] = {}
    model_names: Counter[str] = Counter()
    municipalities_used = 0

    for municipality in municipalities:
        valid_history = _truncate_history(
            history_by_municipality.get(municipality.id, []),
            anchor_year,
            require_exact_anchor=anchor_year is not None,
        )
        if not valid_history:
            continue

        forecast_result = generate_forecast(
            valid_history,
            {
                "region": municipality.region.name if municipality.region else "",
                "municipality": municipality.name,
                "mun_type": municipality.municipality_type,
                "oktmo": municipality.oktmo_code or "",
                "area_sq_km": municipality.area_sq_km,
            },
            horizon_years,
        )
        if not forecast_result["forecast"]:
            continue

        municipalities_used += 1
        model_names[forecast_result["model_name"]] += 1

        for point in valid_history:
            history_totals[point["year"]] += point["population"]

        for point in forecast_result["forecast"]:
            year = point["year"]
            if year not in forecast_totals:
                forecast_totals[year] = {
                    "year": year,
                    "predicted_population": 0,
                    "confidence_lower": 0,
                    "confidence_upper": 0,
                }
            forecast_totals[year]["predicted_population"] += int(point["predicted_population"])
            forecast_totals[year]["confidence_lower"] += int(point["confidence_lower"])
            forecast_totals[year]["confidence_upper"] += int(point["confidence_upper"])

    if not history_totals or not forecast_totals:
        return None

    dominant_model = model_names.most_common(1)[0][0] if model_names else DEFAULT_FORECAST_MODEL_NAME
    historical = [
        {"year": year, "population": population}
        for year, population in sorted(history_totals.items())
    ]
    forecast = [forecast_totals[year] for year in sorted(forecast_totals)]

    return ScopeForecastResult(
        scope_type=scope_type,
        scope_id=scope_id,
        scope_name=scope_label,
        model_name=dominant_model,
        historical=historical,
        forecast=forecast,
        municipalities_used=municipalities_used,
        municipalities_total=len(municipalities),
    )


def get_forecast_snapshot(
    forecast_result: ScopeForecastResult,
    target_year: int | None = None,
) -> dict[str, Any] | None:
    if not forecast_result.historical or not forecast_result.forecast:
        return None

    point = None
    if target_year is not None:
        point = next((item for item in forecast_result.forecast if item["year"] == target_year), None)
    if point is None:
        point = forecast_result.forecast[-1]

    base_point = forecast_result.historical[-1]
    base_population = base_point["population"]
    predicted_population = point["predicted_population"]
    absolute_change = predicted_population - base_population
    percent_change = ((absolute_change / base_population) * 100.0) if base_population else None

    return {
        "model_name": forecast_result.model_name,
        "anchor_year": base_point["year"],
        "anchor_population": base_population,
        "target_year": point["year"],
        "predicted_population": predicted_population,
        "confidence_lower": point["confidence_lower"],
        "confidence_upper": point["confidence_upper"],
        "absolute_change": absolute_change,
        "percent_change": percent_change,
        "municipalities_used": forecast_result.municipalities_used,
        "municipalities_total": forecast_result.municipalities_total,
    }
