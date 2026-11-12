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
import history  # noqa: E402
import rag  # noqa: E402
import smalltalk  # noqa: E402
import staff  # noqa: E402

if not staff.STAFF:
    print("NOTE: no teaching staff list. Run:  python src/staff.py import \"your_file.xlsx\"")
else:
    print(f"Teaching staff list: {len(staff.STAFF)} rows loaded.")
from config import CHAT_LOG_FILE, LOCAL_NETWORK, MAX_QUESTIONS_PER_DAY, MAX_QUESTIONS_PER_VISITOR, SHARE  # noqa: E402
from llm import NoProviderAvailable  # noqa: E402
from textutils import text_of  # noqa: E402



ICONS = Path(__file__).parent / "assets" / "icons"
# (question, short label shown on the card, icon)
STARTERS = [
    ("معدلي 62 علمي، ما الأقسام المتاحة لي؟", "ما الأقسام المتاحة لمعدلي؟", "grade"),
    ("ما الوثائق المطلوبة للتسجيل؟", "الوثائق المطلوبة للتسجيل", "documents"),
    ("كم أجور الدراسة؟", "أجور الدراسة لكل قسم", "fees"),
    ("ما الأقسام الموجودة في الجامعة؟", "الأقسام والكليات", "departments"),
    ("ما هي التخفيضات؟", "التخفيضات في الأجور", "discounts"),
    ("أنا طالب في الجامعة", "أنا طالب حالي في الجامعة", "student"),
]
EXAMPLES = [q for q, _, _ in STARTERS]

WELCOME = """
<div class="welcome">
  <div class="orb"><span>✦</span></div>
  <h2>مرحباً بك في المساعد الذكي للجامعة الإسلامية - فرع بابل</h2>
  <p>للطلبة الجدد: اكتب معدلك وفرعك لتعرف الأقسام المتاحة لك، أو اسأل عن الأجور والتخفيضات والوثائق.
  ولطلبة الجامعة: اسأل عن التعليمات الامتحانية والرسوب والانتقال والاستضافة وسنة الترك والتدريب الصيفي.</p>
</div>
"""

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


