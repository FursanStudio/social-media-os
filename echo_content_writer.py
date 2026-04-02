# echo_content_writer.py
# All platform writers: LinkedIn, X, Instagram, Facebook, TikTok
# Uses Claude API (Anthropic) as primary, Groq as fallback

import os, json, re
from dotenv import load_dotenv
load_dotenv()

# ── AI Client: Claude first, Groq fallback ────────────────
def _llm(prompt: str, temperature: float = 0.7) -> str:
    # Try Claude (Anthropic) first
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        try:
            import anthropic
            c = anthropic.Anthropic(api_key=anthropic_key)
            msg = c.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = msg.content[0].text.strip()
            raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
            return raw
        except Exception as e:
            print(f"[Writer] Claude error: {e}, falling back to Groq")

    # Fallback: Groq
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        raise Exception("No AI key found. Add ANTHROPIC_API_KEY or GROQ_API_KEY to .env")
    from groq import Groq
    c = Groq(api_key=groq_key)
    r = c.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=2000
    )
    raw = r.choices[0].message.content.strip()
    return re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()


def _rag(topic: str, brand: str) -> str:
    try:
        from echo_brand_memory import build_rag_context
        return build_rag_context(topic, brand)
    except Exception:
        return ""


# ── LinkedIn ──────────────────────────────────────────────
def write_linkedin_post(topic: str, brand_name: str, industry: str) -> dict:
    rag = _rag(topic, brand_name)
    result = _llm(f"""{rag}
You are a LinkedIn expert writing for {brand_name} ({industry} industry).
Topic: {topic}

Write a professional LinkedIn post (200-300 words).
Return ONLY raw JSON (no markdown fences):
{{
  "hook": "One powerful opening sentence",
  "body": "3-4 professional paragraphs with insights",
  "insight": "One unique data point or opinion",
  "cta": "Engaging closing question or call to action",
  "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}""", 0.7)
    return json.loads(result)


# ── X / Twitter ───────────────────────────────────────────
def write_x_post(topic: str, brand_name: str, industry: str) -> dict:
    rag = _rag(topic, brand_name)
    result = _llm(f"""{rag}
You are a viral X (Twitter) copywriter for {brand_name} ({industry}).
Topic: {topic}

Write a punchy tweet. Total max 260 chars.
Return ONLY raw JSON:
{{
  "hook": "Scroll-stopping first line (max 80 chars)",
  "body": "Core insight (max 150 chars)",
  "cta": "Short action (max 40 chars)",
  "hashtags": ["tag1", "tag2", "tag3"]
}}""", 0.8)
    return json.loads(result)


# ── Instagram ─────────────────────────────────────────────
def write_instagram_post(topic: str, brand_name: str, industry: str) -> dict:
    rag = _rag(topic, brand_name)
    result = _llm(f"""{rag}
You are an Instagram content creator for {brand_name} ({industry}).
Topic: {topic}

Write an engaging Instagram post with emojis and storytelling.
Return ONLY raw JSON:
{{
  "caption": "Full Instagram caption with emojis (150-200 words, conversational, relatable)",
  "hook_line": "First line before 'more' button - must be attention-grabbing",
  "cta": "Call to action (comment, save, share, tag a friend)",
  "hashtags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10"],
  "story_idea": "One Instagram Story idea to complement this post"
}}""", 0.8)
    return json.loads(result)


# ── Facebook ──────────────────────────────────────────────
def write_facebook_post(topic: str, brand_name: str, industry: str) -> dict:
    rag = _rag(topic, brand_name)
    result = _llm(f"""{rag}
You are a Facebook community manager for {brand_name} ({industry}).
Topic: {topic}

Write a Facebook post that drives comments and shares.
Return ONLY raw JSON:
{{
  "post": "Full Facebook post (100-180 words). Conversational, community-focused, includes a question to drive comments)",
  "hook": "Opening line that appears in the preview",
  "question": "Engaging question at the end to drive comments",
  "hashtags": ["tag1", "tag2", "tag3"],
  "post_type": "Text with image / Poll / Event / Video suggestion"
}}""", 0.75)
    return json.loads(result)


