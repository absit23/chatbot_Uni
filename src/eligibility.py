"""The eligibility calculator: "my average is 60, scientific branch" -> departments.

This is a TOOL, not a guess. When a question contains a grade, we compare it
with the departments table using plain arithmetic and answer instantly. No AI
request is used, so it is exact, fast and does not spend your free quota.
If the student has not said their branch yet, we ask for it, and we remember
the grade from earlier in the conversation.
"""
import csv
import re

from config import DEPARTMENTS_FILE, UNIVERSITY_NAME
from textutils import normalize, tokenize

BRANCHES = {
    "علمي": "علمي", "احيائي": "احيائي", "تطبيقي": "تطبيقي", "ادبي": "ادبي",
    "مهني": "مهني", "صناعي": "مهني", "صناعه": "مهني", "تجاري": "مهني", "زراعي": "مهني",
}
BRANCH_NAMES = {"علمي": "علمي", "احيائي": "إحيائي", "تطبيقي": "تطبيقي", "ادبي": "أدبي", "مهني": "مهني"}
GRADE_WORDS = {"معدل", "معدلي", "درجتي", "درجه", "درجات", "مجموعي", "حصلت", "جبت", "جايب"}
QUESTION_WORDS = {"اقسام", "قسم", "يحق", "اقدر", "اكدر", "اگدر", "اسجل", "اقدم", "يقبلني", "يقبل", "مقبول", "متاح", "متاحه"}
NOT_A_GRADE_WORDS = {"تخفيض", "تخفيضات", "خصم", "ص", "صفحه", "نسبه"}
GENERIC_NAME_WORDS = {"هندسه", "تقنيات", "علوم", "قسم", "كليه", "اسلاميه", "جامعه"}
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
    about_grades = (bool(words & (GRADE_WORDS | QUESTION_WORDS)) or branch is not None or grade is not None) \
        and not (words & NOT_A_GRADE_WORDS) and "%" not in text
    return {"grade": grade, "branch": branch, "times": times, "wanted": wanted, "about_grades": about_grades}


def _user_messages(history: list) -> list[str]:
    """Earlier user messages, newest first. Works with both Gradio history formats."""
    messages = []
    for item in history or []:
        if isinstance(item, dict) and item.get("role") == "user":
            content = item.get("content")
            messages.append(content if isinstance(content, str) else str(content))
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


def calculate(grade: float, branch: str, times: list[str], wanted: list[dict]) -> str:
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
    if yes:
        parts += ["", f"✅ يحق لك التقديم في {UNIVERSITY_NAME} على:"] + yes
    if near:
        parts += ["", "❌ لا يكفي معدلك لـ:"] + near
    not_for_branch = [d["department"] for d in wanted if branch not in d["branches"]]
    if not yes and not near and not not_for_branch:
        parts += ["", f"لا يوجد في {UNIVERSITY_NAME} قسم يقبل هذا المعدل والفرع حالياً."]
    if not_for_branch:
        parts += ["", f"⚠️ لا يقبل فرع {BRANCH_NAMES[branch]} في: " + "، ".join(not_for_branch)]
    parts += ["", "💡 اسألني عن التخفيضات المتاحة في الأجور."]
    return "\n".join(parts)


def handle(message: str, history: list) -> str | None:
    """Return a calculator answer, a question asking for the branch, or None."""
    now = _read(message)
    if now["grade"] is None and now["branch"] is None:
        return None
    if now["grade"] is not None and not now["about_grades"]:
        return None  # a number, but probably not a grade question

    grade, branch, times, wanted = now["grade"], now["branch"], now["times"], now["wanted"]
    for old in _user_messages(history):  # fill gaps from earlier messages
        before = _read(old)
        grade = grade if grade is not None else before["grade"]
        branch = branch or before["branch"]
        times = times or before["times"]
        wanted = wanted or before["wanted"]
    if grade is None:
        return None  # a branch alone, with no grade anywhere: let the normal search answer
    if branch is None:
        return f"معدلك {_grade_text(grade)}. ما هو فرعك في السادس الإعدادي؟ (علمي، إحيائي، تطبيقي، أدبي، مهني)\nاكتب فرعك وسأعرض لك فوراً كل الأقسام المتاحة لك في {UNIVERSITY_NAME}."
    return calculate(grade, branch, times, wanted)
