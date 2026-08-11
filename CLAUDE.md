# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

Python 3.12 + uv + PyQt6 desktop app. `pyproject.toml`, `.python-version`, and the build workflow
exist; there is no application code or test yet. Entry point is expected at
`src/content_rewriter/__main__.py` with a `main()` function — the workflow and console script both
reference it.

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
uv run <module>          # run the app
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
- All Python runs through `uv run` — do not use a manually activated venv or bare `python`.
- Qt work belongs on the GUI thread; anything blocking (network, disk, model calls) goes to a
  `QThread`/`QRunnable` and reports back via signals.
