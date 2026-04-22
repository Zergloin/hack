from pydantic import BaseModel


class DemographicsTimeseriesPoint(BaseModel):
    year: int
    births: int | None = None
    deaths: int | None = None
    natural_growth: int | None = None
    net_migration: int | None = None
    birth_rate: float | None = None
    death_rate: float | None = None
    natural_growth_rate: float | None = None
    net_migration_rate: float | None = None


class DemographicsTimeseries(BaseModel):
    municipality_id: int
    municipality_name: str
    data: list[DemographicsTimeseriesPoint]


class DemographicsSummary(BaseModel):
    total_births: int | None = None
    total_deaths: int | None = None
    total_natural_growth: int | None = None
    total_net_migration: int | None = None
    avg_birth_rate: float | None = None
    avg_death_rate: float | None = None
    avg_natural_growth_rate: float | None = None
    avg_net_migration_rate: float | None = None
