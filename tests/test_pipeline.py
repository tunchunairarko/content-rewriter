import pytest

from content_rewriter.pipeline import Stage, run_file, run_text, write_error_log


class StubRewriter:
    def __init__(self, reply="humanized text"):
        self.reply = reply
        self.seen = []

    def rewrite(self, text):
        self.seen.append(text)
        return self.reply


class FailingRewriter:
    def rewrite(self, text):
        raise RuntimeError("upstream refused")


def test_run_text_cleans_before_and_after_the_model():
    rewriter = StubRewriter(reply="clean—reply")
    result = run_text("dirty — input 😀", rewriter)

    assert rewriter.seen == ["dirty, input"]
    assert result.text == "clean, reply"


def test_run_text_reports_every_stage_in_order():
    seen = []
    run_text("input", StubRewriter(), progress=lambda stage: seen.append(stage))

    assert seen == [Stage.CLEANING, Stage.REWRITING, Stage.POLISHING, Stage.DONE]


def test_run_text_rejects_blank_input():
    with pytest.raises(ValueError):
        run_text("   \n  ", StubRewriter())


def test_run_text_rejects_input_that_is_only_strippable():
    with pytest.raises(ValueError):
        run_text("😀😀", StubRewriter())


def test_run_file_writes_a_sibling_output(tmp_path):
    source = tmp_path / "essay.md"
    source.write_text("original — content\n", encoding="utf-8")

    result = run_file(source, StubRewriter())

    assert result.path == tmp_path / "essay.rewritten.md"
    assert result.path.read_text(encoding="utf-8") == "humanized text"
    assert result.text == "humanized text"


def test_run_file_reports_read_and_write_stages(tmp_path):
    source = tmp_path / "essay.txt"
    source.write_text("content", encoding="utf-8")

    seen = []
    run_file(source, StubRewriter(), progress=lambda stage: seen.append(stage))

    assert seen[0] == Stage.READING
    assert Stage.WRITING in seen
    assert seen[-1] == Stage.DONE


def test_docx_formatting_survives_the_whole_pipeline(tmp_path):
    docx = pytest.importorskip("docx")

    source = tmp_path / "report.docx"
    document = docx.Document()
    document.add_paragraph("Report", style="Heading 1")
    body = document.add_paragraph()
    body.add_run("intro — with ")
    body.add_run("emphasis").bold = True
    document.add_paragraph("one", style="List Bullet")
    document.add_paragraph("two", style="List Bullet")
    document.save(source)

    class Echo:
        def rewrite(self, text):
            self.seen = text
            return text

    echo = Echo()
    result = run_file(source, echo)

    assert echo.seen == "# Report\n\nintro, with **emphasis**\n\n- one\n- two"

    written = docx.Document(result.path)
    assert [p.style.name for p in written.paragraphs] == [
        "Heading 1",
        "Normal",
        "List Bullet",
        "List Bullet",
    ]
    assert [run.text for run in written.paragraphs[1].runs if run.bold] == ["emphasis"]


def test_failures_propagate(tmp_path):
    source = tmp_path / "essay.txt"
    source.write_text("content", encoding="utf-8")

    with pytest.raises(RuntimeError):
        run_file(source, FailingRewriter())


def test_write_error_log_names_file_with_timestamp(tmp_path):
    try:
        raise ValueError("boom")
    except ValueError as error:
        path = write_error_log(error, directory=tmp_path)

    assert path.parent == tmp_path
    assert path.name.startswith("log_")
    assert path.name.endswith(".txt")

    written = path.read_text(encoding="utf-8")
    assert "ValueError" in written
    assert "boom" in written
    assert "Traceback" in written


def test_write_error_logs_do_not_collide(tmp_path):
    first = write_error_log(ValueError("a"), directory=tmp_path)
    second = write_error_log(ValueError("b"), directory=tmp_path)
    assert first != second
