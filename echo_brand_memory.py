# echo_brand_memory.py — Week 1 Day 2
# Qdrant vector store for Brand Bible + RAG retrieval
# Falls back to in-memory store if Qdrant isn't running

import os, uuid, hashlib, json
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

# ── Try Qdrant, fall back to in-memory ───────────────────────────────────
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        Filter, FieldCondition, MatchValue
    )
    qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
    qdrant.get_collections()          # test connection
    USE_QDRANT = True
    print("[BrandMemory] ✅ Connected to Qdrant")
except Exception:
    USE_QDRANT = False
    print("[BrandMemory] ⚠️  Qdrant offline — using in-memory store")

COLLECTION = "brand_bible"
_mem: List[dict] = []   # in-memory fallback


# ── Embedding ─────────────────────────────────────────────────────────────
def _embed(text: str) -> List[float]:
    """
    Use Ollama nomic-embed-text if available, else deterministic mock.
    For production: replace with OpenAI text-embedding-3-small.
    """
    try:
        import ollama
        return ollama.embeddings(model="nomic-embed-text", prompt=text)["embedding"]
    except Exception:
        h = int(hashlib.sha256(text.encode()).hexdigest(), 16)
        vec = []
        for _ in range(384):
            h = (h * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
            vec.append((h / 0xFFFFFFFFFFFFFFFF) * 2 - 1)
        return vec


def _ensure_collection():
    if not USE_QDRANT:
        return
    names = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION not in names:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )


# ── Public API ─────────────────────────────────────────────────────────────
def add_to_brand_bible(
    brand_name: str,
    content: str,
    content_type: str = "post",   # post | tone_rule | forbidden | ceo_voice
    metadata: Optional[dict] = None
) -> str:
    """Store brand knowledge. content_type controls RAG filtering."""
    doc_id = str(uuid.uuid4())
    payload = {"brand": brand_name, "content": content,
                "type": content_type, "meta": metadata or {}}
    vec = _embed(content)

    if USE_QDRANT:
        _ensure_collection()
        qdrant.upsert(COLLECTION,
                      points=[PointStruct(id=doc_id, vector=vec, payload=payload)])
    else:
        _mem.append({"id": doc_id, "vec": vec, **payload})
    return doc_id


def search_brand_memory(query: str, brand_name: str, top_k: int = 5) -> List[dict]:
    """Semantic search — returns top_k relevant brand memories for RAG."""
    qvec = _embed(query)

    if USE_QDRANT:
        hits = qdrant.search(
            collection_name=COLLECTION,
            query_vector=qvec,
            query_filter=Filter(must=[
                FieldCondition(key="brand", match=MatchValue(value=brand_name))
            ]),
            limit=top_k
        )
        return [{"score": h.score, "content": h.payload["content"],
                 "type": h.payload["type"]} for h in hits]

    # In-memory cosine similarity
    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x**2 for x in a) ** 0.5
        nb = sum(x**2 for x in b) ** 0.5
        return dot / (na * nb + 1e-9)

    scored = [
        {"score": cosine(qvec, item["vec"]),
         "content": item["content"], "type": item["type"]}
        for item in _mem if item["brand"] == brand_name
    ]
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:top_k]


def build_rag_context(query: str, brand_name: str) -> str:
    """
    Week 1 Day 2 — Build a RAG context block to inject into prompts.
    This makes the agent 'write like the CEO'.
    """
    memories = search_brand_memory(query, brand_name, top_k=6)
    if not memories:
        return ""

    sections = {"ceo_voice": [], "tone_rule": [], "post": [], "forbidden": []}
    for m in memories:
        t = m.get("type", "post")
        sections.get(t, sections["post"]).append(m["content"])

    ctx = "=== BRAND BIBLE (use this to match brand voice) ===\n"
    if sections["ceo_voice"]:
        ctx += "\n[CEO Writing Style Examples]\n" + "\n---\n".join(sections["ceo_voice"][:2])
    if sections["tone_rule"]:
        ctx += "\n\n[Tone Rules]\n" + "\n".join(f"• {r}" for r in sections["tone_rule"])
    if sections["forbidden"]:
        ctx += "\n\n[Forbidden Words/Phrases — NEVER USE]\n" + "\n".join(f"✗ {r}" for r in sections["forbidden"])
    if sections["post"]:
        ctx += "\n\n[Top Performing Past Posts]\n" + "\n---\n".join(sections["post"][:2])
    ctx += "\n=== END BRAND BIBLE ===\n"
    return ctx


def seed_brand_bible(brand_name: str, industry: str):
    """Seed default brand voice entries so RAG works immediately."""
    entries = [
        ("ceo_voice", f"At {brand_name}, we don't just sell {industry} products — we build relationships. Our customers aren't buyers, they're community members."),
        ("ceo_voice", f"The future of {industry} is sustainable and human-centered. {brand_name} leads by example."),
        ("tone_rule", "Always use 'we' not 'I' — brand voice is collective."),
        ("tone_rule", "End every post with a question to drive engagement."),
        ("tone_rule", "Use data and numbers whenever possible — audiences trust specifics."),
        ("forbidden", "cheap, discount, limited time offer, act now, buy now"),
        ("forbidden", "guaranteed results, 100% proven, no risk"),
        ("post", f"🌱 Sustainability isn't optional — it's our mission. {brand_name} reduced packaging waste by 40% this year. What changes is your brand making? #Sustainability #{industry.replace(' ','')}"),
    ]
    for ctype, text in entries:
        add_to_brand_bible(brand_name, text, ctype)
    print(f"[BrandMemory] Seeded {len(entries)} entries for '{brand_name}'")


if __name__ == "__main__":
    seed_brand_bible("Aoraza", "dairy")
    ctx = build_rag_context("sustainable milk product launch", "Aoraza")
    print(ctx)
