# echo_publisher.py — Multi-platform publisher (Updated with Mastodon fix)
# Free option: Mastodon (100% free, no payment needed)
# Paid options: X/Twitter, LinkedIn (require API accounts)

import os, json, time, requests
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


# ═══════════════════════════════════════════════════════════
#  MASTODON — 100% FREE, NO PAYMENT, NO WAITLIST
#  Setup takes 5 minutes — see SETUP_GUIDE.md
# ═══════════════════════════════════════════════════════════
def publish_to_mastodon(text: str, image_url: str = "") -> dict:
    """
    Post to Mastodon — completely free forever.
    
    SETUP (5 minutes):
    1. Go to https://mastodon.social and create a free account
    2. Click Settings (top right) → Development → New Application
    3. Name it "Echo", leave defaults, click Submit
    4. Copy the "Your access token" value
    5. Add to your .env file:
       MASTODON_ACCESS_TOKEN=your_token_here
       MASTODON_BASE_URL=https://mastodon.social
    """
    token    = os.getenv("MASTODON_ACCESS_TOKEN", "")
    base_url = os.getenv("MASTODON_BASE_URL", "https://mastodon.social").rstrip("/")

    if not token:
        return {
            "success": False,
            "platform": "Mastodon",
            "error": "No MASTODON_ACCESS_TOKEN found in .env",
            "setup_steps": [
                "1. Go to https://mastodon.social → create free account",
                "2. Settings → Development → New Application → Submit",
                "3. Copy 'Your access token'",
                "4. Add MASTODON_ACCESS_TOKEN=your_token to .env"
            ]
        }

    headers = {"Authorization": f"Bearer {token}"}

    # ── Upload image if provided ──
    media_ids = []
    if image_url:
        try:
            # Download image first
            img_resp = requests.get(image_url, timeout=20)
            if img_resp.status_code == 200:
                media_resp = requests.post(
                    f"{base_url}/api/v1/media",
                    headers=headers,
                    files={"file": ("image.jpg", img_resp.content, "image/jpeg")},
                    timeout=30
                )
                if media_resp.status_code in (200, 202):
                    media_ids = [media_resp.json()["id"]]
                    # Wait for media to process
                    time.sleep(2)
        except Exception as e:
            print(f"[Mastodon] Image upload skipped: {e}")

    # ── Post the status ──
    payload = {
        "status":     text[:500],  # Mastodon limit is 500 chars
        "visibility": "public",
    }
    if media_ids:
        payload["media_ids"] = media_ids

    try:
        resp = requests.post(
            f"{base_url}/api/v1/statuses",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=20
        )
        if resp.status_code in (200, 201, 202):
            data = resp.json()
            post_url = data.get("url", "")
            print(f"[Mastodon] ✅ Posted! URL: {post_url}")
            return {
                "success":  True,
                "platform": "Mastodon",
                "post_id":  data.get("id", ""),
                "url":      post_url,
                "message":  "Posted successfully to Mastodon!"
            }
        else:
            return {
                "success":  False,
                "platform": "Mastodon",
                "error":    f"API error {resp.status_code}: {resp.text[:200]}"
            }
    except Exception as e:
        return {"success": False, "platform": "Mastodon", "error": str(e)}


# ═══════════════════════════════════════════════════════════
#  X / TWITTER — Requires paid developer account ($100/month)
# ═══════════════════════════════════════════════════════════
def publish_to_x(text: str) -> dict:
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=os.getenv("X_API_KEY"),
            consumer_secret=os.getenv("X_API_SECRET"),
            access_token=os.getenv("X_ACCESS_TOKEN"),
            access_token_secret=os.getenv("X_ACCESS_SECRET")
        )
        response = client.create_tweet(text=text[:280])
        tweet_id = response.data["id"]
        return {
            "success":  True,
            "platform": "X",
            "post_id":  str(tweet_id),
            "url":      f"https://x.com/i/web/status/{tweet_id}"
        }
    except ImportError:
        return {"success": False, "error": "Run: pip install tweepy"}
    except Exception as e:
        return {"success": False, "platform": "X", "error": str(e)}


# ═══════════════════════════════════════════════════════════
#  LINKEDIN — Requires LinkedIn Developer account approval
# ═══════════════════════════════════════════════════════════
def publish_to_linkedin(text: str) -> dict:
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    urn   = os.getenv("LINKEDIN_PERSON_URN", "")

    if not token or not urn:
        return {
            "success": False,
            "error":   "Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN in .env"
        }
    try:
        payload = {
            "author": f"urn:li:person:{urn}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        resp = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            },
            json=payload,
            timeout=15
        )
        if resp.status_code in (200, 201):
            return {"success": True, "platform": "LinkedIn",
                    "post_id": resp.headers.get("X-RestLi-Id", "ok")}
        return {"success": False, "platform": "LinkedIn", "error": resp.text}
    except Exception as e:
        return {"success": False, "platform": "LinkedIn", "error": str(e)}


# ═══════════════════════════════════════════════════════════
#  UNIVERSAL PUBLISH
# ═══════════════════════════════════════════════════════════
def publish(platform: str, content: str, image_url: str = "") -> dict:
    """Auto-routes to the correct platform publisher."""
    p = platform.lower()
    if p == "mastodon":
        return publish_to_mastodon(content, image_url)
    elif p in ("x", "twitter"):
        return publish_to_x(content)
    elif p == "linkedin":
        return publish_to_linkedin(content)
    else:
        return {
            "success": False,
            "error":   f"Platform '{platform}' not supported yet",
            "supported": ["Mastodon (free)", "X (paid API)", "LinkedIn (approval required)"]
        }