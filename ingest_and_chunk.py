"""
ingest_and_chunk.py — Milestone 2: ingestion, cleaning, and chunking
Implements the Chunking Strategy from planning.md:
  - RMP files:    1 review = 1 chunk, ~250 token cap, 0 overlap
  - Reddit files: 1 comment = 1 chunk; comments over the cap are split
                  with ~50 token overlap
  - Every chunk gets a metadata prefix: [Professor | Dept | Course | Rating]
 
Expected raw file format (data/raw/*.txt):
    PROFESSOR: Jane Doe
    DEPARTMENT: Computer Science
    COURSE: CSIT-345
    SOURCE: https://...
    TYPE: rmp            (or: reddit)
    ---
    Rating: 4.0 | Course: CSIT345
    <review text>
    ---
    <next review>
    ---
 
Usage:
    python ingest_and_chunk.py            # chunk everything in data/raw/
    python ingest_and_chunk.py --inspect  # also print 5 random chunks to review
"""
 
import argparse
import html
import json
import random
import re
from pathlib import Path
 
RAW_DIR = Path("data/raw")
OUT_FILE = Path("data/chunks.json")
CHUNK_TOKEN_CAP = 250
SPLIT_OVERLAP_TOKENS = 50
 
# ---------------------------------------------------------------- tokenizer
# Use the REAL MiniLM tokenizer so token counts match what the embedding
# model actually sees (planning.md: "checked with the tokenizer, not len()").
# Falls back to a word-based estimate if transformers isn't installed yet.
try:
    from transformers import AutoTokenizer
    _tok = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
 
    def count_tokens(text: str) -> int:
        return len(_tok.encode(text, add_special_tokens=False))
 
    def tokenize_words(text: str):
        return text.split()
 
    USING_REAL_TOKENIZER = True
except Exception:
    def count_tokens(text: str) -> int:
        # rough estimate: 1 word ~ 1.3 MiniLM tokens
        return int(len(text.split()) * 1.3)
 
    def tokenize_words(text: str):
        return text.split()
 
    USING_REAL_TOKENIZER = False
 
# ---------------------------------------------------------------- cleaning
BOILERPLATE_PATTERNS = [
    r"Helpful\s*·?\s*\d+\s*·?\s*\d+",          # RMP helpful/unhelpful counts
    r"Report this rating",
    r"Share\b.*$",
    r"Read more",
    r"\d+\s+(points?|upvotes?)\s*·",            # reddit vote counts
    r"Reply\s*·",
    r"level \d+",                                # reddit comment depth markers
    r"https?://\S+",                             # stray links inside review text
]
 
