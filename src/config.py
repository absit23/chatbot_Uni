"""All settings in one place. Values come from the .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- Your data. To use different documents, change PDF_FILE, ASSISTANT_ROLE and DOCUMENT_NAME. ---
PDF_FILE = ROOT / "data" / "guide.pdf"
# guide_pages.jsonl is the accurate version made by src/transcribe_guide.py.
# guide_pages_ocr.jsonl is a rough backup: good words, but unreliable numbers.
CLEAN_PAGES_FILE = ROOT / "data" / "guide_pages.jsonl"
OCR_PAGES_FILE = ROOT / "data" / "guide_pages_ocr.jsonl"
PAGES_FILE = CLEAN_PAGES_FILE if CLEAN_PAGES_FILE.exists() else OCR_PAGES_FILE
ASSISTANT_ROLE = "مساعد للإجابة عن أسئلة التقديم والقبول في الجامعات والكليات الأهلية العراقية للسنة الدراسية 2026-2027"
DOCUMENT_NAME = "الدليل الإرشادي للتقديم وضوابط القبول 2026-2027"

# The PDF's first page is the cover, so printed page number = PDF page - 1.
PRINTED_PAGE_OFFSET = 1

# --- The vector database ---
DB_DIR = ROOT / "db"
COLLECTION = "guide"
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")

# --- Chunking and retrieval ---
CHUNK_SIZE = 900        # characters in one chunk
CHUNK_OVERLAP = 150     # characters shared with the next chunk
CANDIDATES = 15         # how many chunks each search method returns
TOP_K = 6               # how many chunks the LLM finally reads

# --- The brain ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# --- The website ---
SHARE = os.getenv("SHARE", "true").lower() == "true"
MAX_QUESTIONS_PER_VISITOR = int(os.getenv("MAX_QUESTIONS_PER_VISITOR", "15"))
MAX_QUESTIONS_PER_DAY = int(os.getenv("MAX_QUESTIONS_PER_DAY", "400"))
