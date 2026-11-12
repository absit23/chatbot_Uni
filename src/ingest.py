"""STEP 1 (run once per dataset): pages -> chunks -> embeddings -> vector database.

Think of it as the "training" step, except nothing is trained. We only build a
searchable index. To change the data, swap the pages file and run this again.
"""
import json
import re
import shutil

import chromadb
from sentence_transformers import SentenceTransformer

from config import CHUNK_OVERLAP, CHUNK_SIZE, CLEAN_PAGES_FILE, COLLECTION, DB_DIR, EMBED_MODEL, PAGES_FILE, UNIVERSITY_INFO_FILE


def load_pages() -> list[dict]:
    with open(PAGES_FILE, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def split_page(text: str) -> list[str]:
    """Cut one page into overlapping pieces, preferring to cut at line ends."""
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    chunks, start = [], 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            newline = text.rfind("\n", start + CHUNK_SIZE // 2, end)
            if newline != -1:
                end = newline
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


PAGE_JOIN = 400  # characters borrowed from the neighbouring pages


def build_chunks(pages: list[dict]) -> list[dict]:
    """Each chunk remembers its page, so answers can cite their source.

    A list or table often starts at the bottom of one page and continues on
    the next (the required documents start on page 19 and are listed on 20).
    So each page also gets the end of the previous page and the start of the
    next one, and a question about the heading also finds the list under it.
    """
    pages = sorted(pages, key=lambda p: p["page"])
    chunks = []
    for index, page in enumerate(pages):
        before = pages[index - 1]["text"][-PAGE_JOIN:] if index > 0 else ""
        after = pages[index + 1]["text"][:PAGE_JOIN] if index + 1 < len(pages) else ""
        joined = "\n".join(part for part in (before, page["text"], after) if part)
        for number, text in enumerate(split_page(joined)):
            if len(text) >= 30:  # skip page headers and empty scraps
                chunks.append({"id": f"p{page['page']}-{number}", "text": text, "page": page["page"], "source": "guide"})
    return chunks


def build_university_chunks() -> list[dict]:
    """Your university's info file: every '# heading' section becomes one chunk."""
    text = UNIVERSITY_INFO_FILE.read_text(encoding="utf-8")
    sections = [s.strip() for s in re.split(r"(?m)^# ", text) if s.strip()]
    return [
        {"id": f"u{number}", "text": section, "page": 0, "source": "university"}
        for number, section in enumerate(sections)
    ]


def main():
    if PAGES_FILE != CLEAN_PAGES_FILE:
        print("WARNING: using the rough OCR text. Scores and dates may be WRONG.")
        print("Run: python src/transcribe_guide.py   before showing this to anyone.")
    chunks = build_chunks(load_pages()) + build_university_chunks()
    print(f"{len(chunks)} chunks. Creating embeddings with {EMBED_MODEL} (a few minutes)...")

    model = SentenceTransformer(EMBED_MODEL)
    vectors = model.encode(
        [c["text"] for c in chunks], normalize_embeddings=True, batch_size=8, show_progress_bar=True
    ).tolist()

    if DB_DIR.exists():
        shutil.rmtree(DB_DIR)  # start clean so old data cannot mix with new data
    db = chromadb.PersistentClient(path=str(DB_DIR))
    collection = db.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    collection.add(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        embeddings=vectors,
        metadatas=[{"page": c["page"], "source": c["source"]} for c in chunks],
    )
    print(f"Done. Saved to {DB_DIR}")


if __name__ == "__main__":
    main()
