import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from content_rewriter.cleaning import clean
from content_rewriter.prompt import SYSTEM_PROMPT

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.85


class MissingCredentials(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    base_url: str
    temperature: float

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
                {"role": "system", "content": SYSTEM_PROMPT},
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
