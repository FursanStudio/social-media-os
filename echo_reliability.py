# echo_reliability.py — Week 3 (All 5 Days)
# Brand Safety Judge + Comment Triage + LangSmith observability

import os, json, re, uuid
from typing import List
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from echo_models import BrandSafetyResult, TriagedComment, CommentCategory

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Week 3 Day 1 — LangSmith Observability ───────────────────────────────
try:
    from langsmith import Client as LangSmithClient
    from langsmith import traceable
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"]    = os.getenv("LANGSMITH_API_KEY", "")
    os.environ["LANGCHAIN_PROJECT"]    = "Echo-Brand-Strategist"
    ls_client = LangSmithClient()
    USE_LANGSMITH = True
    print("[Reliability] ✅ LangSmith tracing enabled")
except Exception:
    USE_LANGSMITH = False
    print("[Reliability] ⚠️  LangSmith not available — tracing disabled")
    def traceable(func=None, **kwargs):  # no-op decorator
        def decorator(f): return f
        return decorator if func is None else func


def _llm(prompt: str, temperature: float = 0.3) -> str:
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature, max_tokens=1500
    )
    raw = resp.choices[0].message.content.strip()
    return re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")


# ── Week 3 Day 3 — Brand Safety Judge ────────────────────────────────────
@traceable(name="brand_safety_check")
def check_brand_safety(content: str, brand_name: str, industry: str) -> BrandSafetyResult:
    """
    Run every post through a safety check before it enters the approval queue.
    Catches: controversial claims, competitor mentions, misleading data,
    political/religious content, legal risks.
    """
    prompt = f"""You are a brand safety compliance officer for {brand_name} in {industry}.
Review this social media post for safety risks.

POST CONTENT:
{content}

Check for:
1. Controversial or politically charged statements
2. Unverifiable health/medical claims
3. Competitor brand mentions
4. Legal risk phrases ("guaranteed", "best in world", "100% proven")
5. Offensive or discriminatory language
6. Misleading statistics

Return ONLY valid JSON:
{{
  "is_safe": true,
  "safety_score": 85,
  "flags": ["issue1 if any"],
  "controversial_phrases": ["exact phrase from post if any"],
  "recommendation": "One sentence: approve, revise, or reject + reason"
}}

If no issues found, return is_safe: true, safety_score: 90+, empty arrays."""

    result = json.loads(_llm(prompt, 0.1))
    return BrandSafetyResult(**result)


def bulk_safety_check(posts: List[str], brand_name: str, industry: str) -> List[dict]:
    """
    Week 3 Day 3 — Run last 50 drafts through safety judge.
    Returns list with safety scores attached to each post.
    """
    print(f"\n🛡️  Running brand safety check on {len(posts)} posts...")
    results = []
    for i, post in enumerate(posts, 1):
        safety = check_brand_safety(post, brand_name, industry)
        results.append({
            "post_preview": post[:100] + "...",
            "is_safe":      safety.is_safe,
            "score":        safety.safety_score,
            "flags":        safety.flags,
            "recommendation": safety.recommendation
        })
        status = "✅" if safety.is_safe else "⚠️ "
        print(f"  [{i}/{len(posts)}] {status} Score: {safety.safety_score} | {safety.recommendation[:60]}")
    return results


# ── Week 3 Day 4 — Comment Triage ────────────────────────────────────────
@traceable(name="comment_triage")
def triage_comment(comment: str, brand_name: str) -> TriagedComment:
    """
    Reads a comment and categorizes it: Support | Troll | Lead | Question | Neutral
    Then generates a suggested reply.
    """
    prompt = f"""You are a community manager for {brand_name}.
Triage this social media comment.

COMMENT: "{comment}"

Categories:
- Support: positive feedback, praise, loyalty
- Troll: harassment, spam, deliberately provocative
- Lead: buying intent, asking about products/pricing/availability
- Question: genuine question needing an answer
- Neutral: generic comment, no action needed

Return ONLY valid JSON:
{{
  "original_comment": "{comment}",
  "category": "Lead",
  "sentiment": "positive/negative/neutral",
  "priority": 4,
  "suggested_reply": "A personalized, on-brand reply to this comment",
  "escalate": false
}}

Priority: 1=ignore, 2=low, 3=normal, 4=high, 5=urgent
Escalate=true for: legal threats, crisis PR, explicit complaints."""

    result = json.loads(_llm(prompt, 0.3))
    result["original_comment"] = comment
    return TriagedComment(**result)


