import json

import pytest
from fastapi.testclient import TestClient

from content_rewriter.pipeline import Stage
from content_rewriter.web import app


class StubRewriter:
    def __init__(self, reply=None):
        self.reply = reply
        self.seen = []

    def rewrite(self, text):
        self.seen.append(text)
        return self.reply if self.reply is not None else text


class FailingRewriter:
    def rewrite(self, text):
        raise RuntimeError("upstream refused")


@pytest.fixture
def stub(monkeypatch):
    rewriter = StubRewriter()
    monkeypatch.setattr("content_rewriter.web.build_rewriter", lambda: rewriter)
    return rewriter


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    return TestClient(app)


def rewrite(client, **data):
    response = client.post("/api/rewrite", data=data)
    assert response.status_code == 200
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def upload(client, name, content):
    files = {"file": (name, content, "application/octet-stream")}
    response = client.post("/api/rewrite", files=files)
    assert response.status_code == 200
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def final(events):
    return events[-1]


def test_index_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Content Rewriter" in response.text
    assert "/static/app.js" in response.text


def test_static_assets_resolve(client):
    for asset in ("/static/app.js", "/static/style.css"):
        assert client.get(asset).status_code == 200


def test_text_streams_every_stage_then_the_result(client, stub):
    events = rewrite(client, text="dirty — input 😀")

    stages = [event["stage"] for event in events if "stage" in event]
    assert stages == [Stage.CLEANING.name, Stage.REWRITING.name, Stage.POLISHING.name]
    assert [event["progress"] for event in events if "progress" in event] == sorted(
        event["progress"] for event in events if "progress" in event
    )

    assert stub.seen == ["dirty, input"]
    assert final(events)["done"] is True
    assert final(events)["text"] == "dirty, input"


def test_model_output_is_cleaned_again(client, monkeypatch):
    monkeypatch.setattr(
        "content_rewriter.web.build_rewriter",
        lambda: StubRewriter(reply="model—reply ‘quoted’ 😀"),
    )
    assert final(rewrite(client, text="input"))["text"] == "model, reply 'quoted'"


def test_markdown_upload_is_rendered_as_html(client, stub):
    events = upload(client, "note.md", b"# Heading\n\n- one\n- two\n")
    payload = final(events)

    assert payload["kind"] == "markdown"
    assert "<h1>Heading</h1>" in payload["html"]
    assert "<li>one</li>" in payload["html"]
    assert payload["text"] == "# Heading\n\n- one\n- two\n"
    assert payload["filename"] == "note.rewritten.md"


def test_plain_upload_is_not_rendered_as_markdown(client, stub):
    payload = final(upload(client, "note.txt", b"# not a heading"))

    assert payload["kind"] == "plain"
    assert "<h1>" not in payload["html"]
    assert "# not a heading" in payload["html"]
    assert payload["text"] == "# not a heading"


def test_upload_reports_the_reading_stage(client, stub):
    events = upload(client, "note.txt", b"content")
    assert [event["stage"] for event in events if "stage" in event][0] == Stage.READING.name


def test_docx_structure_survives_the_round_trip(client, stub, tmp_path):
    docx = pytest.importorskip("docx")

    source = tmp_path / "report.docx"
    document = docx.Document()
    document.add_paragraph("Report", style="Heading 1")
    body = document.add_paragraph()
    body.add_run("intro — with ")
    body.add_run("emphasis").bold = True
    document.add_paragraph("one", style="List Bullet")
    document.save(source)

    payload = final(upload(client, "report.docx", source.read_bytes()))

    assert payload["text"] == "# Report\n\nintro, with **emphasis**\n\n- one"
    assert "<h1>Report</h1>" in payload["html"]
    assert "<strong>emphasis</strong>" in payload["html"]
    assert payload["filename"] == "report.rewritten.docx"


def test_rendered_html_escapes_injected_markup(client, monkeypatch):
    monkeypatch.setattr(
        "content_rewriter.web.build_rewriter",
        lambda: StubRewriter(reply="# Title\n\n<script>alert(1)</script>"),
    )
    payload = final(upload(client, "note.md", b"anything"))

    assert "<script>" not in payload["html"]
    assert "&lt;script&gt;" in payload["html"]


def test_blank_input_is_reported_as_an_error(client, stub):
    payload = final(rewrite(client, text="   \n "))
    assert "error" in payload
    assert "text" in payload["error"].lower()


def test_input_that_is_only_emoji_is_reported_as_an_error(client, stub):
    payload = final(rewrite(client, text="😀😀"))
    assert "error" in payload


