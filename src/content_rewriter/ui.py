import os
import sys
from pathlib import Path

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    QSize,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from content_rewriter import theme
from content_rewriter.documents import READABLE, Kind, kind_of, supported_filter
from content_rewriter.pipeline import Stage, run_file, run_text, write_error_log
from content_rewriter.rewriter import Rewriter, Settings

STAGE_PROGRESS = {
    Stage.READING: 12,
    Stage.CLEANING: 26,
    Stage.REWRITING: 62,
    Stage.POLISHING: 86,
    Stage.WRITING: 94,
    Stage.DONE: 100,
}


class Worker(QThread):
    advanced = pyqtSignal(object)
    finished_with = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(self, source, rewriter, parent=None):
        super().__init__(parent)
        self.source = source
        self.rewriter = rewriter

    def run(self):
        try:
            if isinstance(self.source, Path):
                result = run_file(self.source, self.rewriter, progress=self.advanced.emit)
            else:
                result = run_text(self.source, self.rewriter, progress=self.advanced.emit)
        except BaseException as error:
            self.failed.emit(error)
        else:
            self.finished_with.emit(result)


class Card(QFrame):
    file_dropped = pyqtSignal(Path)

    def __init__(self, label, accepts_files=False, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setProperty("dragging", "false")
        self.setAcceptDrops(accepts_files)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(38)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 130))
        self.setGraphicsEffect(shadow)

        self.heading = QLabel(label)
        self.heading.setObjectName("cardLabel")

        self.header = QHBoxLayout()
        self.header.setContentsMargins(0, 0, 0, 0)
        self.header.addWidget(self.heading)
        self.header.addStretch(1)

        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(22, 18, 22, 20)
        self.body.setSpacing(12)
        self.body.addLayout(self.header)

    def set_dragging(self, dragging):
        self.setProperty("dragging", "true" if dragging else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):
        if _dropped_path(event) is not None:
            event.acceptProposedAction()
            self.set_dragging(True)

    def dragLeaveEvent(self, event):
        self.set_dragging(False)

    def dropEvent(self, event):
        path = _dropped_path(event)
        self.set_dragging(False)
        if path is not None:
            event.acceptProposedAction()
            self.file_dropped.emit(path)


