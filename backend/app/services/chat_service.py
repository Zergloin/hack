"""
Chat service — LangGraph agent for demographic data queries.
Streams responses via SSE.
"""

from typing import AsyncIterator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.demographics import DemographicIndicator
from app.models.municipality import Municipality
from app.models.population import PopulationRecord
from app.models.region import Region
from app.services.llm import get_llm


async def _query_data(db: AsyncSession, question: str) -> str:
    """Query database for context relevant to the user's question."""
    question_lower = question.lower()
    context_parts = []

    # Search all municipalities and regions for name match
    all_munis = await db.execute(select(Municipality))
    all_regions = await db.execute(select(Region))

    target_muni = None
    target_region = None

    for m in all_munis.scalars().all():
        # Match by key part of the name (strip prefixes like "г.", "г.о.")
        name_clean = m.name.lower().replace("г.", "").replace("г.о.", "").replace("м.р.", "").strip()
        if name_clean in question_lower or m.name.lower() in question_lower:
            target_muni = m
            break

    if not target_muni:
        for r in all_regions.scalars().all():
            name_clean = r.name.lower().replace("республика ", "").replace("область", "").replace("край", "").strip()
            if name_clean in question_lower or r.name.lower() in question_lower:
                target_region = r
                break

    if target_muni:
        pop_q = (
            select(PopulationRecord)
            .where(PopulationRecord.municipality_id == target_muni.id)
            .order_by(PopulationRecord.year.desc())
            .limit(13)
        )
        pop_res = await db.execute(pop_q)
        pops = pop_res.scalars().all()
        if pops:
            context_parts.append(f"Население {target_muni.name} (регион ID={target_muni.region_id}):")
            for p in reversed(pops):
                context_parts.append(f"  {p.year}: {p.population:,}")

        demo_q = (
            select(DemographicIndicator)
            .where(DemographicIndicator.municipality_id == target_muni.id)
            .order_by(DemographicIndicator.year.desc())
            .limit(3)
        )
        demo_res = await db.execute(demo_q)
        demos = demo_res.scalars().all()
        for demo in demos:
            context_parts.append(
                f"Демография {target_muni.name} ({demo.year}): "
                f"рождаемость={demo.birth_rate}\u2030, смертность={demo.death_rate}\u2030, "
                f"ест.прирост={demo.natural_growth_rate}\u2030, миграция={demo.net_migration_rate}\u2030"
            )

    elif target_region:
        pop_q = (
            select(PopulationRecord.year, func.sum(PopulationRecord.population))
            .join(Municipality)
            .where(Municipality.region_id == target_region.id)
            .group_by(PopulationRecord.year)
            .order_by(PopulationRecord.year.desc())
            .limit(13)
        )
        pop_res = await db.execute(pop_q)
        rows = pop_res.all()
        context_parts.append(f"Население {target_region.name} ({target_region.federal_district} ФО):")
        for year, total in reversed(rows):
            context_parts.append(f"  {year}: {total:,}")

    else:
        # General stats
        total_q = select(func.sum(PopulationRecord.population)).where(
            PopulationRecord.year == 2022
        )
        total_res = await db.execute(total_q)
        total = total_res.scalar()
        if total:
            context_parts.append(f"Общее население РФ (2022, по данным муниципалитетов в БД): {total:,}")

        # Top growth/decline
        from app.api.population import population_rankings
        # Just add a note
        context_parts.append("В базе данных 83 региона и ~200 муниципалитетов с данными за 2010-2022.")

    return "\n".join(context_parts) if context_parts else "Данные не найдены по указанному запросу."


