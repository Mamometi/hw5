"""Portkey / model configuration and the team's run limits.

Loads .env from Homeworks/5 and every folder above it (nearest wins).

All five agents use gpt-6-luna through Portkey. gpt-6-luna needs the Responses
API for function tools, and the course Portkey account routes the model as
`@integration-slug/model` (e.g. @azure-openai-global/gpt-6-luna). Override the
slug with PORTKEY_PROVIDER.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
for folder in [PROJECT_ROOT, *PROJECT_ROOT.parents]:
    if (folder / ".env").exists():
        load_dotenv(folder / ".env", override=False)

MODEL_NAME = "gpt-6-luna"  # every agent uses this; not overridable on purpose
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")
PORTKEY_PROVIDER = os.getenv("PORTKEY_PROVIDER", "@azure-openai-global").rstrip("/")

PROMPTS_DIR = BACKEND_DIR / "prompts"
MCP_SERVER_PATH = PROJECT_ROOT / "mcp_server" / "server.py"
MCP_PYTHON = os.getenv("MCP_PYTHON", str(PROJECT_ROOT / ".venv" / "bin" / "python"))
AUDIT_PATH = Path(os.getenv("AUDIT_PATH", PROJECT_ROOT / "output" / "audit_trail.json"))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


# ---- Loop and token limits -------------------------------------------------
# Delegation: Boss -> specialist is depth 1, specialist -> colleague is depth 2.
MAX_DELEGATION_DEPTH = _int("MAX_DELEGATION_DEPTH", 2)
MAX_DELEGATIONS_PER_RUN = _int("MAX_DELEGATIONS_PER_RUN", 8)
# Every agent run in one desk run shares this token budget; hitting it stops the run.
TEAM_TOKEN_BUDGET = _int("TEAM_TOKEN_BUDGET", 300_000)

BOSS_LIMITS = UsageLimits(
    request_limit=_int("BOSS_REQUEST_LIMIT", 12),
    tool_calls_limit=_int("BOSS_TOOL_CALLS_LIMIT", 15),
    total_tokens_limit=_int("BOSS_TOTAL_TOKENS_LIMIT", 100_000),
)
SPECIALIST_LIMITS = UsageLimits(
    request_limit=_int("SPECIALIST_REQUEST_LIMIT", 8),
    tool_calls_limit=_int("SPECIALIST_TOOL_CALLS_LIMIT", 10),
    total_tokens_limit=_int("SPECIALIST_TOTAL_TOKENS_LIMIT", 60_000),
)


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY is missing. Put it in Homeworks/5/.env (see .env.example)."
        )
    return key


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    key = require_api_key()
    client = AsyncOpenAI(
        api_key=key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": key},
        timeout=120,  # SDK default is 600s x 3 attempts: a stuck call could hang a run for 30 min
        max_retries=1,
    )
    routed = f"{PORTKEY_PROVIDER}/{MODEL_NAME}" if PORTKEY_PROVIDER else MODEL_NAME
    return OpenAIResponsesModel(routed, provider=OpenAIProvider(openai_client=client))
