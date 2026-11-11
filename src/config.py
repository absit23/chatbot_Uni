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
UNIVERSITY_NAME = "الجامعة الإسلامية - فرع بابل"
# \u200e keeps each number left-to-right, so Arabic text cannot reorder or cut it.
ADMISSION_CONTACT = "شعبة التسجيل والقبول في الجامعة الإسلامية فرع بابل على الرقم \u200e07726018188\u200e أو \u200e7535\u200e"
ASSISTANT_ROLE = f"مساعد القبول في {UNIVERSITY_NAME}، يجيب عن أسئلة التقديم والقبول والأجور للسنة الدراسية 2026-2027"
DOCUMENT_NAME = "الدليل الإرشادي للتقديم وضوابط القبول 2026-2027"

# Your university's own data (confirmed from its 2026-2027 admission poster)
UNIVERSITY_DIR = ROOT / "data" / "university"
DEPARTMENTS_FILE = UNIVERSITY_DIR / "departments.csv"   # used by the eligibility calculator
UNIVERSITY_INFO_FILE = UNIVERSITY_DIR / "info.md"      # searched like the guide's pages

# The PDF's first page is the cover, so printed page number = PDF page - 1.
PRINTED_PAGE_OFFSET = 1

# Every question and answer is saved here, without names, to review and improve the bot.
CHAT_LOG_FILE = ROOT / "logs" / "chats.jsonl"

# --- The vector database ---
DB_DIR = ROOT / "db"
COLLECTION = "guide"
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")

# --- Chunking and retrieval ---
CHUNK_SIZE = 900        # characters in one chunk
CHUNK_OVERLAP = 150     # characters shared with the next chunk
CANDIDATES = 15         # how many chunks each search method returns
TOP_K = 7               # how many chunks the LLM finally reads
UNIVERSITY_K = 2        # of those, how many always come from the university file

# --- The brain ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# --- The website ---
SHARE = os.getenv("SHARE", "true").lower() == "true"
# true = phones on the same Wi-Fi can open http://<this laptop's IP>:7860
LOCAL_NETWORK = os.getenv("LOCAL_NETWORK", "true").lower() == "true"
MAX_QUESTIONS_PER_VISITOR = int(os.getenv("MAX_QUESTIONS_PER_VISITOR", "15"))
MAX_QUESTIONS_PER_DAY = int(os.getenv("MAX_QUESTIONS_PER_DAY", "400"))
