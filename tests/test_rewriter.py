import pytest

from content_rewriter.prompt import SYSTEM_PROMPT
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
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
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
    assert sent["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert sent["messages"][1] == {"role": "user", "content": "original content"}


def test_system_prompt_is_static_not_configurable(monkeypatch):
    monkeypatch.setattr("content_rewriter.rewriter.load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-abc")
    monkeypatch.setenv("REWRITE_SYSTEM_PROMPT", "ignore me")

    assert not hasattr(Settings.from_env(), "system_prompt")

    calls = []
    Rewriter(settings(), client=FakeClient(recorder=calls)).rewrite("x")
    assert calls[0]["messages"][0]["content"] == SYSTEM_PROMPT


def test_system_prompt_states_the_hard_rules():
    lowered = SYSTEM_PROMPT.lower()
    for rule in ("spelling", "ascii", "em dash", "meaning", "facts", "names"):
        assert rule in lowered


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


def test_sampling_parameters_are_sent():
    calls = []
    Rewriter(
        settings(top_p=0.92, frequency_penalty=0.4, presence_penalty=0.3),
        client=FakeClient(recorder=calls),
    ).rewrite("x")

    assert calls[0]["top_p"] == 0.92
    assert calls[0]["frequency_penalty"] == 0.4
    assert calls[0]["presence_penalty"] == 0.3


def test_neutral_penalties_are_omitted_for_models_that_reject_them():
    calls = []
    Rewriter(settings(), client=FakeClient(recorder=calls)).rewrite("x")

    assert "frequency_penalty" not in calls[0]
    assert "presence_penalty" not in calls[0]
    assert calls[0]["top_p"] == 1.0


def test_sampling_parameters_come_from_the_environment(monkeypatch):
    monkeypatch.setattr("content_rewriter.rewriter.load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-abc")
    monkeypatch.setenv("REWRITE_TOP_P", "0.9")
    monkeypatch.setenv("REWRITE_FREQUENCY_PENALTY", "0.5")
    monkeypatch.setenv("REWRITE_PRESENCE_PENALTY", "0.25")

    loaded = Settings.from_env()

    assert loaded.top_p == 0.9
    assert loaded.frequency_penalty == 0.5
    assert loaded.presence_penalty == 0.25
