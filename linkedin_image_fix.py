# linkedin_image_fix.py
# Run: python linkedin_image_fix.py
# Tests LinkedIn image upload directly

import os, requests
from dotenv import load_dotenv
load_dotenv()

token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
urn   = os.getenv("LINKEDIN_PERSON_URN", "")

def post_to_linkedin_with_image(text, image_url=""):
    if not token or not urn:
        print("ERROR: Missing LINKEDIN_ACCESS_TOKEN or LINKEDIN_PERSON_URN in .env")
        return

    media_asset = None

    # ── Step 1: Download image first (LinkedIn needs real bytes) ──
    if image_url:
        print(f"Downloading image from: {image_url[:60]}...")
        try:
            img_resp = requests.get(image_url, timeout=30,
                                    headers={"User-Agent": "Mozilla/5.0"})
            if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                image_bytes = img_resp.content
                print(f"Image downloaded: {len(image_bytes)//1024}KB")
            else:
                print(f"Image download failed ({img_resp.status_code}) — posting text only")
                image_bytes = None
        except Exception as e:
            print(f"Image download error: {e} — posting text only")
            image_bytes = None

        # ── Step 2: Register upload with LinkedIn ──
        if image_bytes:
            try:
                reg = requests.post(
                    "https://api.linkedin.com/v2/assets?action=registerUpload",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0"
                    },
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
                print(f"Register upload status: {reg.status_code}")
                if reg.status_code == 200:
                    data = reg.json()
                    upload_url  = data["value"]["uploadMechanism"] \
                        ["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                    media_asset = data["value"]["asset"]
                    print(f"Upload URL received. Asset: {media_asset}")

                    # ── Step 3: Upload image bytes ──
                    put = requests.put(
                        upload_url,
                        data=image_bytes,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "image/jpeg"
                        },
                        timeout=30
                    )
                    print(f"Image upload status: {put.status_code}")
                    if put.status_code not in (200, 201):
                        print(f"Image upload failed — posting text only")
                        media_asset = None
                else:
                    print(f"Register failed: {reg.text[:200]}")
            except Exception as e:
                print(f"Image upload error: {e}")
                media_asset = None

    # ── Step 4: Create the post ──
    share_content = {
        "shareCommentary": {"text": text},
        "shareMediaCategory": "NONE"
    }
    if media_asset:
        share_content["shareMediaCategory"] = "IMAGE"
        share_content["media"] = [{
            "status": "READY",
            "description": {"text": "Echo AI generated image"},
            "media": media_asset,
            "title": {"text": "Echo AI Post"}
        }]

    r = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        },
        json={
            "author": f"urn:li:person:{urn}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": share_content
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        },
        timeout=20
    )

    print(f"\nPost status: {r.status_code}")
    if r.status_code in (200, 201):
        print("SUCCESS! Post is live on LinkedIn!")
        print(f"With image: {'YES' if media_asset else 'NO (text only)'}")
        print("Check: https://www.linkedin.com/feed/")
    else:
        print(f"FAILED: {r.text[:300]}")

# Test it
if __name__ == "__main__":
    post_to_linkedin_with_image(
        text="Testing Echo AI image upload to LinkedIn! This post was created by an autonomous AI social media system. #AI #Automation #Echo",
        image_url="https://picsum.photos/1200/628"
    )
