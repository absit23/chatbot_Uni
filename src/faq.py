"""Fixed answers for the most common questions (the suggestion buttons).

These are written from data/university/info.md and departments.csv, not by
the AI, so the wording is always correct ("تقع" never becomes "تتجمع"),
the answer is instant, and no free quota is used.
"""
import csv
import re

from config import ADMISSION_CONTACT, DEPARTMENTS_FILE, UNIVERSITY_INFO_FILE, UNIVERSITY_NAME
from textutils import normalize, tokenize


def _sections() -> dict[str, str]:
    text = UNIVERSITY_INFO_FILE.read_text(encoding="utf-8")
    parts = [p.strip() for p in re.split(r"(?m)^# ", text) if p.strip()]
    return {p.split("\n", 1)[0].strip(): p.split("\n", 1)[1].strip() for p in parts if "\n" in p}


def _section(start: str) -> str:
    return next(body for title, body in _sections().items() if title.startswith(start))


def _money(value: str) -> str:
    return f"{int(value):,} دينار" if value else "لا توجد دراسة مسائية"


def location() -> str:
    return (
        f"تقع {UNIVERSITY_NAME} في محافظة بابل، على طريق حلة - نجف، مقابل جامعة بابل.\n"
        f"للاستفسار يمكنك التواصل مع {ADMISSION_CONTACT}."
    )


def departments() -> str:
    by_college: dict[str, list[str]] = {}
    with open(DEPARTMENTS_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["department"] + ("" if row["evening_min"] else " (صباحي فقط)")
            by_college.setdefault(row["college"], []).append(name)
    lines = [f"الأقسام الموجودة في {UNIVERSITY_NAME}:"]
    for college, names in by_college.items():
        lines.append(f"\n**{college}**")
        lines += [f"• {n}" for n in names]
    return "\n".join(lines)


def fees() -> str:
    lines = [f"أجور الدراسة في {UNIVERSITY_NAME} للعام الدراسي 2026-2027:"]
    with open(DEPARTMENTS_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lines.append(f"• {row['department']}: صباحي {_money(row['morning_fee'])}، مسائي {_money(row['evening_fee'])}")
    return "\n".join(lines)


def _as_list(body: str) -> str:
    return "\n".join(line if line[:1].isdigit() else f"• {line}" for line in body.split("\n") if line.strip())


def discounts() -> str:
    return (
        f"التخفيضات في أجور الدراسة في {UNIVERSITY_NAME}:\n\n"
        f"**الدراسة الصباحية**\n{_as_list(_section('التخفيضات في الأجور - الدراسة الصباحية'))}\n\n"
        f"**الدراسة المسائية**\n{_as_list(_section('التخفيضات في الأجور - الدراسة المسائية'))}"
    )


def documents() -> str:
    return _section("الوثائق المطلوبة للتسجيل")


ANSWERS = {
    "location": location,
    "departments": departments,
    "fees": fees,
    "discounts": discounts,
    "documents": documents,
}

# Exact button texts.
BUTTONS = {
    "أين تقع الجامعة؟": "location",
    "ما الأقسام الموجودة في الجامعة؟": "departments",
    "كم أجور الدراسة؟": "fees",
    "ما هي التخفيضات؟": "discounts",
    "ما الوثائق المطلوبة للتسجيل؟": "documents",
}
# A typed question gets a fixed answer only if it is GENERAL (all its words are
# topic words or filler). "اخوي شهيد كم الخصم؟" has specific details, so the AI
# answers that exact case instead of dumping the whole list.
FILLER = {"شنو", "شني", "اكو", "يوجد", "توجد", "موجود", "موجوده", "عندكم", "لديكم", "ماهي", "ماهو",
          "ممكن", "اعرف", "اريد", "ابي", "مطلوبه", "مطلوب", "تسجيل", "للتسجيل", "جامعه", "جامعتكم",
          "وين", "اين", "تقع", "بالضبط", "انتم", "الجامعه", "دراسه", "جميع", "كل", "هناك", "شلون"}
TOPICS = {
    "location": {"موقع", "عنوان", "مكان", "تقع", "وين", "اين", "لوكيشن"},
    "documents": {"وثائق", "مستمسكات", "اوراق", "مستندات", "اوراقي"},
    "discounts": {"تخفيضات", "تخفيض", "خصم", "خصومات"},
    "fees": {"اجور", "اقساط", "قسط", "الاجور"},
}


# Rules the small AI model got wrong (it reversed their meaning), so they are always
# answered with the plain summary written in info.md, never re-worded by the AI.
def _rule(start: str) -> str:
    title = next(t for t in _sections() if t.startswith(start))
    lines = [f"**{line}**" if line.endswith(":") and not line.startswith("-") else line
             for line in _section(start).split("\n")]
    return f"**{title}**\n" + "\n".join(lines)


RULES = {
    "cheating": (lambda words: bool(words & {"غش", "الغش", "غشيت", "اغش", "غشاش", "يغش", "بالغش", "للغش"}),
                 lambda: _rule("عقوبة الغش")),
    "failing": (lambda words: bool(words & {"ترقين", "يرقن", "يترقن", "ترقن", "يرقنون"}) or (
                    bool(words & {"ارسب", "رسوب", "رسبت", "راسب", "يرسب", "الرسوب"})
                    and bool(words & {"كم", "سنه", "سنتين", "سنوات", "مرات", "مره", "متى", "يحق"})),
                lambda: _rule("الرسوب وترقين القيد")),
}


def answer(message: str) -> str | None:
    """A fixed answer for a button or a general question, or None to let the calculator or AI answer."""
    key = BUTTONS.get(message.strip())
    words = set(tokenize(message)) | set(normalize(message).split())
    if key is None and len(words) <= 12:
        for matches, rule in RULES.values():
            if matches(words):
                return rule()
    if key is None:
        words = set(tokenize(message))
        for name, topic_words in TOPICS.items():
            if words & topic_words and words <= (topic_words | FILLER):
                key = name
                break
    return ANSWERS[key]() if key else None
