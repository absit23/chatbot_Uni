"""Saved conversations: kept in the visitor's own browser, with pin, rename and delete.

The list lives in the browser (gr.BrowserState), so there is no account and
nothing is stored on the laptop. Each saved conversation is a dict:
    {"id": "...", "title": "...", "pinned": False, "time": 1731312000.0, "messages": [...]}
These functions are plain Python so they can be tested without a browser.
"""
import html
import time
import uuid

from textutils import text_of

TITLE_LENGTH = 40


def _clean(messages: list) -> list:
    """Drop the temporary "searching…" message, which is not part of the conversation."""
    return [m for m in messages or [] if (m.get("metadata") or {}).get("status") != "pending"]


def _title(messages: list) -> str:
    first = next((text_of(m.get("content")) for m in messages if m.get("role") == "user"), "محادثة")
    first = " ".join(first.split())
    return first if len(first) <= TITLE_LENGTH else first[:TITLE_LENGTH].rstrip() + "…"


def save(store: list, current_id: str | None, messages: list) -> tuple[list, str | None]:
    """Save the open conversation. Returns the new list and the conversation's id."""
    messages = _clean(messages)
    if not any(m.get("role") == "assistant" for m in messages):
        return store, current_id  # nothing worth saving yet
    store = list(store or [])
    for chat in store:
        if chat["id"] == current_id:
            chat["messages"] = messages
            chat["time"] = time.time()
            return store, current_id
    new_id = uuid.uuid4().hex[:12]
    store.insert(0, {"id": new_id, "title": _title(messages), "pinned": False,
                     "time": time.time(), "messages": messages})
    return store, new_id


def find(store: list, chat_id: str | None) -> dict | None:
    return next((c for c in store or [] if c["id"] == chat_id), None)


def rename(store: list, chat_id: str, title: str) -> list:
    title = " ".join((title or "").split())[:60]
    if title:
        for chat in store:
            if chat["id"] == chat_id:
                chat["title"] = title
    return store


def toggle_pin(store: list, chat_id: str) -> list:
    for chat in store:
        if chat["id"] == chat_id:
            chat["pinned"] = not chat.get("pinned")
    return store


def delete(store: list, chat_id: str) -> list:
    return [c for c in store if c["id"] != chat_id]


def ordered(store: list) -> list:
    """Pinned conversations first, then the most recent."""
    return sorted(store or [], key=lambda c: (not c.get("pinned"), -c.get("time", 0)))


def render(store: list, current_id: str | None) -> str:
    """The side list as HTML. Titles are escaped because visitors can rename them."""
    if not store:
        return "<div class='chat-empty'>محادثاتك ستظهر هنا</div>"
    rows = []
    for chat in ordered(store):
        cid = html.escape(chat["id"])
        title = html.escape(chat["title"])
        pin_label = "إلغاء التثبيت" if chat.get("pinned") else "تثبيت"
        rows.append(f"""
<div class="chat-item{' active' if chat['id'] == current_id else ''}{' pinned' if chat.get('pinned') else ''}" data-id="{cid}" data-title="{title}">
  <span class="chat-title" title="{title}">{'📌 ' if chat.get('pinned') else ''}{title}</span>
  <button class="chat-dots" aria-label="خيارات">⋮</button>
  <div class="chat-menu">
    <button data-action="pin">📌 {pin_label}</button>
    <button data-action="rename">✏️ إعادة التسمية</button>
    <button data-action="delete" class="danger">🗑️ حذف</button>
  </div>
</div>""")
    return "<div class='chat-list'>" + "".join(rows) + "</div>"


# Runs in the browser: opens the ⋮ menu and sends the chosen action to Python.
LIST_JS = """
element.addEventListener('click', (event) => {
  const item = event.target.closest('.chat-item');
  const dots = event.target.closest('.chat-dots');
  const action = event.target.closest('.chat-menu button');
  element.querySelectorAll('.chat-menu.open').forEach(m => {
    if (!dots || m !== item.querySelector('.chat-menu')) m.classList.remove('open');
  });
  if (!item) return;
  const id = item.dataset.id;
  if (dots) {
    // The list scrolls, which would cut the menu off, so the menu floats above
    // the page (position: fixed), placed just under the ⋮ button.
    const menu = item.querySelector('.chat-menu');
    const box = dots.getBoundingClientRect();
    menu.style.top = (box.bottom + 4) + 'px';
    menu.style.left = Math.max(8, box.left) + 'px';
    menu.classList.toggle('open');
    return;
  }
  if (action) {
    const what = action.dataset.action;
    item.querySelector('.chat-menu').classList.remove('open');
    if (what === 'rename') {
      const title = window.prompt('الاسم الجديد للمحادثة:', item.dataset.title);
      if (title && title.trim()) trigger('click', {action: 'rename', id: id, title: title.trim()});
    } else if (what === 'delete') {
      if (window.confirm('هل تريد حذف هذه المحادثة؟')) trigger('click', {action: 'delete', id: id});
    } else {
      trigger('click', {action: what, id: id});
    }
    return;
  }
  trigger('click', {action: 'open', id: id});
});
const closeMenus = () => element.querySelectorAll('.chat-menu.open').forEach(m => m.classList.remove('open'));
document.addEventListener('click', (event) => { if (!element.contains(event.target)) closeMenus(); });
window.addEventListener('scroll', closeMenus, true);
window.addEventListener('resize', closeMenus);
"""
