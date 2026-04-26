from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.forecast import Forecast
from app.schemas.forecast import ForecastPoint, ForecastRequest, ForecastResponse
from app.services.forecast_service import DEFAULT_FORECAST_MODEL_NAME, get_scope_forecast

router = APIRouter()


@router.post("/predict", response_model=ForecastResponse)
async def predict(
    request: ForecastRequest,
    db: AsyncSession = Depends(get_db),
):
    forecast_result = await get_scope_forecast(
        db,
        "municipality",
        request.municipality_id,
        request.horizon_years,
    )
    if not forecast_result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Municipality not found")
    model_name = forecast_result.model_name
    forecast_data = forecast_result.forecast

    await db.execute(
        delete(Forecast).where(
            Forecast.municipality_id == request.municipality_id,
            Forecast.model_name == model_name,
        )
    )

    for point in forecast_data:
        f = Forecast(
            municipality_id=request.municipality_id,
            forecast_year=point["year"],
            predicted_population=point["predicted_population"],
            confidence_lower=point.get("confidence_lower"),
            confidence_upper=point.get("confidence_upper"),
            model_name=model_name,
        )
        db.add(f)
    await db.commit()

    return ForecastResponse(
        municipality_id=request.municipality_id,
        municipality_name=forecast_result.scope_name,
        model_name=model_name,
        historical=forecast_result.historical,
        forecast=[ForecastPoint(**p) for p in forecast_data],
    )


@router.get("/{municipality_id}", response_model=list[ForecastPoint])
async def get_forecasts(
    municipality_id: int,
    model_name: str = Query(default=DEFAULT_FORECAST_MODEL_NAME),
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
