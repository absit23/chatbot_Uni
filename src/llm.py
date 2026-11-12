"""The API layer: send a prompt to Gemini, and fall back to Groq if that fails."""
import time
from google import genai
from google.genai import types
from groq import Groq

from config import GEMINI_API_KEY, GEMINI_FALLBACK_MODEL, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL


# A model that just failed (busy, or out of daily quota) is skipped for a few minutes,
# so the next visitors do not wait for the same failure again.
COOLDOWN_SECONDS = 300
# A model that has not answered by then is treated as busy. The first (strong) model
# gets a short wait; the backups are normally fast, so they get a little more time.
FIRST_TIMEOUT_SECONDS = 10  # Google refuses anything under 10 seconds
TIMEOUT_SECONDS = 15
_resting_until: dict[str, float] = {}


class NoProviderAvailable(Exception):
    """Every configured API failed, for example because free limits ran out."""


def _ask_gemini(system: str, prompt: str, model: str, timeout: int = TIMEOUT_SECONDS) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY, http_options=types.HttpOptions(
        timeout=timeout * 1000, retry_options=types.HttpRetryOptions(attempts=1)))  # fail fast, the next model answers
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, temperature=0.3),
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty answer")
    return response.text


def _ask_groq(system: str, prompt: str) -> str:
    client = Groq(api_key=GROQ_API_KEY, timeout=TIMEOUT_SECONDS)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content


def ask(system: str, prompt: str) -> tuple[str, str]:
    """Return (answer, name of the provider that answered)."""
    providers = []
    if GEMINI_API_KEY:
        # The main model first; when its daily free limit runs out, the lighter model with a bigger limit.
        models = [GEMINI_MODEL, *GEMINI_FALLBACK_MODEL.split(",")]  # the fallback can be a list: a,b,c
        for model in dict.fromkeys(m.strip() for m in models if m.strip()):
            wait = FIRST_TIMEOUT_SECONDS if not providers else TIMEOUT_SECONDS
            providers.append((model, lambda s, p, m=model, w=wait: _ask_gemini(s, p, m, w)))
    if GROQ_API_KEY:
        providers.append(("Groq", _ask_groq))
    if not providers:
        raise NoProviderAvailable("No API key found. Add GEMINI_API_KEY to your .env file.")

    errors = []
    ready = [p for p in providers if _resting_until.get(p[0], 0) <= time.time()] or providers
    for name, call in ready:
        try:
            return call(system, prompt), name
        except Exception as error:  # rate limit, network failure, retired model...
            print(f"[{name} failed, skipped for {COOLDOWN_SECONDS // 60} minutes] {str(error)[:120]}")
            _resting_until[name] = time.time() + COOLDOWN_SECONDS
            errors.append(f"{name}: {error}")
    raise NoProviderAvailable(" | ".join(errors))
