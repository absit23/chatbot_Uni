"""The eligibility calculator: "my average is 60, scientific branch" -> departments.

This is a TOOL, not a guess. When a question contains a grade, we compare it
with the departments table using plain arithmetic and answer instantly. No AI
request is used, so it is exact, fast and does not spend your free quota.
If the student has not said their branch yet, we ask for it, and we remember
the grade from earlier in the conversation.
"""
import csv
import re

import json

from config import DEPARTMENTS_FILE, PAGES_FILE, UNIVERSITY_NAME
from textutils import normalize, text_of, tokenize

BRANCHES = {
    "علمي": "علمي", "احيائي": "احيائي", "تطبيقي": "تطبيقي", "ادبي": "ادبي",
    "مهني": "مهني", "صناعي": "مهني", "صناعه": "مهني", "تجاري": "مهني", "زراعي": "مهني",
}
BRANCH_NAMES = {"علمي": "علمي", "احيائي": "إحيائي", "تطبيقي": "تطبيقي", "ادبي": "أدبي", "مهني": "مهني"}
GRADE_WORDS = {"معدل", "معدلي", "درجتي", "درجه", "درجات", "مجموعي", "حصلت", "جبت", "جايب"}
QUESTION_WORDS = {"اقسام", "قسم", "يحق", "اقدر", "اكدر", "اگدر", "اسجل", "اقدم", "يقبلني", "يقبل", "مقبول", "متاح", "متاحه"}
# Words that mean "use the grade I already gave you" in a follow-up like "ماذا يقبل معدلي ايضا؟"
FOLLOW_UP_WORDS = GRADE_WORDS | {"يحق", "يقبل", "يقبلني", "يقبلوني", "اقدر", "اكدر", "اگدر", "اسجل", "اقدم", "متاح", "متاحه", "ايضا", "غيرها"}
NOT_A_GRADE_WORDS = {"تخفيض", "تخفيضات", "خصم", "ص", "صفحه", "نسبه"}
GENERIC_NAME_WORDS = {"هندسه", "تقنيات", "علوم", "قسم", "كليه", "اسلاميه", "جامعه", "طبيه", "تربيه", "اداب", "دراسات", "دراسه"}
BRANCH_BUTTONS = ["علمي", "إحيائي", "تطبيقي", "أدبي", "مهني"]
NEAR_MISS = 5  # also show departments the student misses by up to this many marks
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _load_departments() -> list[dict]:
    with open(DEPARTMENTS_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["branches"] = set(row["branches"].split(";"))
        row["name_words"] = set(tokenize(row["department"])) - GENERIC_NAME_WORDS
    return rows


DEPARTMENTS = _load_departments()

# --- The ministry guide's minimum-grade tables (printed pages 50-58) ---
# Used only to answer precisely when a student asks about a department that
# our university does NOT have: "not offered here, but elsewhere it needs...".
GUIDE_TABLE_PAGES = range(50, 59)
TABLE_BRANCHES = {  # words in each table title -> branches that table covers
    "الاحيائي": {"علمي", "احيائي"},
    "التطبيقي": {"علمي", "تطبيقي"},
    "المشتركه": {"علمي", "احيائي", "تطبيقي"},
    "الادبي": {"ادبي"},
    "الفنون": set(),
    "المهنيه": {"مهني"},
}
ROW_NUMBER_LABELS = {"ت", "رقم", "الرقم"}


def _table_branches(title: str) -> set[str]:
    clean = normalize(title)
    for word, branches in TABLE_BRANCHES.items():
        if word in clean:
            return branches
    return set()


def _parse_row(line: str) -> tuple[str, list[float | None]] | None:
    """Turn one transcribed table row into (department name, [morning, evening])."""
    name, values = "", []
    for raw in line.split("|"):
        field = normalize(raw).strip()
        label, _, value = field.rpartition(":")
        label, value = label.strip(), value.strip()
        if label in ROW_NUMBER_LABELS:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?|-", value):
            values.append(float(value) if value != "-" else None)
        elif re.search("[\u0621-\u064A]", value) and not re.search(r"\d{2}", value):
            shown = re.sub(r"^[\d\u0660-\u0669\u06F0-\u06F9]+\s*", "", raw.rpartition(":")[2].strip())
            name = max(name, shown, key=len)
    if name and 1 <= len(values) <= 2:
        return name, (values + [None])[:2]
    return None


def _load_guide_rows() -> list[dict]:
    rows, title = [], ""
    try:
        with open(PAGES_FILE, encoding="utf-8") as f:
            pages = sorted((json.loads(line) for line in f if line.strip()), key=lambda r: r["page"])
    except FileNotFoundError:
        return rows
    for page in pages:
        if page["page"] not in GUIDE_TABLE_PAGES:
            continue
        for line in page["text"].split("\n"):
            if re.match(r"^\s*ج\s*-\s*[2٢]\s*-\s*[0-9٠-٩]", line):
                title = re.sub(r"\(تكمله.*", "", normalize(line)).strip()
                continue
            parsed = _parse_row(line)
            if parsed and title:
                name, (morning, evening) = parsed
                rows.append({
                    "name": name, "morning": morning, "evening": evening, "page": page["page"],
                    "table": title, "branches": _table_branches(title),
                    "name_words": set(tokenize(name)) - GENERIC_NAME_WORDS,
                })
    return rows


GUIDE_ROWS = _load_guide_rows()


def _number(value: str) -> float | None:
    return float(value) if value else None


def _read(text: str) -> dict:
    """Find a grade, a branch, a study time and department names in one message."""
    clean = normalize(text).replace("٫", ".")
    words = set(tokenize(text))
    grade = None
    for match in NUMBER.findall(clean):
        value = float(match.replace(",", "."))
        if 40 <= value <= 100:
            grade = value
            break
    branch = next((BRANCHES[w] for w in words if w in BRANCHES), None)
    study = {"صباحي": "صباحي", "مسائي": "مسائي"}
    times = [study[w] for w in words if w in study]
    overlap = {id(d): len(d["name_words"] & words) for d in DEPARTMENTS}
    best = max(overlap.values())
    wanted = [d for d in DEPARTMENTS if best and overlap[id(d)] == best]
    elsewhere = []
    if not wanted and GUIDE_ROWS:
        guide_overlap = {id(r): len(r["name_words"] & words) for r in GUIDE_ROWS}
        best = max(guide_overlap.values())
        elsewhere = [r for r in GUIDE_ROWS if best and guide_overlap[id(r)] == best]
    about_grades = (bool(words & (GRADE_WORDS | QUESTION_WORDS)) or branch is not None or grade is not None) \
        and not (words & NOT_A_GRADE_WORDS) and "%" not in text
    follow_up = bool(words & FOLLOW_UP_WORDS) and not (words & NOT_A_GRADE_WORDS)
    return {"grade": grade, "branch": branch, "times": times, "wanted": wanted,
            "elsewhere": elsewhere, "about_grades": about_grades, "follow_up": follow_up}


def _assistant_text(history: list) -> str:
    """Everything the bot already said in this conversation."""
    parts = []
    for item in history or []:
        if isinstance(item, dict) and item.get("role") == "assistant":
            parts.append(text_of(item.get("content")))
        elif isinstance(item, (list, tuple)) and len(item) > 1 and item[1]:
            parts.append(text_of(item[1]))
    return "\n".join(parts)


def _user_messages(history: list) -> list[str]:
    """Earlier user messages, newest first. Works with both Gradio history formats."""
    messages = []
    for item in history or []:
        if isinstance(item, dict) and item.get("role") == "user":
            messages.append(text_of(item.get("content")))
        elif isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
            messages.append(item[0])
    return messages[::-1][:4]


def _minimum(dept: dict, time: str, branch: str) -> float | None:
    """The minimum grade for this branch and study time, or None if not offered."""
    if branch not in dept["branches"]:
        return None
    key = "morning" if time == "صباحي" else "evening"
    if branch == "مهني" and dept[f"{key}_min_vocational"]:
        return _number(dept[f"{key}_min_vocational"])
    return _number(dept[f"{key}_min"])


def _fee(dept: dict, time: str) -> str:
    value = dept["morning_fee" if time == "صباحي" else "evening_fee"]
    return f"{int(value):,} دينار" if value else "-"


def _grade_text(value: float) -> str:
    return f"{value:g}"


def _short_name(row: dict) -> str:
    name = row["name"].split("/")[0].strip()
    return name if name.startswith(("كلية", "قسم")) else f"قسم {name}"


def _who(row: dict) -> str:
    if row["branches"]:
        return "لخريجي " + " + ".join(BRANCH_NAMES[b] for b in ("علمي", "احيائي", "تطبيقي", "ادبي", "مهني") if b in row["branches"])
    return row["table"].split(" ", 1)[-1]


def not_offered(rows: list[dict], grade: float | None, branch: str | None) -> str:
    """Say clearly that we do not have this department, then what the guide says."""
    name = _short_name(rows[0])
    lines = [f"❌ {name} {'غير موجودة' if name.startswith('كلية') else 'غير موجود'} في {UNIVERSITY_NAME}."]
    for row in rows:
        if branch and row["branches"] and branch not in row["branches"]:
            continue
        limits = []
        if row["morning"] is not None:
            limits.append(f"صباحي {_grade_text(row['morning'])}")
        if row["evening"] is not None:
            limits.append(f"مسائي {_grade_text(row['evening'])}")
        line = f"ℹ️ في الجامعات الأهلية الأخرى، حده الأدنى {_who(row)}: {'، '.join(limits)} (ص {row['page']})"
        lowest = min(v for v in (row["morning"], row["evening"]) if v is not None) if limits else None
        if grade is not None and lowest is not None:
            line += "، ومعدلك يكفي للتقديم عليه هناك." if grade >= lowest else "، ومعدلك لا يكفي له."
        lines.append(line)
    return "\n".join(lines)


def calculate(grade: float, branch: str, times: list[str], wanted: list[dict], elsewhere: list[dict]) -> str:
    departments = wanted or DEPARTMENTS
    times = times or ["صباحي", "مسائي"]
    yes, near = [], []
    for dept in departments:
        for time in times:
            minimum = _minimum(dept, time, branch)
            if minimum is None:
                continue
            line = f"{dept['department']} ({time}): الحد الأدنى {_grade_text(minimum)}"
            if grade >= minimum:
                yes.append(f"• {line}، الأجور {_fee(dept, time)}")
            elif wanted or minimum - grade <= NEAR_MISS:
                near.append(f"• {line}، ينقصك {_grade_text(minimum - grade)}")

    parts = [f"📊 حاسبة القبول، {UNIVERSITY_NAME}", f"معدلك: {_grade_text(grade)} | فرعك: {BRANCH_NAMES[branch]}"]
    if elsewhere:
        parts += ["", not_offered(elsewhere, grade, branch)]
    if yes:
        parts += ["", f"✅ يحق لك التقديم في {UNIVERSITY_NAME} على:"] + yes
    if near:
        parts += ["", "❌ لا يكفي معدلك لـ:"] + near
    not_for_branch = [d["department"] for d in wanted if branch not in d["branches"]]
    if not yes and not near and not not_for_branch:
        closest = sorted(
            ((m, d, t) for d in DEPARTMENTS for t in times if (m := _minimum(d, t, branch)) is not None),
            key=lambda x: x[0],
        )[:3]
        if closest:
            parts += ["", f"معدلك أقل من الحد الأدنى لكل الأقسام التي تقبل فرع {BRANCH_NAMES[branch]} في {UNIVERSITY_NAME}. أقربها لك:"]
            parts += [f"• {d['department']} ({t}): الحد الأدنى {_grade_text(m)}، ينقصك {_grade_text(m - grade)}" for m, d, t in closest]
        else:
            parts += ["", f"لا يوجد في {UNIVERSITY_NAME} قسم يقبل فرع {BRANCH_NAMES[branch]}."]
    if not_for_branch:
        parts += ["", f"⚠️ لا يقبل فرع {BRANCH_NAMES[branch]} في: " + "، ".join(not_for_branch)]
    return "\n".join(parts)


def handle(message: str, history: list) -> tuple[str, list[str]] | None:
    """Return (answer, follow-up buttons) for grade questions, or None for normal search."""
    now = _read(message)
    if now["grade"] is None and now["branch"] is None and not now["follow_up"]:
        return None
    if now["grade"] is not None and not now["about_grades"]:
        return None  # a number, but probably not a grade question

    grade, branch, times, wanted, elsewhere = now["grade"], now["branch"], now["times"], now["wanted"], now["elsewhere"]
    # Is this message only the answer to "what is your branch?" (e.g. "علمي")?
    answering_branch = now["branch"] and now["grade"] is None and not (now["wanted"] or now["elsewhere"] or now["times"])
    for old in _user_messages(history):  # fill gaps from earlier messages, newest first
        before = _read(old)
        if grade is None and before["grade"] is not None:
            grade = before["grade"]
            if answering_branch:  # keep what that grade question was about
                times, wanted, elsewhere = before["times"], before["wanted"], before["elsewhere"]
        branch = branch or before["branch"]
    if elsewhere and not now["elsewhere"] and f"{_short_name(elsewhere[0])} غير موجود" in _assistant_text(history):
        elsewhere = []  # already told the student, do not repeat it
    if grade is None:
        return None  # a branch alone, with no grade anywhere: let the normal search answer
    if branch is None:
        ask = f"ما هو فرعك في السادس الإعدادي؟ اختر من الأزرار، وسأعرض لك فوراً كل الأقسام المتاحة لك في {UNIVERSITY_NAME}."
        if elsewhere:
            return not_offered(elsewhere, grade, None) + "\n\n" + ask, BRANCH_BUTTONS
        return f"معدلك {_grade_text(grade)}. {ask}", BRANCH_BUTTONS
    return calculate(grade, branch, times, wanted, elsewhere), []
