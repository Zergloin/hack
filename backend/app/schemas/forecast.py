from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    municipality_id: int
    horizon_years: int = Field(ge=5, le=15, default=10)


class ForecastPoint(BaseModel):
    year: int
    predicted_population: int
    confidence_lower: int | None = None
    confidence_upper: int | None = None


class ForecastResponse(BaseModel):
    municipality_id: int
    municipality_name: str
    model_name: str
    historical: list[dict]
    forecast: list[ForecastPoint]