def triage_comments_batch(comments: List[str], brand_name: str) -> List[TriagedComment]:
    """Process multiple comments and return sorted by priority."""
    print(f"\n💬 Triaging {len(comments)} comments for {brand_name}...")
    results = []
    for comment in comments:
        t = triage_comment(comment, brand_name)
        icon = {"Support": "💚", "Troll": "🚫", "Lead": "💰", "Question": "❓", "Neutral": "⚪"}.get(t.category, "•")
        print(f"  {icon} [{t.category}] P{t.priority} | {comment[:50]}...")
        results.append(t)
    return sorted(results, key=lambda x: x.priority, reverse=True)


# ── Week 3 Day 2+5 — HITL Approval Queue ─────────────────────────────────
class ApprovalQueue:
    """In-memory approval queue (backed by JSON file). Week 3 Milestone."""

    def __init__(self, queue_file: str = "approval_queue.json"):
        self.file = queue_file
        self._load()

    def _load(self):
        try:
            with open(self.file) as f:
                self.queue = json.load(f)
        except Exception:
            self.queue = []

    def _save(self):
        with open(self.file, "w") as f:
            json.dump(self.queue, f, indent=2)

    def add_post(self, platform: str, content: str, brand_name: str,
                 industry: str, image_url: str = "") -> str:
        """Add a post to the queue with safety score attached."""
        safety   = check_brand_safety(content, brand_name, industry)
        post_id  = str(uuid.uuid4())[:8]
        item = {
            "post_id":    post_id,
            "platform":   platform,
            "content":    content,
            "image_url":  image_url,
            "safety_score":    safety.safety_score,
            "safety_flags":    safety.flags,
            "safety_recommendation": safety.recommendation,
            "status":     "pending",
            "created_at": datetime.now().isoformat()
        }
        self.queue.append(item)
        self._save()
        icon = "✅" if safety.is_safe else "⚠️ "
        print(f"  [Queue] {icon} Added post {post_id} | Safety: {safety.safety_score}/100")
        return post_id

    def approve(self, post_id: str, notes: str = "") -> bool:
        for item in self.queue:
            if item["post_id"] == post_id:
                item["status"] = "approved"
                item["reviewer_notes"] = notes
                item["approved_at"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    def reject(self, post_id: str, notes: str = "") -> bool:
        for item in self.queue:
            if item["post_id"] == post_id:
                item["status"] = "rejected"
                item["reviewer_notes"] = notes
                self._save()
                return True
        return False

    def get_pending(self) -> List[dict]:
        return [i for i in self.queue if i["status"] == "pending"]

    def print_queue(self):
        """Week 3 Milestone 3 — Print the approval dashboard."""
        pending = self.get_pending()
        print(f"\n{'='*65}")
        print(f"  📋 APPROVAL QUEUE — {len(pending)} posts waiting")
        print(f"{'='*65}")
        for i, item in enumerate(pending, 1):
            score = item.get("safety_score", 0)
            bar   = "█" * (score // 10) + "░" * (10 - score // 10)
            flag  = "🟢" if score >= 80 else ("🟡" if score >= 60 else "🔴")
            print(f"\n  [{i}] Post ID: {item['post_id']} | Platform: {item['platform']}")
            print(f"      Safety: {flag} {score}/100  [{bar}]")
            print(f"      Content: {item['content'][:80]}...")
            if item.get("safety_flags"):
                print(f"      ⚠️  Flags: {', '.join(item['safety_flags'])}")
            print(f"      📝 {item.get('safety_recommendation','')[:80]}")
        print(f"\n{'='*65}")
        print(f"  Commands: queue.approve('post_id') / queue.reject('post_id')")
        print(f"{'='*65}\n")


# ── CLI demo ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    brand, industry = "Aoraza", "dairy"

    # Demo: triage comments
    test_comments = [
        "Where can I buy your milk? Do you ship to Lahore?",
        "This is the worst product I've ever tried. Complete scam!",
        "Love your brand! Been a customer for 3 years 💚",
        "Are you guys using sustainable packaging?",
        "spam spam buy cheap followers click here"
    ]
    triaged = triage_comments_batch(test_comments, brand)
    print("\n── Top Priority Comments ──")
    for t in triaged[:3]:
        print(f"  [{t.category}] {t.suggested_reply[:100]}")

    # Demo: approval queue
    queue = ApprovalQueue()
    queue.add_post("LinkedIn",
                   "🌱 Sustainable dairy starts with us. Aoraza cut packaging waste by 40% this year.",
                   brand, industry)
    queue.print_queue()
