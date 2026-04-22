"""
ML Model interface for population forecasting.
Replace this stub with your own model implementation.

Interface:
    predict(historical_data, horizon_years) -> list[dict]

Each dict in the result should have:
    - year: int
    - predicted_population: int
    - confidence_lower: int (optional)
    - confidence_upper: int (optional)
"""

import numpy as np


def predict(historical_data: list[dict], horizon_years: int = 10) -> list[dict]:
    """
    Predict future population based on historical data.

    Args:
        historical_data: list of {"year": int, "population": int}
        horizon_years: number of years to forecast

    Returns:
        list of forecast points
    """
    # This is a simple linear regression stub.
    # Replace with your trained model.
    from app.services.forecast_service import generate_forecast
    return generate_forecast(historical_data, horizon_years)
