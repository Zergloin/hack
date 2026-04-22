from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.forecast import Forecast
from app.models.municipality import Municipality
from app.models.population import PopulationRecord
from app.schemas.forecast import ForecastPoint, ForecastRequest, ForecastResponse
from app.services.forecast_service import generate_forecast

router = APIRouter()


@router.post("/predict", response_model=ForecastResponse)
async def predict(
    request: ForecastRequest,
    db: AsyncSession = Depends(get_db),
):
    muni = await db.get(Municipality, request.municipality_id)
    if not muni:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Municipality not found")

    hist_query = (
        select(PopulationRecord)
        .where(PopulationRecord.municipality_id == request.municipality_id)
        .order_by(PopulationRecord.year)
    )
    hist_result = await db.execute(hist_query)
    historical = hist_result.scalars().all()

    historical_data = [{"year": r.year, "population": r.population} for r in historical]

    forecast_data = generate_forecast(historical_data, request.horizon_years)

    await db.execute(
        delete(Forecast).where(
            Forecast.municipality_id == request.municipality_id,
            Forecast.model_name == "linear_regression",
        )
    )

    for point in forecast_data:
        f = Forecast(
            municipality_id=request.municipality_id,
            forecast_year=point["year"],
            predicted_population=point["predicted_population"],
            confidence_lower=point.get("confidence_lower"),
            confidence_upper=point.get("confidence_upper"),
            model_name="linear_regression",
        )
        db.add(f)
    await db.commit()

    return ForecastResponse(
        municipality_id=request.municipality_id,
        municipality_name=muni.name,
        model_name="linear_regression",
        historical=historical_data,
        forecast=[ForecastPoint(**p) for p in forecast_data],
    )


@router.get("/{municipality_id}", response_model=list[ForecastPoint])
async def get_forecasts(
    municipality_id: int,
    model_name: str = Query(default="linear_regression"),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Forecast)
        .where(
            Forecast.municipality_id == municipality_id,
            Forecast.model_name == model_name,
        )
        .order_by(Forecast.forecast_year)
    )
    result = await db.execute(query)
    forecasts = result.scalars().all()
    return [
        ForecastPoint(
            year=f.forecast_year,
            predicted_population=f.predicted_population,
            confidence_lower=f.confidence_lower,
            confidence_upper=f.confidence_upper,
        )
        for f in forecasts
    ]
