import pytest

from content_rewriter.rewriter import MissingCredentials, Rewriter, Settings


class FakeCompletions:
    def __init__(self, reply, recorder):
        self.reply = reply
        self.recorder = recorder

    def create(self, **kwargs):
        self.recorder.append(kwargs)
        message = type("Message", (), {"content": self.reply})
        choice = type("Choice", (), {"message": message})
        return type("Completion", (), {"choices": [choice]})


class FakeClient:
    def __init__(self, reply="rewritten text", recorder=None):
        self.recorder = recorder if recorder is not None else []
        self.chat = type("Chat", (), {"completions": FakeCompletions(reply, self.recorder)})


def settings(**overrides):
    values = {
        "api_key": "test-key",
        "model": "openai/gpt-4o-mini",
        "base_url": "https://openrouter.ai/api/v1",
        "temperature": 0.8,
        "system_prompt": "humanize this",
    }
    values.update(overrides)
    return Settings(**values)


def test_sends_system_prompt_and_content():
    calls = []
    rewriter = Rewriter(settings(), client=FakeClient(recorder=calls))

    assert rewriter.rewrite("original content") == "rewritten text"

    sent = calls[0]
    assert sent["model"] == "openai/gpt-4o-mini"
    assert sent["temperature"] == 0.8
    assert sent["messages"][0] == {"role": "system", "content": "humanize this"}
    assert sent["messages"][1] == {"role": "user", "content": "original content"}


def test_response_is_cleaned_of_reintroduced_unicode():
    rewriter = Rewriter(settings(), client=FakeClient(reply="model—output ‘quoted’ 😀"))
    assert rewriter.rewrite("x") == "model, output 'quoted'"


def test_empty_response_is_an_error():
    rewriter = Rewriter(settings(), client=FakeClient(reply=""))
    with pytest.raises(RuntimeError):
        rewriter.rewrite("x")


def test_settings_require_an_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("content_rewriter.rewriter.load_dotenv", lambda *a, **k: False)
    with pytest.raises(MissingCredentials):
        Settings.from_env()


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setattr("content_rewriter.rewriter.load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-abc")
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4")
    monkeypatch.setenv("REWRITE_TEMPERATURE", "0.4")

    loaded = Settings.from_env()

    assert loaded.api_key == "sk-abc"
    assert loaded.model == "anthropic/claude-sonnet-4"
    assert loaded.temperature == 0.4
    assert loaded.base_url == "https://openrouter.ai/api/v1"
    assert "spelling" in loaded.system_prompt.lower()