# ── TikTok Script ─────────────────────────────────────────
def write_tiktok_script(topic: str, brand_name: str, industry: str) -> dict:
    result = _llm(f"""You are a TikTok content strategist for {brand_name} ({industry}).
Topic: {topic}

Write a TikTok video script outline.
Return ONLY raw JSON:
{{
  "hook": "First 3 seconds hook text (spoken or on-screen text)",
  "script": "30-60 second script broken into sections",
  "on_screen_text": ["text overlay 1", "text overlay 2", "text overlay 3"],
  "cta": "End screen call to action",
  "hashtags": ["tag1","tag2","tag3","tag4","tag5"],
  "trending_audio_vibe": "Describe the type of trending audio to use"
}}""", 0.85)
    return json.loads(result)


# ── Image Prompts ─────────────────────────────────────────
def generate_image_prompts(post_text: str, platform: str = "Instagram") -> dict:
    result = _llm(f"""You are an AI image prompt engineer.
Based on this post, create optimized image generation prompts.

POST: {post_text[:500]}
PLATFORM: {platform}

Return ONLY raw JSON:
{{
  "dalle_prompt": "Detailed DALL-E 3 prompt, photorealistic, describe scene+lighting+composition (max 200 chars)",
  "midjourney_prompt": "Midjourney prompt with --ar 1:1 --style raw --v 6.1",
  "pollinations_url": "https://image.pollinations.ai/prompt/YOUR_PROMPT_HERE?model=flux-schnell&width=1080&height=1080",
  "style": "Visual style descriptor",
  "mood": "Emotional mood",
  "colors": ["color1", "color2", "color3"]
}}""", 0.6)
    data = json.loads(result)
    # Build actual pollinations URL
    prompt_clean = re.sub(r"[^\w\s,]", "", post_text[:80]).replace(" ", "+")
    data["pollinations_url"] = f"https://image.pollinations.ai/prompt/{prompt_clean}+professional+{platform}+marketing?model=flux-schnell&width=1080&height=1080&nologo=true"
    return data


# ── Social Pack (no URL needed) ───────────────────────────
def generate_social_pack(topic: str, brand_name: str, industry: str) -> dict:
    """
    Milestone 1 — Generate complete Social Pack from topic alone.
    Returns all 5 platforms + image prompts.
    """
    print(f"\n📦 Generating Social Pack for: {topic}")
    print(f"   Brand: {brand_name} | Industry: {industry}\n")

    pack = {"topic": topic, "brand_name": brand_name, "industry": industry}

    print("💼 Writing LinkedIn post...")
    pack["linkedin"] = write_linkedin_post(topic, brand_name, industry)

    print("𝕏  Writing X post...")
    pack["x_post"] = write_x_post(topic, brand_name, industry)

    print("📸 Writing Instagram post...")
    pack["instagram"] = write_instagram_post(topic, brand_name, industry)

    print("👥 Writing Facebook post...")
    pack["facebook"] = write_facebook_post(topic, brand_name, industry)

    print("🎵 Writing TikTok script...")
    pack["tiktok"] = write_tiktok_script(topic, brand_name, industry)

    print("🎨 Generating image prompts...")
    li = pack["linkedin"]
    combined = f"{li.get('hook','')} {li.get('body','')[:200]}"
    pack["image_prompts"] = generate_image_prompts(combined, "Instagram")

    score = min(100, 65 + len(li.get("hashtags", [])) * 3 + (8 if "?" in li.get("cta","") else 0))
    pack["brand_voice_score"] = score

    print(f"\n✅ Social Pack complete! Brand Voice Score: {score}/100")
    return pack


if __name__ == "__main__":
    import sys
    topic   = sys.argv[1] if len(sys.argv) > 1 else "sustainable dairy farming"
    brand   = sys.argv[2] if len(sys.argv) > 2 else "Aoraza"
    industry = sys.argv[3] if len(sys.argv) > 3 else "dairy"
    pack = generate_social_pack(topic, brand, industry)
    print(json.dumps(pack, indent=2))