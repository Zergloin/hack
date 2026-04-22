from pydantic import BaseModel


class RegionOut(BaseModel):
    id: int
    code: str
    name: str
    federal_district: str | None = None

    model_config = {"from_attributes": True}


class MunicipalityOut(BaseModel):
    id: int
    oktmo_code: str | None = None
    name: str
    municipality_type: str
    region_id: int
    region_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    area_sq_km: float | None = None

    model_config = {"from_attributes": True}
