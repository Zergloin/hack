import json
import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.municipality import Municipality
from app.models.population import PopulationRecord
from app.models.region import Region

router = APIRouter()

# Mapping from GeoJSON names to DB region names (for fuzzy matching)
NAME_ALIASES = {
    "Бурятия": "Республика Бурятия",
    "Алтай": "Республика Алтай",
    "Тыва": "Республика Тыва",
    "Хакасия": "Республика Хакасия",
    "Адыгея": "Республика Адыгея",
    "Башкортостан": "Республика Башкортостан",
    "Дагестан": "Республика Дагестан",
    "Ингушетия": "Республика Ингушетия",
    "Калмыкия": "Республика Калмыкия",
    "Карелия": "Республика Карелия",
    "Коми": "Республика Коми",
    "Марий Эл": "Республика Марий Эл",
    "Мордовия": "Республика Мордовия",
    "Татарстан": "Республика Татарстан",
    "Удмуртия": "Удмуртская Республика",
    "Чечня": "Чеченская Республика",
    "Чувашия": "Чувашская Республика",
    "Саха (Якутия)": "Республика Саха (Якутия)",
    "Карачаево-Черкесская республика": "Карачаево-Черкесская Республика",
    "Кабардино-Балкарская республика": "Кабардино-Балкарская Республика",
    "Северная Осетия - Алания": "Республика Северная Осетия — Алания",
    "Ханты-Мансийский автономный округ - Югра": "Ханты-Мансийский АО — Югра",
    "Ямало-Ненецкий автономный округ": "Ямало-Ненецкий АО",
    "Чукотский автономный округ": "Чукотский автономный округ",
    "Еврейская автономная область": "Еврейская автономная область",
}


def _match_region(geojson_name: str, db_regions: dict[str, dict]) -> dict | None:
    """Match GeoJSON feature name to DB region."""
    # Direct match
    if geojson_name in db_regions:
        return db_regions[geojson_name]
    # Alias match
    alias = NAME_ALIASES.get(geojson_name)
    if alias and alias in db_regions:
        return db_regions[alias]
    # Partial match
    for db_name, data in db_regions.items():
        if geojson_name.lower() in db_name.lower() or db_name.lower() in geojson_name.lower():
            return data
    return None


@router.get("/geojson")
async def get_geojson(
    level: str = Query(default="region", pattern="^(region|municipality)$"),
    region_id: int | None = Query(default=None),
    year: int = Query(default=2022),
    db: AsyncSession = Depends(get_db),
):
    geo_dir = os.path.join(settings.data_dir, "geo")

    if level == "region":
        geo_path = os.path.join(geo_dir, "regions.geojson")
    else:
        geo_path = os.path.join(geo_dir, "municipalities.geojson")

    if not os.path.exists(geo_path):
        return {"type": "FeatureCollection", "features": []}

    with open(geo_path, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    if level == "region":
        query = select(Region.id, Region.name)
        result = await db.execute(query)
        db_regions = {r[1]: {"id": r[0], "name": r[1]} for r in result.all()}

        # Aggregate population by region
        pop_query = (
            select(Municipality.region_id, func.sum(PopulationRecord.population))
            .join(Municipality)
            .where(PopulationRecord.year == year)
            .group_by(Municipality.region_id)
        )
        pop_result = await db.execute(pop_query)
        region_pops = {row[0]: row[1] or 0 for row in pop_result.all()}

        matched = 0
        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            geojson_name = props.get("name", "")
            region = _match_region(geojson_name, db_regions)
            if region:
                props["db_id"] = region["id"]
                props["db_name"] = region["name"]
                props["population"] = region_pops.get(region["id"], 0)
                matched += 1
            else:
                props["population"] = 0

    return geojson


@router.get("/density")
async def get_density_data(
    year: int = Query(default=2022),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            Region.id,
            Region.code,
            Region.name,
            func.sum(PopulationRecord.population),
        )
        .select_from(PopulationRecord)
        .join(Municipality, PopulationRecord.municipality_id == Municipality.id)
        .join(Region, Municipality.region_id == Region.id)
        .where(PopulationRecord.year == year)
        .group_by(Region.id, Region.code, Region.name)
    )
    result = await db.execute(query)
    return [
        {"id": row[0], "code": row[1], "name": row[2], "population": row[3] or 0}
        for row in result.all()
    ]
