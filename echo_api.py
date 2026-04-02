# echo_api.py — Echo v4.0 CLEAN — All endpoints, no duplicates

import os, json, re
from typing import Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Echo — Autonomous Brand Strategist v4", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Serve dashboard ────────────────────────────────────────
@app.get("/")
async def root():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"status": "Echo API v4 running", "docs": "/docs"}

# ══════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════
class ContentRequest(BaseModel):
    topic: str; brand_name: str; industry: str
    platform: Optional[str] = "LinkedIn"

class SocialPackRequest(BaseModel):
    topic: str; brand_name: str; industry: str

class AutoPilotRequest(BaseModel):
    brand_name: str; industry: str; topics: List[str]
    platforms: List[str] = ["LinkedIn", "Instagram", "Facebook", "X", "TikTok"]
    days_ahead: Optional[int] = 7

class CommentRequest(BaseModel):
    comment: str; brand_name: str

class CommentsRequest(BaseModel):
    comments: List[str]; brand_name: str

class SafetyRequest(BaseModel):
    content: str; brand_name: str; industry: str

class ApproveRequest(BaseModel):
    post_id: str; notes: Optional[str] = ""

class QueueAddRequest(BaseModel):
    platform: str; content: str; brand_name: str
    industry: str; image_url: Optional[str] = ""

class BrandMemRequest(BaseModel):
    brand_name: str; content: str; content_type: str = "post"

class ABTestRequest(BaseModel):
    topic: str; brand_name: str; industry: str

class ImageRequest(BaseModel):
    content: str
    platform: Optional[str] = "Instagram"
    brand_name: Optional[str] = ""

class ScheduleUpdateRequest(BaseModel):
    post_id: str; status: str

class VoiceAutopilotRequest(BaseModel):
    brand_name: str; industry: str
    transcript: str
    platforms: Optional[List[str]] = ["LinkedIn", "Instagram"]
    days_ahead: Optional[int] = 7

class PublishNowRequest(BaseModel):
    post_id: str
    platform: Optional[str] = "LinkedIn"
    content: Optional[str] = ""
    image_url: Optional[str] = ""

class LIPostRequest(BaseModel):
    content: str; image_url: Optional[str] = ""

class MastPostRequest(BaseModel):
    content: str; image_url: Optional[str] = ""

# ══════════════════════════════════════════════════════════
# HEALTH
# ══════════════════════════════════════════════════════════
@app.get("/echo/health")
async def health():
    ai = "Groq (LLaMA)" if os.getenv("GROQ_API_KEY") else "No AI key set"
    return {
        "status": "online", "version": "4.0", "ai_provider": ai,
        "platforms": ["LinkedIn", "Instagram", "Facebook", "X", "TikTok", "Mastodon"],
        "features": ["voice", "autopilot", "scheduler", "image_gen", "safety", "triage", "queue"]
    }

# ══════════════════════════════════════════════════════════
# VOICE TRANSCRIPTION
# ══════════════════════════════════════════════════════════
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
            return {"transcript": text, "text": text, "success": True}
        return {"transcript": "", "error": f"Groq {r.status_code}: {r.text[:100]}"}
    except Exception as e:
        return {"transcript": "", "error": str(e)}
    finally:
        try: os.unlink(tmp_path)
        except: pass

# ══════════════════════════════════════════════════════════
# VOICE AUTOPILOT
# ══════════════════════════════════════════════════════════
@app.post("/echo/voice-autopilot")
async def voice_autopilot(req: VoiceAutopilotRequest):
    import requests as rq
    groq_key = os.getenv("GROQ_API_KEY", "")
    topics = []
    if groq_key and req.transcript:
        try:
            r = rq.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile", "max_tokens": 120,
                      "messages": [{"role": "user", "content":
                          f"Extract 3-4 social media content topics from this voice message.\n"
                          f"Voice: '{req.transcript}'\nBrand: {req.brand_name}\n"
                          f'Return ONLY a JSON array like ["topic 1","topic 2","topic 3"]'
                      }]},
                timeout=15
            )
            if r.status_code == 200:
                raw = r.json()["choices"][0]["message"]["content"].strip()
                m = re.search(r'\[.*?\]', raw, re.DOTALL)
                if m:
                    topics = json.loads(m.group())
        except Exception as e:
            print(f"[VoiceAP] error: {e}")
    if not topics:
        words = [w.strip(".,!?") for w in req.transcript.lower().split() if len(w.strip(".,!?")) > 4]
        for i in range(0, min(len(words), 9), 3):
            chunk = " ".join(words[i:i+3])
            if chunk: topics.append(chunk)
    if not topics:
        topics = [f"{req.brand_name} content", "industry news", "product update"]
    topics = topics[:4]
    print(f"[VoiceAP] Topics: {topics}")
    try:
        from echo_autopilot import run_autopilot
        result = run_autopilot(req.brand_name, req.industry, topics, req.platforms, req.days_ahead)
        result["extracted_topics"] = topics
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════════════
# AUTOPILOT
# ══════════════════════════════════════════════════════════
@app.post("/echo/autopilot")
async def run_autopilot(req: AutoPilotRequest):
    try:
        from echo_autopilot import run_autopilot
        return run_autopilot(req.brand_name, req.industry, req.topics, req.platforms, req.days_ahead)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════════════