def clean_text(text: str) -> str:
    """Strip HTML artifacts and site boilerplate, keep the substantive review."""
    text = html.unescape(text)                       # &amp; &#39; &nbsp; -> chars
    text = re.sub(r"<[^>]+>", " ", text)             # any leftover HTML tags
    for pat in BOILERPLATE_PATTERNS:
        text = re.sub(pat, " ", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()         # collapse whitespace
    return text
 
# ---------------------------------------------------------------- parsing
HEADER_KEYS = ("PROFESSOR", "DEPARTMENT", "COURSE", "SOURCE", "TYPE")
 
def parse_file(path: Path):
    """Returns (metadata dict, list of raw review/comment blocks)."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    meta = {k.lower(): "" for k in HEADER_KEYS}
 
    header, _, body = raw.partition("---")
    for line in header.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip().upper()
            if key in HEADER_KEYS:
                meta[key.lower()] = val.strip()
 
    if not meta["professor"] and not meta["type"]:
        raise ValueError(
            f"{path.name}: missing header. Each raw file needs PROFESSOR/TYPE "
            f"lines followed by '---' separated reviews (see script docstring)."
        )
 
    blocks = [b.strip() for b in body.split("---") if b.strip()]
    return meta, blocks
 
def extract_block_rating(block: str):
    """Pull a 'Rating: 4.0' line off the front of a review block, if present."""
    m = re.match(r"Rating:\s*([\d.]+)\s*(?:\|\s*Course:\s*(\S+))?\s*\n?", block)
    if m:
        rating = m.group(1)
        course = m.group(2) or ""
        rest = block[m.end():]
        return rating, course, rest
    return "", "", block
 
# ---------------------------------------------------------------- chunking
def metadata_prefix(meta: dict, rating: str, course_override: str) -> str:
    course = course_override or meta["course"]
    parts = [p for p in (meta["professor"], meta["department"], course) if p]
    if rating:
        parts.append(f"Rating {rating}/5")
    return "[" + " | ".join(parts) + "] "
 
def split_with_overlap(text: str, cap: int, overlap: int):
    """Split an oversized block into <=cap-token pieces with token overlap.
    Splits on sentence boundaries where possible."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces, current = [], []
    current_count = 0
    for sent in sentences:
        n = count_tokens(sent)
        if current and current_count + n > cap:
            pieces.append(" ".join(current))
            # carry the tail of the previous piece forward as overlap
            tail_words = tokenize_words(pieces[-1])[-overlap:]
            current = [" ".join(tail_words)]
            current_count = count_tokens(current[0])
        current.append(sent)
        current_count += n
    if current:
        pieces.append(" ".join(current))
    return pieces
 
def chunk_file(meta: dict, blocks: list[str]):
    """Apply the planning.md strategy: 1 block = 1 chunk; split only if oversized."""
    chunks = []
    for i, block in enumerate(blocks):
        rating, course, body = extract_block_rating(block)
        body = clean_text(body)
        if not body or count_tokens(body) < 5:      # skip empty/junk blocks
            continue
        prefix = metadata_prefix(meta, rating, course)
 
        if count_tokens(prefix + body) <= CHUNK_TOKEN_CAP:
            pieces = [body]
        else:
            # only Reddit comments should realistically hit this branch
            budget = CHUNK_TOKEN_CAP - count_tokens(prefix)
            pieces = split_with_overlap(body, budget, SPLIT_OVERLAP_TOKENS)
 
        for j, piece in enumerate(pieces):
            chunks.append({
                "id": f"{meta['professor'] or meta['source']}-{i}-{j}".replace(" ", "_"),
                "text": prefix + piece,
                "professor": meta["professor"],
                "department": meta["department"],
                "course": course or meta["course"],
                "rating": rating,
                "source": meta["source"],
                "source_type": meta["type"],
            })
    return chunks
 
# ---------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect", action="store_true",
                        help="print 5 random chunks for manual review")
    args = parser.parse_args()
 
    if not USING_REAL_TOKENIZER:
        print("NOTE: transformers not installed — token counts are estimates.")
        print("      pip install transformers  (then rerun) for exact counts.\n")
 
    files = sorted(RAW_DIR.glob("*.txt"))
    if not files:
        print(f"No .txt files found in {RAW_DIR}/ — collect your documents first.")
        return
 
    all_chunks = []
    for path in files:
        meta, blocks = parse_file(path)
        file_chunks = chunk_file(meta, blocks)
        all_chunks.extend(file_chunks)
        print(f"{path.name:40s} -> {len(blocks):3d} blocks -> {len(file_chunks):3d} chunks")
 
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(all_chunks, indent=2), encoding="utf-8")
 
    print(f"\nTotal: {len(all_chunks)} chunks from {len(files)} documents")
    print(f"Saved to {OUT_FILE}")
    if len(all_chunks) < 50:
        print("WARNING: <50 chunks — per the checklist, chunks may be too large "
              "or you need more documents.")
    if len(all_chunks) > 2000:
        print("WARNING: >2000 chunks — chunks may be too small.")
 
    if args.inspect:
        print("\n----- 5 random chunks for inspection -----")
        for c in random.sample(all_chunks, min(5, len(all_chunks))):
            print(f"\n[{c['id']}] ({count_tokens(c['text'])} tokens)")
            print(c["text"])
 
if __name__ == "__main__":
    main()
 