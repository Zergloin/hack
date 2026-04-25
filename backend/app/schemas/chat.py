from pydantic import BaseModel


class ChatMessage(BaseModel):
    message: str
    thread_id: str | None = None


class AIInsightRequest(BaseModel):
    municipality_id: int | None = None
    region_id: int | None = None
    year: int | None = None
