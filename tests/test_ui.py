import pytest

from content_rewriter.documents import Kind
from content_rewriter.pipeline import Result, Stage
from content_rewriter.ui import STAGE_PROGRESS, Window, Worker, main


@pytest.fixture
def window(qtbot, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    widget = Window()
    qtbot.addWidget(widget)
    return widget


def test_every_stage_maps_to_progress():
    assert set(STAGE_PROGRESS) == set(Stage)
    assert STAGE_PROGRESS[Stage.DONE] == 100
    assert sorted(STAGE_PROGRESS.values()) == list(STAGE_PROGRESS.values())


def test_window_starts_ready(window):
    assert window.status_text.text() == "Ready"
    assert "test/model" in window.model_label.text()
    assert not window.copy_button.isEnabled()
    assert not window.save_button.isEnabled()


def test_empty_input_is_refused(window):
    window.start()
    assert window.worker is None
    assert "text" in window.banner.message.text().lower()


def test_success_enables_the_result_actions(window):
    window.on_success(Result(text="humanised body"))

    assert window.result.toPlainText() == "humanised body"
    assert window.copy_button.isEnabled()
    assert window.save_button.isEnabled()
    assert window.status_text.text() == "Done"


def test_failure_writes_a_log_and_shows_it(window, tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    window.on_failure(RuntimeError("model exploded"))

    assert "model exploded" in window.banner.message.text()
    assert window.log_path.parent == tmp_path
    assert window.log_path.exists()
    assert window.run_button.isEnabled()


def test_loading_a_file_locks_the_editor(window, tmp_path):
    source = tmp_path / "note.txt"
    source.write_text("file body", encoding="utf-8")

    window.load_file(source)

    assert window.editor.toPlainText() == "file body"
    assert window.editor.isReadOnly()
    assert window.chip.isVisibleTo(window)
    assert window.source_count.text() == "9 characters"

    window.clear_file()
    assert not window.editor.isReadOnly()
    assert window.editor.toPlainText() == ""


def test_markdown_source_is_rendered_not_shown_raw(window, tmp_path):
    source = tmp_path / "note.md"
    source.write_text("# Heading\n\n- one\n- two\n", encoding="utf-8")

    window.load_file(source)

    assert window.source_kind is Kind.MARKDOWN
    assert window.source_text == "# Heading\n\n- one\n- two\n"
    assert "#" not in window.editor.toPlainText()
    assert "Heading" in window.editor.toPlainText()


def test_plain_source_is_shown_verbatim(window, tmp_path):
    source = tmp_path / "note.txt"
    source.write_text("# not a heading", encoding="utf-8")

    window.load_file(source)

    assert window.source_kind is Kind.PLAIN
    assert window.editor.toPlainText() == "# not a heading"


def test_result_renders_in_the_source_format(window, tmp_path):
    source = tmp_path / "note.md"
    source.write_text("# Heading\n", encoding="utf-8")
    window.load_file(source)

    window.on_success(Result(text="# Rewritten\n\n- point"))

    assert "#" not in window.result.toPlainText()
    assert "Rewritten" in window.result.toPlainText()
    assert window.result_text == "# Rewritten\n\n- point"


def test_copy_and_save_use_the_raw_markdown(window, tmp_path, monkeypatch):
    source = tmp_path / "note.md"
    source.write_text("# Heading\n", encoding="utf-8")
    window.load_file(source)
    window.on_success(Result(text="# Rewritten\n\n- point"))

    copied = []
    monkeypatch.setattr(
        "content_rewriter.ui.QGuiApplication.clipboard",
        lambda: type("Board", (), {"setText": staticmethod(copied.append)}),
    )
    window.copy_result()
    assert copied == ["# Rewritten\n\n- point"]

    target = tmp_path / "out.md"
    monkeypatch.setattr(
        "content_rewriter.ui.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "")),
    )
    window.save_result()
    assert target.read_text(encoding="utf-8") == "# Rewritten\n\n- point"


def test_self_check_builds_the_window_and_exits(qapp, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    assert main(["content-rewriter", "--self-check"]) == 0


def test_worker_reports_failure_without_raising(qtbot):
    class Boom:
        def rewrite(self, text):
            raise RuntimeError("no")

    worker = Worker("some text", Boom())
    with qtbot.waitSignal(worker.failed, timeout=3000) as blocker:
        worker.start()

    assert isinstance(blocker.args[0], RuntimeError)
    worker.wait(2000)


def test_worker_emits_result(qtbot):
    class Stub:
        def rewrite(self, text):
            return "done"

    worker = Worker("some text", Stub())
    with qtbot.waitSignal(worker.finished_with, timeout=3000) as blocker:
        worker.start()

    assert blocker.args[0].text == "done"
    worker.wait(2000)
