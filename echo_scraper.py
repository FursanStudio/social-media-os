# echo_scraper.py — Week 1 Day 1
# Scrape any URL → extract structured talking points via Groq

import os, json, re, requests
from dotenv import load_dotenv
from groq import Groq
from echo_models import ScrapedContent

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
FIRECRAWL_KEY = os.getenv("FIRECRAWL_API_KEY", "")


def scrape_with_firecrawl(url: str) -> str | None:
    if not FIRECRAWL_KEY:
        return None
    try:
        r = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {FIRECRAWL_KEY}",
                     "Content-Type": "application/json"},
            json={"url": url, "formats": ["markdown"]},
            timeout=30
        )
        data = r.json()
        if data.get("success"):
            return data["data"].get("markdown", "")
    except Exception as e:
        print(f"[Firecrawl] {e}")
    return None


def scrape_basic(url: str) -> str:
    """Fallback when Firecrawl key not set."""
    try:
        r = requests.get(url, timeout=15,
                         headers={"User-Agent": "Mozilla/5.0"})
        text = re.sub(r"<[^>]+>", " ", r.text)
        return re.sub(r"\s+", " ", text)[:8000]
    except Exception as e:
        return f"Could not fetch URL: {e}"


def extract_talking_points(url: str, brand_industry: str = "general") -> ScrapedContent:
    """
    Week 1 Day 1 — Scrape URL and return structured ScrapedContent.
    Usage: result = extract_talking_points("https://...", "dairy")
    """
    raw = scrape_with_firecrawl(url) or scrape_basic(url)

    prompt = f"""You are a content research analyst for a {brand_industry} brand.
Analyze this article and extract structured talking points.

URL: {url}
CONTENT:
{raw[:5000]}

Return ONLY valid JSON with this exact structure — no markdown fences:
{{
  "url": "{url}",
  "title": "Article title",
  "talking_points": [
    {{
      "headline": "Key point",
      "summary": "Two sentence summary.",
      "relevance": "Why this matters to {brand_industry} brands.",
      "keywords": ["word1", "word2"]
    }}
  ],
  "overall_theme": "One sentence theme",
  "trending_score": 75
}}
Include 3-5 talking_points."""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2, max_tokens=2000
    )
    raw_json = resp.choices[0].message.content.strip()
    raw_json = re.sub(r"```(?:json)?", "", raw_json).strip().rstrip("`")
    return ScrapedContent(**json.loads(raw_json))


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://techcrunch.com"
    industry = sys.argv[2] if len(sys.argv) > 2 else "technology"
    result = extract_talking_points(url, industry)
    print(result.model_dump_json(indent=2))
