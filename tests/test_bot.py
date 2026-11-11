"""Automatic checks for the chatbot. Run with:  python -m pytest

Each test is a real question we tried while building the bot, with what the
correct behaviour is. Run this after EVERY change: if a fix breaks something
that worked before, a test turns red and tells you which question broke.

These tests need no API key, no internet and no database: they check the
calculator and the fixed answers, and which part of the bot handles each
question. The AI's own wording cannot be tested this way.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import eligibility  # noqa: E402
import faq  # noqa: E402


def say(text: str) -> dict:
    """A chat message in Gradio 6's format."""
    return {"role": "user", "content": [{"type": "text", "text": text}]}


def bot(text: str) -> dict:
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def calculator(message: str, history: list | None = None) -> str | None:
    result = eligibility.handle(message, history or [])
    return result[0] if result else None


# ---------- The calculator: exact numbers ----------

def test_grade_60_scientific_computer_engineering_evening_only():
    answer = calculator("معدلي 60 علمي أكدر أسجل هندسة تقنيات الحاسوب؟")
    assert "هندسة تقنيات الحاسوب (مسائي): الحد الأدنى 59.5" in answer
    assert "هندسة تقنيات الحاسوب (صباحي): الحد الأدنى 62.5، ينقصك 2.5" in answer


def test_arabic_digits_and_decimal_comma():
    assert "معدلك: 62.5" in calculator("معدلي ٦٢٫٥ إحيائي صباحي")


def test_grade_without_branch_asks_for_branch_with_buttons():
    text, buttons = eligibility.handle("معدلي 58", [])
    assert "ما هو فرعك" in text
    assert buttons == eligibility.BRANCH_BUTTONS


def test_branch_answer_remembers_grade():
    history = [say("معدلي 58"), bot("ما هو فرعك؟")]
    assert "معدلك: 58 | فرعك: علمي" in calculator("علمي", history)


def test_branch_correction_uses_new_branch():
    history = [say("معدلي 55 اريد التخدير"), bot("..."), say("فرعي مهني"), bot("...")]
    assert "فرعك: علمي" in calculator("اسف اقصد علمي", history)


def test_vocational_no_fit_says_so_clearly():
    answer = calculator("معدلي 60 مهني")
    assert "معدلك لا يكفي حالياً لأي قسم يقبل فرع مهني" in answer
    assert "61.5" in answer


def test_literary_branch_not_accepted_in_engineering():
    answer = calculator("معدلي 80 ادبي اريد هندسة تقنيات الأمن السيبراني")
    assert "لا يقبل فرع أدبي" in answer


# ---------- Departments the university does not have ----------

def test_missing_department_said_clearly_with_guide_minimum():
    answer = calculator("معدلي ٥٥ واريد اقدم على الجامعة قسم التخدير يقبلني؟")
    assert "تقنيات التخدير غير موجود في الجامعة الإسلامية" in answer
    assert "صباحي 70، مسائي 65 (ص 50)" in answer


def test_missing_department_notice_not_repeated():
    history = [say("معدلي ٥٥ قسم التخدير"), bot("❌ قسم تقنيات التخدير غير موجود في الجامعة الإسلامية - فرع بابل.")]
    assert "غير موجود" not in calculator("علمي", history)


# ---------- Follow-ups reuse the earlier grade ----------

GRADE_60 = [say("معدلي 60 فرع علمي، ما الأقسام المتاحة لي؟"), bot("📊 حاسبة القبول")]


def test_follow_up_reuses_grade():
    assert "معدلك: 60 | فرعك: علمي" in calculator("ماذا يقبل معدلي ايضا ؟", GRADE_60)


def test_follow_up_about_one_department():
    answer = calculator("هل يقبلني القانون؟", GRADE_60)
    assert "القانون (صباحي): الحد الأدنى 67.5" in answer


@pytest.mark.parametrize("question", [
    "هل يحق لي ترك سنة؟ وماهي شروط التحميل؟",
    "ما هي التخفيضات؟",
    "كم قسط المالية والمصرفية؟",
    "ما الوثائق المطلوبة للتسجيل؟",
])
def test_general_questions_do_not_trigger_calculator(question):
    assert calculator(question, GRADE_60) is None


@pytest.mark.parametrize("question", [
    "هل يوجد تخفيض 50% للشهداء",
    "ما تخفيض ذوي الشهداء 50",
    "الطالب الأول 100% تخفيض؟",
])
def test_discount_numbers_are_not_grades(question):
    assert calculator(question) is None


# ---------- Fixed answers ----------

@pytest.mark.parametrize("question, expected", [
    ("أين تقع الجامعة؟", "تقع الجامعة الإسلامية"),
    ("وين الجامعة", "تقع الجامعة الإسلامية"),
    ("ما الأقسام الموجودة في الجامعة؟", "**الكلية التقنية الهندسية**"),
    ("كم أجور الدراسة؟", "العلوم المالية والمصرفية الإسلامية: صباحي 1,000,000"),
    ("ما هي التخفيضات؟", "ذوو الشهداء: تخفيض 50%"),
    ("شنو الاوراق المطلوبة", "صور حديثة عدد (3)"),
])
def test_fixed_answers(question, expected):
    assert expected in faq.answer(question)


@pytest.mark.parametrize("question", ["كم أجور قسم القانون؟", "هل يمكن تقسيط الأجور؟", "متى يلغى قبول الطالب؟"])
def test_specific_questions_go_to_the_ai(question):
    assert faq.answer(question) is None


def test_all_ten_departments_have_fees():
    answer = faq.fees()
    assert answer.count("• ") == 10


def test_phone_number_is_complete():
    assert "07726018188" in faq.location()
