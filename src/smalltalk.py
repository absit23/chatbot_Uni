"""Friendly fixed replies for greetings, thanks, insults and "who are you?".

Small models answer these badly (they repeat "I am the assistant..." to
everything), so short social messages get a natural fixed reply instead,
instantly and without using the AI quota.
"""
import random
import re

from config import ADMISSION_CONTACT, UNIVERSITY_NAME
from textutils import normalize, tokenize

HELP = ("يمكنك سؤالي عن الأقسام المتاحة لمعدلك، أو الأجور والتخفيضات والوثائق، "
        "وإذا كنت طالباً في الجامعة فاسألني عن الامتحانات والرسوب والانتقال وسنة الترك.")

GREETING_WORDS = {"السلام", "سلام", "مرحبا", "مرحبه", "هلا", "هلو", "اهلا", "صباح", "مساء", "هاي"}
THANKS_WORDS = {"شكرا", "شكر", "مشكور", "احسنت", "تسلم", "عاشت", "ممتاز", "رائع", "جميل", "يعطيك", "حلو"}
INSULT_WORDS = {"غبي", "فاشل", "سيء", "سيئ", "زفت", "تافه", "حمار", "خايس"}
WRONG_WORDS = {"جذاب", "كذاب", "تكذب", "تجذب", "غلط", "خطا", "غلطان", "مو صحيح"}
SAD_WORDS = {"ضايج", "ضايق", "زعلان", "حزين", "متضايق", "طفشان", "ملل", "ملان", "نسولف", "اسولف", "سوالف"}
HOW_ARE_YOU = {"حالك", "شلونك", "شلونكم", "اخبارك", "احوالك", "عامل", "شخبارك", "شونك"}
HUMAN_WORDS = {"انسان", "بشر", "روبوت", "موظف", "حقيقي", "اله", "بوت"}
WHO_WORDS = {"من", "انت", "اسمك", "شنو", "منو"}

# Words that show the message also contains a real question, which the AI should answer
TOPIC_WORDS = {"اجور", "قسط", "تخفيض", "تخفيضات", "خصم", "معدل", "معدلي", "قسم", "اقسام", "وثائق",
               "تسجيل", "قبول", "تقديم", "كليه", "دوام", "امتحان", "رسوب", "ارسب", "انتقال", "غش", "ترك", "عطله", "العطله", "امتحانات", "الامتحانات", "مباشره", "اباشر", "تاييد", "استمراريه", "تدريسيين", "التدريسيين", "اساتذه", "الاساتذه", "كادر", "الكادر", "دكاتره", "الدكاتره", "موقع", "عنوان", "وين", "اين", "كم", "متى"}


def _pick(options: list[str]) -> str:
    return random.choice(options)


def answer(message: str) -> str | None:
    """A fixed social reply, or None when the message is a real question."""
    clean = normalize(message).strip()
    raw_words = re.findall("[ء-ي]+", clean)
    words = set(raw_words) | set(tokenize(message))
    if not re.search("[ء-ي0-9]", clean) or (len(clean) <= 2 and not clean.isdigit()):
        return f"لم أفهم رسالتك تماماً 🙂 {HELP}"
    # Longer messages ("شلونك اليوم؟ اني المبرمج مالتك") get a natural AI reply instead
    if words & TOPIC_WORDS or len(raw_words) > 4:
        return None
    if words & WRONG_WORDS:
        return ("إذا كان في جوابي خطأ فأنا آسف 🙏 قل لي أي معلومة تقصد، أو اضغط 👎 تحت الجواب حتى يراجعه الفريق. "
                f"والمعلومة المؤكدة دائماً عند {ADMISSION_CONTACT}.")
    if words & SAD_WORDS:
        return ("سلامتك 🌿 إن شاء الله تتحسن. أنا مختص بشؤون الجامعة والدراسة، فما أقدر أسولف بكل المواضيع، "
                "لكن إذا الدراسة أو اختيار القسم هو الذي يشغل بالك، احكِ لي وأساعدك خطوة بخطوة.")
    if words & INSULT_WORDS:
        return ("أعتذر إن لم يكن جوابي بالمستوى المطلوب. أعد صياغة سؤالك من فضلك، وسأحاول مساعدتك بشكل أفضل. "
                f"ويمكنك دائماً التواصل مع {ADMISSION_CONTACT}.")
    if words & HUMAN_WORDS:
        return (f"لا، أنا مساعد ذكي (برنامج ذكاء اصطناعي) يجيب من معلومات {UNIVERSITY_NAME} "
                f"والدليل الوزاري، ولست موظفاً. وإذا أردت التحدث مع موظف: {ADMISSION_CONTACT}.")
    if words & HOW_ARE_YOU:
        return f"بخير والحمد لله، شكراً لسؤالك 🌿 وأنت كيف حالك؟ {HELP}"
    if "السلام" in raw_words or "سلام" in raw_words:
        return f"وعليكم السلام ورحمة الله وبركاته 🌿 أهلاً بك في المساعد الذكي لـ{UNIVERSITY_NAME}. {HELP}"
    if words & GREETING_WORDS:
        return f"أهلاً وسهلاً بك 🌿 أنا المساعد الذكي لـ{UNIVERSITY_NAME}. {HELP}"
    if words & THANKS_WORDS:
        return _pick(["العفو، يسعدني ذلك! هل تحتاج شيئاً آخر؟",
                      "شكراً لك 🌿 إذا عندك سؤال آخر فأنا جاهز.",
                      "يسعدني أني ساعدتك! تفضل بأي سؤال آخر."])
    if (words & {"اسمك", "انت"} and len(raw_words) <= 4) or "اسم جامعتك" in clean or "اسم الجامعه" in clean:
        return (f"أنا المساعد الذكي لـ{UNIVERSITY_NAME}، برنامج ذكاء اصطناعي يجيب عن أسئلة "
                f"القبول والتسجيل والأجور، وتعليمات الطلبة للعام الدراسي 2026-2027. {HELP}")
    return None