async def stream_chat_response(
    db: AsyncSession, message: str, thread_id: str | None = None
) -> AsyncIterator[str]:
    """Stream chat response via LLM or fallback."""
    data_context = await _query_data(db, message)

    llm = get_llm(streaming=True)
    if llm:
        try:
            system_prompt = (
                "Ты — AI-ассистент по демографии России. Отвечай только на вопросы о демографии, "
                "населении, муниципалитетах и регионах РФ. На вопросы не по теме — вежливо отказывай "
                "и предлагай задать вопрос по демографии.\n"
                "Отвечай на русском языке, кратко и информативно. Используй данные из контекста.\n"
                "Указывай годы данных. Форматируй числа с разделителями тысяч.\n\n"
                f"Контекст данных из БД:\n{data_context}"
            )

            async for chunk in llm.astream(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ]
            ):
                if chunk.content:
                    yield chunk.content
            return
        except Exception as e:
            yield f"Ошибка LLM: {str(e)}\n\n"

    # Fallback without LLM
    off_topic_keywords = ["погода", "спорт", "кино", "рецепт", "анекдот", "игр"]
    if any(kw in message.lower() for kw in off_topic_keywords):
        yield "Извините, я могу помочь только с вопросами о демографии и населении России."
        return

    yield f"На основе имеющихся данных:\n\n{data_context}"


async def get_ai_insight(
    db: AsyncSession, municipality_id: int | None, region_id: int | None
) -> str:
    """Generate a quick AI insight for a municipality or region."""
    context_parts = []

    if municipality_id:
        muni = await db.get(Municipality, municipality_id)
        if not muni:
            return "Муниципалитет не найден."

        pop_q = (
            select(PopulationRecord)
            .where(PopulationRecord.municipality_id == municipality_id)
            .order_by(PopulationRecord.year)
        )
        pop_res = await db.execute(pop_q)
        pops = pop_res.scalars().all()

        if pops:
            first, last = pops[0], pops[-1]
            if first.population and last.population:
                change = ((last.population - first.population) / first.population) * 100
                direction = "выросло" if change > 0 else "снизилось"
                context_parts.append(
                    f"Население {muni.name} {direction} на {abs(change):.1f}% "
                    f"с {first.year} по {last.year} год "
                    f"(с {first.population:,} до {last.population:,} чел.)."
                )

        demo_q = (
            select(DemographicIndicator)
            .where(DemographicIndicator.municipality_id == municipality_id)
            .order_by(DemographicIndicator.year.desc())
            .limit(1)
        )
        demo_res = await db.execute(demo_q)
        demo = demo_res.scalars().first()
        if demo:
            context_parts.append(
                f"Коэффициент рождаемости: {demo.birth_rate}\u2030, "
                f"смертности: {demo.death_rate}\u2030, "
                f"ест. прирост: {demo.natural_growth_rate}\u2030."
            )

    elif region_id:
        region = await db.get(Region, region_id)
        if not region:
            return "Регион не найден."

        pop_q = (
            select(PopulationRecord.year, func.sum(PopulationRecord.population))
            .join(Municipality)
            .where(Municipality.region_id == region_id)
            .group_by(PopulationRecord.year)
            .order_by(PopulationRecord.year)
        )
        pop_res = await db.execute(pop_q)
        rows = pop_res.all()
        if rows:
            first_year, first_pop = rows[0]
            last_year, last_pop = rows[-1]
            change = ((last_pop - first_pop) / first_pop) * 100 if first_pop else 0
            direction = "выросло" if change > 0 else "снизилось"
            context_parts.append(
                f"Население {region.name} {direction} на {abs(change):.1f}% "
                f"с {first_year} по {last_year} ({first_pop:,} → {last_pop:,})."
            )

    if not context_parts:
        return "Выберите муниципалитет или регион для получения AI-инсайта."

    llm = get_llm(streaming=False)
    if llm:
        try:
            prompt = (
                "Дай краткий (2-3 предложения) аналитический инсайт по демографии "
                "на русском языке. Будь конкретным, используй цифры.\n\n"
                f"Данные:\n{chr(10).join(context_parts)}"
            )
            response = await llm.ainvoke(prompt)
            return response.content
        except Exception:
            pass

    return " ".join(context_parts)
