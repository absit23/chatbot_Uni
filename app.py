"""STEP 3: the chat website. Run with: python app.py"""
import base64
import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import gradio as gr

sys.path.insert(0, str(Path(__file__).parent / "src"))

import eligibility  # noqa: E402
import faq  # noqa: E402
import rag  # noqa: E402
from config import CHAT_LOG_FILE, LOCAL_NETWORK, MAX_QUESTIONS_PER_DAY, MAX_QUESTIONS_PER_VISITOR, SHARE  # noqa: E402
from llm import NoProviderAvailable  # noqa: E402
from textutils import text_of  # noqa: E402



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


THINKING = gr.ChatMessage(
    role="assistant",
    content="",
    metadata={"title": "🔎 أبحث لك في معلومات الجامعة والدليل الوزاري…", "status": "pending"},
)


def chat(message: str, history: list, request: gr.Request):
    """A generator: it can first show "searching…" and then replace it with the answer."""
    message = (message or "").strip()[:1000]
    if not message:
        yield "اكتب سؤالك من فضلك."
        return

    visitor = request.session_hash or "unknown"
    blocked = limit_message(visitor)
    if blocked:
        yield blocked
        return
    visitor_questions[visitor] += 1
    today["count"] += 1

    if message == CALCULATOR_BUTTON:
        text = "اكتب معدلك وفرعك في رسالة واحدة، مثل: معدلي 62 علمي"
        save_to_archive(visitor, message, text, "calculator")
        yield text
        return

    fixed = faq.answer(message)
    if fixed and not eligibility.handle(message, history):
        save_to_archive(visitor, message, fixed, "fixed")
        yield with_buttons(fixed, next_suggestions(history, message))
        return

    calculator = eligibility.handle(message, history)
    if calculator:
        text, buttons = calculator
        save_to_archive(visitor, message, text, "calculator")
        yield with_buttons(text, buttons or next_suggestions(history, message, skip=(CALCULATOR_BUTTON,)))
        return

    yield THINKING  # shown only while the AI works (1-3 seconds); the answer replaces it
    try:
        previous = [text_of(i.get("content")) for i in history or [] if isinstance(i, dict) and i.get("role") == "user"]
        result = rag.answer(message, previous[-1] if previous else "")
    except NoProviderAvailable as error:
        print(f"[all providers failed] {error}")
        save_to_archive(visitor, message, "", "failed")
        yield "عذراً، الخدمة مشغولة حالياً. حاول بعد دقيقة."
        return

    # The answer already cites its source inline, e.g. (ص 50) or (معلومات الجامعة).
    # The searched pages are printed in the terminal only, to help with testing.
    print(f"[searched] university info: {result['used_university_info']} | guide pages: {result['pages']} | {result['provider']}")
    save_to_archive(visitor, message, result["answer"], f"search/{result['provider']}")
    yield with_buttons(result["answer"], next_suggestions(history, message))
    return


# ---------- Look and feel ----------
ASSETS = Path(__file__).parent / "assets"
LOGO_FILE = ASSETS / "logo.png"
LOGO = "data:image/png;base64," + base64.b64encode(LOGO_FILE.read_bytes()).decode()

THEME = gr.themes.Soft(
    primary_hue=gr.themes.colors.amber,
    font=[gr.themes.GoogleFont("Tajawal"), "Segoe UI", "Tahoma", "sans-serif"],
)
STYLE = {
    "theme": THEME,
    "css": (ASSETS / "style.css").read_text(encoding="utf-8"),
    # Phone margins, added as a plain <style> because Gradio rewrites @media rules in "css".
    "head": """<style>
      @media (max-width: 560px) {
        .gradio-container.gradio-container { padding: 6px 2px 2px !important; }
        .gradio-container .main.main { padding-left: 4px !important; padding-right: 4px !important; }
      }
    </style>""",
    # Always use the light design, even on phones set to dark mode.
    "js": """() => {
        const url = new URL(window.location);
        if (url.searchParams.get('__theme') !== 'light') {
            url.searchParams.set('__theme', 'light');
            window.location.replace(url);
        }
    }""",
}

HEADER = f"""
<div id="uni-header">
  <img src="{LOGO}" alt="شعار الجامعة الإسلامية - فرع بابل">
  <div class="titles">
    <div class="eyebrow">الجامعة الإسلامية - فرع بابل</div>
    <h1>المساعد الذكي للقبول</h1>
    <div class="english">The Islamic University – Babylon Campus · AI Admission Assistant</div>
  </div>
  <div class="year">2026 - 2027</div>
</div>
<div id="intro">اكتب معدلك وفرعك لتعرف الأقسام المتاحة لك، أو اسأل عن الأجور والتخفيضات وشروط التقديم.</div>
"""
NOTE = (
    "<div id='note'>الحد الأدنى يؤهلك للتقديم، والقبول النهائي يخضع للتنافس وضوابط الوزارة. "
    "تُحفظ الأسئلة بدون أسماء لتحسين الخدمة.</div>"
)

with gr.Blocks(title="المساعد الذكي للقبول - الجامعة الإسلامية فرع بابل") as demo:
    gr.HTML(HEADER, elem_id="uni-header-box", padding=False)
    # api_visibility="private": nobody can call the bot from their own code and
    # skip the website (and its limits); only the chat page can use it.
    gr.ChatInterface(
        fn=chat,
        examples=EXAMPLES,
        cache_examples=False,
        api_visibility="private",
        show_progress="hidden",  # no seconds counter: a friendly "searching…" message is shown instead
        chatbot=gr.Chatbot(
            # The chat fills the screen height under the header, on laptops and phones.
            elem_id="chat", show_label=False, rtl=True, height="calc(100dvh - 330px)", min_height=380,
            buttons=["copy"],  # only a copy button on each message: no share or delete
            avatar_images=(None, str(LOGO_FILE)),
            placeholder="<div style='text-align:center;color:#0b2350;font-weight:700'>اسأل عن القبول في الجامعة الإسلامية - فرع بابل</div>",
        ),
        textbox=gr.Textbox(
            elem_id="ask", rtl=True, show_label=False, submit_btn=True,
            placeholder="اكتب سؤالك هنا… مثال: معدلي 62 علمي",
        ),
    )
    gr.HTML(NOTE, elem_id="note-box", padding=False)

if __name__ == "__main__":
    if LOCAL_NETWORK:
        print("Phones on the same Wi-Fi: open http://<this laptop's IPv4 address>:7860  (find it with: ipconfig)")
    demo.queue(default_concurrency_limit=3).launch(
        share=SHARE, server_name="0.0.0.0" if LOCAL_NETWORK else "127.0.0.1", server_port=7860,
        footer_links=[],  # hide "Use via API · Built with Gradio · Settings"
        **STYLE,
    )
