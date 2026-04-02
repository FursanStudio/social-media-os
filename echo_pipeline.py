# echo_pipeline.py — Week 2 (All 5 Days)
# LangGraph workflow: TrendScraper → Writer → Editor → ImageGen
# Redis state persistence + A/B headline debate + daily content machine

import os, json, time, uuid, re
from typing import TypedDict, Optional, List
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Try LangGraph, fallback to manual sequential pipeline ────────────────
try:
    from langgraph.graph import StateGraph, END
    USE_LANGGRAPH = True
    print("[Pipeline] ✅ LangGraph loaded")
except ImportError:
    USE_LANGGRAPH = False
    print("[Pipeline] ⚠️  LangGraph not installed — using sequential fallback")
    print("[Pipeline]    Install with: pip install langgraph")

# ── Try Redis, fallback to file-based state ───────────────────────────────
try:
    import redis
    r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
    r.ping()
    USE_REDIS = True
    print("[Pipeline] ✅ Redis connected")
except Exception:
    USE_REDIS = False
    print("[Pipeline] ⚠️  Redis offline — using file-based state")

STATE_FILE = "pipeline_state.json"


# ── Week 2 Day 3 — State Persistence ─────────────────────────────────────
def save_state(job_id: str, state: dict):
    """Save pipeline state so we can resume from any step on failure."""
    if USE_REDIS:
        r.setex(f"echo:job:{job_id}", 3600, json.dumps(state))
    else:
        existing = {}
        try:
            with open(STATE_FILE) as f:
                existing = json.load(f)
        except Exception:
            pass
        existing[job_id] = state
        with open(STATE_FILE, "w") as f:
            json.dump(existing, f, indent=2)


def load_state(job_id: str) -> Optional[dict]:
    """Resume a pipeline from saved state."""
    if USE_REDIS:
        data = r.get(f"echo:job:{job_id}")
        return json.loads(data) if data else None
    try:
        with open(STATE_FILE) as f:
            return json.load(f).get(job_id)
    except Exception:
        return None


# ── Pipeline State Schema (Week 2 Day 1) ─────────────────────────────────
class PipelineState(TypedDict):
    job_id:        str
    url:           str
    brand_name:    str
    industry:      str
    scraped:       Optional[dict]
    linkedin_post: Optional[dict]
    x_post:        Optional[dict]
    editor_notes:  Optional[str]
    image_url:     Optional[str]
    image_prompt:  Optional[str]
    errors:        List[str]
    step:          str          # tracks which step we're on for Redis resume
    completed:     bool


def _llm(prompt: str, temperature: float = 0.7) -> str:
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature, max_tokens=1500
    )
    raw = resp.choices[0].message.content.strip()
    return re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")


# ── Node 1: Trend Scraper ─────────────────────────────────────────────────
def node_trend_scraper(state: PipelineState) -> PipelineState:
    print(f"[Node 1/4] 🔍 Scraping {state['url']}...")
    try:
        from echo_scraper import extract_talking_points
        scraped = extract_talking_points(state["url"], state["industry"])
        state["scraped"] = scraped.model_dump()
        state["step"] = "scraped"
        save_state(state["job_id"], state)
    except Exception as e:
        state["errors"].append(f"Scraper error: {e}")
        state["scraped"] = {"overall_theme": f"Content about {state['industry']}", "talking_points": []}
    return state


# ── Node 2: Writer ────────────────────────────────────────────────────────
def node_writer(state: PipelineState) -> PipelineState:
    print("[Node 2/4] ✍️  Writing content...")
    theme = state.get("scraped", {}).get("overall_theme", state["industry"])
    try:
        from echo_content_writer import write_linkedin_post, write_x_post
        li = write_linkedin_post(theme, state["brand_name"], state["industry"])
        xp = write_x_post(theme, state["brand_name"], state["industry"])
        state["linkedin_post"] = li.model_dump()
        state["x_post"] = xp.model_dump()
        state["step"] = "written"
        save_state(state["job_id"], state)
    except Exception as e:
        state["errors"].append(f"Writer error: {e}")
    return state


