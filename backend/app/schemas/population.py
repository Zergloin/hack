from pydantic import BaseModel


class PopulationTimeseriesPoint(BaseModel):
    year: int
    population: int | None = None


class PopulationTimeseries(BaseModel):
    municipality_id: int
    municipality_name: str
    data: list[PopulationTimeseriesPoint]


class PopulationRankingItem(BaseModel):
    municipality_id: int
    municipality_name: str
    region_id: int
    region_name: str
    population_start: int | None = None
    population_end: int | None = None
    change_absolute: int | None = None
    change_percent: float | None = None


class PopulationSummary(BaseModel):
    total_population: int
    total_municipalities: int
    avg_growth_percent: float | None = None
    max_growth_municipality: str | None = None
    max_decline_municipality: str | None = None
