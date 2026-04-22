from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.municipality import Municipality
from app.models.region import Region
from app.schemas.municipality import MunicipalityOut, RegionOut

router = APIRouter()


@router.get("/regions", response_model=list[RegionOut])
async def list_regions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Region).order_by(Region.name))
    return result.scalars().all()


@router.get("/regions/{region_id}/municipalities", response_model=list[MunicipalityOut])
async def list_municipalities_by_region(
    region_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Municipality)
        .options(joinedload(Municipality.region))
        .where(Municipality.region_id == region_id)
        .order_by(Municipality.name)
    )
    municipalities = result.scalars().all()
    return [
        MunicipalityOut(
            id=m.id,
            oktmo_code=m.oktmo_code,
            name=m.name,
            municipality_type=m.municipality_type,
            region_id=m.region_id,
            region_name=m.region.name if m.region else None,
            latitude=m.latitude,
            longitude=m.longitude,
            area_sq_km=m.area_sq_km,
        )
        for m in municipalities
    ]


@router.get("/municipalities", response_model=list[MunicipalityOut])
async def search_municipalities(
    search: str = Query(default="", description="Search by name"),
    municipality_type: str = Query(default="", alias="type"),
    region_id: int | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
):
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
    return [
        MunicipalityOut(
            id=m.id,
            oktmo_code=m.oktmo_code,
            name=m.name,
            municipality_type=m.municipality_type,
            region_id=m.region_id,
            region_name=m.region.name if m.region else None,
            latitude=m.latitude,
            longitude=m.longitude,
            area_sq_km=m.area_sq_km,
        )
        for m in municipalities
    ]