def test_unsupported_upload_is_reported_as_an_error(client, stub):
    payload = final(upload(client, "sheet.pdf", b"%PDF-1.4"))
    assert "not supported" in payload["error"]


def test_model_failure_writes_a_log_file(client, tmp_path, monkeypatch):
    monkeypatch.setattr("content_rewriter.web.build_rewriter", lambda: FailingRewriter())
    payload = final(rewrite(client, text="content"))

    assert "upstream refused" in payload["error"]
    assert payload["log"].startswith("log_")
    assert (tmp_path / payload["log"]).is_file()
    assert "Traceback" in (tmp_path / payload["log"]).read_text(encoding="utf-8")


def test_missing_credentials_are_reported_not_raised(client, monkeypatch):
    monkeypatch.setattr("content_rewriter.rewriter.load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    payload = final(rewrite(client, text="content"))
    assert "OPENROUTER_API_KEY" in payload["error"]


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("out.txt", b"# Heading\n\n- one"),
        ("out.md", b"# Heading\n\n- one"),
    ],
)
def test_download_returns_plain_bytes(client, filename, expected):
    response = client.post(
        "/api/download", json={"text": "# Heading\n\n- one", "filename": filename}
    )

    assert response.status_code == 200
    assert response.content == expected
    assert filename in response.headers["content-disposition"]


def test_download_builds_a_real_docx(client, tmp_path):
    docx = pytest.importorskip("docx")

    response = client.post(
        "/api/download",
        json={"text": "# Heading\n\nbody **bold** text\n\n- one", "filename": "out.docx"},
    )
    assert response.status_code == 200

    target = tmp_path / "out.docx"
    target.write_bytes(response.content)
    paragraphs = docx.Document(target).paragraphs

    assert [p.style.name for p in paragraphs] == ["Heading 1", "Normal", "List Bullet"]
    assert [run.text for run in paragraphs[1].runs if run.bold] == ["bold"]


def test_download_rejects_a_path_outside_the_name(client):
    response = client.post(
        "/api/download", json={"text": "x", "filename": "../../etc/passwd.txt"}
    )
    assert response.status_code == 200
    assert "passwd.txt" in response.headers["content-disposition"]
    assert ".." not in response.headers["content-disposition"]


def test_download_rejects_an_unsupported_format(client):
    response = client.post("/api/download", json={"text": "x", "filename": "out.pdf"})
    assert response.status_code == 400


def test_self_check_confirms_the_routes():
    from content_rewriter.__main__ import main

    assert main(["--self-check"]) == 0


def test_preview_renders_the_source_in_its_own_format(client):
    response = client.post(
        "/api/preview", files={"file": ("note.md", b"# Heading\n\n- one", "text/markdown")}
    )
    payload = response.json()

    assert payload["kind"] == "markdown"
    assert "<h1>Heading</h1>" in payload["html"]
    assert payload["text"] == "# Heading\n\n- one"
    assert payload["name"] == "note.md"


def test_preview_of_plain_text_is_escaped_not_rendered(client):
    response = client.post(
        "/api/preview", files={"file": ("note.txt", b"# not a heading", "text/plain")}
    )
    payload = response.json()

    assert payload["kind"] == "plain"
    assert "<h1>" not in payload["html"]


def test_preview_rejects_an_unsupported_file(client):
    response = client.post(
        "/api/preview", files={"file": ("sheet.pdf", b"%PDF-1.4", "application/pdf")}
    )
    assert response.status_code == 400


def test_host_defaults_to_loopback(monkeypatch):
    from content_rewriter.__main__ import resolve_host

    monkeypatch.delenv("HOST", raising=False)
    assert resolve_host([]) == "127.0.0.1"


def test_host_comes_from_the_environment(monkeypatch):
    from content_rewriter.__main__ import resolve_host

    monkeypatch.setenv("HOST", "0.0.0.0")
    assert resolve_host([]) == "0.0.0.0"


def test_host_flag_beats_the_environment(monkeypatch):
    from content_rewriter.__main__ import resolve_host

    monkeypatch.setenv("HOST", "0.0.0.0")
    assert resolve_host(["--host", "192.168.1.50"]) == "192.168.1.50"


def test_port_flag_beats_the_environment(monkeypatch):
    from content_rewriter.__main__ import resolve_port

    monkeypatch.setenv("PORT", "9000")
    assert resolve_port([]) == 9000
    assert resolve_port(["--port", "8080"]) == 8080
