"""The API layer: send a prompt to Gemini, and fall back to Groq if that fails."""
from google import genai
from google.genai import types
from groq import Groq

from config import GEMINI_API_KEY, GEMINI_FALLBACK_MODEL, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL


class NoProviderAvailable(Exception):
    """Every configured API failed, for example because free limits ran out."""


def _ask_gemini(system: str, prompt: str, model: str) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, temperature=0.1),
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty answer")
    return response.text


def _ask_groq(system: str, prompt: str) -> str:
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return response.choices[0].message.content


def ask(system: str, prompt: str) -> tuple[str, str]:
    """Return (answer, name of the provider that answered)."""
    providers = []
    if GEMINI_API_KEY:
        # The main model first; when its daily free limit runs out, the lighter model with a bigger limit.
        models = [GEMINI_MODEL, *GEMINI_FALLBACK_MODEL.split(",")]  # the fallback can be a list: a,b,c
        for model in dict.fromkeys(m.strip() for m in models if m.strip()):
            providers.append((model, lambda s, p, m=model: _ask_gemini(s, p, m)))
    if GROQ_API_KEY:
        providers.append(("Groq", _ask_groq))
    if not providers:
        raise NoProviderAvailable("No API key found. Add GEMINI_API_KEY to your .env file.")

    errors = []
    for name, call in providers:
        try:
            return call(system, prompt), name
        except Exception as error:  # rate limit, network failure, retired model...
            print(f"[{name} failed] {error}")
            errors.append(f"{name}: {error}")
    raise NoProviderAvailable(" | ".join(errors))
