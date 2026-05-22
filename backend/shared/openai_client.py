from openai import AsyncOpenAI
from .settings import settings


def make_openai_client() -> AsyncOpenAI:
    """Single source of OpenAI clients. CRITICAL: max_retries=0 — Temporal handles retries."""
    return AsyncOpenAI(api_key=settings.openai_api_key, max_retries=0, timeout=30.0)