# ── Node 3: Editor Critique Loop (Week 2 Day 2) ───────────────────────────
def node_editor(state: PipelineState) -> PipelineState:
    """
    Week 2 Day 2 — Self-correction loop.
    Editor checks for: hashtags, CTA, brand voice, no forbidden words.
    If issues found, rewrites automatically.
    """
    print("[Node 3/4] 📝 Editor reviewing content...")
    if not state.get("linkedin_post"):
        return state

    li = state["linkedin_post"]
    post_text = f"{li.get('hook','')} {li.get('body','')} {li.get('cta','')}"

    critique_prompt = f"""You are a senior social media editor. Review this LinkedIn post:

POST: {post_text}
HASHTAGS: {li.get('hashtags', [])}

Check ALL of these:
1. Does it have a clear CTA (question or action)?
2. Does it have 3-5 relevant hashtags?
3. Is the hook strong (first sentence grabs attention)?
4. Is there a unique insight or data point?
5. Is it free of salesy/spammy language?

Return JSON:
{{
  "passes": true/false,
  "issues": ["issue1", "issue2"],
  "improved_cta": "Better CTA if needed, else keep original",
  "improved_hook": "Better hook if needed, else keep original",
  "improved_hashtags": ["tag1", "tag2", "tag3", "tag4"]
}}"""

    try:
        result = json.loads(_llm(critique_prompt, 0.3))
        state["editor_notes"] = json.dumps(result.get("issues", []))

        if not result.get("passes", True):
            # Auto-fix the issues
            state["linkedin_post"]["cta"]      = result.get("improved_cta", li.get("cta", ""))
            state["linkedin_post"]["hook"]     = result.get("improved_hook", li.get("hook", ""))
            state["linkedin_post"]["hashtags"] = result.get("improved_hashtags", li.get("hashtags", []))
            print(f"  [Editor] Fixed {len(result.get('issues',[]))} issues automatically")
        else:
            print("  [Editor] ✅ Content passed quality check")

        state["step"] = "edited"
        save_state(state["job_id"], state)
    except Exception as e:
        state["errors"].append(f"Editor error: {e}")
    return state


# ── Node 4: Image Generator (with Redis retry logic) ─────────────────────
def node_image_gen(state: PipelineState) -> PipelineState:
    """
    Week 2 Day 3 — If image fails, Redis saves the text so we only retry image,
    not the whole pipeline.
    """
    print("[Node 4/4] 🎨 Generating image...")
    if state.get("image_url"):          # already have an image (resumed job)
        print("  [ImageGen] Skipping — image already generated")
        return state
    try:
        from image_generator import generate_content_image
        li = state.get("linkedin_post", {})
        content = f"{li.get('hook','')} {li.get('body','')[:200]}"
        result = generate_content_image(content, "LinkedIn", state["brand_name"])
        state["image_url"]    = result.get("image_url", "")
        state["image_prompt"] = result.get("prompt", "")
        state["step"] = "complete"
        state["completed"] = True
        save_state(state["job_id"], state)
        print(f"  [ImageGen] ✅ Image: {state['image_url']}")
    except Exception as e:
        state["errors"].append(f"ImageGen error: {e}")
        state["step"] = "image_failed"
        save_state(state["job_id"], state)  # save so only image is retried
    return state


# ── Week 2 Day 4 — A/B Headline Debate ───────────────────────────────────
def ab_headline_debate(topic: str, brand_name: str, industry: str) -> dict:
    """
    Two agents argue over which headline is more click-worthy.
    Returns winner with reasoning.
    """
    print(f"\n⚔️  A/B Headline Debate for: {topic}")

    # Agent 1 generates headline A
    a_prompt = f"""You are an aggressive growth-hacker copywriter.
Write ONE punchy LinkedIn headline for {brand_name} ({industry}) about: {topic}
Make it bold, controversial, data-driven. Max 15 words.
Return just the headline text, nothing else."""
    headline_a = _llm(a_prompt, 0.9).strip('"')

    # Agent 2 generates headline B
    b_prompt = f"""You are a thoughtful brand storyteller.
Write ONE warm, authentic LinkedIn headline for {brand_name} ({industry}) about: {topic}
Make it human, relatable, with emotional hook. Max 15 words.
Return just the headline text, nothing else."""
    headline_b = _llm(b_prompt, 0.8).strip('"')

    # Judge decides winner
    judge_prompt = f"""You are a social media performance analyst.
Two copywriters are debating which headline gets more clicks on LinkedIn.

HEADLINE A (growth-hacker style): "{headline_a}"
HEADLINE B (brand storyteller style): "{headline_b}"

Brand: {brand_name} | Industry: {industry} | Topic: {topic}

Analyze both and pick the winner based on:
- Scroll-stopping power
- Emotional hook
- Clarity
- Target audience fit

Return ONLY valid JSON:
{{
  "headline_a": "{headline_a}",
  "argument_a": "Why A works",
  "ctr_a": 0.045,
  "headline_b": "{headline_b}",
  "argument_b": "Why B works",
  "ctr_b": 0.038,
  "winner": "A or B",
  "reasoning": "Why this one wins",
  "confidence": 72
}}"""

    result = json.loads(_llm(judge_prompt, 0.3))
    winner_text = result["headline_a"] if result.get("winner") == "A" else result["headline_b"]
    print(f"  Winner: {result.get('winner')} — \"{winner_text}\"")
    print(f"  Reasoning: {result.get('reasoning','')}")
    return result


