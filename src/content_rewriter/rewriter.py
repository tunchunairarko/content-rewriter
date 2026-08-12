import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from content_rewriter.cleaning import clean
from content_rewriter.prompt import with_keywords

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.85
DEFAULT_TOP_P = 1.0
DEFAULT_FREQUENCY_PENALTY = 0.0
DEFAULT_PRESENCE_PENALTY = 0.0


class MissingCredentials(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    base_url: str
    temperature: float
    top_p: float
    frequency_penalty: float
    presence_penalty: float

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
            top_p=_read_float("REWRITE_TOP_P", DEFAULT_TOP_P),
            frequency_penalty=_read_float("REWRITE_FREQUENCY_PENALTY", DEFAULT_FREQUENCY_PENALTY),
            presence_penalty=_read_float("REWRITE_PRESENCE_PENALTY", DEFAULT_PRESENCE_PENALTY),
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

    def _request(self, text: str, keywords) -> dict:
        request = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "top_p": self.settings.top_p,
            "messages": [
                {"role": "system", "content": with_keywords(keywords)},
                {"role": "user", "content": text},
            ],
        }
        if self.settings.frequency_penalty:
            request["frequency_penalty"] = self.settings.frequency_penalty
        if self.settings.presence_penalty:
            request["presence_penalty"] = self.settings.presence_penalty
        return request

    def rewrite(self, text: str, keywords=()) -> str:
        completion = self.client.chat.completions.create(**self._request(text, keywords))

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