def save_feedback(data: gr.LikeData, request: gr.Request) -> None:
    """A visitor pressed 👍 or 👎 under an answer."""
    answer = text_of(data.value)
    route = "feedback/like" if data.liked else "feedback/dislike"
    save_to_archive(request.session_hash or "unknown", f"[feedback on message {data.index}]", answer, route)


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
STUDENT_BUTTON = "أنا طالب في الجامعة"
STUDENT_TEXT = (
    "أهلاً بك 🎓 أستطيع مساعدتك في تعليمات الطلبة حسب الدليل الوزاري والتعليمات الامتحانية لسنة 2026، مثل:\n"
    "• النجاح والرسوب والدور الثاني، ومتى يُرقّن القيد\n"
    "• الغياب عن الامتحانات وعقوبات الغش\n"
    "• الانتقال والاستضافة بين الجامعات\n"
    "• سنة الترك في الدراسة المسائية\n"
    "• التدريب الصيفي وحساب معدل التخرج\n"
    "• انضباط الطلبة\n"
    "• إجراءات الجامعة: المباشرة بالدراسة وتأييد الاستمرارية\n\n"
    "اكتب سؤالك أو اختر من الأسئلة:"
)
STUDENT_QUESTIONS = [
    "كيف أباشر بالدراسة؟",
    "كيف أطلب تأييد استمرارية؟",
    "متى يُرقّن قيد الطالب بسبب الرسوب؟",
    "ما عقوبة الغش في الامتحان؟",
    "كيف أنتقل إلى جامعة أخرى؟",
    "ما هي سنة الترك في الدراسة المسائية؟",
]
SUGGESTIONS = [
    "ما هي التخفيضات؟",
    "ما الوثائق المطلوبة للتسجيل؟",
    CALCULATOR_BUTTON,
    "ما الأقسام الموجودة في الجامعة؟",
    "أين تقع الجامعة؟",
    "كم أجور الدراسة؟",
    STUDENT_BUTTON,
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
    metadata={"title": "المساعد يبحث لك في معلومات الجامعة والدليل الوزاري…", "status": "pending"},
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

    if message == STUDENT_BUTTON:
        save_to_archive(visitor, message, STUDENT_TEXT, "fixed")
        yield with_buttons(STUDENT_TEXT, [q for q in STUDENT_QUESTIONS if q not in str(history)])
        return

    if message == CALCULATOR_BUTTON:
        text = "اكتب معدلك وفرعك في رسالة واحدة، مثل: معدلي 62 علمي"
        save_to_archive(visitor, message, text, "calculator")
        yield text
        return

    social = smalltalk.answer(message)
    if social:
        save_to_archive(visitor, message, social, "smalltalk")
        yield with_buttons(social, next_suggestions(history, message))
        return

    replies = [text_of(i.get("content")) for i in history or []
               if isinstance(i, dict) and i.get("role") == "assistant" and not (i.get("metadata") or {}).get("title")]
    staff_answer = staff.handle(message, replies[-1] if replies else "")
    if staff_answer:
        save_to_archive(visitor, message, staff_answer, "staff")
        yield with_buttons(staff_answer, next_suggestions(history, message))
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
        turns = [i for i in history or [] if isinstance(i, dict)]
        asked = [text_of(i.get("content")) for i in turns if i.get("role") == "user"]
        replies = [text_of(i.get("content")) for i in turns if i.get("role") == "assistant" and not (i.get("metadata") or {}).get("title")]
        result = rag.answer(message, asked[-1] if asked else "", replies[-1] if replies else "")
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
    font=[gr.themes.GoogleFont("IBM Plex Sans Arabic"), gr.themes.GoogleFont("Tajawal"), "Segoe UI", "sans-serif"],
)
STYLE = {
    "theme": THEME,
    "css": (ASSETS / "style.css").read_text(encoding="utf-8"),
    # Arabic text for Gradio's own buttons, whatever language the visitor's browser uses.
    "i18n": gr.I18n(**{lang: {"chat_interface.new_chat": "محادثة جديدة"} for lang in ("en", "ar")}),
    # Phone margins, added as a plain <style> because Gradio rewrites @media rules in "css".
    "head": """<style>
      /* Never show Gradio's seconds counter or loading cover: the "searching…" message replaces them. */
      .progress-text, .meta-text, .meta-text-center, .eta-bar, .timer,
      .wrap.minimal .progress-text { display: none !important; }
      #chat .wrap.default, #chat .wrap.translucent, #chat .wrap.generating { display: none !important; }

      /* The message box floats: no grey band behind it */
      .form:has(#ask), .styler:has(#ask), .gr-group:has(#ask) {
        background: transparent !important; border: none !important; box-shadow: none !important;
      }

      /* Tablets */
      @media (max-width: 900px) {
        .gradio-container.gradio-container { padding: 12px 12px 4px !important; }
        #layout { flex-direction: column !important; }
        /* The side panel becomes a drawer that slides in from the right (☰ in the header) */
        #sidebar {
          position: fixed !important; top: 0; right: 0; bottom: 0; z-index: 900;
          width: 100vw !important; min-width: 0 !important; max-width: none !important;
          padding: 0 16px 24px !important; overflow-y: auto; gap: 12px !important;
          background: var(--ivory, #f7f3ea) !important;
          transform: translateX(105%); transition: transform .3s cubic-bezier(.2,.7,.2,1);
        }
        body.drawer-open #sidebar { transform: none; }
        #drawer-backdrop {
          position: fixed; inset: 0; z-index: 850; background: rgba(11,35,80,.35);
          opacity: 0; pointer-events: none; transition: opacity .25s;
        }
        body.drawer-open #drawer-backdrop { opacity: 1; pointer-events: auto; }
        .head-actions { display: flex !important; }
        #drawer-top { display: flex !important; }
        #chat-list .chat-list { max-height: none !important; }
      }
      /* Phones */
      @media (max-width: 560px) {
        .gradio-container.gradio-container { padding: 6px 2px 2px !important; }
        .gradio-container .main.main { padding-left: 4px !important; padding-right: 4px !important; }
        #uni-header { padding: 12px 14px !important; gap: 12px !important; border-radius: 18px !important; }
        #uni-header img { width: 50px !important; height: 50px !important; }
        #uni-header h1 { font-size: 17px !important; white-space: nowrap; }
        #uni-header .eyebrow { font-size: 12px !important; white-space: nowrap; }
        #uni-header { gap: 10px !important; }
        #uni-header .round-btn { width: 36px !important; height: 36px !important; font-size: 16px !important; }
        #uni-header .year { display: none !important; }
        #uni-header .english { display: none; }
        #uni-header .year { padding: 4px 8px !important; font-size: 10.5px !important; }
        #chat .welcome h2 { font-size: 19px !important; }
        #chat .welcome p { font-size: 13.5px !important; }
        /* Starter questions: compact two-column cards with the icon beside the text */
        #chat .examples { grid-template-columns: 1fr 1fr !important; gap: 8px !important; width: 100% !important; }
        #chat .example { padding: 10px !important; min-height: 0 !important; }
        #chat .example-content { flex-direction: row !important; align-items: center !important; gap: 8px !important; }
        #chat .example-content img { width: 20px !important; height: 20px !important; }
        #chat .example-content * { font-size: 13px !important; }
        #chat .welcome { padding-top: 0 !important; }
        #chat .welcome .orb { width: 52px !important; height: 52px !important; margin-bottom: 10px !important; }
      }
    </style>""",
    # Always use the light design, even on phones set to dark mode.
    "js": """() => {
        const url = new URL(window.location);
        if (url.searchParams.get('__theme') !== 'light') {
            url.searchParams.set('__theme', 'light');
            window.location.replace(url);
            return;
        }
        // Phones and tablets: ☰ opens the conversations drawer; choosing anything closes it.
        if (!document.getElementById('drawer-backdrop')) {
            const backdrop = document.createElement('div');
            backdrop.id = 'drawer-backdrop';
            document.body.appendChild(backdrop);
        }
        const close = () => document.body.classList.remove('drawer-open');
        document.addEventListener('click', (event) => {
            if (event.target.closest('#menu-btn')) { document.body.classList.add('drawer-open'); return; }
            if (event.target.closest('#drawer-close')) { close(); return; }
            if (event.target.closest('#newchat-btn')) { const b = document.querySelector('#new-chat'); if (b) b.click(); close(); return; }
            if (event.target.id === 'drawer-backdrop') { close(); return; }
            const picked = event.target.closest('#new-chat, #quick-list button, #chat-list .chat-item');
            const menu = event.target.closest('.chat-dots, .chat-menu');
            if (picked && !menu) setTimeout(close, 150);
        });
    }""",
}

