"""
embed_and_retrieve.py — Milestone 4: embedding, vector store, and retrieval
Implements the Embedding & Retrieval sections of planning.md:
  - Embeds chunks from data/chunks.json with all-MiniLM-L6-v2 (local, free)
  - Stores vectors + metadata in ChromaDB (persisted to data/chroma/)
  - retrieve(query, k=5) returns top-k chunks with distances + sources
 
Usage:
    python embed_and_retrieve.py --index        # (re)build the vector store
    python embed_and_retrieve.py --sanity       # self-retrieval sanity check
    python embed_and_retrieve.py --query "is attendance mandatory for Boddu?"
    python embed_and_retrieve.py --test         # run the eval questions in TEST_QUERIES
 
Requires:
    pip install sentence-transformers chromadb
"""
 
import argparse
import json
from pathlib import Path
 
import chromadb
from sentence_transformers import SentenceTransformer
 
CHUNKS_FILE = Path("data/chunks.json")
CHROMA_DIR = "data/chroma"
COLLECTION_NAME = "msu_prof_reviews"
MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 5  # from planning.md: small chunks -> higher k to capture contradictions
 
# Put 3+ of your evaluation-plan questions here (Milestone 4 checklist)
TEST_QUERIES = [
    "Is attendance mandatory in Professor Boddu's CSIT100 class?",
    "What do students say about classes that use zybooks?",
    "How is the grade weighted in Professor Coutras's computer networks class?",
]
 
# ---------------------------------------------------------------- setup
_model = None
def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"Loading embedding model {MODEL_NAME}...")
        _model = SentenceTransformer(MODEL_NAME)
    return _model
 
def get_collection(client=None):
    client = client or chromadb.PersistentClient(path=CHROMA_DIR)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},  # cosine distance: 0 = identical
    )
 
# ---------------------------------------------------------------- indexing
def build_index():
    if not CHUNKS_FILE.exists():
        raise SystemExit(f"{CHUNKS_FILE} not found — run ingest_and_chunk.py first.")
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    print(f"Loaded {len(chunks)} chunks from {CHUNKS_FILE}")
 
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    # Rebuild from scratch so the index always mirrors chunks.json exactly
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = get_collection(client)
 
    model = get_model()
    texts = [c["text"] for c in chunks]
    print("Embedding chunks (one-time cost)...")
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
 
    collection.add(
        ids=[c["id"] for c in chunks],
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=[{
            "professor": c.get("professor", ""),
            "department": c.get("department", ""),
            "course": c.get("course", ""),
            "rating": c.get("rating", ""),
            "source": c.get("source", ""),
            "source_file": c.get("source_file", c.get("source", "")),
            "source_type": c.get("source_type", ""),
        } for c in chunks],
    )
    print(f"Indexed {collection.count()} chunks into ChromaDB at {CHROMA_DIR}/")
    if collection.count() != len(chunks):
        print("WARNING: collection count != chunk count — something was dropped!")
 
# ---------------------------------------------------------------- retrieval
def retrieve(query: str, k: int = TOP_K):
    """Return the top-k chunks for a query: list of dicts with text,
    metadata, and cosine distance (lower = more similar)."""
    collection = get_collection()
    q_emb = get_model().encode([query], normalize_embeddings=True)
    res = collection.query(query_embeddings=q_emb.tolist(), n_results=k)
    hits = []
    for i in range(len(res["ids"][0])):
        hits.append({
            "id": res["ids"][0][i],
            "text": res["documents"][0][i],
            "distance": round(res["distances"][0][i], 3),
            "metadata": res["metadatas"][0][i],
        })
    return hits
 
def print_hits(query: str, hits):
    print(f"\n=== Query: {query}")
    for rank, h in enumerate(hits, 1):
        m = h["metadata"]
        src = m.get("source_file") or m.get("source") or "?"
        flag = "  <-- weak match (>0.5)" if h["distance"] > 0.5 else ""
        print(f"\n  #{rank}  distance={h['distance']}  [{src}]{flag}")
        print(f"      {h['text']}")
 
# ---------------------------------------------------------------- checks
def sanity_check():
    """Embed an indexed chunk's own text as the query — it must come back #1.
    (Verification step from planning.md AI-usage section.)"""
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    probe = chunks[0]
    hits = retrieve(probe["text"], k=1)
    top = hits[0]
    ok = top["id"] == probe["id"]
    print(f"Self-retrieval: queried chunk '{probe['id']}', got '{top['id']}' "
          f"(distance {top['distance']}) -> {'PASS' if ok else 'FAIL'}")
    if not ok:
        print("FAIL means indexing is broken — do not proceed to generation.")
 
def run_tests():
    for q in TEST_QUERIES:
        print_hits(q, retrieve(q))
    print("\nCheckpoint reminders:")
    print(" - Can you point at each top chunk and say WHY it's relevant?")
    print(" - Are top-result distances below ~0.5?")
    print(" - Are results coming from the RIGHT professor's file?")
 
# ---------------------------------------------------------------- main
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--index", action="store_true", help="(re)build the vector store")
    p.add_argument("--sanity", action="store_true", help="self-retrieval check")
    p.add_argument("--query", type=str, help="run a single ad-hoc query")
    p.add_argument("--test", action="store_true", help="run TEST_QUERIES")
    p.add_argument("-k", type=int, default=TOP_K, help="top-k (default 5)")
    args = p.parse_args()
 
    if args.index:
        build_index()
    if args.sanity:
        sanity_check()
    if args.query:
        print_hits(args.query, retrieve(args.query, k=args.k))
    if args.test:
        run_tests()
    if not any([args.index, args.sanity, args.query, args.test]):
        p.print_help()