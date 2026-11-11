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


# ---------- Added after the 11 Nov test session ----------

@pytest.mark.parametrize("question, grade", [
    ("معدلي ستين علمي", "60"),
    ("معدلي خمسة وستين علمي", "65"),
    ("معدلي سبعين ونص احيائي", "70.5"),
])
def test_grade_written_in_words(question, grade):
    assert f"معدلك: {grade} |" in calculator(question)


def test_grade_in_words_without_branch_asks_branch():
    text, buttons = eligibility.handle("معدلي ستين ماذا يقبلني؟", [])
    assert "معدلك 60" in text


def test_engineering_follow_up_in_dialect():
    history = [say("معدلي 50 وعلمي"), bot("📊 حاسبة القبول")]
    answer = calculator("هندسه مايقبل", history)
    assert "هندسة تقنيات الحاسوب (مسائي): الحد الأدنى 59.5، ينقصك 9.5" in answer
    assert "اللغة الإنجليزية" not in answer


def test_branch_joined_with_waw():
    assert "فرعك: علمي" in calculator("معدلي 50 وعلمي")


# ---------- Saved conversations ----------

import history  # noqa: E402

CHAT = [say("معدلي 60 علمي"), bot("📊 حاسبة القبول")]


def test_history_saves_new_conversation_with_title():
    store, cid = history.save([], None, CHAT)
    assert len(store) == 1 and store[0]["title"] == "معدلي 60 علمي" and cid == store[0]["id"]


def test_history_updates_same_conversation():
    store, cid = history.save([], None, CHAT)
    store, cid2 = history.save(store, cid, CHAT + [say("شكرا"), bot("عفواً")])
    assert cid2 == cid and len(store) == 1 and len(store[0]["messages"]) == 4


def test_history_ignores_searching_message_and_empty_chats():
    pending = {"role": "assistant", "content": "", "metadata": {"status": "pending"}}
    store, cid = history.save([], None, [say("سؤال"), pending])
    assert store == [] and cid is None


def test_history_pin_rename_delete():
    store, a = history.save([], None, CHAT)
    store, b = history.save(store, None, [say("كم أجور القانون؟"), bot("1,000,000")])
    store = history.toggle_pin(store, a)
    assert history.ordered(store)[0]["id"] == a          # pinned goes first
    store = history.rename(store, a, "  معدلي   ")
    assert history.find(store, a)["title"] == "معدلي"
    store = history.delete(store, a)
    assert [c["id"] for c in store] == [b]


def test_history_titles_are_escaped():
    store, cid = history.save([], None, [say("<script>x</script>"), bot("y")])
    assert "<script>" not in history.render(store, cid)


# ---------- Small talk, specific questions, department groups (11 Nov test) ----------
import smalltalk  # noqa: E402


def test_small_talk_replies():
    assert "وعليكم السلام" in smalltalk.answer("السلام عليكم")
    thanks = smalltalk.answer("احسنت")
    assert any(w in thanks for w in ("العفو", "شكراً", "يسعدني")) and "أنا المساعد" not in thanks
    assert "لست موظفاً" in smalltalk.answer("انت انسان؟")
    assert "أعتذر" in smalltalk.answer("انت غبي")
    assert "لم أفهم" in smalltalk.answer("؟؟")
    assert "آسف" in smalltalk.answer("جذاب")
    assert "سلامتك" in smalltalk.answer("ضايج اريد نسولف")
    assert "بخير" in smalltalk.answer("كيف حالك") and "بخير" in smalltalk.answer("شلونك")


def test_small_talk_leaves_real_questions():
    for q in ["مرحبا كم اجور القانون؟", "شكرا، وما الوثائق المطلوبة؟", "معدلي 70 علمي", "هل يوجد قسم صيدلة؟"]:
        assert smalltalk.answer(q) is None, q


def test_specific_discount_question_goes_to_ai():
    assert faq.answer("ما هي التخفيضات؟") is not None
    assert faq.answer("شنو التخفيضات") is not None
    assert faq.answer("اخوي شهيد كم الخصم") is None
    assert faq.answer("هل يوجد تخفيض لأبناء الموظفين؟") is None


def test_department_groups():
    text, _ = eligibility.handle("معدلي 70 علمي وأريد فقط الاقسام الانسانية", [])
    assert "القانون" in text and "هندسة" not in text
    text, _ = eligibility.handle("معدلي 80 احيائي شنو الاقسام الطبية", [])
    assert "المختبرات" in text and "القانون" not in text


def test_busy_model_is_skipped_for_a_while(monkeypatch):
    import llm
    calls = []

    def fake(system, prompt, model, timeout=0):
        calls.append(model)
        if model == "strong":
            raise RuntimeError("503 UNAVAILABLE")
        return "ok"

    monkeypatch.setattr(llm, "GEMINI_API_KEY", "x")
    monkeypatch.setattr(llm, "GEMINI_MODEL", "strong")
    monkeypatch.setattr(llm, "GEMINI_FALLBACK_MODEL", "light")
    monkeypatch.setattr(llm, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm, "_ask_gemini", fake)
    monkeypatch.setattr(llm, "_resting_until", {})
    assert llm.ask("s", "p") == ("ok", "light")
    assert llm.ask("s", "p") == ("ok", "light")
    assert calls == ["strong", "light", "light"]  # the busy model was not tried again


def test_bot_is_not_admission_only():
    assert "للقبول" not in smalltalk.answer("مرحبا")
    assert "الامتحانات" in smalltalk.answer("من انت")
    assert smalltalk.answer("شكرا كم مرة ارسب") is None


def test_university_procedures_reach_the_search():
    assert smalltalk.answer("شكرا كيف اباشر") is None
    assert smalltalk.answer("مرحبا اريد تأييد استمرارية") is None
    info = (Path(__file__).parent.parent / "data" / "university" / "info.md").read_text(encoding="utf-8")
    assert "رقم الوصل" in info and "إلى من يهمه الأمر" in info
