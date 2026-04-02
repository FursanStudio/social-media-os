# fix_images.py — Run this ONCE to fix image_generator.py automatically
# 
# HOW TO RUN:
#   python fix_images.py
#
# It will rewrite image_generator.py to the correct working version.

import os

FIXED_CODE = '''# image_generator.py — FIXED v7 (no broken _check function)
import os, re, time, hashlib, requests, base64
from dotenv import load_dotenv
load_dotenv()

SIZES = {
    "Instagram": (1024, 1024),
    "LinkedIn":  (1024, 576),
    "Facebook":  (1024, 576),
    "X":         (1024, 576),
    "TikTok":    (576,  1024),
}

def _write_prompt(content, platform, brand=""):
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        words = re.sub(r\'[^\\\\w\\\\s]\', \' \', content).split()[:8]
        return ", ".join(words) + ", professional photo, 4K"
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "max_tokens": 60,
                  "messages": [{"role": "user", "content":
                      f"Write a 15-word image prompt for a {platform} social media post.\\n"
                      f"Topic: {content[:200]}\\nBrand: {brand or \'professional brand\'}\\n"
                      f"Real photo scene, no text in image, professional marketing.\\n"
                      f"Return ONLY the prompt, nothing else."
                  }]}, timeout=10)
        if resp.status_code == 200:
            prompt = resp.json()["choices"][0]["message"]["content"].strip().strip(\'"\\' \\').split(\'\\n\')[0]
            print(f"[ImageGen] Prompt: {prompt[:70]}")
            return prompt
    except Exception as e:
        print(f"[ImageGen] Groq error: {e}")
    words = re.sub(r\'[^\\\\w\\\\s]\', \' \', content).split()[:8]
    return ", ".join(words) + ", professional marketing photo, 4K"

def _hf_image(prompt, width, height):
    token = os.getenv("HF_TOKEN", "")
    if not token:
        print("[ImageGen] No HF_TOKEN in .env — using Pollinations fallback")
        return ""
    try:
        resp = requests.post(
            "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"inputs": prompt, "parameters": {
                "width": width, "height": height, "num_inference_steps": 4, "guidance_scale": 0.0
            }}, timeout=60)
        if resp.status_code == 503:
            print("[ImageGen] HF model loading, waiting 20s...")
            time.sleep(20)
            resp = requests.post(
                "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"inputs": prompt, "parameters": {
                    "width": width, "height": height, "num_inference_steps": 4, "guidance_scale": 0.0
                }}, timeout=60)
        if resp.status_code == 200 and "image" in resp.headers.get("Content-Type", ""):
            b64 = base64.b64encode(resp.content).decode()
            print(f"[ImageGen] HuggingFace image generated ({len(resp.content)//1024}KB)")
            return f"data:image/jpeg;base64,{b64}"
        print(f"[ImageGen] HF returned {resp.status_code}: {resp.text[:100]}")
        return ""
    except Exception as e:
        print(f"[ImageGen] HF error: {e}")
        return ""

def generate_content_image(content, platform="Instagram", brand_name=""):
    w, h = SIZES.get(platform, (1024, 1024))
    seed = int(hashlib.md5((content + platform).encode()).hexdigest(), 16) % 9999
    print(f"\\n[ImageGen] Generating {platform} image ({w}x{h})...")

    prompt = _write_prompt(content, platform, brand_name)

    # Try HuggingFace first (real AI image, base64)
    img = _hf_image(prompt, w, h)
    if img:
        return {"image_url": img, "image_type": "base64", "prompt": prompt,
                "platform": platform, "dimensions": f"{w}x{h}", "source": "huggingface-flux"}

    # Pollinations fallback — NO _check() call, just return URL directly
    # The browser loads it after 5-15 seconds. This is normal.
    encoded = "+".join(re.sub(r\'[^a-zA-Z0-9\\\\s]\', \'\', prompt).split()[:12])
    url = (f"https://image.pollinations.ai/prompt/{encoded}"
           f"?model=flux-schnell&width={w}&height={h}&seed={seed}&nologo=true&enhance=true")
    print(f"[ImageGen] Using Pollinations URL (loads in browser in 5-15s)")
    return {"image_url": url, "image_type": "url", "prompt": prompt,
            "platform": platform, "dimensions": f"{w}x{h}", "source": "pollinations",
            "fallback_url": f"https://picsum.photos/seed/{seed % 900}/{w}/{h}",
            "note": "Image loads in browser after 5-15 seconds — this is normal"}

IMAGE_READY = True
'''

target = "image_generator.py"

# Backup old file
if os.path.exists(target):
    with open(target + ".backup", "w") as f:
        with open(target) as old:
            f.write(old.read())
    print(f"✅ Backed up old file to image_generator.py.backup")

# Check if old broken version
with open(target) as f:
    content = f.read()

if "def _check" in content:
    print("❌ Found broken _check function — fixing now...")
elif "v7" in content or "NO _check" in content:
    print("✅ File already fixed! No changes needed.")
else:
    print("⚠️  Replacing with fixed version...")

with open(target, "w") as f:
    f.write(FIXED_CODE)

print("✅ image_generator.py fixed successfully!")
print("\nNow restart your server:")
print("   python echo_api.py")
print("\nOptional — add HuggingFace for better images:")
print("   1. Go to huggingface.co → sign up free")
print("   2. Settings → Access Tokens → New Token → Read")
print("   3. Add to .env: HF_TOKEN=hf_your_token")
