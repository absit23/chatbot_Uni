# University Admission Chatbot (RAG)

An Arabic admission assistant for The Islamic University - Babylon Campus. It calculates which departments a student can apply to from their grade and branch, and answers questions from the university's own information and the ministry's 2026-2027 admission guide, showing its sources.

## How it works

```
Once:          PDF + university info -> clean text -> chunks -> embeddings -> vector database
Grade question: "معدلي 60 علمي" -> eligibility calculator (exact arithmetic, no AI request)
Other question: question -> search (university info first, then guide) -> Gemini -> answer
```

| File | Job |
|---|---|
| `src/transcribe_guide.py` | Gemini reads each page image and writes clean text (run once) |
| `src/ingest.py` | Builds the searchable database (run once per dataset) |
| `src/eligibility.py` | The calculator: grade + branch -> departments, fees, near misses |
| `src/rag.py` | Finds the right chunks and builds the prompt |
| `src/llm.py` | Calls Gemini, and switches to Groq if Gemini fails |
| `src/textutils.py` | Normalizes Arabic spelling for search |
| `src/config.py` | All settings |
| `app.py` | The chat website and the public link |
| `data/university/departments.csv` | Your university's departments, minimum grades and fees |
| `data/university/info.md` | Your university's discounts, contacts and department details |

## Setup

You need Python 3.10 or newer.

```
git clone https://github.com/absit23/chatbot_uni
cd chatbot_uni
git checkout build-chatbot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On Mac or Linux, activate with `source .venv/bin/activate`.

Copy `.env.example` to a new file named `.env` and add your free key from https://aistudio.google.com/apikey. Never upload `.env`.

## Run

```
python src/transcribe_guide.py
python src/ingest.py
python app.py
```

`transcribe_guide.py` takes about 20 minutes and uses about 143 free requests. Do not run it on the day of the event. It lists any pages whose numbers need checking by eye. Commit `data/guide_pages.jsonl` afterwards so you never need to repeat it.

`app.py` prints a public `gradio.live` link. It works while your laptop and the app stay running, lasts up to 72 hours, and changes on every restart.

## Check that nothing broke

After any change, run:

```
python -m pytest
```

Every dot is a passing check. A red `FAILED` line names the question that broke. The checks live in `tests/test_bot.py`: when you find a new mistake, add it there as a test, so it can never come back.

## Update university data

Edit `data/university/departments.csv` for minimum grades and fees (the calculator reads it directly), and `data/university/info.md` for anything students might ask. Each `# heading` section in `info.md` is searched as one piece, so keep one topic per section. Run `python src/ingest.py` after changing `info.md`.

## Use different documents

Replace `data/guide.pdf`, edit `ASSISTANT_ROLE` and `DOCUMENT_NAME` in `src/config.py`, delete `data/guide_pages.jsonl`, and run the three commands again. No training is involved.

## Limits to know

- This repository is public, so only add documents that are already public.
- Answers can still be wrong. For decisions, students should confirm in the guide itself.
- `data/guide_pages_ocr.jsonl` is a rough backup. Its words are good, but its numbers are unreliable.