class Banner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("banner")
        self.setProperty("tone", "info")
        self.setMaximumHeight(0)

        self.message = QLabel()
        self.message.setObjectName("bannerText")
        self.message.setWordWrap(True)

        self.action = QPushButton("Open log")
        self.action.setObjectName("ghost")
        self.action.hide()

        close = QPushButton("Dismiss")
        close.setObjectName("ghost")
        close.clicked.connect(self.hide_banner)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.message, 1)
        layout.addWidget(self.action)
        layout.addWidget(close)

        self.animation = QPropertyAnimation(self, b"maximumHeight", self)
        self.animation.setDuration(260)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def show_message(self, text, tone="info", on_action=None, action_text="Open log"):
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)
        self.message.setText(text)

        try:
            self.action.clicked.disconnect()
        except TypeError:
            pass

        if on_action is None:
            self.action.hide()
        else:
            self.action.setText(action_text)
            self.action.clicked.connect(on_action)
            self.action.show()

        self.animation.stop()
        self.animation.setStartValue(self.maximumHeight())
        self.animation.setEndValue(max(self.sizeHint().height(), 58))
        self.animation.start()

    def hide_banner(self):
        self.animation.stop()
        self.animation.setStartValue(self.maximumHeight())
        self.animation.setEndValue(0)
        self.animation.start()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Content Rewriter")
        self.setMinimumSize(QSize(1060, 700))
        self.setAcceptDrops(True)

        self.source_path = None
        self.source_text = ""
        self.source_kind = Kind.PLAIN
        self.result_text = ""
        self.worker = None
        self.log_path = None
        self.settings = None

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(34, 28, 34, 26)
        outer.setSpacing(18)
        outer.addLayout(self._build_header())

        self.banner = Banner()
        outer.addWidget(self.banner)

        outer.addLayout(self._build_panes(), 1)
        outer.addLayout(self._build_footer())

        self._pulse = None
        self._load_settings()

    def _build_header(self):
        title = QLabel("Content Rewriter")
        title.setObjectName("title")

        subtitle = QLabel("Strip the machine tells, keep the meaning.")
        subtitle.setObjectName("subtitle")

        text = QVBoxLayout()
        text.setSpacing(3)
        text.addWidget(title)
        text.addWidget(subtitle)

        self.status_dot = QLabel()
        self.status_dot.setFixedSize(9, 9)
        self.status_dot.setPixmap(_dot(theme.SUCCESS))

        self.status_text = QLabel("Ready")
        self.status_text.setObjectName("statusText")

        status = QHBoxLayout()
        status.setSpacing(8)
        status.addWidget(self.status_dot)
        status.addWidget(self.status_text)

        header = QHBoxLayout()
        header.addLayout(text)
        header.addStretch(1)
        header.addLayout(status)
        return header

    def _build_panes(self):
        self.source_card = Card("SOURCE", accepts_files=True)
        self.source_card.file_dropped.connect(self.load_file)

        self.chip = QFrame()
        self.chip.setObjectName("chip")
        self.chip.hide()

        self.chip_text = QLabel()
        self.chip_text.setObjectName("chipText")

        chip_clear = QPushButton("Clear")
        chip_clear.setObjectName("ghost")
        chip_clear.clicked.connect(self.clear_file)

        chip_layout = QHBoxLayout(self.chip)
        chip_layout.setContentsMargins(14, 6, 8, 6)
        chip_layout.setSpacing(8)
        chip_layout.addWidget(self.chip_text, 1)
        chip_layout.addWidget(chip_clear)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText(
            "Paste your text here, or drop a .txt, .md or .docx file anywhere on this panel."
        )
        self.editor.setAcceptRichText(False)
        self.editor.textChanged.connect(self._sync_counts)

        open_file = QPushButton("Open file")
        open_file.clicked.connect(self.choose_file)

        self.source_count = QLabel("0 characters")
        self.source_count.setObjectName("metaText")

        source_actions = QHBoxLayout()
        source_actions.setSpacing(10)
        source_actions.addWidget(open_file)
        source_actions.addStretch(1)
        source_actions.addWidget(self.source_count)

        self.source_card.body.addWidget(self.chip)
        self.source_card.body.addWidget(self.editor, 1)
        self.source_card.body.addLayout(source_actions)

        self.result_card = Card("RESULT")

        self.result = QTextEdit()
        self.result.setObjectName("result")
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("The humanised version will appear here.")

        self.result_opacity = QGraphicsOpacityEffect(self.result)
        self.result_opacity.setOpacity(1.0)
        self.result.setGraphicsEffect(self.result_opacity)

        self.copy_button = QPushButton("Copy")
        self.copy_button.clicked.connect(self.copy_result)
        self.copy_button.setEnabled(False)

        self.save_button = QPushButton("Save as")
        self.save_button.clicked.connect(self.save_result)
        self.save_button.setEnabled(False)

        self.result_count = QLabel("")
        self.result_count.setObjectName("metaText")

        result_actions = QHBoxLayout()
        result_actions.setSpacing(10)
        result_actions.addWidget(self.copy_button)
        result_actions.addWidget(self.save_button)
        result_actions.addStretch(1)
        result_actions.addWidget(self.result_count)

        self.result_card.body.addWidget(self.result, 1)
        self.result_card.body.addLayout(result_actions)

        panes = QHBoxLayout()
        panes.setSpacing(18)
        panes.addWidget(self.source_card, 1)
        panes.addWidget(self.result_card, 1)
        return panes

    def _build_footer(self):
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)

        self.progress_animation = QPropertyAnimation(self.progress, b"value", self)
        self.progress_animation.setDuration(520)
        self.progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.stage_label = QLabel("Idle")
        self.stage_label.setObjectName("metaText")

        self.model_label = QLabel("")
        self.model_label.setObjectName("metaText")

        meta = QHBoxLayout()
        meta.addWidget(self.stage_label)
        meta.addStretch(1)
        meta.addWidget(self.model_label)

        self.run_button = QPushButton("Humanise")
        self.run_button.setObjectName("primary")
        self.run_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_button.clicked.connect(self.start)
        self.run_button.setMinimumWidth(180)

        glow = QGraphicsDropShadowEffect(self.run_button)
        glow.setBlurRadius(34)
        glow.setXOffset(0)
        glow.setYOffset(6)
        glow.setColor(QColor(109, 94, 248, 150))
        self.run_button.setGraphicsEffect(glow)

        controls = QHBoxLayout()
        controls.addStretch(1)
        controls.addWidget(self.run_button)

        footer = QVBoxLayout()
        footer.setSpacing(12)
        footer.addWidget(self.progress)
        footer.addLayout(meta)
        footer.addLayout(controls)
        return footer

    def _load_settings(self):
        try:
            self.settings = Settings.from_env()
        except Exception as error:
            self.model_label.setText("No model configured")
            self._set_status("Needs setup", theme.DANGER)
            self.report_failure(error)
        else:
            self.model_label.setText(f"Model: {self.settings.model}")

    def _sync_counts(self):
        raw = self.source_text if self.source_path is not None else self.editor.toPlainText()
        self.source_count.setText(f"{len(raw):,} characters")

    def _render(self, widget, text, kind):
        if kind is Kind.MARKDOWN:
            widget.setMarkdown(text)
        else:
            widget.setPlainText(text)

    def _set_status(self, text, color):
        self.status_text.setText(text)
        self.status_dot.setPixmap(_dot(color))

    def _start_pulse(self):
        effect = QGraphicsOpacityEffect(self.status_dot)
        self.status_dot.setGraphicsEffect(effect)

        fade_out = QPropertyAnimation(effect, b"opacity", self)
        fade_out.setDuration(700)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.25)
        fade_out.setEasingCurve(QEasingCurve.Type.InOutSine)

        fade_in = QPropertyAnimation(effect, b"opacity", self)
        fade_in.setDuration(700)
        fade_in.setStartValue(0.25)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.InOutSine)

        group = QSequentialAnimationGroup(self)
        group.addAnimation(fade_out)
        group.addAnimation(fade_in)
        group.setLoopCount(-1)
        group.start()
        self._pulse = group

    def _stop_pulse(self):
        if self._pulse is not None:
            self._pulse.stop()
            self._pulse = None
        self.status_dot.setGraphicsEffect(None)

    def _animate_progress(self, value):
        self.progress_animation.stop()
        self.progress_animation.setStartValue(self.progress.value())
        self.progress_animation.setEndValue(value)
        self.progress_animation.start()

    def dragEnterEvent(self, event):
        if _dropped_path(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event):
        path = _dropped_path(event)
        if path is not None:
            event.acceptProposedAction()
            self.load_file(path)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open document", "", supported_filter())
        if path:
            self.load_file(Path(path))

    def load_file(self, path):
        from content_rewriter.documents import load

        try:
            content = load(path)
        except Exception as error:
            self.report_failure(error)
            return

        self.source_path = path
        self.source_text = content
        self.source_kind = kind_of(path)
        self.chip_text.setText(f"{path.name}  ·  {_readable_size(path)}")
        self.chip.show()
        self.editor.setReadOnly(True)
        self._render(self.editor, content, self.source_kind)
        self.banner.hide_banner()
        self._set_status("File loaded", theme.SUCCESS)

    def clear_file(self):
        self.source_path = None
        self.source_text = ""
        self.source_kind = Kind.PLAIN
        self.chip.hide()
        self.editor.setReadOnly(False)
        self.editor.clear()
        self._set_status("Ready", theme.SUCCESS)

    def start(self):
        if self.worker is not None and self.worker.isRunning():
            return

        if self.settings is None:
            self._load_settings()
            if self.settings is None:
                return

        source = self.source_path if self.source_path else self.editor.toPlainText()
        if isinstance(source, str) and not source.strip():
            self.banner.show_message("Add some text or open a file first.", tone="error")
            return

        try:
            rewriter = Rewriter(self.settings)
        except Exception as error:
            self.report_failure(error)
            return

        self.run_button.setEnabled(False)
        self.run_button.setText("Working")
        self.copy_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.result.clear()
        self.result_text = ""
        self.result_count.setText("")
        self.banner.hide_banner()
        self._set_status("Working", theme.ACCENT_ALT)
        self._start_pulse()
        self._animate_progress(6)

        self.worker = Worker(source, rewriter, self)
        self.worker.advanced.connect(self.on_stage)
        self.worker.finished_with.connect(self.on_success)
        self.worker.failed.connect(self.on_failure)
        self.worker.start()

    def on_stage(self, stage):
        self.stage_label.setText(stage.value)
        self._animate_progress(STAGE_PROGRESS.get(stage, self.progress.value()))

    def on_success(self, result):
        self._finish()
        self._animate_progress(100)
        self.stage_label.setText("Finished")
        self._set_status("Done", theme.SUCCESS)

        self.result_text = result.text
        self._render(self.result, result.text, self.source_kind)
        self.result_count.setText(f"{len(result.text):,} characters")
        self.copy_button.setEnabled(True)
        self.save_button.setEnabled(True)

        fade = QPropertyAnimation(self.result_opacity, b"opacity", self)
        fade.setDuration(420)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade.start()
        self._fade = fade

        if result.path is not None:
            self.banner.show_message(
                f"Saved to {result.path}",
                tone="success",
                on_action=lambda: _reveal(result.path),
                action_text="Show file",
            )

        QTimer.singleShot(2400, lambda: self._animate_progress(0))

    def on_failure(self, error):
        self._finish()
        self._animate_progress(0)
        self.stage_label.setText("Failed")
        self.report_failure(error)

    def report_failure(self, error):
        self._set_status("Error", theme.DANGER)
        try:
            self.log_path = write_error_log(error, directory=_log_directory(self.source_path))
        except Exception:
            self.log_path = None

        message = f"{type(error).__name__}: {error}"
        if self.log_path is None:
            self.banner.show_message(message, tone="error")
        else:
            self.banner.show_message(
                message,
                tone="error",
                on_action=lambda: _reveal(self.log_path),
                action_text="Open log",
            )

    def _finish(self):
        self._stop_pulse()
        self.run_button.setEnabled(True)
        self.run_button.setText("Humanise")

    def copy_result(self):
        QGuiApplication.clipboard().setText(self.result_text)
        self.banner.show_message("Copied to clipboard.", tone="success")
        QTimer.singleShot(1800, self.banner.hide_banner)

    def save_result(self):
        suggested = "rewritten.txt"
        if self.source_path is not None:
            suggested = f"{self.source_path.stem}.rewritten{self.source_path.suffix}"

        path, _ = QFileDialog.getSaveFileName(self, "Save result", suggested, supported_filter())
        if not path:
            return

        from content_rewriter.documents import save

        try:
            written = save(Path(path), self.result_text)
        except Exception as error:
            self.report_failure(error)
            return

        self.banner.show_message(
            f"Saved to {written}",
            tone="success",
            on_action=lambda: _reveal(written),
            action_text="Show file",
        )

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait(2000)
        super().closeEvent(event)


