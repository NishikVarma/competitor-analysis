import asyncio

from app.schemas import Competitor
from app.services.website_extractor import fetch_html, make_client, parse
from app.utils.validators import AppError


async def _verify(client, c: Competitor) -> None:
    if not c.website:
        return
    url = c.website if c.website.startswith("http") else f"https://{c.website}"
    try:
        p = parse(await fetch_html(client, url), url)
    except AppError:
        return  # stays ai_suggested
    if p["title"] or p["description"]:
        c.website = url
        c.verified_summary = f"{p['title']} — {p['description']}"[:300] + " | " + " | ".join(p["headings"][:5])
        c.source = "verified_from_website"


async def verify_competitors(competitors: list[Competitor]) -> None:
    """Fetch each suggested competitor's homepage (title/meta/headings only, no LLM call)."""
    async with await make_client() as client:
        await asyncio.gather(*(_verify(client, c) for c in competitors[:5]))
