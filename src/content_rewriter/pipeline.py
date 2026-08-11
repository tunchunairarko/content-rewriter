import platform
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Protocol

from content_rewriter.cleaning import clean
from content_rewriter.documents import load, output_path_for, save


class Stage(str, Enum):
    READING = "Reading document"
    CLEANING = "Stripping hidden characters"
    REWRITING = "Humanising with the model"
    POLISHING = "Polishing the response"
    WRITING = "Writing output file"
    DONE = "Finished"


class SupportsRewrite(Protocol):
    def rewrite(self, text: str) -> str: ...


Progress = Optional[Callable[[Stage], None]]


@dataclass(frozen=True)
class Result:
    text: str
    path: Optional[Path] = None


def run_text(text: str, rewriter: SupportsRewrite, progress: Progress = None) -> Result:
    report = progress or (lambda stage: None)

    report(Stage.CLEANING)
    prepared = clean(text)
    if not prepared.strip():
        raise ValueError("There is no usable text to rewrite once hidden characters are removed.")

    report(Stage.REWRITING)
    rewritten = rewriter.rewrite(prepared)

    report(Stage.POLISHING)
    polished = clean(rewritten)

    report(Stage.DONE)
    return Result(text=polished)


def run_file(path: Path, rewriter: SupportsRewrite, progress: Progress = None) -> Result:
    report = progress or (lambda stage: None)
    path = Path(path)

    report(Stage.READING)
    original = load(path)

    result = run_text(original, rewriter, progress=_skip_done(report))

    report(Stage.WRITING)
    target = save(output_path_for(path), result.text)

    report(Stage.DONE)
    return Result(text=result.text, path=target)


def write_error_log(error: BaseException, directory: Optional[Path] = None) -> Path:
    directory = Path(directory) if directory else Path.cwd()
    directory.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = directory / f"log_{stamp}.txt"

    trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    if "Traceback" not in trace:
        trace = f"Traceback (most recent call last):\n  <not available>\n{trace}"

    path.write_text(
        "\n".join(
            [
                f"Content Rewriter error log",
                f"Time: {datetime.now().isoformat(timespec='seconds')}",
                f"Platform: {platform.platform()}",
                f"Python: {sys.version.split()[0]}",
                f"Error: {type(error).__name__}: {error}",
                "",
                trace,
            ]
        ),
        encoding="utf-8",
    )
    return path


def _skip_done(report: Callable[[Stage], None]) -> Callable[[Stage], None]:
    def forward(stage: Stage) -> None:
        if stage is not Stage.DONE:
            report(stage)

    return forward
