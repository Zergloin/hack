from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.demographics import DemographicIndicator
from app.models.municipality import Municipality
from app.schemas.demographics import (
    DemographicsSummary,
    DemographicsTimeseries,
    DemographicsTimeseriesPoint,
)

router = APIRouter()


@router.get("/timeseries", response_model=list[DemographicsTimeseries])
async def demographics_timeseries(
    municipality_id: list[int] = Query(default=[]),
    year_from: int = Query(default=2010),
    year_to: int = Query(default=2023),
    db: AsyncSession = Depends(get_db),
):
    results = []
    for mid in municipality_id[:20]:
        muni = await db.get(Municipality, mid)
        if not muni:
            continue
        query = (
            select(DemographicIndicator)
            .where(
                DemographicIndicator.municipality_id == mid,
                DemographicIndicator.year >= year_from,
                DemographicIndicator.year <= year_to,
            )
            .order_by(DemographicIndicator.year)
        )
        res = await db.execute(query)
        records = res.scalars().all()
        results.append(
            DemographicsTimeseries(
                municipality_id=mid,
                municipality_name=muni.name,
                data=[
                    DemographicsTimeseriesPoint(
                        year=r.year,
                        births=r.births,
                        deaths=r.deaths,
                        natural_growth=r.natural_growth,
                        net_migration=r.net_migration,
                        birth_rate=r.birth_rate,
                        death_rate=r.death_rate,
                        natural_growth_rate=r.natural_growth_rate,
                        net_migration_rate=r.net_migration_rate,
                    )
                    for r in records
                ],
            )
        )
    return results


@router.get("/summary", response_model=DemographicsSummary)
async def demographics_summary(
    year: int = Query(default=2022),
    region_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    query = select(
        func.sum(DemographicIndicator.births),
        func.sum(DemographicIndicator.deaths),
        func.sum(DemographicIndicator.natural_growth),
        func.sum(DemographicIndicator.net_migration),
        func.avg(DemographicIndicator.birth_rate),
        func.avg(DemographicIndicator.death_rate),
        func.avg(DemographicIndicator.natural_growth_rate),
        func.avg(DemographicIndicator.net_migration_rate),
    ).where(DemographicIndicator.year == year)

    if region_id:
        query = query.join(Municipality).where(Municipality.region_id == region_id)

    result = await db.execute(query)
    row = result.one()

    return DemographicsSummary(
        total_births=row[0],
        total_deaths=row[1],
        total_natural_growth=row[2],
        total_net_migration=row[3],
        avg_birth_rate=round(row[4], 2) if row[4] else None,
        avg_death_rate=round(row[5], 2) if row[5] else None,
        avg_natural_growth_rate=round(row[6], 2) if row[6] else None,
        avg_net_migration_rate=round(row[7], 2) if row[7] else None,
    )
