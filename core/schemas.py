"""
Pydantic Schemas for the Daily AI News Web Crawler.
These schemas enforce strict structured data validation at each stage of the pipeline:
1. Discovery Output Schema
2. Extraction Output Schema
3. Verification Output Schema
4. Deduplication Output Schema
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional

# ==========================================
# 1. DISCOVERY OUTPUT SCHEMA
# ==========================================

class NewsletterDiscovery(BaseModel):
    name: str = Field(..., description="Name of the newsletter (TLDR AI, The Neuron, or The Rundown AI)")
    publish_date: str = Field(..., description="The publish date of the latest issue found (YYYY-MM-DD or readable date)")
    issue_url: str = Field(..., description="The direct URL of the latest published issue (NOT the homepage or archive link)")
    issue_url_verification: Literal["verified", "partially verified", "not verified"] = Field(..., description="Verification status of the issue URL")
    notes: str = Field(..., description="Details of how the issue was verified and found")

class DiscoveryAgentOutput(BaseModel):
    newsletters: List[NewsletterDiscovery] = Field(..., description="List of discovered latest issues for the specified newsletters")


# ==========================================
# 2. EXTRACTION OUTPUT SCHEMA
# ==========================================

class ExtractedNewsletterItem(BaseModel):
    item_id: str = Field(..., description="Unique ID for the extracted item (e.g. tldr-ai-item-01)")
    order: int = Field(..., description="1-based reading order index of the item inside the newsletter")
    title: str = Field(..., description="Extracted headline or story title (do not invent titles)")
    type: Literal[
        "model", "product", "company announcement", "policy change",
        "research result", "workflow tip", "tool", "hardware", "analysis", "other"
    ] = Field(..., description="Primary entity type of the content block")
    summary: str = Field(..., description="Comprehensive summary of the item including key facts")
    evidence_text: str = Field(..., description="The raw raw/cleaned text or snippet extracted as evidence for this block")
    candidate_links: List[str] = Field(default_factory=list, description="All links/URLs found directly inside this content block")

class ExtractedNewsletter(BaseModel):
    newsletter_name: str = Field(..., description="The name of the newsletter (e.g., TLDR AI)")
    publish_date: str = Field(..., description="The publish date of the issue")
    issue_url: str = Field(..., description="The source URL of the issue page")
    items: List[ExtractedNewsletterItem] = Field(..., description="List of all extracted substantive items in exact reading order")

class ExtractionAgentOutput(BaseModel):
    extracted_newsletters: List[ExtractedNewsletter] = Field(..., description="List of all extracted newsletters")


# ==========================================
# 3. VERIFICATION OUTPUT SCHEMA
# ==========================================

class VerificationItem(BaseModel):
    item_id: str = Field(..., description="The unique item_id from the extraction output")
    primary_source_url: str = Field(..., description="The exact original source URL (announcement, GitHub repo, paper, product page) or 'not verifiable'")
    primary_source_verification: Literal["verified", "partially verified", "not verified"] = Field(..., description="Status of the primary source URL verification")
    newsletter_link_url: str = Field(..., description="The exact URL of the item on the newsletter site or issue page")
    newsletter_link_type: Literal["item-level permalink", "issue-level only", "not available"] = Field(..., description="The type of newsletter link found")
    newsletter_link_verification: Literal["verified", "partially verified", "not verified"] = Field(..., description="Status of the newsletter link verification")
    story_status: Literal["verified", "partially verified", "not verified"] = Field(..., description="Overall story validation status based on source checks")
    verification_notes: str = Field(..., description="Details regarding link validation, findings, and issues identified")

class VerificationAgentOutput(BaseModel):
    verified_items: List[VerificationItem] = Field(..., description="The list of all verified items matching the extraction inputs")


# ==========================================
# 4. DEDUPLICATION OUTPUT SCHEMA
# ==========================================

class NewsletterLinkRef(BaseModel):
    newsletter_name: str = Field(..., description="The name of the newsletter source")
    url: str = Field(..., description="The exact url verified for this item")
    link_type: str = Field(..., description="The type of link (e.g. item-permalink, issue-level)")
    verification: str = Field(..., description="The verification status of the link")

class CanonicalStory(BaseModel):
    canonical_story_id: str = Field(..., description="Unique ID for the deduplicated story")
    canonical_title: str = Field(..., description="Unified high-quality headline for the merged story")
    merged_from: List[str] = Field(..., description="List of item_ids that were merged into this story")
    same_event_confidence: Literal["high", "medium", "low"] = Field(..., description="Level of confidence that these refer to the exact same event")
    canonical_summary: str = Field(..., description="Synthesized, comprehensive summary covering all merged aspects")
    primary_source_url: str = Field(..., description="The unified primary source URL (verified original announcement, repo, paper, etc.)")
    primary_source_verification: Literal["verified", "partially verified", "not verified"] = Field(..., description="Verification status of the primary source URL")
    newsletter_links: List[NewsletterLinkRef] = Field(..., description="List of verified newsletter links referencing this story")

class DeduplicationAgentOutput(BaseModel):
    canonical_stories: List[CanonicalStory] = Field(..., description="List of deduplicated and merged stories")
    unmerged_items: List[str] = Field(..., description="List of item_ids that were kept separate and not merged")