HEADER = f"""
<div id="uni-header">
  <img src="{LOGO}" alt="شعار الجامعة الإسلامية - فرع بابل">
  <div class="titles">
    <div class="eyebrow">الجامعة الإسلامية - فرع بابل</div>
    <h1>المساعد الذكي</h1>
    <div class="english">The Islamic University – Babylon Campus · AI Assistant</div>
  </div>
  <div class="year">2026 – 2027</div>
  <div class="head-actions">
    <button id="newchat-btn" class="round-btn" aria-label="محادثة جديدة">✎</button>
    <button id="menu-btn" class="round-btn" aria-label="المحادثات">☰</button>
  </div>
</div>
"""
NOTE = (
    "<div id='note'>المعلومات من الجامعة والدليل الوزاري، والقبول النهائي يخضع للتنافس وضوابط الوزارة. "
    "تُحفظ الأسئلة بدون أسماء لتحسين الخدمة.</div>"
)

def _svg_data(name: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode((ICONS / f"{name}.svg").read_bytes()).decode()


QUICK_LIST = "<div class='quick'>" + "".join(
    f"<button data-q='{q}'><img src='{_svg_data(icon)}' alt=''>{label}</button>" for q, label, icon in STARTERS
) + "</div>"
# Runs in the browser: a quick question is typed into the message box and sent.
QUICK_JS = """
element.addEventListener('click', (event) => {
  const button = event.target.closest('button[data-q]');
  if (!button) return;
  const box = document.querySelector('#ask textarea');
  if (!box) return;
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  setter.call(box, button.dataset.q);
  box.dispatchEvent(new Event('input', { bubbles: true }));
  setTimeout(() => {
    const send = document.querySelector('#ask button.submit-button') || document.querySelector('#ask button');
    if (send) send.click();
  }, 60);
});
"""


# ---------- Saved conversations (pin, rename, delete) ----------

def show_list(store, current_id):
    return history.render(store, current_id)


def remember(messages, current_id, store):
    """After every answer, save the open conversation in the visitor's browser."""
    store, current_id = history.save(store, current_id, messages)
    return current_id, store, history.render(store, current_id)


def start_new_chat(store):
    return [], [], None, history.render(store, None)


def list_action(store, current_id, event: gr.EventData):
    """A click in the side list: open a conversation, or pin / rename / delete it."""
    data = getattr(event, "_data", None) or {}
    action, chat_id = data.get("action"), data.get("id")
    keep = gr.skip()
    chat_view, state = keep, keep
    if action == "open" and history.find(store, chat_id):
        messages = history.find(store, chat_id)["messages"]
        chat_view, state, current_id = messages, messages, chat_id
    elif action == "pin":
        store = history.toggle_pin(store, chat_id)
    elif action == "rename":
        store = history.rename(store, chat_id, data.get("title", ""))
    elif action == "delete":
        store = history.delete(store, chat_id)
        if chat_id == current_id:
            chat_view, state, current_id = [], [], None
    return chat_view, state, current_id, store, history.render(store, current_id)


with gr.Blocks(title="المساعد الذكي - الجامعة الإسلامية فرع بابل") as demo:
    gr.HTML(HEADER, elem_id="uni-header-box", padding=False)
    saved = gr.BrowserState([], storage_key="islamic_uni_babylon_chats")
    current = gr.State(None)

    with gr.Row(elem_id="layout", equal_height=False):
        with gr.Column(scale=1, min_width=220, elem_id="sidebar"):
            # Top bar of the conversations page on phones (hidden on laptops)
            gr.HTML("<div id='drawer-top'><button id='drawer-close' class='round-btn' aria-label='رجوع'>→</button>"
                    "<span>المحادثات</span></div>", padding=False)
            new_chat = gr.Button("＋  محادثة جديدة", elem_id="new-chat")
            gr.HTML("<div class='side-title'>المحادثات</div>", padding=False)
            chat_list = gr.HTML(history.render([], None), elem_id="chat-list", js_on_load=history.LIST_JS,
                                padding=False, apply_default_css=False)
            gr.HTML("<div class='side-title quick-title'>أسئلة سريعة</div>", padding=False)
            gr.HTML(QUICK_LIST, elem_id="quick-list", js_on_load=QUICK_JS, padding=False, apply_default_css=False)
        with gr.Column(scale=4, min_width=320):
            chatbot = gr.Chatbot(
                # The chat fills the screen height under the header, on laptops and phones.
                elem_id="chat", show_label=False, rtl=True, height="calc(100dvh - 250px)", min_height=420,
                render=False,  # placed inside the ChatInterface below
                buttons=["copy"],  # only a copy button on each message: no share or delete
                feedback_options=("Like", "Dislike"),
                avatar_images=(None, str(LOGO_FILE)),
                placeholder=WELCOME,
            )
            interface = gr.ChatInterface(
                fn=chat,
                examples=EXAMPLES,
                example_labels=[label for _, label, _ in STARTERS],
                example_icons=[str(ICONS / f"{icon}.svg") for _, _, icon in STARTERS],
                cache_examples=False,
                # api_visibility="private": nobody can call the bot from their own code and
                # skip the website (and its limits); only the chat page can use it.
                api_visibility="private",
                show_progress="hidden",  # no seconds counter: a friendly "searching…" message is shown instead
                chatbot=chatbot,
                textbox=gr.Textbox(
                    elem_id="ask", rtl=True, show_label=False, submit_btn=True,
                    stop_btn=True,  # while the bot answers, a stop button takes the send button's place
                    placeholder="اكتب سؤالك هنا… مثال: معدلي 62 علمي",
                ),
            )
    gr.HTML(NOTE, elem_id="note-box", padding=False)

    # 👍 / 👎 under each answer: saved to the chat archive to see which answers need fixing.
    chatbot.like(save_feedback, inputs=None, outputs=None, api_visibility="private")

    # Saved conversations live in the visitor's browser: no account, nothing stored on this laptop.
    hidden = {"api_visibility": "private", "show_progress": "hidden", "queue": False}
    demo.load(show_list, [saved, current], [chat_list], **hidden)
    chatbot.change(remember, [chatbot, current, saved], [current, saved, chat_list], **hidden)
    chatbot.clear(start_new_chat, [saved], [chatbot, interface.chatbot_state, current, chat_list], **hidden)
    new_chat.click(start_new_chat, [saved], [chatbot, interface.chatbot_state, current, chat_list], **hidden)
    chat_list.click(list_action, [saved, current],
                    [chatbot, interface.chatbot_state, current, saved, chat_list], **hidden)


if __name__ == "__main__":
    if LOCAL_NETWORK:
        print("Phones on the same Wi-Fi: open http://<this laptop's IPv4 address>:7860  (find it with: ipconfig)")
    demo.queue(default_concurrency_limit=3).launch(
        share=SHARE, server_name="0.0.0.0" if LOCAL_NETWORK else "127.0.0.1", server_port=7860,
        footer_links=[],  # hide "Use via API · Built with Gradio · Settings"
        **STYLE,
    )
