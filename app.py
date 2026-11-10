"""STEP 3: the chat website. Run with: python app.py"""
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import gradio as gr

sys.path.insert(0, str(Path(__file__).parent / "src"))

import eligibility  # noqa: E402
import rag  # noqa: E402
from config import MAX_QUESTIONS_PER_DAY, MAX_QUESTIONS_PER_VISITOR, SHARE  # noqa: E402
from llm import NoProviderAvailable  # noqa: E402

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


def limit_message(visitor: str) -> str | None:
    if today["date"] != date.today():
        today.update(date=date.today(), count=0)
    if today["count"] >= MAX_QUESTIONS_PER_DAY:
        return "عذراً، تم الوصول إلى الحد اليومي للأسئلة. حاول مرة أخرى غداً."
    if visitor_questions[visitor] >= MAX_QUESTIONS_PER_VISITOR:
        return "لقد وصلت إلى الحد الأقصى من الأسئلة لهذه الجلسة. شكراً لتجربتك!"
    return None


def chat(message: str, history: list, request: gr.Request) -> str:
    message = (message or "").strip()[:1000]
    if not message:
        return "اكتب سؤالك من فضلك."

    visitor = request.session_hash or "unknown"
    blocked = limit_message(visitor)
    if blocked:
        return blocked
    visitor_questions[visitor] += 1
    today["count"] += 1

    calculator_answer = eligibility.handle(message, history)
    if calculator_answer:
        return calculator_answer

    try:
        result = rag.answer(message)
    except NoProviderAvailable as error:
        print(f"[all providers failed] {error}")
        return "عذراً، الخدمة مشغولة حالياً. حاول بعد دقيقة."

    # The answer already cites its source inline, e.g. (ص 50) or (معلومات الجامعة).
    # The searched pages are printed in the terminal only, to help with testing.
    print(f"[searched] university info: {result['used_university_info']} | guide pages: {result['pages']} | {result['provider']}")
    return result["answer"]


with gr.Blocks(title="مساعد القبول - الجامعة الإسلامية فرع بابل") as demo:
    gr.HTML(f"<style>{CSS}</style>")
    gr.Markdown(
        "<div dir='rtl' align='center'><h2>مساعد القبول، الجامعة الإسلامية فرع بابل 2026-2027</h2>"
        "اكتب معدلك وفرعك لتعرف الأقسام المتاحة لك، أو اسأل عن الأجور والتخفيضات وشروط التقديم.<br>"
        "<small>الحد الأدنى يؤهلك للتقديم، والقبول النهائي يخضع للتنافس وضوابط الوزارة.</small></div>"
    )
    gr.ChatInterface(fn=chat, examples=EXAMPLES, cache_examples=False)

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=3).launch(share=SHARE)
