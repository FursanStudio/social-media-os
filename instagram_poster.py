# instagram_poster.py — Post to Instagram FREE
# Uses instagrapi — no business account, no API approval, no payment
# Install: pip install instagrapi pillow

import os, requests, tempfile, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

def _download_image(image_url: str, save_path: str) -> bool:
    """Download image from URL and save to disk."""
    try:
        # Pollinations images take time to generate — wait and retry
        for attempt in range(4):
            resp = requests.get(image_url, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 5000:
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                return True
            print(f"[Instagram] Image not ready yet, waiting 5s... (attempt {attempt+1}/4)")
            time.sleep(5)
        return False
    except Exception as e:
        print(f"[Instagram] Image download failed: {e}")
        return False

def _make_square(image_path: str) -> str:
    """Instagram requires square images (1:1 ratio). This fixes non-square images."""
    try:
        from PIL import Image
        img = Image.open(image_path)
        w, h = img.size
        if w == h:
            return image_path  # Already square

        size    = max(w, h)
        square  = Image.new("RGB", (size, size), (15, 15, 25))  # Dark background
        offset  = ((size - w) // 2, (size - h) // 2)
        square.paste(img, offset)

        square_path = image_path.replace(".jpg", "_square.jpg")
        square.save(square_path, "JPEG", quality=95)
        return square_path
    except Exception as e:
        print(f"[Instagram] Square conversion skipped: {e}")
        return image_path


def post_to_instagram(
    caption: str,
    image_url: str = "",
    username: str = "",
    password: str = ""
) -> dict:
    """
    Post a photo to Instagram using your normal username and password.
    
    Args:
        caption:   The post text (hashtags included)
        image_url: URL of the image to post (from Pollinations or any URL)
        username:  Your Instagram username (or set INSTAGRAM_USERNAME in .env)
        password:  Your Instagram password (or set INSTAGRAM_PASSWORD in .env)
    
    Returns:
        dict with success, post_url, media_id
    """
    # Get credentials from args or .env
    ig_user = username or os.getenv("INSTAGRAM_USERNAME", "")
    ig_pass = password or os.getenv("INSTAGRAM_PASSWORD", "")

    if not ig_user or not ig_pass:
        return {
            "success": False,
            "error":   "Missing credentials",
            "fix":     "Add INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD to your .env file"
        }

    # Check instagrapi is installed
    try:
        from instagrapi import Client
    except ImportError:
        return {
            "success": False,
            "error":   "instagrapi not installed",
            "fix":     "Run this in your terminal: pip install instagrapi pillow"
        }

    # ── Download the image ──────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        img_path = os.path.join(tmp, "post_image.jpg")

        if image_url:
            print(f"[Instagram] Downloading image...")
            ok = _download_image(image_url, img_path)
            if not ok:
                # Generate a simple placeholder if download failed
                try:
                    from PIL import Image, ImageDraw, ImageFont
                    img = Image.new("RGB", (1080, 1080), (15, 15, 25))
                    draw = ImageDraw.Draw(img)
                    draw.rectangle([40, 40, 1040, 1040], outline=(123, 104, 245), width=3)
                    # Write caption text on image
                    words = caption[:100].split()
                    line, lines = "", []
                    for w in words:
                        if len(line + w) < 35:
                            line += w + " "
                        else:
                            lines.append(line.strip())
                            line = w + " "
                    if line:
                        lines.append(line.strip())
                    y = 460
                    for l in lines[:5]:
                        draw.text((540, y), l, fill=(238, 240, 248), anchor="mm")
                        y += 40
                    img.save(img_path, "JPEG", quality=95)
                    print("[Instagram] Using text-on-image fallback")
                except Exception:
                    return {"success": False, "error": "Could not prepare image"}
        else:
            # No image URL — create a simple colored card
            try:
                from PIL import Image, ImageDraw
                img = Image.new("RGB", (1080, 1080), (15, 15, 25))
                draw = ImageDraw.Draw(img)
                draw.rectangle([40, 40, 1040, 1040], outline=(123, 104, 245), width=4)
                img.save(img_path, "JPEG", quality=95)
            except Exception:
                return {"success": False, "error": "No image provided and PIL not available"}

        # Make square (Instagram requirement)
        img_path = _make_square(img_path)

        # ── Log in to Instagram ─────────────────────────────
        print(f"[Instagram] Logging in as @{ig_user}...")
        cl = Client()

        # Load saved session if it exists (avoids re-login every time)
        session_file = f"ig_session_{ig_user}.json"
        if os.path.exists(session_file):
            try:
                cl.load_settings(session_file)
                cl.login(ig_user, ig_pass)
                print("[Instagram] ✅ Logged in using saved session")
            except Exception:
                print("[Instagram] Session expired, logging in fresh...")
                cl = Client()
                cl.login(ig_user, ig_pass)
                cl.dump_settings(session_file)
        else:
            cl.login(ig_user, ig_pass)
            cl.dump_settings(session_file)
            print("[Instagram] ✅ Logged in and session saved")

        # ── Upload the post ──────────────────────────────────
        print(f"[Instagram] Uploading post...")
        media = cl.photo_upload(
            path=img_path,
            caption=caption[:2200]  # Instagram caption limit
        )

        post_url = f"https://www.instagram.com/p/{media.code}/"
        print(f"[Instagram] ✅ Posted! URL: {post_url}")

        return {
            "success":  True,
            "platform": "Instagram",
            "post_id":  str(media.pk),
            "post_url": post_url,
            "username": ig_user,
            "message":  f"Successfully posted to @{ig_user}!"
        }


def test_instagram_connection(username: str = "", password: str = "") -> dict:
    """Test if Instagram login works without actually posting."""
    ig_user = username or os.getenv("INSTAGRAM_USERNAME", "")
    ig_pass = password or os.getenv("INSTAGRAM_PASSWORD", "")

    if not ig_user or not ig_pass:
        return {"connected": False, "error": "No credentials found in .env"}

    try:
        from instagrapi import Client
        cl = Client()
        cl.login(ig_user, ig_pass)
        info = cl.account_info()
        return {
            "connected":  True,
            "username":   ig_user,
            "full_name":  info.full_name,
            "followers":  info.follower_count,
            "following":  info.following_count,
            "message":    f"✅ Connected to @{ig_user} ({info.follower_count} followers)"
        }
    except ImportError:
        return {"connected": False, "error": "Run: pip install instagrapi pillow"}
    except Exception as e:
        return {"connected": False, "error": str(e)}
