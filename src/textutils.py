"""Arabic text helpers, so that small spelling differences do not break search."""
import re

DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟـ]")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
TOKEN = re.compile(r"[ء-ي]+|\d+")
PREFIX = re.compile("^(وال|بال|كال|فال|لل|ال)")
STOP_WORDS = set(
    "ما ماذا هو هي هل كيف متي اين كم من في علي الي عن او و ثم ان اذا هذا هذه ذلك التي الذي "
    "مع لا لم لكل كل بعد قبل عند".split()
)


def normalize(text: str) -> str:
    """Make equivalent spellings identical: إ/أ/آ -> ا, ى -> ي, ة -> ه, ٣ -> 3."""
    text = DIACRITICS.sub("", text).translate(ARABIC_DIGITS)
    text = re.sub("[إأآ]", "ا", text)
    return text.replace("ى", "ي").replace("ة", "ه")


def tokenize(text: str) -> list[str]:
    """Split text into words for keyword search, removing "ال" style prefixes and filler words."""
    tokens = []
    for word in TOKEN.findall(normalize(text)):
        if word in STOP_WORDS:
            continue
        match = PREFIX.match(word)
        if match and len(word) - match.end() >= 3:
            word = word[match.end():]
        tokens.append(word)
    return tokens
