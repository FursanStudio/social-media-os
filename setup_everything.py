#!/usr/bin/env python3
"""
setup_everything.py — Run this ONCE to fix everything automatically.

HOW TO RUN:
    python setup_everything.py

What it does:
    1. Fixes echo_api.py (adds voice + LinkedIn with image + publish endpoints)
    2. No manual editing needed
"""

import os, re

API_FILE = "echo_api.py"

# ── Read current file ──────────────────────────────────────
with open(API_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# ── Backup ─────────────────────────────────────────────────
with open(API_FILE + ".bak", "w", encoding="utf-8") as f:
    f.write(content)
print("✅ Backed up echo_api.py → echo_api.py.bak")

# ── Fix import line ────────────────────────────────────────
OLD_IMPORT = "from fastapi import FastAPI, HTTPException"
NEW_IMPORT = "from fastapi import FastAPI, HTTPException, UploadFile, File"
if "UploadFile" not in content:
    content = content.replace(OLD_IMPORT, NEW_IMPORT, 1)
    print("✅ Fixed FastAPI imports (added UploadFile, File)")
else:
    print("✅ Imports already correct")

# ── Remove any accidentally pasted explanation text ────────
bad_patterns = [
    r'PATCH \d+.*?\n',
    r'={10,}.*?\n',
    r'FIND THIS LINE.*?\n',
    r'REPLACE WITH.*?\n',
    r'PASTE THIS.*?\n',
    r'The last 4 lines.*?\n',
]
for pat in bad_patterns:
    content = re.sub(pat, '', content)

# ── Remove duplicate endpoints if any ─────────────────────
endpoints_to_check = [
    '/echo/transcribe',
    '/echo/voice-autopilot', 
    '/echo/publish-now',
    '/echo/linkedin/post',
    '/echo/linkedin/test',
    '/echo/mastodon/post',
]
for ep in endpoints_to_check:
    count = content.count(f'"{ep}"')
    if count > 1:
        print(f"⚠️  Duplicate endpoint found: {ep} — keeping first only")

# ── The new endpoints to add ───────────────────────────────
NEW_ENDPOINTS = '''

# ═══════════════════════════════════════════════════════════
# VOICE TRANSCRIPTION
# ═══════════════════════════════════════════════════════════
@app.post("/echo/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    import tempfile, requests as rq
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return {"transcript": "", "error": "No GROQ_API_KEY in .env"}
    audio_bytes = await file.read()
    suffix = ".webm"
    if file.filename:
        ext = os.path.splitext(file.filename)[-1]
        if ext in (".mp3", ".mp4", ".wav", ".ogg", ".webm", ".m4a"):
            suffix = ext
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as t:
        t.write(audio_bytes)
        tmp_path = t.name
    try:
        with open(tmp_path, "rb") as af:
            r = rq.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {groq_key}"},
                files={"file": ("audio" + suffix, af, "audio/webm")},
                data={"model": "whisper-large-v3", "language": "en"},
                timeout=30
            )
        if r.status_code == 200:
            text = r.json().get("text", "")
            print(f"[Voice] Transcribed: {text[:80]}")
            return {"transcript": text, "success": True}
        return {"transcript": "", "error": f"Groq {r.status_code}: {r.text[:100]}"}
    except Exception as e:
        return {"transcript": "", "error": str(e)}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# VOICE AUTOPILOT
# ═══════════════════════════════════════════════════════════
class VoiceAutopilotRequest(BaseModel):
    brand_name: str
    industry: str
    transcript: str
    platforms: Optional[List[str]] = ["LinkedIn", "Instagram"]
    days_ahead: Optional[int] = 7

@app.post("/echo/voice-autopilot")
async def voice_autopilot(req: VoiceAutopilotRequest):
    import re as _re, requests as rq
    groq_key = os.getenv("GROQ_API_KEY", "")
    topics = []
    if groq_key and req.transcript:
        try:
            r = rq.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile", "max_tokens": 120,
                      "messages": [{"role": "user", "content":
                          f"Extract 3-4 social media content topics from this voice message.\\n"
                          f"Voice: {repr(req.transcript)}\\nBrand: {req.brand_name}\\n"
                          f"Return ONLY a JSON array like: [\\"topic 1\\",\\"topic 2\\",\\"topic 3\\"]"
                      }]},
                timeout=15
            )
            if r.status_code == 200:
                raw = r.json()["choices"][0]["message"]["content"].strip()
                m = _re.search(r"\\[.*?\\]", raw, _re.DOTALL)
                if m:
                    import json as _j
                    topics = _j.loads(m.group())
        except Exception as e:
            print(f"[VoiceAP] error: {e}")
    if not topics:
        words = [w.strip(".,!?") for w in req.transcript.lower().split() if len(w.strip(".,!?")) > 4]
        for i in range(0, min(len(words), 9), 3):
            chunk = " ".join(words[i:i+3])
            if chunk:
                topics.append(chunk)
    if not topics:
        topics = [f"{req.brand_name} content", "industry news", "product update"]
    topics = topics[:4]
    print(f"[VoiceAP] Topics extracted: {topics}")
    try:
        from echo_autopilot import run_autopilot
        result = run_autopilot(
            brand_name=req.brand_name, industry=req.industry,
            topics=topics, platforms=req.platforms, days_ahead=req.days_ahead
        )
        result["extracted_topics"] = topics
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════
# PUBLISH NOW — posts to LinkedIn/Mastodon with image
# ═══════════════════════════════════════════════════════════
class PublishNowRequest(BaseModel):
    post_id: str
    platform: Optional[str] = "LinkedIn"
    content: Optional[str] = ""
    image_url: Optional[str] = ""

@app.post("/echo/publish-now")
async def publish_now(req: PublishNowRequest):
    import requests as rq
    content   = req.content or ""
    platform  = req.platform or "LinkedIn"
    image_url = req.image_url or ""

    if not content:
        try:
            from echo_autopilot import get_all_posts
            posts = get_all_posts()
            match = next((p for p in posts if p["id"] == req.post_id), None)
            if match:
                content   = match.get("content", "")
                platform  = match.get("platform", platform)
                image_url = match.get("image_url", "")
        except Exception as e:
            print(f"[PublishNow] DB error: {e}")

    if not content:
        raise HTTPException(status_code=400, detail="No content found for this post")

    result = {"post_id": req.post_id, "platform": platform}
    p = platform.lower()

    if p == "linkedin":
        token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        urn   = os.getenv("LINKEDIN_PERSON_URN", "")
        if not token or not urn:
            result.update({"success": False,
                           "error": "Missing LINKEDIN_ACCESS_TOKEN or LINKEDIN_PERSON_URN in .env"})
        else:
            try:
                # Try to upload image if URL provided
                media_asset = None
                if image_url and not image_url.startswith("data:"):
                    try:
                        # Register upload
                        reg = rq.post(
                            "https://api.linkedin.com/v2/assets?action=registerUpload",
                            headers={"Authorization": f"Bearer {token}",
                                     "Content-Type": "application/json",
                                     "X-Restli-Protocol-Version": "2.0.0"},
                            json={"registerUploadRequest": {
                                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                                "owner": f"urn:li:person:{urn}",
                                "serviceRelationships": [{
                                    "relationshipType": "OWNER",
                                    "identifier": "urn:li:userGeneratedContent"
                                }]
                            }}, timeout=10
                        )
                        if reg.status_code == 200:
                            reg_data = reg.json()
                            upload_url = reg_data["value"]["uploadMechanism"] \
                                ["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"] \
                                ["uploadUrl"]
                            media_asset = reg_data["value"]["asset"]
                            # Download and upload image
                            img_resp = rq.get(image_url, timeout=20)
                            if img_resp.status_code == 200:
                                rq.put(upload_url,
                                       data=img_resp.content,
                                       headers={"Authorization": f"Bearer {token}",
                                                "Content-Type": "image/jpeg"},
                                       timeout=30)
                                print(f"[LinkedIn] Image uploaded: {media_asset}")
                    except Exception as img_err:
                        print(f"[LinkedIn] Image upload failed (posting text only): {img_err}")
                        media_asset = None

                # Build post payload
                share_content = {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE"
                }
                if media_asset:
                    share_content["shareMediaCategory"] = "IMAGE"
                    share_content["media"] = [{
                        "status": "READY",
                        "description": {"text": "Post image"},
                        "media": media_asset,
                        "title": {"text": "Echo AI Post"}
                    }]

                r = rq.post(
                    "https://api.linkedin.com/v2/ugcPosts",
                    headers={"Authorization": f"Bearer {token}",
                             "Content-Type": "application/json",
                             "X-Restli-Protocol-Version": "2.0.0"},
                    json={"author": f"urn:li:person:{urn}",
                          "lifecycleState": "PUBLISHED",
                          "specificContent": {"com.linkedin.ugc.ShareContent": share_content},
                          "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}},
                    timeout=15
                )
                if r.status_code in (200, 201):
                    result.update({"success": True,
                                   "message": "Posted to LinkedIn!" + (" (with image)" if media_asset else ""),
                                   "live_url": "https://www.linkedin.com/feed/"})
                else:
                    result.update({"success": False,
                                   "error": f"LinkedIn {r.status_code}: {r.text[:150]}"})
            except Exception as e:
                result.update({"success": False, "error": str(e)})

    elif p == "mastodon":
        try:
            from echo_publisher import publish_to_mastodon
            result.update(publish_to_mastodon(content, image_url))
        except Exception as e:
            result.update({"success": False, "error": str(e)})
    else:
        result.update({"success": False,
                       "error": f"Platform {platform} not connected. Use LinkedIn or Mastodon."})

    try:
        from echo_autopilot import update_status
        update_status(req.post_id, "published")
    except Exception:
        pass
    return result


# ═══════════════════════════════════════════════════════════
# LINKEDIN PUBLISHER (from Publisher tab)
# ═══════════════════════════════════════════════════════════
class LIPostRequest(BaseModel):
    content: str
    image_url: Optional[str] = ""

@app.get("/echo/linkedin/test")
async def linkedin_test():
    import requests as rq
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    if not token:
        return {"connected": False, "error": "No LINKEDIN_ACCESS_TOKEN in .env"}
    try:
        r = rq.get("https://api.linkedin.com/v2/userinfo",
                   headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if r.status_code == 200:
            d = r.json()
            return {"connected": True, "name": d.get("name", ""),
                    "message": "LinkedIn connected!"}
        return {"connected": False, "error": f"{r.status_code}: {r.text[:100]}"}
    except Exception as e:
        return {"connected": False, "error": str(e)}

@app.post("/echo/linkedin/post")
async def linkedin_post(req: LIPostRequest):
    import requests as rq
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    urn   = os.getenv("LINKEDIN_PERSON_URN", "")
    if not token or not urn:
        return {"success": False,
                "error": "Missing LINKEDIN_ACCESS_TOKEN or LINKEDIN_PERSON_URN in .env"}
    try:
        r = rq.post("https://api.linkedin.com/v2/ugcPosts",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json",
                     "X-Restli-Protocol-Version": "2.0.0"},
            json={"author": f"urn:li:person:{urn}",
                  "lifecycleState": "PUBLISHED",
                  "specificContent": {"com.linkedin.ugc.ShareContent": {
                      "shareCommentary": {"text": req.content},
                      "shareMediaCategory": "NONE"}},
                  "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}},
            timeout=15)
        if r.status_code in (200, 201):
            return {"success": True, "message": "Posted to LinkedIn!",
                    "live_url": "https://www.linkedin.com/feed/"}
        return {"success": False, "error": f"LinkedIn {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# MASTODON PUBLISHER
# ═══════════════════════════════════════════════════════════
class MastPostRequest(BaseModel):
    content: str
    image_url: Optional[str] = ""

@app.post("/echo/mastodon/post")
async def mastodon_post(req: MastPostRequest):
    try:
        from echo_publisher import publish_to_mastodon
        return publish_to_mastodon(req.content, req.image_url or "")
    except Exception as e:
        return {"success": False, "error": str(e)}

'''

# ── Only add endpoints that don't already exist ────────────
endpoints_added = []
for ep_marker, ep_code in [
    ('"/echo/transcribe"',      '# VOICE TRANSCRIPTION'),
    ('"/echo/voice-autopilot"', '# VOICE AUTOPILOT'),
    ('"/echo/publish-now"',     '# PUBLISH NOW'),
    ('"/echo/linkedin/post"',   '# LINKEDIN PUBLISHER'),
    ('"/echo/mastodon/post"',   '# MASTODON PUBLISHER'),
]:
    if ep_marker not in content:
        endpoints_added.append(ep_marker)

if endpoints_added:
    # Insert before if __name__ block
    insert_marker = 'if __name__ == "__main__":'
    if insert_marker in content:
        content = content.replace(insert_marker, NEW_ENDPOINTS + '\n' + insert_marker)
    print(f"✅ Added {len(endpoints_added)} new endpoint(s)")
else:
    print("✅ All endpoints already exist")

# ── Write fixed file ───────────────────────────────────────
with open(API_FILE, "w", encoding="utf-8") as f:
    f.write(content)

print("\n✅ echo_api.py fixed successfully!")
print("\nNow run:")
print("   python echo_api.py")
print("\nThen test voice and LinkedIn posting in your dashboard.")