# SCHEDULE
# ══════════════════════════════════════════════════════════
@app.get("/echo/schedule")
async def get_schedule(brand_name: Optional[str] = None):
    try:
        from echo_autopilot import init_db, get_all_posts
        init_db()
        posts = get_all_posts(brand_name)
        return {"posts": posts, "total": len(posts)}
    except Exception as e:
        return {"posts": [], "total": 0, "error": str(e)}

@app.post("/echo/schedule/update")
async def update_schedule(req: ScheduleUpdateRequest):
    try:
        from echo_autopilot import update_status
        update_status(req.post_id, req.status)
        return {"success": True, "post_id": req.post_id, "status": req.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/echo/schedule/{post_id}")
async def delete_schedule_post(post_id: str):
    try:
        from echo_autopilot import delete_post
        delete_post(post_id)
        return {"success": True, "deleted": post_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════════════
# PUBLISH NOW — Sends post to real platform with image
# ══════════════════════════════════════════════════════════
@app.post("/echo/publish-now")
async def publish_now(req: PublishNowRequest):
    import requests as rq, base64
    content   = req.content or ""
    platform  = req.platform or "LinkedIn"
    image_url = req.image_url or ""

    # Load from DB if content not provided
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
            result.update({"success": False, "error": "Missing LINKEDIN_ACCESS_TOKEN or LINKEDIN_PERSON_URN in .env"})
        else:
            try:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0"
                }

                # ── Step 1: Get image bytes FIRST ──────────────────────────
                media_asset  = None
                image_bytes  = None

                if image_url:
                    try:
                        if image_url.startswith("data:image"):
                            # HuggingFace base64 image — decode to bytes
                            _, b64data = image_url.split(",", 1)
                            image_bytes = base64.b64decode(b64data)
                            print(f"[LinkedIn] Base64 image decoded: {len(image_bytes)//1024}KB")
                        elif image_url.startswith("http"):
                            # URL image — download bytes first
                            resp = rq.get(image_url, timeout=30,
                                          headers={"User-Agent": "Mozilla/5.0"})
                            if resp.status_code == 200 and len(resp.content) > 1000:
                                image_bytes = resp.content
                                print(f"[LinkedIn] Image downloaded: {len(image_bytes)//1024}KB")
                            else:
                                print(f"[LinkedIn] Download failed ({resp.status_code})")
                    except Exception as e:
                        print(f"[LinkedIn] Image prep error: {e}")

                # ── Step 2: Register upload with LinkedIn ──────────────────
                if image_bytes:
                    try:
                        reg = rq.post(
                            "https://api.linkedin.com/v2/assets?action=registerUpload",
                            headers=headers,
                            json={"registerUploadRequest": {
                                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                                "owner": f"urn:li:person:{urn}",
                                "serviceRelationships": [{
                                    "relationshipType": "OWNER",
                                    "identifier": "urn:li:userGeneratedContent"
                                }]
                            }},
                            timeout=15
                        )
                        if reg.status_code == 200:
                            reg_data    = reg.json()
                            upload_url  = reg_data["value"]["uploadMechanism"] \
                                ["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                            media_asset = reg_data["value"]["asset"]

                            # ── Step 3: Upload the bytes ───────────────────
                            put = rq.put(
                                upload_url,
                                data=image_bytes,
                                headers={"Authorization": f"Bearer {token}",
                                         "Content-Type": "image/jpeg"},
                                timeout=30
                            )
                            if put.status_code in (200, 201):
                                print(f"[LinkedIn] Image uploaded OK! Asset: {media_asset}")
                            else:
                                print(f"[LinkedIn] Image upload failed ({put.status_code})")
                                media_asset = None
                        else:
                            print(f"[LinkedIn] Register failed: {reg.text[:100]}")
                    except Exception as e:
                        print(f"[LinkedIn] Upload error: {e}")
                        media_asset = None

                # ── Step 4: Build post payload ─────────────────────────────
                share_content = {"shareCommentary": {"text": content}, "shareMediaCategory": "NONE"}
                if media_asset:
                    share_content["shareMediaCategory"] = "IMAGE"
                    share_content["media"] = [{
                        "status": "READY",
                        "description": {"text": "Echo AI generated image"},
                        "media": media_asset,
                        "title": {"text": "Echo AI Post"}
                    }]

                # ── Step 5: Post to LinkedIn ───────────────────────────────
                r = rq.post("https://api.linkedin.com/v2/ugcPosts",
                    headers=headers,
                    json={"author": f"urn:li:person:{urn}", "lifecycleState": "PUBLISHED",
                          "specificContent": {"com.linkedin.ugc.ShareContent": share_content},
                          "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}},
                    timeout=15)
                if r.status_code in (200, 201):
                    result.update({
                        "success":    True,
                        "live_url":   "https://www.linkedin.com/feed/",
                        "with_image": media_asset is not None,
                        "message":    "Posted to LinkedIn!" + (" (with image ✅)" if media_asset else " (text only)")
                    })
                else:
                    result.update({"success": False, "error": f"LinkedIn {r.status_code}: {r.text[:150]}"})
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
                       "error": f"Platform '{platform}' not connected. Use LinkedIn or Mastodon."})

    # Mark published in DB
    try:
        from echo_autopilot import update_status
        update_status(req.post_id, "published")
    except: pass
    return result

# ══════════════════════════════════════════════════════════
# IMAGE GENERATION
# ══════════════════════════════════════════════════════════
@app.post("/echo/generate-image")
async def generate_image(req: ImageRequest):
    try:
        from image_generator import generate_content_image
        return generate_content_image(req.content, req.platform, req.brand_name)
    except Exception as e:
        import hashlib
        s = int(hashlib.md5(req.content.encode()).hexdigest(), 16) % 800
        return {"image_url": f"https://picsum.photos/seed/{s}/1080/1080",
                "platform": req.platform, "source": "fallback"}

# ══════════════════════════════════════════════════════════
# CONTENT WRITERS
# ══════════════════════════════════════════════════════════
@app.post("/echo/social-pack")
async def social_pack(req: SocialPackRequest):
    try:
        from echo_content_writer import generate_social_pack
        return generate_social_pack(req.topic, req.brand_name, req.industry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/echo/write-linkedin")
async def write_li(req: ContentRequest):
    try:
        from echo_content_writer import write_linkedin_post
        return write_linkedin_post(req.topic, req.brand_name, req.industry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/echo/write-x")
async def write_x(req: ContentRequest):
    try:
        from echo_content_writer import write_x_post
        return write_x_post(req.topic, req.brand_name, req.industry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/echo/write-instagram")
async def write_ig(req: ContentRequest):
    try:
        from echo_content_writer import write_instagram_post
        return write_instagram_post(req.topic, req.brand_name, req.industry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/echo/write-facebook")
async def write_fb(req: ContentRequest):
    try:
        from echo_content_writer import write_facebook_post
        return write_facebook_post(req.topic, req.brand_name, req.industry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/echo/write-tiktok")
async def write_tt(req: ContentRequest):
    try:
        from echo_content_writer import write_tiktok_script
        return write_tiktok_script(req.topic, req.brand_name, req.industry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/echo/image-prompts")
async def img_prompts(req: ContentRequest):
    try:
        from echo_content_writer import generate_image_prompts
        return generate_image_prompts(req.topic, req.platform)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════════════
# A/B TEST
# ══════════════════════════════════════════════════════════
@app.post("/echo/ab-test")
async def ab_test(req: ABTestRequest):
    try:
        from echo_pipeline import ab_headline_debate
        return ab_headline_debate(req.topic, req.brand_name, req.industry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════════════
# SAFETY
# ══════════════════════════════════════════════════════════
@app.post("/echo/safety-check")
async def safety(req: SafetyRequest):
    try:
        from echo_reliability import check_brand_safety
        return check_brand_safety(req.content, req.brand_name, req.industry).model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════════════
# COMMENT TRIAGE
# ══════════════════════════════════════════════════════════
@app.post("/echo/triage-comment")
async def triage_one(req: CommentRequest):
    try:
        from echo_reliability import triage_comment
        return triage_comment(req.comment, req.brand_name).model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/echo/triage-comments")
async def triage_many(req: CommentsRequest):
    try:
        from echo_reliability import triage_comments_batch
        return [r.model_dump() for r in triage_comments_batch(req.comments, req.brand_name)]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════════════
# APPROVAL QUEUE
# ══════════════════════════════════════════════════════════
@app.get("/echo/queue")
async def get_queue():
    try:
        from echo_reliability import ApprovalQueue
        q = ApprovalQueue()
        return {"pending": q.get_pending(), "all": q.queue}
    except Exception:
        return {"pending": [], "all": []}

@app.post("/echo/queue/add")
async def add_queue(req: QueueAddRequest):
    try:
        from echo_reliability import ApprovalQueue
        q = ApprovalQueue()
        pid = q.add_post(req.platform, req.content, req.brand_name, req.industry, req.image_url)
        return {"post_id": pid, "status": "pending"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/echo/queue/approve")
async def approve(req: ApproveRequest):
    try:
        from echo_reliability import ApprovalQueue
        ApprovalQueue().approve(req.post_id, req.notes)
        return {"success": True, "status": "approved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/echo/queue/reject")
async def reject(req: ApproveRequest):
    try:
        from echo_reliability import ApprovalQueue
        ApprovalQueue().reject(req.post_id, req.notes)
        return {"success": True, "status": "rejected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════════════
# LINKEDIN PUBLISHER
# ══════════════════════════════════════════════════════════
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
            return {"connected": True, "name": d.get("name", ""), "message": "LinkedIn connected!"}
        return {"connected": False, "error": f"{r.status_code}: {r.text[:100]}"}
    except Exception as e:
        return {"connected": False, "error": str(e)}

@app.post("/echo/linkedin/post")
async def linkedin_post(req: LIPostRequest):
    import requests as rq
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    urn   = os.getenv("LINKEDIN_PERSON_URN", "")
    if not token or not urn:
        return {"success": False, "error": "Missing LINKEDIN_ACCESS_TOKEN or LINKEDIN_PERSON_URN in .env"}
    try:
        r = rq.post("https://api.linkedin.com/v2/ugcPosts",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                     "X-Restli-Protocol-Version": "2.0.0"},
            json={"author": f"urn:li:person:{urn}", "lifecycleState": "PUBLISHED",
                  "specificContent": {"com.linkedin.ugc.ShareContent": {
                      "shareCommentary": {"text": req.content}, "shareMediaCategory": "NONE"}},
                  "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}},
            timeout=15)
        if r.status_code in (200, 201):
            return {"success": True, "message": "Posted to LinkedIn!", "live_url": "https://www.linkedin.com/feed/"}
        return {"success": False, "error": f"LinkedIn {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ══════════════════════════════════════════════════════════
# MASTODON PUBLISHER
# ══════════════════════════════════════════════════════════
@app.post("/echo/mastodon/post")
async def mastodon_post(req: MastPostRequest):
    try:
        from echo_publisher import publish_to_mastodon
        return publish_to_mastodon(req.content, req.image_url or "")
    except Exception as e:
        return {"success": False, "error": str(e)}

# ══════════════════════════════════════════════════════════
# BRAND MEMORY
# ══════════════════════════════════════════════════════════
@app.post("/echo/brand-memory/add")
async def add_mem(req: BrandMemRequest):
    try:
        from echo_brand_memory import add_to_brand_bible
        return {"doc_id": add_to_brand_bible(req.brand_name, req.content, req.content_type)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/echo/brand-memory/seed")
async def seed_mem(brand_name: str = "Aoraza", industry: str = "dairy"):
    try:
        from echo_brand_memory import seed_brand_bible
        seed_brand_bible(brand_name, industry)
        return {"status": "seeded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    print(f"\n🚀 Echo v4 → http://localhost:{port}")
    print(f"📖 Docs   → http://localhost:{port}/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=port)