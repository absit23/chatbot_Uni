"""Friendly fixed replies for greetings, thanks, insults and "who are you?".

Small models answer these badly (they repeat "I am the assistant..." to
everything), so short social messages get a natural fixed reply instead,
instantly and without using the AI quota.
"""
import random
import re

from config import ADMISSION_CONTACT, UNIVERSITY_NAME
from textutils import normalize, tokenize

HELP = "يمكنك سؤالي عن الأقسام المتاحة لمعدلك، أو الأجور والتخفيضات، أو الوثائق المطلوبة للتسجيل."

GREETING_WORDS = {"السلام", "سلام", "مرحبا", "مرحبه", "هلا", "هلو", "اهلا", "صباح", "مساء", "هاي"}
THANKS_WORDS = {"شكرا", "شكر", "مشكور", "احسنت", "تسلم", "عاشت", "ممتاز", "رائع", "جميل", "يعطيك", "حلو"}
INSULT_WORDS = {"غبي", "فاشل", "سيء", "سيئ", "زفت", "تافه", "حمار", "خايس"}
HOW_ARE_YOU = {"حالك", "شلونك", "شلونكم", "اخبارك", "احوالك", "عامل", "شخبارك", "شونك"}
HUMAN_WORDS = {"انسان", "بشر", "روبوت", "موظف", "حقيقي", "اله", "بوت"}
WHO_WORDS = {"من", "انت", "اسمك", "شنو", "منو"}

# Words that show the message also contains a real question, which the AI should answer
TOPIC_WORDS = {"اجور", "قسط", "تخفيض", "تخفيضات", "خصم", "معدل", "معدلي", "قسم", "اقسام", "وثائق",
               "تسجيل", "قبول", "تقديم", "كليه", "دوام", "موقع", "عنوان", "وين", "اين", "كم", "متى"}


def _pick(options: list[str]) -> str:
    return random.choice(options)


def answer(message: str) -> str | None:
    """A fixed social reply, or None when the message is a real question."""
    clean = normalize(message).strip()
    raw_words = re.findall("[ء-ي]+", clean)
    words = set(raw_words) | set(tokenize(message))
    if not re.search("[ء-ي0-9]", clean) or (len(clean) <= 2 and not clean.isdigit()):
        return f"لم أفهم رسالتك تماماً 🙂 {HELP}"
    if words & TOPIC_WORDS or len(raw_words) > 7:
        return None
    if words & INSULT_WORDS:
        return ("أعتذر إن لم يكن جوابي بالمستوى المطلوب. أعد صياغة سؤالك من فضلك، وسأحاول مساعدتك بشكل أفضل. "
                f"ويمكنك دائماً التواصل مع {ADMISSION_CONTACT}.")
    if words & HUMAN_WORDS:
        return (f"لا، أنا مساعد ذكي (برنامج ذكاء اصطناعي) يجيب من معلومات {UNIVERSITY_NAME} "
                f"ودليل القبول الوزاري، ولست موظفاً. وإذا أردت التحدث مع موظف: {ADMISSION_CONTACT}.")
    if words & HOW_ARE_YOU:
        return f"بخير والحمد لله، شكراً لسؤالك 🌿 وأنت كيف حالك؟ {HELP}"
    if "السلام" in raw_words or "سلام" in raw_words:
        return f"وعليكم السلام ورحمة الله وبركاته 🌿 أهلاً بك في المساعد الذكي للقبول في {UNIVERSITY_NAME}. {HELP}"
    if words & GREETING_WORDS:
        return f"أهلاً وسهلاً بك 🌿 أنا المساعد الذكي للقبول في {UNIVERSITY_NAME}. {HELP}"
    if words & THANKS_WORDS:
        return _pick(["العفو، يسعدني ذلك! هل تحتاج شيئاً آخر عن القبول؟",
                      "شكراً لك 🌿 إذا عندك سؤال آخر فأنا جاهز.",
                      "يسعدني أني ساعدتك! تفضل بأي سؤال آخر."])
    if (words & {"اسمك", "انت"} and len(raw_words) <= 4) or "اسم جامعتك" in clean or "اسم الجامعه" in clean:
        return (f"أنا المساعد الذكي للقبول في {UNIVERSITY_NAME}، برنامج ذكاء اصطناعي يجيب عن أسئلة "
                f"التقديم والقبول والأجور للعام الدراسي 2026-2027. {HELP}")
    return None
