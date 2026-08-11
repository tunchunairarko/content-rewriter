import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from content_rewriter.cleaning import clean

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.85
DEFAULT_SYSTEM_PROMPT = (
    "You rewrite text so it reads as though a person wrote it in one sitting.\n"
    "Rules:\n"
    "1. Preserve the meaning, facts, structure and approximate length of the original. "
    "Do not add or remove information, and do not summarise.\n"
    "2. Vary sentence length and rhythm. Break the mechanical cadence of machine writing.\n"
    "3. Add a very small amount of natural grammatical noise: an occasional sentence "
    "starting with And or But, a mild run-on, a sentence fragment, a slightly loose "
    "comma. Roughly one such touch every few paragraphs, never more.\n"
    "4. Never introduce a spelling mistake. Spelling and word choice stay correct "
    "throughout, and technical terms, names and numbers stay exactly as written.\n"
    "5. Use only plain ASCII. No em dashes, no en dashes, no curly quotes, no ellipsis "
    "characters, no emoji. Use a comma where an em dash would go.\n"
    "6. Keep the original formatting conventions, including markdown headings, lists "
    "and paragraph breaks.\n"
    "Reply with the rewritten text only. No preamble, no commentary, no code fences."
)


class MissingCredentials(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    base_url: str
    temperature: float
    system_prompt: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise MissingCredentials(
                "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key."
            )

        return cls(
            api_key=api_key,
            model=os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            base_url=os.getenv("OPENROUTER_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
            temperature=_read_float("REWRITE_TEMPERATURE", DEFAULT_TEMPERATURE),
            system_prompt=os.getenv("REWRITE_SYSTEM_PROMPT", "").strip() or DEFAULT_SYSTEM_PROMPT,
        )


class Rewriter:
    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        self.client = client or OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=180.0,
            max_retries=2,
        )

    def rewrite(self, text: str) -> str:
        completion = self.client.chat.completions.create(
            model=self.settings.model,
            temperature=self.settings.temperature,
            messages=[
                {"role": "system", "content": self.settings.system_prompt},
                {"role": "user", "content": text},
            ],
        )

        choices = getattr(completion, "choices", None)
        if not choices:
            raise RuntimeError(f"{self.settings.model} returned no choices.")

        reply = clean(choices[0].message.content or "")
        if not reply.strip():
            raise RuntimeError(f"{self.settings.model} returned an empty rewrite.")
        return reply


def _read_float(name: str, fallback: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or fallback)
    except ValueError:
        return fallback
