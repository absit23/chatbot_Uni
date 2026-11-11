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

# Exact button texts, and simple word patterns for the same questions typed by hand.
BUTTONS = {
    "أين تقع الجامعة؟": "location",
    "ما الأقسام الموجودة في الجامعة؟": "departments",
    "كم أجور الدراسة؟": "fees",
    "ما هي التخفيضات؟": "discounts",
    "ما الوثائق المطلوبة للتسجيل؟": "documents",
}
PATTERNS = [
    ("location", {"تقع", "موقع", "عنوان", "مكان", "وين", "اين"}, {"جامعه"}),
    ("documents", {"وثائق", "مستمسكات", "اوراق", "مستندات"}, set()),
    ("discounts", {"تخفيضات", "تخفيض", "خصم", "خصومات"}, set()),
]
# Questions that need a more specific answer than the fixed list go to the AI.
SPECIFIC_WORDS = {"تقسيط", "اقساط", "دفع", "موعد", "تاريخ"}


def answer(message: str) -> str | None:
    """A fixed answer, or None to let the calculator or AI answer."""
    key = BUTTONS.get(message.strip())
    if key is None:
        words = set(tokenize(message))
        if words & SPECIFIC_WORDS:
            return None
        for name, any_of, also in PATTERNS:
            if words & any_of and (not also or words & also or len(words) <= 3):
                key = name
                break
    return ANSWERS[key]() if key else None
