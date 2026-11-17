import asyncio
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.utils.validators import AppError, validate_public_url

KEY_PAGE = re.compile(r"about|service|product|solution|what-we-do", re.I)
NOISE = ("script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe")


async def fetch_html(client: httpx.AsyncClient, url: str) -> bytes:
    """GET with manual redirects so every hop is SSRF-checked; body size capped."""
    for _ in range(4):
        await asyncio.to_thread(validate_public_url, url)
        try:
            async with client.stream("GET", url) as r:
                if r.is_redirect:
                    url = urljoin(url, r.headers.get("location", ""))
                    continue
                if r.status_code >= 400:
                    raise AppError(502, f"Website returned HTTP {r.status_code}")
                if "html" not in r.headers.get("content-type", "html"):
                    raise AppError(422, "URL does not point to an HTML page")
                body = b""
                async for chunk in r.aiter_bytes():
                    body += chunk
                    if len(body) > settings.max_response_bytes:
                        break
                return body  # raw bytes: BeautifulSoup detects charset (meta/utf-8) instead of guessing latin-1
        except httpx.TimeoutException:
            raise AppError(504, "Website timed out")
        except httpx.HTTPError as e:
            raise AppError(502, f"Could not fetch website: {type(e).__name__}")
    raise AppError(502, "Too many redirects")


def parse(html: str | bytes, base: str) -> dict:
    """Compact page facts: title, meta, headings, de-duplicated text, same-site key links."""
    soup = BeautifulSoup(html, "html.parser")
    meta = lambda **a: (soup.find("meta", attrs=a) or {}).get("content", "")  # noqa: E731
    host = urlparse(base).netloc
    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"]).split("#")[0]
        if urlparse(href).netloc == host and KEY_PAGE.search(href) and href not in links:
            links.append(href)
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]
    for t in soup(NOISE):
        t.decompose()
    seen, lines = set(), []
    for s in soup.get_text("\n", strip=True).splitlines():
        if len(s) > 25 and s not in seen:  # drop menu crumbs / repeats
            seen.add(s)
            lines.append(s)
    return {
        "title": soup.title.get_text(strip=True) if soup.title else "",
        "description": meta(name="description") or meta(property="og:description"),
        "headings": list(dict.fromkeys(headings))[:25],
        "text": " ".join(lines),
        "links": links,
    }


async def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=settings.fetch_timeout,
        follow_redirects=False,
        headers={"User-Agent": "Mozilla/5.0 (compatible; LinkAnalysisBot/1.0)"},
    )


async def extract_site(url: str, max_pages: int = 3) -> tuple[dict, str]:
    """Homepage + up to 2 about/services pages -> (homepage facts, compact text for the LLM)."""
    async with await make_client() as client:
        home = parse(await fetch_html(client, url), url)
        if len(home["title"]) + len(home["description"]) + len(home["text"]) < 200:
            raise AppError(422, "Website blocked automated access or has no readable text (e.g. JavaScript-only page)")
        parts = [f"TITLE: {home['title']}\nDESC: {home['description']}\nHEADINGS: {' | '.join(home['headings'])}\n{home['text']}"]
        for link in home["links"][: max_pages - 1]:
            try:
                p = parse(await fetch_html(client, link), link)
                parts.append(f"[{link}] {p['title']}. {' | '.join(p['headings'][:10])}\n{p['text']}")
            except AppError:
                continue  # key pages are best-effort
    return home, "\n\n".join(parts)[: settings.max_content_chars]
