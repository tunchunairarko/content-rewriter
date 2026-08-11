# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A PyQt6 desktop app (Python 3.12, uv) that takes text or a document, strips the machine tells from
it, sends it through OpenRouter to be humanised, and returns the result in the input's format.

## Architecture

The pipeline is pure Python with no Qt import anywhere except `ui.py`, which is what makes it
testable without a display:

- `cleaning.py` — `clean()`, the single text transform. NFKC normalise, drop invisible/bidi
  characters, transliterate punctuation (curly quotes, ellipsis, nbsp) to ASCII, dashes to a
  comma, strip emoji, decompose accents and drop the rest of non-ASCII, then tidy whitespace.
  Order matters: punctuation is transliterated *before* the ASCII strip so `don’t` does not become
  `dont`, and dashes become commas before emoji/ASCII removal would delete them. It is also
  markdown-safe on purpose: leading indentation survives (nested lists, indented code) and a line
  that is only dashes stays a thematic break instead of becoming a comma.
- `documents.py` — format dispatch by suffix, with **markdown as the single intermediate
  representation**. `.docx` is read into markdown (`Heading N`/`Title` → `#`, `List Bullet` → `-`,
  `List Number` → `1.`, `Quote` → `>`, bold/italic runs → `**`/`*`) and written back out of markdown
  the same way, so headings, lists and emphasis survive the round trip. `.txt` is plain, `.md` is
  already markdown. `kind_of()` reports whether a path carries markdown, which is what drives
  rendering in the UI. `.doc` is deliberately unsupported — it would need LibreOffice.
- `rewriter.py` — `Settings.from_env()` (python-dotenv) plus a `Rewriter` wrapping the OpenAI SDK
  pointed at OpenRouter's base URL. Injectable `client` for tests. The default system prompt lives
  here and is overridable via `REWRITE_SYSTEM_PROMPT`.
- `pipeline.py` — `run_text` / `run_file`, a `Stage` enum reported through a `progress` callback,
  and `write_error_log`. **`clean()` runs twice**: once on input, once on the model's reply, because
  models happily reintroduce em dashes and curly quotes.
- `ui.py` — the window. Work runs in a `Worker(QThread)`; stages arrive as signals and drive an
  animated `QProgressBar` via `STAGE_PROGRESS`. Every failure path routes through
  `Window.report_failure`, which writes `log_${timestamp}.txt` and surfaces it in the banner.
  Both panes render through `Window._render`, which picks `setMarkdown` or `setPlainText` from
  `source_kind`. The rendered widget is display only: `source_text` and `result_text` hold the raw
  strings, and copy/save must read those, never `toPlainText()`, or the markers are lost.
- `theme.py` — colour constants and the app-wide QSS.

Anything blocking belongs in the worker, never on the GUI thread.

## Configuration

`.env` (see `.env.example`, never committed): `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`,
`OPENROUTER_BASE_URL`, `REWRITE_TEMPERATURE`, `REWRITE_SYSTEM_PROMPT`, `LOG_DIR`. A missing API key
surfaces as an error banner at startup, not a crash.

## TDD

Tests come first, always:

1. Write a failing test in `tests/` that states the desired behavior.
2. Run it, confirm it fails for the reason you expect.
3. Write the minimum code to pass it.
4. Refactor only with the suite green.

Never write production code without a failing test demanding it. Never add functionality a test
does not cover. Use `pytest-qt`'s `qtbot` for widget behavior; keep logic out of widgets so most
tests need no Qt at all.

## Commands

```bash
uv sync                  # install deps from pyproject.toml/uv.lock
uv run content-rewriter  # run the app
QT_QPA_PLATFORM=offscreen uv run pytest   # headless UI tests (CI uses xvfb on Linux)
uv run pytest            # tests
uv run pytest path/to/test_x.py::test_name   # single test
uv add <pkg>             # add a dependency (never edit pyproject deps by hand)
uv add --dev <pkg>       # dev-only dependency
```

CI: `.github/workflows/build.yml`, manual `workflow_dispatch` only. Run it from the master branch
to test + build PyInstaller executables for Linux/macOS/Windows; binaries land as run artifacts.

## Conventions

- No code comments. Write self-explanatory names instead. This includes docstrings on obvious
  functions and `ponytail:` markers — leave them out.
- No gradients anywhere. Flat fills only: no `qlineargradient`/`qradialgradient`/`qconicalgradient`
  in QSS, no `QLinearGradient`/`QRadialGradient` in painting code. Use solid colours from
  `theme.py` and get depth from borders, elevation and shadows instead.
- Rendering must match the input's actual format. A markdown or `.docx` source is displayed as
  formatted text, never as raw markers; a `.txt` source is displayed verbatim. The output file keeps
  the input's format and structure — headings stay headings, lists stay lists, emphasis stays
  emphasis. Supported formats are `.txt`, `.md` and `.docx` only; no `.doc`, since it would drag in
  a LibreOffice dependency.
- All Python runs through `uv run` — do not use a manually activated venv or bare `python`.
- Qt work belongs on the GUI thread; anything blocking (network, disk, model calls) goes to a
  `QThread`/`QRunnable` and reports back via signals.
