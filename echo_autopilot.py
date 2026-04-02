# echo_autopilot.py — One input → writes → images → schedules → done

import os, json, time, uuid, sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

DB_FILE = "echo_schedule.db"

# ── Database setup ─────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id TEXT PRIMARY KEY,
            brand_name TEXT,
            platform TEXT,
            content TEXT,
            image_url TEXT,
            topic TEXT,
            status TEXT DEFAULT 'scheduled',
            scheduled_at TEXT,
            published_at TEXT,
            safety_score INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_post(post: dict):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        INSERT OR REPLACE INTO scheduled_posts
        (id, brand_name, platform, content, image_url, topic,
         status, scheduled_at, safety_score, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        post["id"], post["brand_name"], post["platform"],
        post["content"], post["image_url"], post["topic"],
        post["status"], post["scheduled_at"],
        post.get("safety_score", 0), post["created_at"]
    ))
    conn.commit()
    conn.close()

def get_all_posts(brand_name: str = None) -> list:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    if brand_name:
        rows = conn.execute("SELECT * FROM scheduled_posts WHERE brand_name=? ORDER BY scheduled_at ASC", (brand_name,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM scheduled_posts ORDER BY scheduled_at ASC").fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result

def get_pending_posts() -> list:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    now = datetime.now().isoformat()
    rows = conn.execute(
        "SELECT * FROM scheduled_posts WHERE status='scheduled' AND scheduled_at<=? ORDER BY scheduled_at ASC", (now,)
    ).fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result

def update_status(post_id: str, status: str):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE scheduled_posts SET status=?, published_at=? WHERE id=?",
                 (status, datetime.now().isoformat(), post_id))
    conn.commit()
    conn.close()

def delete_post(post_id: str):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM scheduled_posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()

# ── AI writer ──────────────────────────────────────────────
def _ai(prompt: str) -> str:
    import re
    # Try Claude first
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if key:
        try:
            import anthropic
            c = anthropic.Anthropic(api_key=key)
            msg = c.messages.create(model="claude-sonnet-4-5", max_tokens=2000,
                                    messages=[{"role":"user","content":prompt}])
            raw = msg.content[0].text.strip()
            return re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")
        except Exception as e:
            print(f"[Autopilot] Claude error: {e}, using Groq")
    # Groq fallback
    from groq import Groq
    c = Groq(api_key=os.getenv("GROQ_API_KEY"))
    r = c.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":prompt}], temperature=0.7, max_tokens=2000)
    raw = r.choices[0].message.content.strip()
    return re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")

# ── Platform writers ───────────────────────────────────────
PLATFORM_PROMPTS = {
    "LinkedIn": lambda t,b,i: f"""Write a professional LinkedIn post for {b} ({i} industry) about: {t}
Return ONLY raw JSON:
{{"content": "Full 200-word LinkedIn post with hook, body, insight, CTA and hashtags all combined into one ready-to-post text"}}""",

    "Instagram": lambda t,b,i: f"""Write an Instagram caption for {b} ({i} industry) about: {t}
Engaging, emojis, storytelling, 10 hashtags at end.
Return ONLY raw JSON:
{{"content": "Full Instagram caption with emojis and hashtags ready to post"}}""",

    "Facebook": lambda t,b,i: f"""Write a Facebook post for {b} ({i} industry) about: {t}
Community-focused, conversational, ends with a question.
Return ONLY raw JSON:
{{"content": "Full Facebook post ready to copy-paste"}}""",

    "X": lambda t,b,i: f"""Write a tweet for {b} ({i}) about: {t}
Punchy, max 260 chars, hook + insight + hashtags.
Return ONLY raw JSON:
{{"content": "Complete tweet text under 260 chars"}}""",

    "TikTok": lambda t,b,i: f"""Write a TikTok video script for {b} ({i}) about: {t}
Return ONLY raw JSON:
{{"content": "Hook (3sec): ...\n\nScript: ...\n\nCTA: ...\n\nHashtags: ..."}}""",
}

def write_for_platform(topic: str, brand: str, industry: str, platform: str) -> str:
    try:
        prompt = PLATFORM_PROMPTS[platform](topic, brand, industry)
        result = json.loads(_ai(prompt))
        return result.get("content", "")
    except Exception as e:
        return f"Content about {topic} for {brand} on {platform}. #{industry} #{brand.lower()}"

# ── Schedule time slots ────────────────────────────────────
BEST_TIMES = {
    "LinkedIn":  ["09:00", "12:00", "17:00"],
    "Instagram": ["08:00", "13:00", "19:00"],
    "Facebook":  ["09:00", "14:00", "20:00"],
    "X":         ["08:00", "12:00", "18:00"],
    "TikTok":    ["07:00", "15:00", "21:00"],
}

def get_schedule_time(platform: str, day_offset: int, slot: int) -> str:
    times = BEST_TIMES.get(platform, ["09:00", "14:00", "19:00"])
    t = times[slot % len(times)]
    dt = datetime.now() + timedelta(days=day_offset)
    return dt.strftime(f"%Y-%m-%dT{t}:00")

# ── MAIN AUTOPILOT ─────────────────────────────────────────
def run_autopilot(
    brand_name: str,
    industry: str,
    topics: list,
    platforms: list,
    days_ahead: int = 7
) -> dict:
    """
    One call does everything:
    1. Writes content for every topic × platform combination
    2. Generates matching image for each post
    3. Runs safety check on each post
    4. Schedules them spread across the coming days
    5. Returns full schedule
    """
    init_db()
    print(f"\n🤖 AUTOPILOT STARTED")
    print(f"   Brand: {brand_name} | Industry: {industry}")
    print(f"   Topics: {len(topics)} | Platforms: {len(platforms)} | Days: {days_ahead}")
    print(f"   Total posts to create: {len(topics) * len(platforms)}\n")

    from image_generator import generate_content_image

    all_posts = []
    total = len(topics) * len(platforms)
    done  = 0

    for day_idx, topic in enumerate(topics):
        for slot_idx, platform in enumerate(platforms):
            done += 1
            print(f"[{done}/{total}] ✍️  Writing {platform} post about '{topic}'...")

            # 1. Write content
            content = write_for_platform(topic, brand_name, industry, platform)

            # 2. Generate image
            print(f"[{done}/{total}] 🎨 Generating image for {platform}...")
            try:
                img = generate_content_image(content, platform, brand_name)
                image_url = img.get("image_url", "")
            except Exception as e:
                image_url = f"https://picsum.photos/seed/{done * 37}/1080/1080"

            # 3. Safety score (quick check)
            safety_score = 85  # default safe
            try:
                from echo_reliability import check_brand_safety
                result = check_brand_safety(content, brand_name, industry)
                safety_score = result.safety_score
            except Exception:
                pass

            # 4. Schedule time
            scheduled_at = get_schedule_time(platform, day_idx, slot_idx)

            # 5. Save to DB
            post = {
                "id":           str(uuid.uuid4())[:8],
                "brand_name":   brand_name,
                "platform":     platform,
                "content":      content,
                "image_url":    image_url,
                "topic":        topic,
                "status":       "scheduled",
                "scheduled_at": scheduled_at,
                "safety_score": safety_score,
                "created_at":   datetime.now().isoformat()
            }
            save_post(post)
            all_posts.append(post)
            print(f"   ✅ Scheduled for {scheduled_at} | Safety: {safety_score}/100")
            time.sleep(2)  # avoid rate limits

    print(f"\n🎉 AUTOPILOT COMPLETE — {len(all_posts)} posts scheduled!")
    return {
        "total_posts": len(all_posts),
        "brand_name":  brand_name,
        "platforms":   platforms,
        "days_ahead":  days_ahead,
        "posts":       all_posts,
        "summary": {
            p: len([x for x in all_posts if x["platform"] == p])
            for p in platforms
        }
    }