def _dropped_path(event):
    data = event.mimeData()
    if not data.hasUrls():
        return None
    for url in data.urls():
        if not url.isLocalFile():
            continue
        path = Path(url.toLocalFile())
        if path.is_file() and path.suffix.lower() in READABLE:
            return path
    return None


def _dot(color):
    pixmap = QPixmap(18, 18)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, 18, 18)
    painter.end()
    return pixmap.scaled(
        9,
        9,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _readable_size(path):
    size = path.stat().st_size
    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} MB"


def _log_directory(source_path):
    configured = os.getenv("LOG_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if source_path is not None:
        return Path(source_path).parent
    return Path.cwd()


def _reveal(path):
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtCore import QUrl

    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    self_check = "--self-check" in argv
    if self_check:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    QApplication.setApplicationName("Content Rewriter")
    QApplication.setOrganizationName("Content Rewriter")

    app = QApplication.instance() or QApplication(argv)
    app.setStyleSheet(theme.STYLESHEET)
    app.setFont(QFont(QFont().defaultFamily(), 10))
    app.setWindowIcon(QIcon(_dot(theme.ACCENT)))

    window = Window()
    if self_check:
        window.close()
        return 0

    window.show()

    fade = QPropertyAnimation(window, b"windowOpacity", window)
    fade.setDuration(320)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(QEasingCurve.Type.OutCubic)
    fade.start()
    window._entrance = fade

    return app.exec()
