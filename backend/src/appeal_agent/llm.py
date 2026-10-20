"""OpenAI-compatible client pointed at Crusoe Managed Inference."""

import os
from functools import cache

from openai import OpenAI

from appeal_agent.config import settings


@cache
def client() -> OpenAI:
    cfg = settings()["llm"]
    return OpenAI(base_url=cfg["base_url"], api_key=os.environ[cfg["api_key_env"]])
