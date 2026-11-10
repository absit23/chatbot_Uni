"""STEP 0 (run once): let Gemini read each PDF page as an image and write clean text.

Why? The guide's built-in text has damaged letters ("اجلامعات" for "الجامعات"),
while normal OCR damages the numbers. Students ask about scores and dates, so
wrong numbers are not acceptable. Gemini reads the page image and writes each
table row as one complete line, so a row still makes sense after chunking.

Safety check: the PDF's damaged text still has CORRECT numbers, so every number
Gemini writes is compared against it. Suspicious pages are listed at the end.

It uses about one free request per page. If it stops, run it again: finished
pages are kept and it continues where it left off.
"""
import json
import re
import time

import pymupdf
from google import genai
from google.genai import types

from config import CLEAN_PAGES_FILE, GEMINI_API_KEY, GEMINI_MODEL, OCR_PAGES_FILE, PDF_FILE, PRINTED_PAGE_OFFSET
from textutils import ARABIC_DIGITS

SECONDS_BETWEEN_PAGES = 7  # stays under the free per-minute limit

PROMPT = """انسخ النص العربي في صورة هذه الصفحة بدقة تامة، دون تلخيص أو إضافة أو تصحيح للمحتوى.
- احذف ترويسة الصفحة المتكررة ورقم الصفحة في الأسفل.
- انقل الأرقام والمعدلات والتواريخ كما هي تماماً بالأرقام الإنجليزية (0-9).
- حوّل كل صف من أي جدول إلى سطر واحد كامل يذكر اسم كل عمود مع قيمته، مثال:
القسم: الصيدلة | الفرع: علمي | الحد الأدنى صباحي: 90 | الحد الأدنى مسائي: لا يوجد
- إذا كانت الصفحة تحتوي على صور شاشة، فانسخ النص الظاهر فيها.
- أخرج النص فقط، بدون أي تعليق."""


def numbers_in(text: str) -> set[str]:
    return set(re.findall(r"\d+", text.translate(ARABIC_DIGITS)))


def load_finished() -> dict[int, str]:
    if not CLEAN_PAGES_FILE.exists():
        return {}
    with open(CLEAN_PAGES_FILE, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    return {r["page"]: r["text"] for r in records}


def transcribe(client: genai.Client, image_png: bytes) -> str | None:
    """Ask Gemini to read one page. Returns None if Gemini keeps refusing this page.

    Busy servers (503) and rate limits (429) are retried with longer waits.
    An EMPTY answer usually means Gemini blocked the page on purpose (for
    example, it looks like text published elsewhere), so retrying the same way
    rarely helps. We try twice more with a little randomness, then give up on
    this page and use the rough OCR text instead.
    """
    empty_answers = 0
    for attempt in range(6):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[types.Part.from_bytes(data=image_png, mime_type="image/png"), PROMPT],
                config=types.GenerateContentConfig(temperature=0 if empty_answers == 0 else 0.4),
            )
            if response.text:
                return response.text.strip()
            empty_answers += 1
            reason = response.candidates[0].finish_reason if response.candidates else "no candidates"
            print(f"  empty answer (reason: {reason})")
            if empty_answers >= 3:
                return None
        except Exception as error:
            wait = 30 * (attempt + 1)
            print(f"  problem: {error}\n  waiting {wait}s before trying again...")
            time.sleep(wait)
    raise SystemExit("Stopped after repeated failures. The daily limit may be used up: run this again later.")


def ocr_fallback(number: int) -> str:
    """The rough Tesseract text for one page: good words, unreliable numbers."""
    with open(OCR_PAGES_FILE, encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            if record["page"] == number:
                return record["text"]
    return ""


def main():
    if not GEMINI_API_KEY:
        raise SystemExit("Add GEMINI_API_KEY to your .env file first.")
    client = genai.Client(api_key=GEMINI_API_KEY)
    pdf = pymupdf.open(PDF_FILE)
    finished = load_finished()
    fallback_pages = []

    with open(CLEAN_PAGES_FILE, "a", encoding="utf-8") as out:
        for index, page in enumerate(pdf):
            number = index + 1 - PRINTED_PAGE_OFFSET
            if number in finished:
                continue
            print(f"page {index + 1}/{len(pdf)}")
            text = transcribe(client, page.get_pixmap(dpi=200).tobytes("png"))
            if text is None:
                print("  Gemini would not read this page. Using the rough OCR text instead.")
                text = ocr_fallback(number)
                fallback_pages.append(number)
            out.write(json.dumps({"page": number, "text": text}, ensure_ascii=False) + "\n")
            out.flush()
            finished[number] = text
            time.sleep(SECONDS_BETWEEN_PAGES)

    suspicious = {}
    for index, page in enumerate(pdf):
        number = index + 1 - PRINTED_PAGE_OFFSET
        extra = numbers_in(finished.get(number, "")) - numbers_in(page.get_text())
        if extra:
            suspicious[number] = sorted(extra)

    print("\nFinished. Now run: python src/ingest.py")
    if fallback_pages:
        print(f"These printed pages use rough OCR text, so check their numbers by eye: {fallback_pages}")
    if suspicious:
        print("Check these printed pages by eye. These numbers were not in the PDF's own text:")
        for number, values in suspicious.items():
            print(f"  page {number}: {values}")
    else:
        print("Number check passed on every page.")


if __name__ == "__main__":
    main()