# ── Main Pipeline Runner ──────────────────────────────────────────────────
def run_pipeline(url: str, brand_name: str, industry: str,
                 resume_job_id: Optional[str] = None) -> dict:
    """
    Week 2 Day 1+3 — Run full pipeline with state persistence.
    Pass resume_job_id to continue a failed job from where it stopped.
    """
    job_id = resume_job_id or str(uuid.uuid4())[:8]

    # Try to resume from saved state
    if resume_job_id:
        saved = load_state(resume_job_id)
        if saved:
            print(f"[Pipeline] Resuming job {resume_job_id} from step: {saved.get('step')}")
            state = saved
        else:
            print(f"[Pipeline] No saved state for {resume_job_id}, starting fresh")
            resume_job_id = None

    if not resume_job_id:
        state: PipelineState = {
            "job_id": job_id, "url": url, "brand_name": brand_name,
            "industry": industry, "scraped": None, "linkedin_post": None,
            "x_post": None, "editor_notes": None, "image_url": None,
            "image_prompt": None, "errors": [], "step": "init", "completed": False
        }

    print(f"\n🚀 Echo Pipeline started — Job ID: {job_id}")
    start = time.time()

    # Run only missing steps (smart resume)
    current_step = state.get("step", "init")
    if current_step in ("init",):
        state = node_trend_scraper(state)
    if state.get("step") in ("scraped", "init") or not state.get("linkedin_post"):
        state = node_writer(state)
    if state.get("step") in ("written", "scraped") or not state.get("editor_notes"):
        state = node_editor(state)
    if not state.get("image_url") or state.get("step") == "image_failed":
        state = node_image_gen(state)

    elapsed = round(time.time() - start, 1)
    print(f"\n✅ Pipeline complete in {elapsed}s — Job: {job_id}")
    if state["errors"]:
        print(f"⚠️  Warnings: {state['errors']}")
    return state


# ── Week 2 Day 5 — Daily Content Machine ─────────────────────────────────
def run_daily_content_machine(brand_name: str, industry: str):
    """
    Milestone 2 — Finds one news story and prepares a vetted post draft
    without human intervention. Run this as a cron job every morning.
    """
    print(f"\n🤖 DAILY CONTENT MACHINE — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Brand: {brand_name} | Industry: {industry}\n")

    # Find trending URL for the industry
    try:
        import requests as req
        serper_key = os.getenv("SERPER_API_KEY", "")
        if serper_key:
            resp = req.post("https://google.serper.dev/news",
                           headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                           json={"q": f"{industry} industry news today", "num": 3},
                           timeout=10)
            news = resp.json().get("news", [])
            url = news[0]["link"] if news else f"https://www.google.com/search?q={industry}+industry+news"
        else:
            url = f"https://techcrunch.com"
    except Exception:
        url = f"https://techcrunch.com"

    # Run the full pipeline
    result = run_pipeline(url, brand_name, industry)

    # Save daily output
    filename = f"daily_output_{datetime.now().strftime('%Y%m%d')}.json"
    with open(filename, "w") as f:
        json.dump(result, f, indent=2)
    print(f"📁 Daily output saved: {filename}")
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        result = run_pipeline(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        result = run_daily_content_machine("Aoraza", "dairy")
    print(json.dumps({k: v for k, v in result.items() if k != "scraped"}, indent=2))
