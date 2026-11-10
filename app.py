"""STEP 3: the chat website. Run with: python app.py"""
import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import gradio as gr

sys.path.insert(0, str(Path(__file__).parent / "src"))

import eligibility  # noqa: E402
import rag  # noqa: E402
from config import CHAT_LOG_FILE, LOCAL_NETWORK, MAX_QUESTIONS_PER_DAY, MAX_QUESTIONS_PER_VISITOR, SHARE  # noqa: E402
from llm import NoProviderAvailable  # noqa: E402
from textutils import text_of  # noqa: E402

CSS = """
.message, .message * { direction: rtl; text-align: right; }
textarea { direction: rtl; text-align: right; }
"""

EXAMPLES = [
    "معدلي 60 فرع علمي، ما الأقسام المتاحة لي؟",
    "كم أجور قسم القانون؟",
    "ما التخفيضات للإخوة؟",
    "ما هي الوثائق المطلوبة للتسجيل؟",
]

# These counters live in memory and reset when the app restarts.
visitor_questions: Counter = Counter()
today = {"date": date.today(), "count": 0}


def save_to_archive(visitor: str, question: str, answer: str, route: str) -> None:
    """Keep every exchange in logs/chats.jsonl. The visitor is a random session code, not a name."""
    try:
        CHAT_LOG_FILE.parent.mkdir(exist_ok=True)
        record = {"time": datetime.now().isoformat(timespec="seconds"), "visitor": visitor[:8],
                  "route": route, "question": question, "answer": answer}
        with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as error:  # never let saving break the chat
        print(f"[archive failed] {error}")


def limit_message(visitor: str) -> str | None:
    if today["date"] != date.today():
        today.update(date=date.today(), count=0)
    if today["count"] >= MAX_QUESTIONS_PER_DAY:
        return "عذراً، تم الوصول إلى الحد اليومي للأسئلة. حاول مرة أخرى غداً."
    if visitor_questions[visitor] >= MAX_QUESTIONS_PER_VISITOR:
        return "لقد وصلت إلى الحد الأقصى من الأسئلة لهذه الجلسة. شكراً لتجربتك!"
    return None


# Suggested next questions, shown as buttons under answers (3 at a time, never one already asked).
CALCULATOR_BUTTON = "اعرف الأقسام المتاحة لمعدلي"
SUGGESTIONS = [
    "ما هي التخفيضات؟",
    "ما الوثائق المطلوبة للتسجيل؟",
    CALCULATOR_BUTTON,
    "ما الأقسام الموجودة في الجامعة؟",
    "أين تقع الجامعة؟",
    "كم أجور الدراسة؟",
]


def next_suggestions(history: list, message: str, skip: tuple[str, ...] = ()) -> list[str]:
    asked = {message.strip(), *skip}
    for item in history or []:
        if isinstance(item, dict) and item.get("role") == "user":
            asked.add(text_of(item.get("content")).strip())
    used_calculator = any("حاسبة القبول" in text_of(i.get("content")) for i in history or [] if isinstance(i, dict))
    pool = [q for q in SUGGESTIONS if q not in asked and not (q == CALCULATOR_BUTTON and used_calculator)]
    return pool[:3]


def with_buttons(text: str, buttons: list[str]) -> gr.ChatMessage:
    """An answer with clickable follow-up questions under it, like ChatGPT's suggestions."""
    return gr.ChatMessage(role="assistant", content=text, options=[{"value": b} for b in buttons])


def chat(message: str, history: list, request: gr.Request) -> str | gr.ChatMessage:
    message = (message or "").strip()[:1000]
    if not message:
        return "اكتب سؤالك من فضلك."

    visitor = request.session_hash or "unknown"
    blocked = limit_message(visitor)
    if blocked:
        return blocked
    visitor_questions[visitor] += 1
    today["count"] += 1

    if message == CALCULATOR_BUTTON:
        text = "اكتب معدلك وفرعك في رسالة واحدة، مثل: معدلي 62 علمي"
        save_to_archive(visitor, message, text, "calculator")
        return text

    calculator = eligibility.handle(message, history)
    if calculator:
        text, buttons = calculator
        save_to_archive(visitor, message, text, "calculator")
        return with_buttons(text, buttons or next_suggestions(history, message, skip=(CALCULATOR_BUTTON,)))

    try:
        previous = [text_of(i.get("content")) for i in history or [] if isinstance(i, dict) and i.get("role") == "user"]
        result = rag.answer(message, previous[-1] if previous else "")
    except NoProviderAvailable as error:
        print(f"[all providers failed] {error}")
        save_to_archive(visitor, message, "", "failed")
        return "عذراً، الخدمة مشغولة حالياً. حاول بعد دقيقة."

    # The answer already cites its source inline, e.g. (ص 50) or (معلومات الجامعة).
    # The searched pages are printed in the terminal only, to help with testing.
    print(f"[searched] university info: {result['used_university_info']} | guide pages: {result['pages']} | {result['provider']}")
    save_to_archive(visitor, message, result["answer"], f"search/{result['provider']}")
    return with_buttons(result["answer"], next_suggestions(history, message))


with gr.Blocks(title="مساعد القبول - الجامعة الإسلامية فرع بابل") as demo:
    gr.HTML(f"<style>{CSS}</style>")
    gr.Markdown(
        "<div dir='rtl' align='center'><h2>مساعد القبول، الجامعة الإسلامية فرع بابل 2026-2027</h2>"
        "اكتب معدلك وفرعك لتعرف الأقسام المتاحة لك، أو اسأل عن الأجور والتخفيضات وشروط التقديم.<br>"
        "<small>الحد الأدنى يؤهلك للتقديم، والقبول النهائي يخضع للتنافس وضوابط الوزارة. "
        "تُحفظ الأسئلة بدون أسماء لتحسين الخدمة.</small></div>"
    )
    gr.ChatInterface(fn=chat, examples=EXAMPLES, cache_examples=False)

if __name__ == "__main__":
    if LOCAL_NETWORK:
        print("Phones on the same Wi-Fi: open http://<this laptop's IPv4 address>:7860  (find it with: ipconfig)")
    demo.queue(default_concurrency_limit=3).launch(
        share=SHARE, server_name="0.0.0.0" if LOCAL_NETWORK else "127.0.0.1", server_port=7860
    )
