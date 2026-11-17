import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import LLMResult
from app.services import analysis_service, llm_service
from app.services.website_extractor import parse
from app.utils.validators import AppError, validate_public_url

client = TestClient(app)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1", "http://localhost", "http://10.0.0.5", "http://169.254.169.254/latest",
    "http://[::1]/", "file:///etc/passwd", "ftp://example.com",
])
def test_ssrf_blocked(url):
    with pytest.raises(AppError) as e:
        validate_public_url(url)
    assert e.value.status_code == 400


def test_public_url_allowed(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 80))])
    assert validate_public_url("https://example.com") == "https://example.com"


def test_parse_strips_noise_and_finds_key_links():
    html = ("<title>Acme</title><meta name='description' content='We build things'>"
            "<nav>menu menu menu menu menu menu menu</nav><script>var x=1</script>"
            "<h1>Web Development</h1><a href='/services'>s</a>"
            "<p>We deliver affordable websites to small businesses.</p>"
            "<p>We deliver affordable websites to small businesses.</p>")
    p = parse(html, "https://acme.com")
    assert p["title"] == "Acme" and p["description"] == "We build things"
    assert p["text"].count("affordable") == 1 and "var x" not in p["text"] and "menu" not in p["text"]
    assert p["links"] == ["https://acme.com/services"]


def test_invalid_url_422():
    assert client.post("/link-analysis", json={"url": "not a url"}).status_code == 422


def test_private_url_400():
    r = client.post("/link-analysis", json={"url": "http://127.0.0.1:8000"})
    assert r.status_code == 400 and r.json()["success"] is False


def _sample() -> LLMResult:
    q = {"query": "q", "platforms": ["Google"], "intent": "i", "business_relevance": "r", "target_audience": "a"}
    s = {"name": "n", "description": "d", "target_industry": "i", "target_customer": "c", "main_benefit": "b", "inferred": False}
    c = {"name": "C", "website": "", "products": [], "strengths": [], "weaknesses": []}
    la = {k: ["x"] for k in ["primary_audience", "secondary_audience", "industries", "business_types",
                             "customer_profiles", "location_focus", "customer_needs", "customer_interests",
                             "recommended_segments"]}
    return LLMResult.model_validate({
        "brand": {"name": "Acme", "category": "Tech", "summary": "s"},
        "competitor_analysis": {"brand_overview": "o", "main_products_services": [], "competitors": [c, c, c],
                                "brand_advantages": [], "positioning_opportunities": []},
        "target_search_queries": [q] * 5,
        "seo_improvements": {"primary_keyword": "k", "secondary_keywords": [], "long_tail_keywords": [],
                             "business_keywords": [], "recommended_title": "t", "meta_description": "m",
                             "supporting_content": []},
        "top_services": [s] * 5,
        "target_audience": la,
    })


def test_endpoint_happy_path(monkeypatch):
    async def fake_extract(url):
        return {}, "content"

    async def fake_generate(prompt, model):
        return _sample(), None

    async def fake_verify(c):
        c[0].source = "verified_from_website"

    monkeypatch.setattr(analysis_service, "extract_site", fake_extract)
    monkeypatch.setattr(analysis_service, "generate", fake_generate)
    monkeypatch.setattr(analysis_service, "verify_competitors", fake_verify)
    r = client.post("/link-analysis", json={"url": "https://acme.com"})
    body = r.json()
    assert r.status_code == 200 and body["success"] and body["brand"]["name"] == "Acme"
    assert len(body["analysis"]["target_search_queries"]) == 5
    assert body["analysis"]["competitor_analysis"]["competitors"][0]["source"] == "verified_from_website"


def test_flat_schema_has_no_refs():
    assert "$ref" not in str(llm_service._flat_schema(LLMResult))


def test_blocked_or_empty_page_rejected(monkeypatch):
    import asyncio

    from app.services import website_extractor as we

    async def empty(client, url):
        return b"<html><head></head><body></body></html>"

    monkeypatch.setattr(we, "fetch_html", empty)
    with pytest.raises(AppError) as e:
        asyncio.run(we.extract_site("https://blocked.example"))
    assert e.value.status_code == 422


def test_duplicate_platforms_collapsed():
    from app.schemas import SearchQuery

    q = SearchQuery(query="q", platforms=["Google"] * 5, intent="i", business_relevance="r", target_audience="a")
    assert q.platforms == ["Google"]


def test_utf8_bytes_without_charset_decode_correctly():
    p = parse("<title>Walmart — Save</title>".encode("utf-8"), "https://w.com")
    assert p["title"] == "Walmart — Save"
