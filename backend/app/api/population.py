from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.municipality import Municipality
from app.models.population import PopulationRecord
from app.models.region import Region
from app.schemas.population import (
    PopulationRankingItem,
    PopulationSummary,
    PopulationTimeseries,
    PopulationTimeseriesPoint,
)

router = APIRouter()


@router.get("/timeseries", response_model=list[PopulationTimeseries])
async def population_timeseries(
    municipality_id: list[int] = Query(default=[]),
    region_id: int | None = Query(default=None),
    year_from: int = Query(default=2010),
    year_to: int = Query(default=2023),
    db: AsyncSession = Depends(get_db),
):
    results = []

    if municipality_id:
        muni_ids = municipality_id
    elif region_id:
        region = await db.get(Region, region_id)
        if not region:
            return []

        query = (
            select(PopulationRecord.year, func.sum(PopulationRecord.population))
            .join(Municipality)
            .where(
                Municipality.region_id == region_id,
                PopulationRecord.year >= year_from,
                PopulationRecord.year <= year_to,
            )
            .group_by(PopulationRecord.year)
            .order_by(PopulationRecord.year)
        )
        res = await db.execute(query)
        rows = res.all()
        return [
            PopulationTimeseries(
                municipality_id=region.id,
                municipality_name=region.name,
                data=[
                    PopulationTimeseriesPoint(year=year, population=population)
                    for year, population in rows
                ],
            )
        ]
    else:
        query = (
            select(PopulationRecord.year, func.sum(PopulationRecord.population))
            .where(
                PopulationRecord.year >= year_from,
                PopulationRecord.year <= year_to,
            )
            .group_by(PopulationRecord.year)
            .order_by(PopulationRecord.year)
        )
        res = await db.execute(query)
        rows = res.all()
        return [
            PopulationTimeseries(
                municipality_id=0,
                municipality_name="Россия",
                data=[
                    PopulationTimeseriesPoint(year=year, population=population)
                    for year, population in rows
                ],
            )
        ]

    for mid in muni_ids[:20]:
        muni = await db.get(Municipality, mid)
        if not muni:
            continue
        query = (
            select(PopulationRecord)
            .where(
                PopulationRecord.municipality_id == mid,
                PopulationRecord.year >= year_from,
                PopulationRecord.year <= year_to,
            )
            .order_by(PopulationRecord.year)
        )
        res = await db.execute(query)
        records = res.scalars().all()
        results.append(
            PopulationTimeseries(
                municipality_id=mid,
                municipality_name=muni.name,
                data=[
                    PopulationTimeseriesPoint(year=r.year, population=r.population)
                    for r in records
                ],
            )
        )
    return results


@router.get("/rankings", response_model=list[PopulationRankingItem])
async def population_rankings(
    year_from: int = Query(default=2010),
    year_to: int = Query(default=2022),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=20, le=100),
    region_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    pop_start = (
        select(PopulationRecord.municipality_id, PopulationRecord.population)
        .where(PopulationRecord.year == year_from)
        .subquery()
    )
    pop_end = (
        select(PopulationRecord.municipality_id, PopulationRecord.population)
        .where(PopulationRecord.year == year_to)
        .subquery()
    )

    query = (
        select(
            Municipality.id,
            Municipality.name,
            Region.id.label("region_id"),
            Region.name.label("region_name"),
            pop_start.c.population.label("pop_start"),
            pop_end.c.population.label("pop_end"),
        )
        .join(Region, Municipality.region_id == Region.id)
        .join(pop_start, Municipality.id == pop_start.c.municipality_id)
        .join(pop_end, Municipality.id == pop_end.c.municipality_id)
        .where(pop_start.c.population > 0, pop_end.c.population.isnot(None))
    )

    if region_id:
        query = query.where(Municipality.region_id == region_id)

    change_expr = (
        (pop_end.c.population - pop_start.c.population)
        * 100.0
        / func.nullif(pop_start.c.population, 0)
    )

    if order == "desc":
        query = query.order_by(change_expr.desc().nulls_last())
    else:
        query = query.order_by(change_expr.asc().nulls_last())

    query = query.limit(limit)
    result = await db.execute(query)
    rows = result.all()

    return [
        PopulationRankingItem(
            municipality_id=r[0],
            municipality_name=r[1],
            region_id=r[2],
            region_name=r[3],
            population_start=r[4],
            population_end=r[5],
            change_absolute=(r[5] - r[4]) if r[4] and r[5] else None,
            change_percent=round((r[5] - r[4]) / r[4] * 100, 2) if r[4] and r[5] and r[4] != 0 else None,
        )
        for r in rows
    ]


@router.get("/summary", response_model=PopulationSummary)
async def population_summary(
    year: int = Query(default=2022),
    region_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    query = select(func.sum(PopulationRecord.population), func.count(PopulationRecord.id)).where(
        PopulationRecord.year == year
    )
    if region_id:
        query = query.join(Municipality).where(Municipality.region_id == region_id)

    result = await db.execute(query)
    row = result.one()
    total_pop = row[0] or 0
    total_muni = row[1] or 0

    return PopulationSummary(
        total_population=total_pop,
        total_municipalities=total_muni,
    )
