import time
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.utils.validators import AppError


@dataclass
class LLMMeta:
    provider: str
    model: str
    prompt_tokens: int
    output_tokens: int
    seconds: float


def _flat_schema(model: type[BaseModel]) -> dict:
    """Pydantic schema with $refs inlined and titles dropped (fewer tokens, wider backend support)."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def walk(n):
        if isinstance(n, dict):
            if "$ref" in n:
                return walk(defs[n["$ref"].split("/")[-1]])
            return {k: walk(v) for k, v in n.items() if not (k == "title" and isinstance(v, str))}
        return [walk(i) for i in n] if isinstance(n, list) else n

    return walk(schema)


async def _ollama(prompt: str, schema: dict) -> tuple[str, int, int]:
    body = {
        "model": settings.ollama_model,
        "messages": [{"role": "user", "content": prompt}],
        "format": schema,
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout) as c:
        r = await c.post(f"{settings.ollama_url}/api/chat", json=body)
        r.raise_for_status()
        d = r.json()
    return d["message"]["content"], d.get("prompt_eval_count", 0), d.get("eval_count", 0)


async def _gemini(prompt: str, schema: dict) -> tuple[str, int, int]:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": schema,
            "temperature": 0.2,
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    async with httpx.AsyncClient(timeout=settings.llm_timeout) as c:
        r = await c.post(url, json=body, headers={"x-goog-api-key": settings.gemini_api_key})
        r.raise_for_status()
        d = r.json()
    u = d.get("usageMetadata", {})
    return d["candidates"][0]["content"]["parts"][0]["text"], u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0)


def _providers() -> list[str]:
    order = [settings.llm_provider, "gemini" if settings.llm_provider == "ollama" else "ollama"]
    return [p for p in order if p != "gemini" or settings.gemini_api_key]


async def generate(prompt: str, model: type[BaseModel], provider: str | None = None) -> tuple[BaseModel, LLMMeta]:
    """One schema-constrained call; falls back to the other provider on error or invalid JSON."""
    schema, errors = _flat_schema(model), []
    for name in [provider] if provider else _providers():
        start = time.perf_counter()
        try:
            text, pin, pout = await (_gemini if name == "gemini" else _ollama)(prompt, schema)
            obj = model.model_validate_json(text)
        except (httpx.HTTPError, KeyError, ValidationError) as e:
            errors.append(f"{name}: {type(e).__name__}")
            continue
        used = settings.gemini_model if name == "gemini" else settings.ollama_model
        return obj, LLMMeta(name, used, pin, pout, round(time.perf_counter() - start, 2))
    raise AppError(503, f"LLM unavailable or returned invalid output ({'; '.join(errors)})")
