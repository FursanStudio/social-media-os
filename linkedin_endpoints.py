# ADD THESE TO echo_api.py — paste ABOVE the last line: if __name__ == "__main__":

# ── LinkedIn Publisher ─────────────────────────────────────────────────────
class LinkedInPostRequest(BaseModel):
    content: str
    image_url: Optional[str] = ""

@app.get("/echo/linkedin/test")
async def linkedin_test():
    """Test LinkedIn connection."""
    token = os.getenv("LINKEDIN_ACCESS_TOKEN","")
    urn   = os.getenv("LINKEDIN_PERSON_URN","")
    if not token:
        return {"connected":False,"error":"No LINKEDIN_ACCESS_TOKEN in .env",
                "setup":"See LinkedIn Publisher tab for setup steps"}
    try:
        import requests as req
        r = req.get("https://api.linkedin.com/v2/me",
                    headers={"Authorization":f"Bearer {token}"},timeout=10)
        if r.status_code==200:
            data=r.json()
            return {"connected":True,"name":f"{data.get('localizedFirstName','')} {data.get('localizedLastName','')}",
                    "id":data.get("id",""),"message":"✅ LinkedIn connected!"}
        return {"connected":False,"error":f"API error {r.status_code}: {r.text[:100]}"}
    except Exception as e:
        return {"connected":False,"error":str(e)}

@app.post("/echo/linkedin/post")
async def linkedin_post(req: LinkedInPostRequest):
    """Publish a post to LinkedIn."""
    token = os.getenv("LINKEDIN_ACCESS_TOKEN","")
    urn   = os.getenv("LINKEDIN_PERSON_URN","")
    if not token or not urn:
        return {"success":False,"error":"Missing LINKEDIN_ACCESS_TOKEN or LINKEDIN_PERSON_URN in .env",
                "setup_steps":["1. Go to linkedin.com/developers → Create App",
                               "2. Auth tab → add scope: w_member_social, r_liteprofile",
                               "3. Get OAuth token → add LINKEDIN_ACCESS_TOKEN=token to .env",
                               "4. Call /echo/linkedin/test to get your ID → add LINKEDIN_PERSON_URN=id to .env"]}
    try:
        import requests as req_lib
        payload={"author":f"urn:li:person:{urn}","lifecycleState":"PUBLISHED",
                 "specificContent":{"com.linkedin.ugc.ShareContent":
                    {"shareCommentary":{"text":req.content},
                     "shareMediaCategory":"NONE"}},
                 "visibility":{"com.linkedin.ugc.MemberNetworkVisibility":"PUBLIC"}}
        r=req_lib.post("https://api.linkedin.com/v2/ugcPosts",
                        headers={"Authorization":f"Bearer {token}","Content-Type":"application/json",
                                 "X-Restli-Protocol-Version":"2.0.0"},
                        json=payload,timeout=15)
        if r.status_code in(200,201):
            post_id=r.headers.get("X-RestLi-Id","")
            return {"success":True,"platform":"LinkedIn","post_id":post_id,
                    "message":f"✅ Posted to LinkedIn! ID: {post_id}"}
        return {"success":False,"error":f"LinkedIn API {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"success":False,"error":str(e)}

# ── Mastodon Publisher ─────────────────────────────────────────────────────
class MastodonPostRequest(BaseModel):
    content: str
    image_url: Optional[str] = ""

@app.post("/echo/mastodon/post")
async def mastodon_post(req: MastodonPostRequest):
    """Post to Mastodon — 100% free."""
    try:
        from echo_publisher import publish_to_mastodon
        return publish_to_mastodon(req.content, req.image_url)
    except Exception as e:
        return {"success":False,"error":str(e)}
