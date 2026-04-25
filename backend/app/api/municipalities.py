from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.municipality import Municipality
from app.models.population import PopulationRecord
from app.models.region import Region
from app.schemas.municipality import MunicipalityOut, RegionOut

router = APIRouter()


def _to_municipality_out(municipality: Municipality, population: int | None = None) -> MunicipalityOut:
    return MunicipalityOut(
        id=municipality.id,
        oktmo_code=municipality.oktmo_code,
        name=municipality.name,
        municipality_type=municipality.municipality_type,
        region_id=municipality.region_id,
        region_name=municipality.region.name if municipality.region else None,
        latitude=municipality.latitude,
        longitude=municipality.longitude,
        area_sq_km=municipality.area_sq_km,
        population=population,
    )


@router.get("/regions", response_model=list[RegionOut])
async def list_regions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Region).order_by(Region.name))
    return result.scalars().all()


@router.get("/regions/{region_id}/municipalities", response_model=list[MunicipalityOut])
async def list_municipalities_by_region(
    region_id: int,
    year: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    if year is None:
        result = await db.execute(
            select(Municipality)
            .options(joinedload(Municipality.region))
            .where(Municipality.region_id == region_id)
            .order_by(Municipality.name)
        )
        municipalities = result.scalars().all()
        return [_to_municipality_out(m) for m in municipalities]

    population_subquery = (
        select(
            PopulationRecord.municipality_id.label("municipality_id"),
            PopulationRecord.population.label("population"),
        )
        .where(PopulationRecord.year == year)
        .subquery()
    )

    result = await db.execute(
        select(Municipality, population_subquery.c.population)
        .options(joinedload(Municipality.region))
        .outerjoin(population_subquery, Municipality.id == population_subquery.c.municipality_id)
        .where(Municipality.region_id == region_id)
        .order_by(population_subquery.c.population.desc().nulls_last(), Municipality.name)
    )
    return [_to_municipality_out(municipality, population) for municipality, population in result.all()]


@router.get("/municipalities", response_model=list[MunicipalityOut])
async def search_municipalities(
    search: str = Query(default="", description="Search by name"),
    municipality_type: str = Query(default="", alias="type"),
    region_id: int | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    year: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    if year is None:
        query = select(Municipality).options(joinedload(Municipality.region))
        if search:
            query = query.where(Municipality.name.ilike(f"%{search}%"))
        if municipality_type:
            query = query.where(Municipality.municipality_type == municipality_type)
        if region_id:
            query = query.where(Municipality.region_id == region_id)
        query = query.order_by(Municipality.name).limit(limit)
        result = await db.execute(query)
        municipalities = result.scalars().all()
        return [_to_municipality_out(m) for m in municipalities]

    population_subquery = (
        select(
            PopulationRecord.municipality_id.label("municipality_id"),
            PopulationRecord.population.label("population"),
        )
        .where(PopulationRecord.year == year)
        .subquery()
    )

    query = (
        select(Municipality, population_subquery.c.population)
        .options(joinedload(Municipality.region))
        .outerjoin(population_subquery, Municipality.id == population_subquery.c.municipality_id)
    )
    if search:
        query = query.where(Municipality.name.ilike(f"%{search}%"))
    if municipality_type:
        query = query.where(Municipality.municipality_type == municipality_type)
    if region_id:
        query = query.where(Municipality.region_id == region_id)
    query = query.order_by(population_subquery.c.population.desc().nulls_last(), Municipality.name).limit(limit)
    result = await db.execute(query)
    return [_to_municipality_out(municipality, population) for municipality, population in result.all()]
