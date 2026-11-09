# University Admission Chatbot (RAG)

An Arabic chatbot that answers questions from the 2026-2027 private university admission guide and shows which pages it used.

## How it works

```
Once:         PDF -> clean text -> chunks -> embeddings -> vector database
Each question: question -> search (meaning + keywords) -> best chunks + question -> Gemini -> answer
```

| File | Job |
|---|---|
| `src/transcribe_guide.py` | Gemini reads each page image and writes clean text (run once) |
| `src/ingest.py` | Builds the searchable database (run once per dataset) |
| `src/rag.py` | Finds the right chunks and builds the prompt |
| `src/llm.py` | Calls Gemini, and switches to Groq if Gemini fails |
| `src/textutils.py` | Normalizes Arabic spelling for search |
| `src/config.py` | All settings |
| `app.py` | The chat website and the public link |

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

## Use different documents

Replace `data/guide.pdf`, edit `ASSISTANT_ROLE` and `DOCUMENT_NAME` in `src/config.py`, delete `data/guide_pages.jsonl`, and run the three commands again. No training is involved.

## Limits to know

- This repository is public, so only add documents that are already public.
- Answers can still be wrong. For decisions, students should confirm in the guide itself.
- `data/guide_pages_ocr.jsonl` is a rough backup. Its words are good, but its numbers are unreliable.
