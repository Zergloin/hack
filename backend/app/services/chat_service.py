"""
Chat service — data-first assistant for demographic queries.
Answers basic questions by resolving the entity/metric, querying the database,
and optionally asking the LLM to phrase the result.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Literal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.demographics import DemographicIndicator
from app.models.municipality import Municipality
from app.models.population import PopulationRecord
from app.models.region import Region
from app.services.forecast_service import get_forecast_snapshot, get_scope_forecast
from app.services.llm import get_llm

ScopeType = Literal["country", "region", "municipality"]
IntentType = Literal["metric_value", "trend", "ranking", "compare", "summary", "forecast", "unsupported"]
RankingDimension = Literal["regions", "municipalities"]

YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
LLM_RETRY_ATTEMPTS = 3
LLM_RETRY_BASE_DELAY = 0.5
STREAM_CHUNK_SIZE = 120
MAX_THREAD_CONTEXTS = 100

THREAD_CONTEXTS: dict[str, "QueryPlan"] = {}

REGION_STOPWORDS = {
    "республика",
    "область",
    "край",
    "автономная",
    "автономный",
    "округ",
    "город",
    "федерального",
    "значения",
    "ао",
}

MUNICIPALITY_STOPWORDS = {
    "городской",
    "муниципальный",
    "административный",
    "округ",
    "район",
    "поселение",
    "сельское",
    "город",
    "го",
    "мр",
    "мо",
}

DOMAIN_KEYWORDS = [
    "насел",
    "демограф",
    "прогноз",
    "будет",
    "будущ",
    "ожида",
    "рождаем",
    "смерт",
    "миграц",
    "прирост",
    "жител",
    "муницип",
    "регион",
    "росси",
    "рф",
]

OFF_TOPIC_KEYWORDS = [
    "погода",
    "спорт",
    "матч",
    "кино",
    "фильм",
    "сериал",
    "анекдот",
    "рецепт",
    "музыка",
    "песня",
    "крипт",
    "биткоин",
]


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    unit: str
    source: Literal["population", "demographics"]
    field_name: str
    is_rate: bool = False
    aggregate_field_name: str | None = None
    decimals: int = 0


@dataclass
class ScopeMatch:
    scope_type: ScopeType
    scope_id: int | None
    scope_name: str
    score: int
    position: int = 10**9


@dataclass
class QueryPlan:
    intent: IntentType
    metric: str | None = None
    scope_type: ScopeType | None = None
    scope_id: int | None = None
    scope_name: str | None = None
    scopes: list[ScopeMatch] = field(default_factory=list)
    year: int | None = None
    year_from: int | None = None
    year_to: int | None = None
    ranking_dimension: RankingDimension = "regions"
    order: Literal["asc", "desc"] = "desc"
    limit: int = 5
    horizon_years: int | None = None
    target_year: int | None = None
    reasoning: str = ""


@dataclass
class QueryResult:
    status: Literal["ok", "unsupported", "not_found"]
    plan: QueryPlan
    title: str
    facts: list[str]
    fallback_answer: str


METRIC_SPECS: dict[str, MetricSpec] = {
    "population": MetricSpec(
        key="population",
        label="население",
        unit="чел.",
        source="population",
        field_name="population",
    ),
    "births": MetricSpec(
        key="births",
        label="число рождений",
        unit="чел.",
        source="demographics",
        field_name="births",
    ),
    "deaths": MetricSpec(
        key="deaths",
        label="число смертей",
        unit="чел.",
        source="demographics",
        field_name="deaths",
    ),
    "natural_growth": MetricSpec(
        key="natural_growth",
        label="естественный прирост",
        unit="чел.",
        source="demographics",
        field_name="natural_growth",
    ),
    "net_migration": MetricSpec(
        key="net_migration",
        label="чистая миграция",
        unit="чел.",
        source="demographics",
        field_name="net_migration",
    ),
    "birth_rate": MetricSpec(
        key="birth_rate",
        label="коэффициент рождаемости",
        unit="‰",
        source="demographics",
        field_name="birth_rate",
        is_rate=True,
        aggregate_field_name="births",
        decimals=2,
    ),
    "death_rate": MetricSpec(
        key="death_rate",
        label="коэффициент смертности",
        unit="‰",
        source="demographics",
        field_name="death_rate",
        is_rate=True,
        aggregate_field_name="deaths",
        decimals=2,
    ),
    "natural_growth_rate": MetricSpec(
        key="natural_growth_rate",
        label="коэффициент естественного прироста",
        unit="‰",
        source="demographics",
        field_name="natural_growth_rate",
        is_rate=True,
        aggregate_field_name="natural_growth",
        decimals=2,
    ),
    "net_migration_rate": MetricSpec(
        key="net_migration_rate",
        label="коэффициент миграции",
        unit="‰",
        source="demographics",
        field_name="net_migration_rate",
        is_rate=True,
        aggregate_field_name="net_migration",
        decimals=2,
    ),
}


def _normalize_text(value: str) -> str:
    value = value.lower().replace("ё", "е")
    value = re.sub(r"[^a-zа-я0-9\s-]", " ", value)
    value = value.replace("-", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _remove_stopwords(value: str, stopwords: set[str]) -> str:
    parts = [part for part in _normalize_text(value).split() if part not in stopwords]
    return " ".join(parts).strip()


def _aliases_for_name(name: str, stopwords: set[str]) -> set[str]:
    normalized = _normalize_text(name)
    simplified = _remove_stopwords(name, stopwords)
    aliases = {alias for alias in {normalized, simplified} if alias}

    expanded_aliases = set(aliases)
    for alias in aliases:
        if len(alias) > 5:
            expanded_aliases.add(alias[:-1])
        if alias.endswith("ая") and len(alias) > 6:
            expanded_aliases.add(alias[:-2])
        if alias.endswith("ия") and len(alias) > 6:
            expanded_aliases.add(alias[:-2])
    return {alias.strip() for alias in expanded_aliases if len(alias.strip()) >= 3}


def _format_number(value: float | int | None, decimals: int = 0) -> str:
    if value is None:
        return "нет данных"
    if decimals == 0:
        return f"{int(round(value)):,}".replace(",", " ")
    return f"{float(value):,.{decimals}f}".replace(",", " ")


def _format_metric_value(metric: str, value: float | int | None) -> str:
    spec = METRIC_SPECS[metric]
    number = _format_number(value, spec.decimals)
    return f"{number} {spec.unit}" if value is not None else "нет данных"


def _format_percent_change(value: float | None) -> str:
    if value is None:
        return "нет данных"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _chunk_text(text: str, chunk_size: int = STREAM_CHUNK_SIZE) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            split_at = text.rfind(" ", start, end)
            if split_at > start + 20:
                end = split_at + 1
        chunks.append(text[start:end])
        start = end
    return chunks


def _contains_domain_signal(question_normalized: str) -> bool:
    return any(keyword in question_normalized for keyword in DOMAIN_KEYWORDS)


def _is_off_topic(question_normalized: str) -> bool:
    return not _contains_domain_signal(question_normalized) and any(
        keyword in question_normalized for keyword in OFF_TOPIC_KEYWORDS
    )


def _extract_years(question_normalized: str) -> list[int]:
    years = sorted({int(match) for match in YEAR_RE.findall(question_normalized)})
    return years


def _extract_limit(question_normalized: str) -> int:
    top_match = re.search(r"\bтоп\s*(\d{1,2})\b", question_normalized)
    if top_match:
        return max(1, min(int(top_match.group(1)), 20))

    numeric_match = re.search(
        r"\b(\d{1,2})\s+(?:регион(?:а|ов)?|муниципалитет(?:а|ов)?|город(?:а|ов)?)\b",
        question_normalized,
    )
    if numeric_match:
        return max(1, min(int(numeric_match.group(1)), 20))

    return 5


def _extract_forecast_horizon(
    question_normalized: str,
    years: list[int],
    latest_population_year: int,
) -> tuple[int | None, int | None]:
    relative_match = re.search(r"(?:через|на|в ближайшие)\s+(\d{1,2})\s+лет", question_normalized)
    if relative_match:
        horizon_years = max(1, min(int(relative_match.group(1)), 15))
        return horizon_years, latest_population_year + horizon_years

    target_year = next((year for year in sorted(years, reverse=True) if year > latest_population_year), None)
    if target_year is not None:
        return max(1, min(target_year - latest_population_year, 15)), target_year

    return None, None


def _detect_metric(question_normalized: str) -> str | None:
    wants_rate = (
        "коэффициент" in question_normalized
        or "на 1000" in question_normalized
        or "промилле" in question_normalized
        or "‰" in question_normalized
    )

    if any(keyword in question_normalized for keyword in ["насел", "численност", "жител", "человек"]):
        return "population"

    if any(keyword in question_normalized for keyword in ["родилось", "рождений", "сколько родил"]):
        return "births"
    if "рождаем" in question_normalized:
        return "birth_rate" if wants_rate else "birth_rate"

    if any(keyword in question_normalized for keyword in ["умерло", "смертей", "сколько умер"]):
        return "deaths"
    if "смерт" in question_normalized:
        return "death_rate" if wants_rate else "death_rate"

    if "естествен" in question_normalized or "ест прирост" in question_normalized:
        return "natural_growth_rate" if wants_rate else "natural_growth"

    if "миграц" in question_normalized:
        return "net_migration_rate" if wants_rate else "net_migration"

    return None


async def _resolve_scope(db: AsyncSession, question_normalized: str) -> ScopeMatch | None:
    matches = await _resolve_scopes(db, question_normalized)
    return _pick_primary_scope(matches)


def _pick_primary_scope(matches: list[ScopeMatch]) -> ScopeMatch | None:
    best_region = next((match for match in matches if match.scope_type == "region"), None)
    best_municipality = next((match for match in matches if match.scope_type == "municipality"), None)
    best_country = next((match for match in matches if match.scope_type == "country"), None)

    if best_municipality and best_region:
        return best_municipality if best_municipality.score >= best_region.score + 3 else best_region
    return best_municipality or best_region or best_country


async def _resolve_scopes(db: AsyncSession, question_normalized: str) -> list[ScopeMatch]:
    matches: list[ScopeMatch] = []
    region_matches: dict[int, ScopeMatch] = {}
    municipality_matches: dict[int, ScopeMatch] = {}

    if any(token in question_normalized for token in ["россия", "россии", "рф"]):
        matches.append(
            ScopeMatch(
                scope_type="country",
                scope_id=None,
                scope_name="Россия",
                score=6,
                position=min(
                    [question_normalized.find(token) for token in ["россия", "россии", "рф"] if token in question_normalized] or [0]
                ),
            )
        )

    regions_result = await db.execute(select(Region.id, Region.name))
    for region_id, region_name in regions_result.all():
        best_match: ScopeMatch | None = None
        for alias in _aliases_for_name(region_name, REGION_STOPWORDS):
            position = question_normalized.find(alias)
            if position >= 0:
                candidate = ScopeMatch(
                    scope_type="region",
                    scope_id=region_id,
                    scope_name=region_name,
                    score=len(alias),
                    position=position,
                )
                if (
                    not best_match
                    or candidate.score > best_match.score
                    or (candidate.score == best_match.score and candidate.position < best_match.position)
                ):
                    best_match = candidate
        if best_match:
            region_matches[region_id] = best_match

    municipalities_result = await db.execute(select(Municipality.id, Municipality.name))
    for municipality_id, municipality_name in municipalities_result.all():
        best_match = None
        for alias in _aliases_for_name(municipality_name, MUNICIPALITY_STOPWORDS):
            position = question_normalized.find(alias)
            if position >= 0:
                candidate = ScopeMatch(
                    scope_type="municipality",
                    scope_id=municipality_id,
                    scope_name=municipality_name,
                    score=len(alias),
                    position=position,
                )
                if (
                    not best_match
                    or candidate.score > best_match.score
                    or (candidate.score == best_match.score and candidate.position < best_match.position)
                ):
                    best_match = candidate
        if best_match:
            municipality_matches[municipality_id] = best_match

    matches.extend(region_matches.values())
    matches.extend(municipality_matches.values())
    return sorted(matches, key=lambda match: (-match.score, match.position, match.scope_name))


def _select_compare_scopes(matches: list[ScopeMatch]) -> list[ScopeMatch]:
    if len(matches) < 2:
        return []

    region_matches = [match for match in matches if match.scope_type == "region"]
    municipality_matches = [match for match in matches if match.scope_type == "municipality"]

    if len(region_matches) >= 2:
        return sorted(region_matches, key=lambda match: (match.position, -match.score))[:2]
    if len(municipality_matches) >= 2:
        return sorted(municipality_matches, key=lambda match: (match.position, -match.score))[:2]

    non_country_matches = [match for match in matches if match.scope_type != "country"]
    country_matches = [match for match in matches if match.scope_type == "country"]
    if non_country_matches and country_matches:
        pair = sorted(non_country_matches, key=lambda match: (match.position, -match.score))[:1] + country_matches[:1]
        return sorted(pair, key=lambda match: match.position)

    return []


def _merge_with_thread_context(plan: QueryPlan, thread_id: str | None) -> QueryPlan:
    if not thread_id or thread_id not in THREAD_CONTEXTS:
        return plan

    previous = THREAD_CONTEXTS[thread_id]

    if plan.scope_type is None:
        plan.scope_type = previous.scope_type
        plan.scope_id = previous.scope_id
        plan.scope_name = previous.scope_name

    if plan.metric is None:
        plan.metric = previous.metric

    if plan.intent == "compare" and not plan.scopes and previous.intent == "compare":
        plan.scopes = list(previous.scopes)

    if plan.intent in {"metric_value", "summary"} and plan.year is None and previous.year is not None:
        if plan.scope_type == previous.scope_type and plan.metric == previous.metric:
            plan.year = previous.year

    if plan.intent in {"trend", "compare"}:
        if plan.year_from is None and previous.year_from is not None:
            plan.year_from = previous.year_from
        if plan.year_to is None and previous.year_to is not None:
            plan.year_to = previous.year_to

    if plan.intent == "forecast":
        if plan.horizon_years is None and previous.horizon_years is not None:
            plan.horizon_years = previous.horizon_years
        if plan.target_year is None and previous.target_year is not None:
            plan.target_year = previous.target_year

    return plan


def _remember_thread_context(thread_id: str | None, plan: QueryPlan) -> None:
    if not thread_id or plan.intent == "unsupported":
        return

    THREAD_CONTEXTS[thread_id] = QueryPlan(**plan.__dict__)

    if len(THREAD_CONTEXTS) > MAX_THREAD_CONTEXTS:
        oldest_key = next(iter(THREAD_CONTEXTS))
        THREAD_CONTEXTS.pop(oldest_key, None)


async def _build_query_plan(db: AsyncSession, question: str, thread_id: str | None) -> QueryPlan:
    question_normalized = _normalize_text(question)

    if _is_off_topic(question_normalized):
        return QueryPlan(intent="unsupported", reasoning="off_topic")

    years = _extract_years(question_normalized)
    metric = _detect_metric(question_normalized)
    scope_matches = await _resolve_scopes(db, question_normalized)
    scope = _pick_primary_scope(scope_matches)
    latest_population_year = await _latest_year_for_metric(db, "population")

    ranking_keywords = ["топ", "лидер", "быстрее всего", "наибольш", "максимальн", "убыль", "рост"]
    trend_keywords = ["динам", "измен", "тренд", "за период", "с ", "по "]
    compare_keywords = ["сравни", "сравнить", "сравнение", "срав", "у кого", "что выше", "кто выше", "чем отличается"]
    forecast_keywords = ["прогноз", "спрогноз", "будет", "ожидается", "ожидаем", "через"]
    ranking_requested = any(keyword in question_normalized for keyword in ranking_keywords)
    trend_requested = len(years) >= 2 or any(keyword in question_normalized for keyword in trend_keywords)
    compare_requested = any(keyword in question_normalized for keyword in compare_keywords)
    horizon_years, target_year = _extract_forecast_horizon(
        question_normalized,
        years,
        latest_population_year,
    )
    forecast_requested = (
        any(keyword in question_normalized for keyword in forecast_keywords)
        or target_year is not None
    )

    if compare_requested:
        compare_scopes = _select_compare_scopes(scope_matches)
        plan = QueryPlan(
            intent="compare",
            metric=metric or "population",
            scopes=compare_scopes,
            year_from=years[0] if years else None,
            year_to=years[1] if len(years) >= 2 else (years[0] if len(years) == 1 else None),
            reasoning="compare",
        )
        return _merge_with_thread_context(plan, thread_id)

    if ranking_requested:
        ranking_dimension: RankingDimension = "regions"
        if any(keyword in question_normalized for keyword in ["муницип", "город", "район"]):
            ranking_dimension = "municipalities"
        elif scope and scope.scope_type == "region":
            ranking_dimension = "municipalities"

        plan = QueryPlan(
            intent="ranking",
            metric=metric or "population",
            scope_type=scope.scope_type if scope else None,
            scope_id=scope.scope_id if scope else None,
            scope_name=scope.scope_name if scope else None,
            year_from=years[0] if years else None,
            year_to=years[1] if len(years) >= 2 else None,
            ranking_dimension=ranking_dimension,
            order="asc" if any(keyword in question_normalized for keyword in ["убыль", "снижен", "паден", "decline"]) else "desc",
            limit=_extract_limit(question_normalized),
            reasoning="ranking",
        )
        return _merge_with_thread_context(plan, thread_id)

    if forecast_requested and (metric in {None, "population"}):
        plan = QueryPlan(
            intent="forecast",
            metric="population",
            scope_type=scope.scope_type if scope else None,
            scope_id=scope.scope_id if scope else None,
            scope_name=scope.scope_name if scope else None,
            horizon_years=horizon_years or 5,
            target_year=target_year,
            reasoning="forecast",
        )
        plan = _merge_with_thread_context(plan, thread_id)
        if plan.scope_type is None:
            plan.scope_type = "country"
            plan.scope_name = "Россия"
        return plan

    if metric or scope:
        if trend_requested:
            plan = QueryPlan(
                intent="trend",
                metric=metric,
                scope_type=scope.scope_type if scope else None,
                scope_id=scope.scope_id if scope else None,
                scope_name=scope.scope_name if scope else None,
                year_from=years[0] if len(years) >= 1 else None,
                year_to=years[1] if len(years) >= 2 else None,
                reasoning="trend",
            )
        elif metric:
            plan = QueryPlan(
                intent="metric_value",
                metric=metric,
                scope_type=scope.scope_type if scope else None,
                scope_id=scope.scope_id if scope else None,
                scope_name=scope.scope_name if scope else None,
                year=years[0] if years else None,
                reasoning="metric_value",
            )
        else:
            plan = QueryPlan(
                intent="summary",
                metric="population",
                scope_type=scope.scope_type if scope else None,
                scope_id=scope.scope_id if scope else None,
                scope_name=scope.scope_name if scope else None,
                reasoning="summary",
            )
        plan = _merge_with_thread_context(plan, thread_id)
        if plan.metric is None:
            plan.metric = "population"
        if plan.scope_type is None:
            plan.scope_type = "country"
            plan.scope_name = "Россия"
        return plan

    if years and thread_id and thread_id in THREAD_CONTEXTS:
        previous = THREAD_CONTEXTS[thread_id]
        future_year = next((year for year in sorted(years, reverse=True) if year > latest_population_year), None)
        if previous.scope_type and future_year is not None:
            return QueryPlan(
                intent="forecast",
                metric="population",
                scope_type=previous.scope_type,
                scope_id=previous.scope_id,
                scope_name=previous.scope_name or "Россия",
                horizon_years=max(1, min(future_year - latest_population_year, 15)),
                target_year=future_year,
                reasoning="thread_forecast_follow_up",
            )
        if previous.intent == "compare" and previous.scopes:
            return QueryPlan(
                intent="compare",
                metric=previous.metric or "population",
                scopes=list(previous.scopes),
                year_from=years[0],
                year_to=years[1] if len(years) >= 2 else years[0],
                reasoning="thread_compare_follow_up",
            )
        return QueryPlan(
            intent="metric_value",
            metric=previous.metric or "population",
            scope_type=previous.scope_type or "country",
            scope_id=previous.scope_id,
            scope_name=previous.scope_name or "Россия",
            year=years[0],
            reasoning="thread_follow_up",
        )

    return QueryPlan(intent="unsupported", reasoning="no_supported_pattern")


async def _latest_year_for_metric(db: AsyncSession, metric: str) -> int:
    if METRIC_SPECS[metric].source == "population":
        result = await db.execute(select(func.max(PopulationRecord.year)))
    else:
        result = await db.execute(select(func.max(DemographicIndicator.year)))
    return int(result.scalar() or 2022)


async def _earliest_year_for_metric(db: AsyncSession, metric: str) -> int:
    if METRIC_SPECS[metric].source == "population":
        result = await db.execute(select(func.min(PopulationRecord.year)))
    else:
        result = await db.execute(select(func.min(DemographicIndicator.year)))
    return int(result.scalar() or 2010)


async def _fetch_metric_value(
    db: AsyncSession,
    metric: str,
    scope_type: ScopeType,
    scope_id: int | None,
    year: int,
) -> float | int | None:
    spec = METRIC_SPECS[metric]

    if metric == "population":
        if scope_type == "country":
            result = await db.execute(
                select(func.sum(PopulationRecord.population)).where(PopulationRecord.year == year)
            )
            return result.scalar()
        if scope_type == "region":
            result = await db.execute(
                select(func.sum(PopulationRecord.population))
                .join(Municipality, Municipality.id == PopulationRecord.municipality_id)
                .where(Municipality.region_id == scope_id, PopulationRecord.year == year)
            )
            return result.scalar()
        result = await db.execute(
            select(PopulationRecord.population).where(
                PopulationRecord.municipality_id == scope_id,
                PopulationRecord.year == year,
            )
        )
        return result.scalar()

    field = getattr(DemographicIndicator, spec.field_name)

    if not spec.is_rate:
        if scope_type == "country":
            result = await db.execute(select(func.sum(field)).where(DemographicIndicator.year == year))
            return result.scalar()
        if scope_type == "region":
            result = await db.execute(
                select(func.sum(field))
                .join(Municipality, Municipality.id == DemographicIndicator.municipality_id)
                .where(Municipality.region_id == scope_id, DemographicIndicator.year == year)
            )
            return result.scalar()
        result = await db.execute(
            select(field).where(
                DemographicIndicator.municipality_id == scope_id,
                DemographicIndicator.year == year,
            )
        )
        return result.scalar()

    aggregate_field = getattr(DemographicIndicator, spec.aggregate_field_name or spec.field_name)

    if scope_type == "municipality":
        result = await db.execute(
            select(field).where(
                DemographicIndicator.municipality_id == scope_id,
                DemographicIndicator.year == year,
            )
        )
        return result.scalar()

    query = (
        select(
            (
                func.sum(aggregate_field) * 1000.0
                / func.nullif(func.sum(PopulationRecord.population), 0)
            )
        )
        .join(
            PopulationRecord,
            and_(
                PopulationRecord.municipality_id == DemographicIndicator.municipality_id,
                PopulationRecord.year == DemographicIndicator.year,
            ),
        )
        .where(DemographicIndicator.year == year)
    )
    if scope_type == "region":
        query = query.join(Municipality, Municipality.id == DemographicIndicator.municipality_id).where(
            Municipality.region_id == scope_id
        )

    result = await db.execute(query)
    value = result.scalar()
    return round(float(value), spec.decimals) if value is not None else None


async def _fetch_metric_series(
    db: AsyncSession,
    metric: str,
    scope_type: ScopeType,
    scope_id: int | None,
    year_from: int,
    year_to: int,
) -> list[tuple[int, float | int | None]]:
    spec = METRIC_SPECS[metric]

    if metric == "population":
        if scope_type == "country":
            result = await db.execute(
                select(PopulationRecord.year, func.sum(PopulationRecord.population))
                .where(PopulationRecord.year >= year_from, PopulationRecord.year <= year_to)
                .group_by(PopulationRecord.year)
                .order_by(PopulationRecord.year)
            )
            return result.all()
        if scope_type == "region":
            result = await db.execute(
                select(PopulationRecord.year, func.sum(PopulationRecord.population))
                .join(Municipality, Municipality.id == PopulationRecord.municipality_id)
                .where(
                    Municipality.region_id == scope_id,
                    PopulationRecord.year >= year_from,
                    PopulationRecord.year <= year_to,
                )
                .group_by(PopulationRecord.year)
                .order_by(PopulationRecord.year)
            )
            return result.all()
        result = await db.execute(
            select(PopulationRecord.year, PopulationRecord.population)
            .where(
                PopulationRecord.municipality_id == scope_id,
                PopulationRecord.year >= year_from,
                PopulationRecord.year <= year_to,
            )
            .order_by(PopulationRecord.year)
        )
        return result.all()

    field = getattr(DemographicIndicator, spec.field_name)
    if not spec.is_rate:
        if scope_type == "country":
            result = await db.execute(
                select(DemographicIndicator.year, func.sum(field))
                .where(DemographicIndicator.year >= year_from, DemographicIndicator.year <= year_to)
                .group_by(DemographicIndicator.year)
                .order_by(DemographicIndicator.year)
            )
            return result.all()
        if scope_type == "region":
            result = await db.execute(
                select(DemographicIndicator.year, func.sum(field))
                .join(Municipality, Municipality.id == DemographicIndicator.municipality_id)
                .where(
                    Municipality.region_id == scope_id,
                    DemographicIndicator.year >= year_from,
                    DemographicIndicator.year <= year_to,
                )
                .group_by(DemographicIndicator.year)
                .order_by(DemographicIndicator.year)
            )
            return result.all()
        result = await db.execute(
            select(DemographicIndicator.year, field)
            .where(
                DemographicIndicator.municipality_id == scope_id,
                DemographicIndicator.year >= year_from,
                DemographicIndicator.year <= year_to,
            )
            .order_by(DemographicIndicator.year)
        )
        return result.all()

    aggregate_field = getattr(DemographicIndicator, spec.aggregate_field_name or spec.field_name)
    if scope_type == "municipality":
        result = await db.execute(
            select(DemographicIndicator.year, field)
            .where(
                DemographicIndicator.municipality_id == scope_id,
                DemographicIndicator.year >= year_from,
                DemographicIndicator.year <= year_to,
            )
            .order_by(DemographicIndicator.year)
        )
        return result.all()

    query = (
        select(
            DemographicIndicator.year,
            (
                func.sum(aggregate_field) * 1000.0
                / func.nullif(func.sum(PopulationRecord.population), 0)
            ),
        )
        .join(
            PopulationRecord,
            and_(
                PopulationRecord.municipality_id == DemographicIndicator.municipality_id,
                PopulationRecord.year == DemographicIndicator.year,
            ),
        )
        .where(DemographicIndicator.year >= year_from, DemographicIndicator.year <= year_to)
        .group_by(DemographicIndicator.year)
        .order_by(DemographicIndicator.year)
    )
    if scope_type == "region":
        query = query.join(Municipality, Municipality.id == DemographicIndicator.municipality_id).where(
            Municipality.region_id == scope_id
        )

    result = await db.execute(query)
    rows = []
    for year, value in result.all():
        rows.append((year, round(float(value), spec.decimals) if value is not None else None))
    return rows


def _average(values: list[float | int]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


async def _execute_metric_value_plan(db: AsyncSession, plan: QueryPlan) -> QueryResult:
    metric = plan.metric or "population"
    year = plan.year or await _latest_year_for_metric(db, metric)
    scope_type = plan.scope_type or "country"
    scope_name = plan.scope_name or "Россия"

    value = await _fetch_metric_value(db, metric, scope_type, plan.scope_id, year)
    if value is None:
        return QueryResult(
            status="not_found",
            plan=plan,
            title="Данные не найдены",
            facts=[],
            fallback_answer=f"Не нашёл данные по запросу: {METRIC_SPECS[metric].label} для «{scope_name}» за {year} год.",
        )

    fact = f"{METRIC_SPECS[metric].label.capitalize()} в «{scope_name}» в {year} году: {_format_metric_value(metric, value)}."
    return QueryResult(
        status="ok",
        plan=plan,
        title=f"{METRIC_SPECS[metric].label.capitalize()} — {scope_name}, {year}",
        facts=[fact],
        fallback_answer=f"{fact} По данным базы проекта.",
    )


async def _execute_trend_plan(db: AsyncSession, plan: QueryPlan) -> QueryResult:
    metric = plan.metric or "population"
    scope_type = plan.scope_type or "country"
    scope_name = plan.scope_name or "Россия"
    earliest_year = await _earliest_year_for_metric(db, metric)
    latest_year = await _latest_year_for_metric(db, metric)
    year_to = plan.year_to or (plan.year_from if plan.year_from and plan.year_from > earliest_year else latest_year)
    year_from = plan.year_from or max(earliest_year, year_to - 5)
    if year_from > year_to:
        year_from, year_to = year_to, year_from

    series = await _fetch_metric_series(db, metric, scope_type, plan.scope_id, year_from, year_to)
    series = [(year, value) for year, value in series if value is not None]
    if not series:
        return QueryResult(
            status="not_found",
            plan=plan,
            title="Динамика не найдена",
            facts=[],
            fallback_answer=f"Не нашёл временной ряд по метрике «{METRIC_SPECS[metric].label}» для «{scope_name}» за {year_from}–{year_to} годы.",
        )

    first_year, first_value = series[0]
    last_year, last_value = series[-1]
    change = (last_value or 0) - (first_value or 0)
    sign = "+" if change > 0 else ""
    series_preview = "; ".join(
        f"{year}: {_format_metric_value(metric, value)}" for year, value in series[:6]
    )
    if len(series) > 6:
        series_preview += "; ..."

    facts = [
        f"{METRIC_SPECS[metric].label.capitalize()} в «{scope_name}»: {first_year} — {_format_metric_value(metric, first_value)}, {last_year} — {_format_metric_value(metric, last_value)}.",
        f"Изменение за период: {sign}{_format_metric_value(metric, change)}.",
        f"Ряд по годам: {series_preview}",
    ]
    fallback_answer = (
        f"{METRIC_SPECS[metric].label.capitalize()} в «{scope_name}» в {first_year} году составляла "
        f"{_format_metric_value(metric, first_value)}, а в {last_year} — {_format_metric_value(metric, last_value)}. "
        f"Изменение за период: {sign}{_format_metric_value(metric, change)}."
    )
    return QueryResult(
        status="ok",
        plan=plan,
        title=f"Динамика — {METRIC_SPECS[metric].label}, {scope_name}",
        facts=facts,
        fallback_answer=fallback_answer,
    )


async def _execute_ranking_plan(db: AsyncSession, plan: QueryPlan) -> QueryResult:
    metric = plan.metric or "population"
    if metric != "population":
        return QueryResult(
            status="unsupported",
            plan=plan,
            title="Рейтинг не поддерживается",
            facts=[],
            fallback_answer="Сейчас рейтинги в чате поддерживаются только по изменению населения.",
        )

    latest_year = await _latest_year_for_metric(db, metric)
    if plan.year_from is None and plan.year_to is None:
        year_to = latest_year
        year_from = max(await _earliest_year_for_metric(db, metric), year_to - 5)
    else:
        year_from = plan.year_from or 2010
        year_to = plan.year_to or latest_year
    if year_from == year_to:
        year_from = max(await _earliest_year_for_metric(db, metric), year_to - 5)

    rows: list[tuple[str, int | None, int | None, float | None]]
    title_suffix = "регионов"

    if plan.ranking_dimension == "regions":
        start_subquery = (
            select(
                Municipality.region_id.label("region_id"),
                func.sum(PopulationRecord.population).label("population_start"),
            )
            .join(Municipality, Municipality.id == PopulationRecord.municipality_id)
            .where(PopulationRecord.year == year_from)
            .group_by(Municipality.region_id)
            .subquery()
        )
        end_subquery = (
            select(
                Municipality.region_id.label("region_id"),
                func.sum(PopulationRecord.population).label("population_end"),
            )
            .join(Municipality, Municipality.id == PopulationRecord.municipality_id)
            .where(PopulationRecord.year == year_to)
            .group_by(Municipality.region_id)
            .subquery()
        )
        result = await db.execute(
            select(
                Region.name,
                start_subquery.c.population_start,
                end_subquery.c.population_end,
                (
                    (end_subquery.c.population_end - start_subquery.c.population_start) * 100.0
                    / func.nullif(start_subquery.c.population_start, 0)
                ).label("change_percent"),
            )
            .join(start_subquery, Region.id == start_subquery.c.region_id)
            .join(end_subquery, Region.id == end_subquery.c.region_id)
            .order_by(
                (
                    (
                        (end_subquery.c.population_end - start_subquery.c.population_start) * 100.0
                        / func.nullif(start_subquery.c.population_start, 0)
                    ).asc()
                    if plan.order == "asc"
                    else (
                        (end_subquery.c.population_end - start_subquery.c.population_start) * 100.0
                        / func.nullif(start_subquery.c.population_start, 0)
                    ).desc()
                )
            )
            .limit(plan.limit)
        )
        rows = result.all()
    else:
        title_suffix = "муниципалитетов"
        start_subquery = (
            select(
                PopulationRecord.municipality_id.label("municipality_id"),
                PopulationRecord.population.label("population_start"),
            )
            .where(PopulationRecord.year == year_from)
            .subquery()
        )
        end_subquery = (
            select(
                PopulationRecord.municipality_id.label("municipality_id"),
                PopulationRecord.population.label("population_end"),
            )
            .where(PopulationRecord.year == year_to)
            .subquery()
        )
        query = (
            select(
                Municipality.name,
                start_subquery.c.population_start,
                end_subquery.c.population_end,
                (
                    (end_subquery.c.population_end - start_subquery.c.population_start) * 100.0
                    / func.nullif(start_subquery.c.population_start, 0)
                ).label("change_percent"),
            )
            .join(start_subquery, Municipality.id == start_subquery.c.municipality_id)
            .join(end_subquery, Municipality.id == end_subquery.c.municipality_id)
        )
        if plan.scope_type == "region" and plan.scope_id is not None:
            query = query.where(Municipality.region_id == plan.scope_id)
            title_suffix = f"муниципалитетов региона {plan.scope_name}"

        query = query.order_by(
            (
                (
                    (end_subquery.c.population_end - start_subquery.c.population_start) * 100.0
                    / func.nullif(start_subquery.c.population_start, 0)
                ).asc()
                if plan.order == "asc"
                else (
                    (end_subquery.c.population_end - start_subquery.c.population_start) * 100.0
                    / func.nullif(start_subquery.c.population_start, 0)
                ).desc()
            )
        ).limit(plan.limit)
        result = await db.execute(query)
        rows = result.all()

    if not rows:
        return QueryResult(
            status="not_found",
            plan=plan,
            title="Рейтинг пуст",
            facts=[],
            fallback_answer="Не удалось построить рейтинг по выбранному периоду.",
        )

    direction = "убыли" if plan.order == "asc" else "роста"
    direction_dative = "убыли" if plan.order == "asc" else "росту"
    lines = []
    for index, (name, value_start, value_end, change_percent) in enumerate(rows, start=1):
        lines.append(
            f"{index}. {name}: {_format_number(value_start)} → {_format_number(value_end)} чел. ({_format_number(change_percent, 2)}%)"
        )

    facts = [f"Рейтинг {direction} населения за {year_from}–{year_to}:"] + lines
    fallback_answer = (
        f"Вот топ-{len(rows)} {title_suffix} по {direction_dative} населения за {year_from}–{year_to} годы:\n"
        + "\n".join(lines)
    )
    return QueryResult(
        status="ok",
        plan=plan,
        title=f"Рейтинг {direction} населения",
        facts=facts,
        fallback_answer=fallback_answer,
    )


async def _execute_compare_plan(db: AsyncSession, plan: QueryPlan) -> QueryResult:
    metric = plan.metric or "population"
    spec = METRIC_SPECS[metric]
    scopes = plan.scopes[:2]
    if len(scopes) < 2:
        return QueryResult(
            status="unsupported",
            plan=plan,
            title="Недостаточно сущностей для сравнения",
            facts=[],
            fallback_answer=(
                "Для сравнения укажите две сущности одного уровня, например: "
                "«Сравни Татарстан и Башкортостан по рождаемости за 2019–2022 годы»."
            ),
        )

    earliest_year = await _earliest_year_for_metric(db, metric)
    latest_year = await _latest_year_for_metric(db, metric)

    if plan.year_from is None and plan.year_to is None:
        year_from = latest_year
        year_to = latest_year
    else:
        year_from = plan.year_from or plan.year_to or latest_year
        year_to = plan.year_to or plan.year_from or latest_year

    if year_from > year_to:
        year_from, year_to = year_to, year_from

    year_from = max(year_from, earliest_year)
    year_to = min(year_to, latest_year)

    scope_series: list[tuple[ScopeMatch, list[tuple[int, float | int]]]] = []
    for scope in scopes:
        series = await _fetch_metric_series(db, metric, scope.scope_type, scope.scope_id, year_from, year_to)
        clean_series = [(year, value) for year, value in series if value is not None]
        if not clean_series:
            return QueryResult(
                status="not_found",
                plan=plan,
                title="Данные для сравнения не найдены",
                facts=[],
                fallback_answer=(
                    f"Не нашёл данные по метрике «{spec.label}» для «{scope.scope_name}» "
                    f"за {year_from}–{year_to} годы."
                ),
            )
        scope_series.append((scope, clean_series))

    (scope_a, series_a), (scope_b, series_b) = scope_series
    single_year = year_from == year_to

    if single_year:
        value_a = series_a[-1][1]
        value_b = series_b[-1][1]
        assert value_a is not None and value_b is not None
        difference = float(value_a) - float(value_b)
        leader_text = (
            f"Выше показатель у «{scope_a.scope_name}»."
            if difference > 0
            else f"Выше показатель у «{scope_b.scope_name}»."
            if difference < 0
            else "Показатели совпадают."
        )
        facts = [
            f"{spec.label.capitalize()} в {year_from} году в «{scope_a.scope_name}»: {_format_metric_value(metric, value_a)}.",
            f"{spec.label.capitalize()} в {year_from} году в «{scope_b.scope_name}»: {_format_metric_value(metric, value_b)}.",
            f"Разница: {_format_metric_value(metric, abs(difference))}. {leader_text}",
        ]
        fallback_answer = " ".join(facts)
        return QueryResult(
            status="ok",
            plan=plan,
            title=f"Сравнение — {spec.label}, {year_from}",
            facts=facts,
            fallback_answer=fallback_answer,
        )

    values_a = [value for _, value in series_a]
    values_b = [value for _, value in series_b]
    avg_a = _average(values_a)
    avg_b = _average(values_b)
    latest_a_year, latest_a_value = series_a[-1]
    latest_b_year, latest_b_value = series_b[-1]

    if spec.is_rate:
        assert avg_a is not None and avg_b is not None
        average_difference = avg_a - avg_b
        leader_text = (
            f"В среднем выше показатель у «{scope_a.scope_name}»."
            if average_difference > 0
            else f"В среднем выше показатель у «{scope_b.scope_name}»."
            if average_difference < 0
            else "В среднем показатели совпадают."
        )
        facts = [
            f"Средний {spec.label} в «{scope_a.scope_name}» за {year_from}–{year_to}: {_format_metric_value(metric, avg_a)}.",
            f"Средний {spec.label} в «{scope_b.scope_name}» за {year_from}–{year_to}: {_format_metric_value(metric, avg_b)}.",
            f"В {latest_a_year} году: «{scope_a.scope_name}» — {_format_metric_value(metric, latest_a_value)}, «{scope_b.scope_name}» — {_format_metric_value(metric, latest_b_value)}.",
            f"Средняя разница за период: {_format_metric_value(metric, abs(average_difference))}. {leader_text}",
        ]
        fallback_answer = (
            f"За {year_from}–{year_to} годы средний {spec.label} в «{scope_a.scope_name}» составил "
            f"{_format_metric_value(metric, avg_a)}, а в «{scope_b.scope_name}» — {_format_metric_value(metric, avg_b)}. "
            f"{leader_text} В {latest_a_year} году значения были "
            f"{_format_metric_value(metric, latest_a_value)} и {_format_metric_value(metric, latest_b_value)} соответственно."
        )
        return QueryResult(
            status="ok",
            plan=plan,
            title=f"Сравнение — {spec.label}, {year_from}–{year_to}",
            facts=facts,
            fallback_answer=fallback_answer,
        )

    if metric == "population":
        first_a_year, first_a_value = series_a[0]
        first_b_year, first_b_value = series_b[0]
        assert first_a_value is not None and first_b_value is not None
        assert latest_a_value is not None and latest_b_value is not None
        change_a = float(latest_a_value) - float(first_a_value)
        change_b = float(latest_b_value) - float(first_b_value)
        leader_text = (
            f"К концу периода больше население у «{scope_a.scope_name}»."
            if latest_a_value > latest_b_value
            else f"К концу периода больше население у «{scope_b.scope_name}»."
            if latest_a_value < latest_b_value
            else "К концу периода население одинаковое."
        )
        facts = [
            f"«{scope_a.scope_name}»: {first_a_year} — {_format_metric_value(metric, first_a_value)}, {latest_a_year} — {_format_metric_value(metric, latest_a_value)}, изменение — {_format_metric_value(metric, change_a)}.",
            f"«{scope_b.scope_name}»: {first_b_year} — {_format_metric_value(metric, first_b_value)}, {latest_b_year} — {_format_metric_value(metric, latest_b_value)}, изменение — {_format_metric_value(metric, change_b)}.",
            leader_text,
        ]
        fallback_answer = (
            f"За {year_from}–{year_to} годы население «{scope_a.scope_name}» изменилось с "
            f"{_format_metric_value(metric, first_a_value)} до {_format_metric_value(metric, latest_a_value)}, "
            f"а «{scope_b.scope_name}» — с {_format_metric_value(metric, first_b_value)} до {_format_metric_value(metric, latest_b_value)}. "
            f"{leader_text}"
        )
        return QueryResult(
            status="ok",
            plan=plan,
            title=f"Сравнение — {spec.label}, {year_from}–{year_to}",
            facts=facts,
            fallback_answer=fallback_answer,
        )

    total_a = sum(float(value) for value in values_a)
    total_b = sum(float(value) for value in values_b)
    average_difference = total_a - total_b
    leader_text = (
        f"Суммарно выше показатель у «{scope_a.scope_name}»."
        if average_difference > 0
        else f"Суммарно выше показатель у «{scope_b.scope_name}»."
        if average_difference < 0
        else "Суммарные показатели совпадают."
    )
    facts = [
        f"Суммарный {spec.label} в «{scope_a.scope_name}» за {year_from}–{year_to}: {_format_metric_value(metric, total_a)}.",
        f"Суммарный {spec.label} в «{scope_b.scope_name}» за {year_from}–{year_to}: {_format_metric_value(metric, total_b)}.",
        f"В {latest_a_year} году: «{scope_a.scope_name}» — {_format_metric_value(metric, latest_a_value)}, «{scope_b.scope_name}» — {_format_metric_value(metric, latest_b_value)}.",
        f"Разница по сумме за период: {_format_metric_value(metric, abs(average_difference))}. {leader_text}",
    ]
    fallback_answer = (
        f"За {year_from}–{year_to} годы суммарный {spec.label} в «{scope_a.scope_name}» составил "
        f"{_format_metric_value(metric, total_a)}, а в «{scope_b.scope_name}» — {_format_metric_value(metric, total_b)}. "
        f"{leader_text}"
    )
    return QueryResult(
        status="ok",
        plan=plan,
        title=f"Сравнение — {spec.label}, {year_from}–{year_to}",
        facts=facts,
        fallback_answer=fallback_answer,
    )


async def _execute_forecast_plan(db: AsyncSession, plan: QueryPlan) -> QueryResult:
    scope_type = plan.scope_type or "country"
    scope_name = plan.scope_name or "Россия"
    horizon_years = max(1, min(plan.horizon_years or 5, 15))

    forecast_result = await get_scope_forecast(
        db,
        scope_type,
        plan.scope_id,
        horizon_years=horizon_years,
    )
    if not forecast_result:
        return QueryResult(
            status="not_found",
            plan=plan,
            title="Прогноз не найден",
            facts=[],
            fallback_answer=(
                f"Не удалось построить прогноз по населению для «{scope_name}». "
                "Проверьте, что для этой территории есть исторический ряд населения."
            ),
        )

    snapshot = get_forecast_snapshot(forecast_result, plan.target_year)
    if not snapshot:
        return QueryResult(
            status="not_found",
            plan=plan,
            title="Прогноз не найден",
            facts=[],
            fallback_answer=f"Не удалось построить прогноз по населению для «{scope_name}».",
        )

    facts = [
        f"Модель прогноза: {snapshot['model_name']}.",
        f"Базовый фактический год: {snapshot['anchor_year']}, население — {_format_metric_value('population', snapshot['anchor_population'])}.",
        f"Прогноз населения «{scope_name}» на {snapshot['target_year']} год: {_format_metric_value('population', snapshot['predicted_population'])}.",
        f"Изменение к {snapshot['anchor_year']} году: {_format_metric_value('population', snapshot['absolute_change'])} ({_format_percent_change(snapshot['percent_change'])}).",
        f"Доверительный интервал: {_format_metric_value('population', snapshot['confidence_lower'])} — {_format_metric_value('population', snapshot['confidence_upper'])}.",
    ]
    fallback_answer = (
        f"По модели {snapshot['model_name']} прогноз населения «{scope_name}» на {snapshot['target_year']} год "
        f"составляет {_format_metric_value('population', snapshot['predicted_population'])}. "
        f"Это {_format_metric_value('population', snapshot['absolute_change'])} к уровню {snapshot['anchor_year']} года "
        f"({_format_percent_change(snapshot['percent_change'])}). "
        f"Доверительный интервал: {_format_metric_value('population', snapshot['confidence_lower'])} — "
        f"{_format_metric_value('population', snapshot['confidence_upper'])}."
    )
    return QueryResult(
        status="ok",
        plan=plan,
        title=f"Прогноз — {scope_name}",
        facts=facts,
        fallback_answer=fallback_answer,
    )


async def _execute_summary_plan(db: AsyncSession, plan: QueryPlan) -> QueryResult:
    scope_type = plan.scope_type or "country"
    scope_name = plan.scope_name or "Россия"
    latest_population_year = await _latest_year_for_metric(db, "population")
    latest_demo_year = await _latest_year_for_metric(db, "birth_rate")

    population = await _fetch_metric_value(db, "population", scope_type, plan.scope_id, latest_population_year)
    birth_rate = await _fetch_metric_value(db, "birth_rate", scope_type, plan.scope_id, latest_demo_year)
    death_rate = await _fetch_metric_value(db, "death_rate", scope_type, plan.scope_id, latest_demo_year)
    migration = await _fetch_metric_value(db, "net_migration", scope_type, plan.scope_id, latest_demo_year)

    facts = [
        f"Население {scope_name} в {latest_population_year} году: {_format_metric_value('population', population)}.",
        f"Коэффициент рождаемости в {latest_demo_year} году: {_format_metric_value('birth_rate', birth_rate)}.",
        f"Коэффициент смертности в {latest_demo_year} году: {_format_metric_value('death_rate', death_rate)}.",
        f"Чистая миграция в {latest_demo_year} году: {_format_metric_value('net_migration', migration)}.",
    ]
    fallback_answer = " ".join(facts)
    return QueryResult(
        status="ok",
        plan=plan,
        title=f"Сводка — {scope_name}",
        facts=facts,
        fallback_answer=fallback_answer,
    )


async def _execute_plan(db: AsyncSession, plan: QueryPlan) -> QueryResult:
    if plan.intent == "unsupported":
        return QueryResult(
            status="unsupported",
            plan=plan,
            title="Запрос не поддержан",
            facts=[],
            fallback_answer=(
                "Я могу помочь с вопросами о населении, рождаемости, смертности, миграции, "
                "динамике по годам и рейтингах регионов или муниципалитетов."
            ),
        )

    if plan.intent == "metric_value":
        return await _execute_metric_value_plan(db, plan)
    if plan.intent == "trend":
        return await _execute_trend_plan(db, plan)
    if plan.intent == "ranking":
        return await _execute_ranking_plan(db, plan)
    if plan.intent == "compare":
        return await _execute_compare_plan(db, plan)
    if plan.intent == "forecast":
        return await _execute_forecast_plan(db, plan)
    return await _execute_summary_plan(db, plan)


async def _llm_answer_from_result(question: str, result: QueryResult) -> str | None:
    llm = get_llm(streaming=False, temperature=0.1)
    if not llm or result.status != "ok":
        return None

    messages = [
        {
            "role": "system",
            "content": (
                "Ты — AI-ассистент по демографии России. "
                "Отвечай только по фактам из переданного контекста. "
                "Не придумывай чисел, не расширяй данные за пределы контекста. "
                "Отвечай на русском, кратко, ясно, с явным указанием года или периода."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Вопрос пользователя: {question}\n\n"
                f"Факты из базы:\n- " + "\n- ".join(result.facts) + "\n\n"
                "Сформулируй финальный ответ пользователю в 2-5 предложениях."
            ),
        },
    ]

    last_error: Exception | None = None
    for attempt in range(LLM_RETRY_ATTEMPTS):
        try:
            response = await llm.ainvoke(messages)
            content = response.content if isinstance(response.content, str) else str(response.content)
            if content and content.strip():
                return content.strip()
            raise ValueError("Empty LLM response")
        except Exception as exc:  # pragma: no cover - retry path
            last_error = exc
            if attempt < LLM_RETRY_ATTEMPTS - 1:
                await asyncio.sleep(LLM_RETRY_BASE_DELAY * (2 ** attempt))

    if last_error:
        return None
    return None


async def stream_chat_response(
    db: AsyncSession, message: str, thread_id: str | None = None
) -> AsyncIterator[str]:
    """Stream chat response via deterministic DB query + optional LLM phrasing."""
    plan = await _build_query_plan(db, message, thread_id)
    result = await _execute_plan(db, plan)

    if result.status == "ok":
        _remember_thread_context(thread_id, plan)

    llm_answer = await _llm_answer_from_result(message, result)
    final_text = llm_answer or result.fallback_answer

    for chunk in _chunk_text(final_text):
        yield chunk
        await asyncio.sleep(0)


async def get_ai_insight(
    db: AsyncSession, municipality_id: int | None, region_id: int | None, year: int | None = None
) -> str:
    """Generate a quick AI insight for a municipality or region."""
    context_parts: list[str] = []
    latest_population_year = await _latest_year_for_metric(db, "population")
    population_year = min(year, latest_population_year) if year else latest_population_year
    latest_demo_year = await _latest_year_for_metric(db, "birth_rate")
    demo_year = min(year, latest_demo_year) if year else latest_demo_year

    if municipality_id:
        municipality = await db.get(Municipality, municipality_id)
        if not municipality:
            return "Муниципалитет не найден."

        population_rows = await _fetch_metric_series(
            db, "population", "municipality", municipality_id, 2010, population_year
        )
        population_rows = [(year, value) for year, value in population_rows if value is not None]
        if population_rows:
            first_year, first_pop = population_rows[0]
            last_year, last_pop = population_rows[-1]
            if first_pop and last_pop:
                change_percent = ((last_pop - first_pop) / first_pop) * 100
                direction = "выросло" if change_percent > 0 else "снизилось"
                context_parts.append(
                    f"Население {municipality.name} {direction} на {abs(change_percent):.1f}% "
                    f"с {first_year} по {last_year} год ({_format_number(first_pop)} -> {_format_number(last_pop)} чел.)."
                )

        birth_rate = await _fetch_metric_value(db, "birth_rate", "municipality", municipality_id, demo_year)
        death_rate = await _fetch_metric_value(db, "death_rate", "municipality", municipality_id, demo_year)
        natural_growth_rate = await _fetch_metric_value(
            db, "natural_growth_rate", "municipality", municipality_id, demo_year
        )
        if year and birth_rate is None and death_rate is None and natural_growth_rate is None:
            demo_year = latest_demo_year
            birth_rate = await _fetch_metric_value(db, "birth_rate", "municipality", municipality_id, demo_year)
            death_rate = await _fetch_metric_value(db, "death_rate", "municipality", municipality_id, demo_year)
            natural_growth_rate = await _fetch_metric_value(
                db, "natural_growth_rate", "municipality", municipality_id, demo_year
            )
        context_parts.append(
            f"В {demo_year} году коэффициент рождаемости составил {_format_metric_value('birth_rate', birth_rate)}, "
            f"смертности — {_format_metric_value('death_rate', death_rate)}, "
            f"естественного прироста — {_format_metric_value('natural_growth_rate', natural_growth_rate)}."
        )
        forecast_result = await get_scope_forecast(
            db,
            "municipality",
            municipality_id,
            horizon_years=5,
            anchor_year=population_year,
        )
        forecast_snapshot = get_forecast_snapshot(forecast_result) if forecast_result else None
        if forecast_snapshot:
            context_parts.append(
                f"По модели {forecast_snapshot['model_name']} прогноз населения на {forecast_snapshot['target_year']} год "
                f"составляет {_format_metric_value('population', forecast_snapshot['predicted_population'])}; "
                f"изменение к {forecast_snapshot['anchor_year']} году — "
                f"{_format_metric_value('population', forecast_snapshot['absolute_change'])} "
                f"({_format_percent_change(forecast_snapshot['percent_change'])})."
            )

    elif region_id:
        region = await db.get(Region, region_id)
        if not region:
            return "Регион не найден."

        population_rows = await _fetch_metric_series(db, "population", "region", region_id, 2010, population_year)
        population_rows = [(year, value) for year, value in population_rows if value is not None]
        if population_rows:
            first_year, first_pop = population_rows[0]
            last_year, last_pop = population_rows[-1]
            if first_pop and last_pop:
                change_percent = ((last_pop - first_pop) / first_pop) * 100
                direction = "выросло" if change_percent > 0 else "снизилось"
                context_parts.append(
                    f"Население {region.name} {direction} на {abs(change_percent):.1f}% "
                    f"с {first_year} по {last_year} ({_format_number(first_pop)} -> {_format_number(last_pop)} чел.)."
                )

        birth_rate = await _fetch_metric_value(db, "birth_rate", "region", region_id, demo_year)
        death_rate = await _fetch_metric_value(db, "death_rate", "region", region_id, demo_year)
        migration = await _fetch_metric_value(db, "net_migration", "region", region_id, demo_year)
        if year and birth_rate is None and death_rate is None and migration is None:
            demo_year = latest_demo_year
            birth_rate = await _fetch_metric_value(db, "birth_rate", "region", region_id, demo_year)
            death_rate = await _fetch_metric_value(db, "death_rate", "region", region_id, demo_year)
            migration = await _fetch_metric_value(db, "net_migration", "region", region_id, demo_year)
        context_parts.append(
            f"В {demo_year} году коэффициент рождаемости составил {_format_metric_value('birth_rate', birth_rate)}, "
            f"смертности — {_format_metric_value('death_rate', death_rate)}, "
            f"чистая миграция — {_format_metric_value('net_migration', migration)}."
        )
        forecast_result = await get_scope_forecast(
            db,
            "region",
            region_id,
            horizon_years=5,
            anchor_year=population_year,
        )
        forecast_snapshot = get_forecast_snapshot(forecast_result) if forecast_result else None
        if forecast_snapshot:
            context_parts.append(
                f"По модели {forecast_snapshot['model_name']} прогноз населения на {forecast_snapshot['target_year']} год "
                f"составляет {_format_metric_value('population', forecast_snapshot['predicted_population'])}; "
                f"изменение к {forecast_snapshot['anchor_year']} году — "
                f"{_format_metric_value('population', forecast_snapshot['absolute_change'])} "
                f"({_format_percent_change(forecast_snapshot['percent_change'])})."
            )

    if not context_parts:
        return "Выберите муниципалитет или регион для получения AI-инсайта."

    llm = get_llm(streaming=False, temperature=0.2)
    if llm:
        prompt = (
            "Дай краткий аналитический инсайт на русском языке в 2-3 предложениях. "
            "Используй только факты из данных ниже.\n\n"
            + "\n".join(f"- {line}" for line in context_parts)
        )
        for attempt in range(LLM_RETRY_ATTEMPTS):
            try:
                response = await llm.ainvoke(prompt)
                content = response.content if isinstance(response.content, str) else str(response.content)
                if content and content.strip():
                    return content.strip()
                raise ValueError("Empty LLM response")
            except Exception:  # pragma: no cover - retry path
                if attempt < LLM_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(LLM_RETRY_BASE_DELAY * (2 ** attempt))

    return " ".join(context_parts)
