from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

Platform = Literal["Google", "Facebook", "Instagram", "LinkedIn", "X"]


class LinkAnalysisRequest(BaseModel):
    url: HttpUrl


class Brand(BaseModel):
    name: str
    category: str = Field(description="Main business category")
    summary: str


class Competitor(BaseModel):
    name: str
    website: str = Field(description="Competitor homepage URL, empty if unsure")
    products: list[str]
    strengths: list[str]
    weaknesses: list[str]
    source: Literal["ai_suggested", "verified_from_website"] = "ai_suggested"
    verified_summary: str = ""


class CompetitorAnalysis(BaseModel):
    brand_overview: str
    main_products_services: list[str]
    competitors: list[Competitor] = Field(min_length=3)
    brand_advantages: list[str]
    positioning_opportunities: list[str]


class SearchQuery(BaseModel):
    query: str
    platforms: list[Platform] = Field(min_length=1, max_length=5, description="Distinct platforms where this query suits")
    intent: str
    business_relevance: str
    target_audience: str

    @field_validator("platforms")
    @classmethod
    def _distinct(cls, v):  # small models repeat items; keep order, drop repeats
        return list(dict.fromkeys(v))


class SEOImprovements(BaseModel):
    primary_keyword: str
    secondary_keywords: list[str]
    long_tail_keywords: list[str]
    business_keywords: list[str]
    recommended_title: str
    meta_description: str
    supporting_content: list[str] = Field(description="Landing pages, FAQs, blog topics, location pages")


class Service(BaseModel):
    name: str
    description: str
    target_industry: str
    target_customer: str
    main_benefit: str
    inferred: bool = Field(description="true if not stated on the website")


class TargetAudience(BaseModel):
    primary_audience: list[str]
    secondary_audience: list[str]
    industries: list[str]
    business_types: list[str]
    customer_profiles: list[str]
    location_focus: list[str]
    customer_needs: list[str]
    customer_interests: list[str]
    recommended_segments: list[str]


class LLMResult(BaseModel):
    """Exactly what the LLM must return (one call, all sections)."""

    brand: Brand
    competitor_analysis: CompetitorAnalysis
    target_search_queries: list[SearchQuery] = Field(min_length=5, max_length=5)
    seo_improvements: SEOImprovements
    top_services: list[Service] = Field(min_length=5, max_length=5)
    target_audience: TargetAudience


class Analysis(BaseModel):
    competitor_analysis: CompetitorAnalysis
    target_search_queries: list[SearchQuery]
    seo_improvements: SEOImprovements
    top_services: list[Service]
    target_audience: TargetAudience


class AnalysisResponse(BaseModel):
    success: bool = True
    website: str
    brand: Brand
    analysis: Analysis
