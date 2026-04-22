"""
Forecast service — wraps ML model inference.
The user will replace the linear regression stub with their own model.
"""

import numpy as np


def generate_forecast(
    historical_data: list[dict],
    horizon_years: int = 10,
) -> list[dict]:
    """
    Generate population forecast using linear regression stub.

    Args:
        historical_data: list of {"year": int, "population": int}
        horizon_years: number of years to forecast (5-15)

    Returns:
        list of {"year", "predicted_population", "confidence_lower", "confidence_upper"}
    """
    if not historical_data:
        return []

    valid = [d for d in historical_data if d.get("population") is not None]
    if len(valid) < 2:
        return []

    years = np.array([d["year"] for d in valid], dtype=float)
    pops = np.array([d["population"] for d in valid], dtype=float)

    # Simple linear regression: y = a + b*x
    n = len(years)
    mean_x = np.mean(years)
    mean_y = np.mean(pops)
    ss_xx = np.sum((years - mean_x) ** 2)
    ss_xy = np.sum((years - mean_x) * (pops - mean_y))

    if ss_xx == 0:
        return []

    b = ss_xy / ss_xx
    a = mean_y - b * mean_x

    # Standard error for prediction interval
    residuals = pops - (a + b * years)
    se = np.sqrt(np.sum(residuals**2) / max(n - 2, 1))

    last_year = int(max(years))
    forecast_years = list(range(last_year + 1, last_year + 1 + horizon_years))

    results = []
    for fy in forecast_years:
        pred = a + b * fy
        # Prediction interval widens with distance from data
        dist = abs(fy - mean_x)
        margin = 1.96 * se * np.sqrt(1 + 1 / n + dist**2 / ss_xx)

        predicted = max(0, int(round(pred)))
        lower = max(0, int(round(pred - margin)))
        upper = max(0, int(round(pred + margin)))

        results.append(
            {
                "year": fy,
                "predicted_population": predicted,
                "confidence_lower": lower,
                "confidence_upper": upper,
            }
        )

    return results
