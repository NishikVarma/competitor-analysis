import time

from app.config import settings
from app.schemas import Analysis, AnalysisResponse, LLMResult
from app.services.competitor_service import verify_competitors
from app.services.llm_service import generate
from app.services.website_extractor import extract_site

_cache: dict[str, tuple[float, AnalysisResponse]] = {}

PROMPT = """Analyze the website below and fill the JSON schema. Be concise (short phrases, no filler).
Rules: use only facts from the website content; top_services must be named in the content (inferred=false only then, otherwise inferred=true);
brand_overview = 2 sentences on what the business does, no competitor names;
competitors = at least 3 real companies in the same category that operate in the site's target country/market (infer it from the domain, e.g. .in = India, and content), each with its official homepage URL (give the real domain for any well-known company; empty only if truly unknown);
search queries: 5 different queries a customer would type; give each 1-3 DIFFERENT platforms from Google, Facebook, Instagram, LinkedIn, X, and spread the five queries across all five platforms; never give search volumes;
long_tail_keywords = 3+ word phrases; supporting_content = specific page/article titles for this business.
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
