"""
LLM client factory — creates a ChatOpenAI instance configured for the chosen provider.
Supports OpenRouter, OpenAI, and any OpenAI-compatible API.
"""

from langchain_openai import ChatOpenAI

from app.config import settings


def get_llm(streaming: bool = False, temperature: float = 0.3) -> ChatOpenAI | None:
    """Get configured LLM client. Returns None if API key is not set."""
    if not settings.llm_api_key:
        return None

    extra_headers = {}
    if "openrouter" in (settings.llm_base_url or ""):
        extra_headers["HTTP-Referer"] = "http://localhost:3000"
        extra_headers["X-Title"] = "Population Analytics"

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url or None,
        temperature=temperature,
        streaming=streaming,
        default_headers=extra_headers or None,
    )
