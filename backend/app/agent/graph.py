"""
LangGraph agent for demographic data queries.
Full implementation requires LLM_API_KEY in .env.
"""

from typing import Annotated, TypedDict

from app.config import settings


class AgentState(TypedDict):
    messages: list
    thread_id: str


# Agent will be fully wired when LLM is configured.
# For now, chat_service.py handles the logic directly.
