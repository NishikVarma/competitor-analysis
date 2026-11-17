"""Measure real latency + token counts per provider: python -m scripts.benchmark URL [URL...]"""
import asyncio
import sys

from app.schemas import LLMResult
from app.services.analysis_service import PROMPT
from app.services.llm_service import generate
from app.services.website_extractor import extract_site


async def main(urls):
    for url in urls:
        _, content = await extract_site(url)
        prompt = PROMPT.format(url=url, content=content)
        for provider in ("ollama", "gemini"):
            try:
                _, m = await generate(prompt, LLMResult, provider)
                print(f"{url} | {m.provider}:{m.model} | in={m.prompt_tokens} out={m.output_tokens} | {m.seconds}s")
            except Exception as e:  # provider not configured / failed
                print(f"{url} | {provider} | skipped: {e}")


asyncio.run(main(sys.argv[1:]))
