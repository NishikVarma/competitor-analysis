import time

from app.config import settings
from app.schemas import Analysis, AnalysisResponse, LLMResult
from app.services.competitor_service import verify_competitors
from app.services.llm_service import generate
from app.services.website_extractor import extract_site

_cache: dict[str, tuple[float, AnalysisResponse]] = {}

PROMPT = """Analyze the website below and fill the JSON schema. Be concise (short phrases, no filler).
Rules: use only facts from the website content; top_services must come from the site (set inferred=true only if you had to infer);
competitors = at least 3 real, well-known companies in the same category with their homepage URL (leave website empty if unsure);
search queries: 5 queries a customer would type, each with suited platforms; never give search volumes.
WEBSITE: {url}
CONTENT:
{content}"""


async def analyze(url: str) -> AnalysisResponse:
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < settings.cache_ttl:
        return hit[1]
    _, content = await extract_site(url)
    result, _meta = await generate(PROMPT.format(url=url, content=content), LLMResult)
    await verify_competitors(result.competitor_analysis.competitors)
    resp = AnalysisResponse(
        website=url,
        brand=result.brand,
        analysis=Analysis(**result.model_dump(exclude={"brand"})),
    )
    _cache[url] = (time.time(), resp)
    return resp
