import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.chat import AIInsightRequest, ChatMessage
from app.services.chat_service import get_ai_insight, stream_chat_response

router = APIRouter()


@router.post("/message")
async def chat_message(
    request: ChatMessage,
    db: AsyncSession = Depends(get_db),
):
    async def event_stream():
        async for chunk in stream_chat_response(db, request.message, request.thread_id):
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/insight")
async def ai_insight(
    request: AIInsightRequest,
    db: AsyncSession = Depends(get_db),
):
    insight = await get_ai_insight(db, request.municipality_id, request.region_id)
    return {"insight": insight}
