"""The teaching staff (الكادر التدريسي): exact answers from the staff list, never from the AI.

Names must never be invented, so staff questions are answered directly from
data/university/staff.csv, like the eligibility calculator answers grades.

The staff list stays on this laptop only (it is in .gitignore, the GitHub repo
is public). To create or update it from the university's Excel file:

    python src/staff.py import "path/to/staff.xlsx"
    python app.py
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import UNIVERSITY_DIR, UNIVERSITY_NAME  # noqa: E402
from textutils import normalize  # noqa: E402

STAFF_FILE = UNIVERSITY_DIR / "staff.csv"
FIELDS = ["department", "name", "degree", "title", "general", "specific"]

# Words in the Excel sheet titles -> the official department names
SHEET_DEPARTMENTS = [
    ("القران", "الدراسات القرآنية واللغوية"),
    ("المختبرات", "تقنيات المختبرات الطبية"),
    ("الحاسوب", "هندسة تقنيات الحاسوب"),
    ("الانكليزيه", "اللغة الإنجليزية"),
    ("الماليه", "العلوم المالية والمصرفية الإسلامية"),
    ("الاجهزه", "هندسة تقنيات الأجهزة الطبية"),
    ("الفيزياء", "علوم الفيزياء الطبية"),
    ("السبراني", "هندسة تقنيات الأمن السيبراني"),
    ("القانون", "القانون"),
    ("الكلي", "تقنيات الكلى الصناعية"),
]

# Words a visitor may use for each department
DEPARTMENT_WORDS = {
    "هندسة تقنيات الحاسوب": ["حاسوب", "حاسبات", "الحاسبات", "كمبيوتر"],
    "هندسة تقنيات الأمن السيبراني": ["سيبراني", "سبراني", "سايبر", "الامن"],
    "هندسة تقنيات الأجهزة الطبية": ["الاجهزه"],
    "تقنيات المختبرات الطبية": ["المختبرات", "مختبرات", "تحليلات"],
    "تقنيات الكلى الصناعية": ["الكلي", "كلي"],
    "علوم الفيزياء الطبية": ["الفيزياء", "فيزياء"],
    "القانون": ["القانون", "قانون"],
    "اللغة الإنجليزية": ["الانكليزي", "الانجليزي", "انكليزي", "انجليزي", "الانكليزيه", "الانجليزيه"],
    "الدراسات القرآنية واللغوية": ["القرانيه", "قرانيه", "الدراسات"],
    "العلوم المالية والمصرفية الإسلامية": ["الماليه", "ماليه", "المصرفيه", "مصرفيه"],
}

STAFF_WORDS = {"تدريسي", "تدريسيين", "التدريسيين", "تدريسيه", "التدريسيه", "التدريسي", "اساتذه",
               "الاساتذه", "استاذه", "دكاتره", "الدكاتره", "كادر", "الكادر", "مدرسين", "المدرسين",
               "اختصاصه", "اختصاصها", "تدريسيات"}
WHO_TEACHES = re.compile(r"(منو|من|مين|اكو|يوجد|هل)\s+(يدرس|يدرسنا|يدرسون|دكتور|استاذ|تدريسي)")
NAME_PREFIX = re.compile(r"^[\s.]*((ا|أ)\s*\.?\s*(م\s*\.?\s*)?د|م\s*\.?\s*م|م\s*\.?\s*د|ا\s*\.?\s*م|د)(\s*\.\s*|\s+)(?=[ء-ي])")
PLURAL_STAFF_WORDS = {"تدريسيين", "التدريسيين", "اساتذه", "الاساتذه", "دكاتره", "الدكاتره", "كادر", "الكادر",
                      "مدرسين", "المدرسين", "تدريسيات", "الهيئه"}
ASK_WORDS = {"منو", "مين", "تعرف", "تعرفه", "تعرفها", "شنو", "معلومات", "اختصاص", "اختصاصه", "اختصاصها",
             "قسمه", "قسمها", "وين", "لقب", "لقبه", "لقبها", "شهاده", "شهادته", "شهادتها"}
SPECIALTY_WORDS = {"اختصاص", "اختصاصه", "اختصاصها", "تخصص", "تخصصه", "متخصص", "متخصصين", "يدرس", "يدرسون"}
GENERIC_SPECIALTY = {"علوم", "العلوم", "اللغه", "هندسه", "تقنيات", "الهندسه", "قسم", "في", "عن", "و"}


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _degree(value: str) -> str:
    v = normalize(value)
    return "دكتوراه" if "دكتور" in v else ("ماجستير" if "ماجستير" in v else _clean(value))


def _title(value: str) -> str:
    v = normalize(_clean(value))
    if not v:
        return ""
    if "لا يوجد" in v:  # the university's file writes "لا يوجد" for assistant lecturers
        return "مدرس مساعد"
    if "متمرس" in v:
        return "أستاذ متمرس"
    if "مساعد" in v:
        return "أستاذ مساعد" if "استاذ" in v else "مدرس مساعد"
    if v in ("م.د", "م د") or v.startswith("مدرس"):
        return "مدرس"
    if v.startswith("استاذ"):
        return "أستاذ"
    return _clean(value)


def import_excel(path: str) -> int:
    """Read the university's Excel file (one sheet per department) into staff.csv."""
    import openpyxl
    rows = []
    for sheet in openpyxl.load_workbook(path, data_only=True):
        cells = [[_clean(c) for c in row] for row in sheet.iter_rows(values_only=True)]
        heading = normalize(" ".join(c for row in cells[:3] for c in row) + " " + sheet.title)
        department = next((name for word, name in SHEET_DEPARTMENTS if word in heading), sheet.title.strip())
        for row in cells:
            if len(row) < 3 or not row[1] or row[1].startswith("اسم") or "الكادر" in row[1] or not row[2]:
                continue
            rows.append({"department": department, "name": row[1], "degree": _degree(row[2]),
                         "title": _title(row[3] if len(row) > 3 else ""),
                         "general": row[4] if len(row) > 4 else "", "specific": row[5] if len(row) > 5 else ""})
    with open(STAFF_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def load() -> list[dict]:
    if not STAFF_FILE.exists():
        return []
    with open(STAFF_FILE, encoding="utf-8") as f:
        return list(csv.DictReader(f))


STAFF = load()


def _bare_name(name: str) -> str:
    return normalize(NAME_PREFIX.sub("", name)).strip()


def _display_name(name: str) -> str:
    """The name without "م.م." / "أ.د": the title is written once, in words, after it."""
    return _clean(NAME_PREFIX.sub("", name))


def _line(person: dict, with_department: bool = False) -> str:
    details = ([person["title"]] if person["title"] else []) + [person["degree"]]
    specialty = person["general"] + (f" ({person['specific']})" if person["specific"] and person["specific"] != person["general"] else "")
    if specialty:
        details.append(specialty)
    where = f"، قسم {person['department']}" if with_department else ""
    return f"• {_display_name(person['name'])}: {'، '.join(details)}{where}"


def _key(person: dict) -> str:
    """The same person can be written with or without "م.م." and with a shorter name."""
    return " ".join(_bare_name(person["name"]).split()[:3])


def _number(n: int) -> str:
    """Arabic counting: 2 تدريسيان، 3-10 تدريسيين، 11+ تدريسياً."""
    if n == 1:
        return "تدريسي واحد"
    if n == 2:
        return "تدريسيان"
    return f"{n} تدريسيين" if n <= 10 else f"{n} تدريسياً"


def _counts(people: list[dict]) -> str:
    degrees = Counter(p["degree"] for p in people)
    titles = Counter(p["title"] for p in people if p["title"])
    parts = [_number(len(people))]
    parts.append("، ".join(f"{n} {d}" for d, n in degrees.most_common()))
    order = ["أستاذ متمرس", "أستاذ", "أستاذ مساعد", "مدرس", "مدرس مساعد"]
    if titles:
        parts.append("الألقاب العلمية: " + "، ".join(f"{titles[t]} {t}" for t in order if titles[t]))
    return " | ".join(parts)


def _departments_in(text: str) -> list[str]:
    words = set(re.findall("[ء-ي]+", text))
    words |= {w[2:] for w in words if w.startswith("ال")} | {w[1:] for w in words if w[:1] in "وب"}
    return [d for d, keys in DEPARTMENT_WORDS.items() if words & set(keys)]


def _people_named(text: str) -> list[dict]:
    """Staff whose first two name words appear in the message, e.g. "عدي صبري"."""
    found = []
    for person in STAFF:
        words = _bare_name(person["name"]).split()
        if len(words) >= 2 and re.search(rf"(^|\s){re.escape(words[0])}\s+{re.escape(words[1])}(\s|$)", text):
            if all(_key(p) != _key(person) for p in found):
                found.append(person)
    return found


def _by_specialty(text: str) -> list[dict]:
    skip = GENERIC_SPECIALTY | STAFF_WORDS | PLURAL_STAFF_WORDS | SPECIALTY_WORDS | {"منو", "مين", "اكو", "يوجد", "دكتور", "استاذ"}
    words = [re.sub("^(وال|بال|لل|ال|ب)(?=...)", "", w) for w in re.findall("[ء-ي]{3,}", text) if w not in skip]
    words = [w for w in words if w not in skip]
    found = []
    for person in STAFF:
        specialty = normalize(f"{person['general']} {person['specific']}")
        hits = [w for w in words if w in specialty]
        if hits and len(hits) >= min(2, len(words)) and all(_key(p) != _key(person) for p in found):
            found.append(person)
    return found


# Group words: "الهندسة" alone means all engineering departments
GROUPS = {
    ("هندسه", "الهندسه", "هندسيه", "الهندسيه"): ["هندسة تقنيات الحاسوب", "هندسة تقنيات الأمن السيبراني",
                                              "هندسة تقنيات الأجهزة الطبية"],
    ("طبيه", "الطبيه", "صحيه", "الصحيه"): ["تقنيات المختبرات الطبية", "علوم الفيزياء الطبية",
                                        "هندسة تقنيات الأجهزة الطبية", "تقنيات الكلى الصناعية"],
}
STAFF_REPLY_STARTS = ("الكادر التدريسي", "معلومات التدريسي", "التدريسيون في")


def handle(message: str, last_reply: str = "") -> str | None:
    """A staff answer, or None when the message is not about the teaching staff.

    last_reply is the bot's previous answer: right after a staff answer, a short
    follow-up like "القانون" or "طيب الهندسة" means that department's staff.
    """
    if not STAFF:
        return None
    text = " ".join(re.findall("[ء-ي0-9]+", normalize(message)))  # no "؟" or dots
    words = set(text.split())
    follow_up = last_reply.startswith(STAFF_REPLY_STARTS) and len(words) <= 5
    if len(text.split()) > 9:
        return None  # a long chatty message (opinions, stories) is for the AI, not a staff list

    named = _people_named(text)
    # "منو زينب ثامر؟" asks for her details; a longer remark that only mentions her is chat for the AI
    if named and len(text.split()) > len(_bare_name(named[0]["name"]).split()) + 2 and not words & ASK_WORDS:
        named = []
    if named:
        lines = []
        for person in named:
            others = [p["department"] for p in STAFF if _key(p) == _key(person) and p["department"] != person["department"]]
            extra = f" (وأيضاً في قسم: {'، '.join(others)})" if others else ""
            lines.append(_line(person, with_department=True) + extra)
        return "معلومات التدريسي في " + UNIVERSITY_NAME + ":\n" + "\n".join(dict.fromkeys(lines))

    departments = _departments_in(text)
    if not departments:
        departments = next((d for keys, d in GROUPS.items() if words & set(keys)), [])
    if not (words & STAFF_WORDS or WHO_TEACHES.search(text) or (follow_up and departments)):
        return None
    if words & {"رئيس", "عميد", "معاون", "مساعد", "المساعد", "نائب"}:
        return None  # not in the staff list: the AI says it is not available

    if departments:
        parts = []
        for department in departments:
            people = [p for p in STAFF if p["department"] == department]
            if not people:
                parts.append(f"لا تتوفر لدي حالياً قائمة الكادر التدريسي لقسم {department}.")
                continue
            parts.append(f"الكادر التدريسي في قسم {department} ({_counts(people)}):\n"
                         + "\n".join(_line(p) for p in people))
        return "\n\n".join(parts)

    bare_words = words | {w[2:] for w in words if w.startswith("ال")}
    asks_specialty = bare_words & SPECIALTY_WORDS or WHO_TEACHES.search(text)
    specialists = _by_specialty(text) if asks_specialty else []
    if specialists and len(specialists) <= 15:
        return (f"التدريسيون في {UNIVERSITY_NAME} المتخصصون بما سألت عنه:\n"
                + "\n".join(_line(p, with_department=True) for p in specialists))

    # General question: a summary of all departments
    if not words & (PLURAL_STAFF_WORDS | {"كم", "عدد"}):
        return None  # "التدريسية الفلانية..." is a remark for the AI, not a request for the whole list
    unique = list({_key(p): p for p in STAFF}.values())
    lines = [f"• {d}: {_counts([p for p in STAFF if p['department'] == d])}"
             for d in dict.fromkeys(p["department"] for p in STAFF)]
    return (f"الكادر التدريسي في {UNIVERSITY_NAME} للعام 2026-2027: {_counts(unique)}.\n\n"
            "حسب الأقسام:\n" + "\n".join(lines)
            + "\n\nاكتب اسم القسم لعرض أسماء تدريسييه، مثل: تدريسيين قسم القانون.")


def _find_excel(given: str | None) -> Path | None:
    """The file named, or else the only .xlsx file in the project folder."""
    if given and Path(given).exists():
        return Path(given)
    found = sorted(Path(__file__).parent.parent.glob("*.xlsx"))
    if given:
        print(f"Not found: {given}")
    if len(found) == 1:
        print(f"Using the Excel file in the project folder: {found[0].name}")
        return found[0]
    if found:
        print("Several Excel files found, name one of them:", ", ".join(f.name for f in found))
    else:
        print("No .xlsx file in the project folder. Put the staff Excel file next to app.py.")
    return None


if __name__ == "__main__":
    if len(sys.argv) in (2, 3) and sys.argv[1] == "import":
        excel = _find_excel(sys.argv[2] if len(sys.argv) == 3 else None)
        if excel:
            print(f"Saved {import_excel(str(excel))} staff rows to {STAFF_FILE}")
    else:
        print('Usage: python src/staff.py import  [path/to/staff.xlsx]')
