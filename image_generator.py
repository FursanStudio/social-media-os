# image_generator.py — v9 FINAL
# Images: HuggingFace FLUX (free) → Pollinations (fallback)
# Prompts: Groq AI writes professional prompts first

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
    """Groq writes a smart professional image prompt."""
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        words = re.sub(r'[^\w\s]', ' ', content).split()[:8]
        return ", ".join(words) + ", professional photo, 4K, marketing"
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "max_tokens": 60,
                "messages": [{
                    "role": "user",
                    "content": (
                        "Write a 15-word image generation prompt for a "
                        + platform + " social media post. "
                        "Topic: " + content[:200] + ". "
                        "Brand: " + (brand or "professional brand") + ". "
                        "Rules: real photo scene, no text, professional, good lighting. "
                        "Return ONLY the prompt."
                    )
                }]
            },
            timeout=10
        )
        if resp.status_code == 200:
            raw = resp.json()["choices"][0]["message"]["content"]
            prompt = raw.strip().strip('"').strip("'").split("\n")[0]
            print("[ImageGen] Prompt: " + prompt[:80])
            return prompt
    except Exception as e:
        print("[ImageGen] Groq error: " + str(e))
    words = re.sub(r'[^\w\s]', ' ', content).split()[:8]
    return ", ".join(words) + ", professional marketing photo, 4K"


def _hf_image(prompt, width, height):
    """
    HuggingFace FLUX — free with account.
    Get token: huggingface.co → Settings → Access Tokens → New Token
    Enable: 'Make calls to Inference Providers'
    Add to .env: HF_TOKEN=hf_...
    """
    token = os.getenv("HF_TOKEN", "")
    if not token:
        print("[ImageGen] No HF_TOKEN — using Pollinations")
        return ""

    # Try multiple HuggingFace endpoints (they keep changing)
    endpoints = [
        "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
        "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
        "https://router.huggingface.co/nebius/v1/images/generations",
    ]

    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
    }

    for i, url in enumerate(endpoints):
        try:
            print("[ImageGen] Trying HF endpoint " + str(i+1) + "...")

            if "nebius" in url:
                # Nebius endpoint has different format
                payload = {
                    "model": "black-forest-labs/FLUX.1-schnell",
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "num_inference_steps": 4,
                    "response_format": "b64_json"
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    b64 = data.get("data", [{}])[0].get("b64_json", "")
                    if b64:
                        print("[ImageGen] HF Nebius OK!")
                        return "data:image/jpeg;base64," + b64
            else:
                payload = {
                    "inputs": prompt,
                    "parameters": {
                        "width": width,
                        "height": height,
                        "num_inference_steps": 4,
                        "guidance_scale": 0.0
                    }
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=60)

                if resp.status_code == 503:
                    print("[ImageGen] HF loading, waiting 15s...")
                    time.sleep(15)
                    resp = requests.post(url, headers=headers, json=payload, timeout=60)

                ct = resp.headers.get("Content-Type", "")
                if resp.status_code == 200 and "image" in ct:
                    b64 = base64.b64encode(resp.content).decode()
                    kb = len(resp.content) // 1024
                    print("[ImageGen] HF OK — " + str(kb) + "KB")
                    return "data:image/jpeg;base64," + b64

            print("[ImageGen] HF ep" + str(i+1) + " returned " + str(resp.status_code))

        except Exception as e:
            print("[ImageGen] HF ep" + str(i+1) + " error: " + str(e))
            continue

    return ""


def generate_content_image(content, platform="Instagram", brand_name=""):
    """
    Main image generation function.
    1. Groq writes a smart prompt
    2. HuggingFace generates image (if HF_TOKEN set)
    3. Pollinations fallback (always works, loads in browser in 5-15s)
    """
    w, h = SIZES.get(platform, (1024, 1024))
    seed = int(hashlib.md5((content + platform).encode()).hexdigest(), 16) % 9999
    print("\n[ImageGen] " + platform + " (" + str(w) + "x" + str(h) + ")...")

    # Step 1: Smart prompt
    prompt = _write_prompt(content, platform, brand_name)

    # Step 2: Try HuggingFace
    hf = _hf_image(prompt, w, h)
    if hf:
        return {
            "image_url":  hf,
            "image_type": "base64",
            "prompt":     prompt,
            "platform":   platform,
            "dimensions": str(w) + "x" + str(h),
            "source":     "huggingface-flux"
        }

    # Step 3: Pollinations — NO HTTP check, just return URL
    clean   = re.sub(r'[^a-zA-Z0-9\s]', '', prompt)
    encoded = "+".join(clean.split()[:12])
    url = (
        "https://image.pollinations.ai/prompt/" + encoded
        + "?model=flux-schnell"
        + "&width=" + str(w)
        + "&height=" + str(h)
        + "&seed=" + str(seed)
        + "&nologo=true&enhance=true"
    )
    fallback = "https://picsum.photos/seed/" + str(seed % 900) + "/" + str(w) + "/" + str(h)

    print("[ImageGen] Pollinations URL ready")
    return {
        "image_url":   url,
        "image_type":  "url",
        "prompt":      prompt,
        "platform":    platform,
        "dimensions":  str(w) + "x" + str(h),
        "source":      "pollinations",
        "fallback_url": fallback,
        "note":        "Image appears in browser after 5-15 seconds"
    }


IMAGE_READY = True