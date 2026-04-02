# echo_models.py  — Week 1 Day 1–3
# Pydantic schemas for every content type in the Echo system

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class Platform(str, Enum):
    LINKEDIN  = "LinkedIn"
    X         = "X"
    INSTAGRAM = "Instagram"
    FACEBOOK  = "Facebook"


# ── Week 1 Day 1 ──────────────────────────────────────────────────────────
class TalkingPoint(BaseModel):
    headline:  str
    summary:   str
    relevance: str
    keywords:  List[str] = []

class ScrapedContent(BaseModel):
    url:             str
    title:           str
    talking_points:  List[TalkingPoint]
    overall_theme:   str
    trending_score:  int = Field(ge=0, le=100)


# ── Week 1 Day 3 — Platform schemas ──────────────────────────────────────
class LinkedInPost(BaseModel):
    """Long-form, professional, 150-300 words"""
    hook:       str = Field(..., description="Opening line to stop the scroll")
    body:       str = Field(..., description="3-5 paragraphs, professional tone")
    insight:    str = Field(..., description="Unique data point or opinion")
    cta:        str = Field(..., description="Clear call to action")
    hashtags:   List[str] = Field(..., max_length=5)

class XPost(BaseModel):
    """Short, punchy, hook-driven, max 280 chars total"""
    hook:     str = Field(..., max_length=90)
    body:     str = Field(..., max_length=160)
    cta:      str = Field(..., max_length=50)
    hashtags: List[str] = Field(..., max_length=3)

    @property
    def full_text(self) -> str:
        tags = " ".join(f"#{t.lstrip('#')}" for t in self.hashtags)
        return f"{self.hook}\n\n{self.body}\n\n{self.cta} {tags}"


# ── Week 1 Day 4 — Image Prompt Engineering ──────────────────────────────
class ImagePrompt(BaseModel):
    dalle_prompt:      str
    midjourney_prompt: str
    style:             str
    mood:              str
    colors:            List[str]
    platform:          Platform


# ── Week 1 Day 5 — Social Pack (Milestone 1) ─────────────────────────────
class SocialPack(BaseModel):
    source_url:        str
    linkedin_post:     LinkedInPost
    x_post:            XPost
    image_prompt:      ImagePrompt
    brand_voice_score: int = Field(ge=0, le=100)
    created_at:        str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Week 2 Day 4 — A/B Headline Debate ───────────────────────────────────
class HeadlineCandidate(BaseModel):
    text:           str
    argument_for:   str
    predicted_ctr:  float = Field(ge=0.0, le=1.0)

class ABTestResult(BaseModel):
    headline_a:  HeadlineCandidate
    headline_b:  HeadlineCandidate
    winner:      str
    reasoning:   str
    confidence:  int = Field(ge=0, le=100)


# ── Week 3 Day 3 — Brand Safety ──────────────────────────────────────────
class BrandSafetyResult(BaseModel):
    is_safe:               bool
    safety_score:          int = Field(ge=0, le=100)
    flags:                 List[str] = []
    controversial_phrases: List[str] = []
    recommendation:        str


# ── Week 3 Day 4 — Comment Triage ────────────────────────────────────────
class CommentCategory(str, Enum):
    SUPPORT  = "Support"
    TROLL    = "Troll"
    LEAD     = "Lead"
    QUESTION = "Question"
    NEUTRAL  = "Neutral"

class TriagedComment(BaseModel):
    original_comment: str
    category:         CommentCategory
    sentiment:        str
    priority:         int = Field(ge=1, le=5)
    suggested_reply:  str
    escalate:         bool = False


# ── Week 3 Day 2+5 — HITL Approval Queue ─────────────────────────────────
class PostApproval(BaseModel):
    post_id:         str
    platform:        Platform
    content:         str
    image_url:       Optional[str] = None
    brand_safety:    BrandSafetyResult
    status:          str = "pending"   # pending | approved | rejected
    reviewer_notes:  Optional[str] = None
    created_at:      str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Week 4 Day 2 — Feedback Loop ─────────────────────────────────────────
class PostPerformance(BaseModel):
    post_id:         str
    platform:        Platform
    content_snippet: str
    likes:           int = 0
    shares:          int = 0
    comments:        int = 0
    impressions:     int = 0
    engagement_rate: float = 0.0
    posted_at:       str = ""
