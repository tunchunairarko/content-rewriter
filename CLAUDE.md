# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local web app (Python 3.12, uv, FastAPI) that takes text or a document, strips the machine tells
from it, sends it through OpenRouter to be humanised, and returns the result in the input's format.
It runs on `127.0.0.1` and opens a browser tab; it is not built to be deployed publicly.

It started as a PyQt6 desktop app. That was abandoned because the packaged executable could not
find its credentials: `python-dotenv` searches from `os.getcwd()` when `sys.frozen` is set, and a
double-clicked macOS `.app` has a working directory of `/`. A server started from a directory makes
`.env` resolution ordinary again. Do not reintroduce a frozen-binary build without solving that.

## Architecture

Everything except `web.py` is pure Python with no web framework import, which is what keeps the
pipeline testable on its own:

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
  rendering. `.doc` is deliberately unsupported — it would need LibreOffice.
- `prompt.py` — `SYSTEM_PROMPT`, the one static multiline string that instructs the model. It is
  deliberately not configurable: it is product behaviour, not deployment config, so it belongs in
  source and never in `.env`.
- `rewriter.py` — `Settings.from_env()` (python-dotenv) plus a `Rewriter` wrapping the OpenAI SDK
  pointed at OpenRouter's base URL. Injectable `client` for tests. `Settings` carries credentials
  and model choice only.
- `pipeline.py` — `run_text`, a `Stage` enum reported through a `progress` callback, and
  `write_error_log`. **`clean()` runs twice**: once on input, once on the model's reply, because
  models happily reintroduce em dashes and curly quotes.
- `web.py` — the FastAPI app. `POST /api/rewrite` runs the pipeline on a worker thread and streams
  **NDJSON** (one `{stage, label, progress}` line per stage, then a final `{done, text, html, kind,
  filename}` or `{error, log}`). NDJSON over `fetch` rather than SSE, because `EventSource` is
  GET-only and would force a job-id handshake and server-side state. `POST /api/preview` renders an
  upload for the source pane; `POST /api/download` rebuilds a file from raw text on demand, which
  is the only place `documents.save` runs. Tests replace `build_rewriter` — it is called *inside*
  the worker's `try`, so a missing API key becomes an error payload rather than a 500.
- `static/` — `index.html`, `style.css`, `app.js`. No build step, no npm, no framework.

## Threading

The OpenAI SDK call is blocking, so the pipeline runs in a `threading.Thread` that feeds a
`queue.Queue`, drained with `asyncio.to_thread`. Nothing blocking may run directly in an async route
handler — it would stall the event loop for every other request.

## Configuration

`.env` (see `.env.example`, never committed): `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`,
`OPENROUTER_BASE_URL`, `REWRITE_TEMPERATURE`, `LOG_DIR`. A missing API key surfaces as an error
banner on the first run, not a crash. The system prompt is not among these — edit `prompt.py`.

## TDD

Tests come first, always:

1. Write a failing test in `tests/` that states the desired behavior.
2. Run it, confirm it fails for the reason you expect.
3. Write the minimum code to pass it.
4. Refactor only with the suite green.

Never write production code without a failing test demanding it. Never add functionality a test
does not cover. Routes are tested through `TestClient` with `build_rewriter` monkeypatched, so the
suite never touches the network and needs no browser.

## Commands

```bash
uv sync                  # install deps from pyproject.toml/uv.lock
uv run content-rewriter  # start the server and open a browser
uv run content-rewriter --no-browser --port 8791   # for scripted checks
uv run pytest            # tests
uv run pytest path/to/test_x.py::test_name   # single test
uv add <pkg>             # add a dependency (never edit pyproject deps by hand)
uv add --dev <pkg>       # dev-only dependency
```

CI: `.github/workflows/build.yml`, manual `workflow_dispatch` only. Runs the suite on
Linux/macOS/Windows and checks the app's routes register.

## Deployment

`start.sh` + `ecosystem.config.js` run the app under pm2 on an always-on host. The script resolves
`uv` explicitly (pm2's environment usually lacks `~/.local/bin` on `PATH`), refuses to start
without `.env`, runs `uv sync --frozen --no-dev`, then `exec`s the server so pm2 tracks the real
process — `uv run` forks a child, and without `exec` a `pm2 stop` would leave the port held.

```bash
pm2 start ecosystem.config.js && pm2 save
```

The ecosystem file sets `HOST=0.0.0.0`, which is the one place the loopback rule is deliberately
broken so the app is reachable from the network. Anyone who can reach that port can spend the configured
OpenRouter credit, so it belongs on a private network, or behind a reverse proxy
that authenticates. Do not copy that setting into local development.

`--no-dev` prunes pytest from the venv, so after running `start.sh` on a dev machine, restore the
test tooling with `uv sync --all-groups`.

## Conventions

- No code comments. Write self-explanatory names instead. This includes docstrings on obvious
  functions and `ponytail:` markers — leave them out.
- No gradients anywhere. Flat fills only: no `linear-gradient`/`radial-gradient`/`conic-gradient`
  in CSS. Use the solid colours from the custom properties in `style.css` and get depth from
  borders, elevation and shadows instead.
- Rendering must match the input's actual format. A markdown or `.docx` source is displayed as
  formatted text, never as raw markers; a `.txt` source and typed text are displayed verbatim in a
  `<pre>`. The downloaded file keeps the input's format and structure — headings stay headings,
  lists stay lists, emphasis stays emphasis. Supported formats are `.txt`, `.md` and `.docx` only.
- Markdown is rendered server-side by `markdown-it-py` with `html=False`, so model output cannot
  inject markup. Never set `innerHTML` from anything that has not been through it.
- The rendered pane is display only. `state.resultText` holds the raw string, and copy and download
  must read that, never `innerText`, or the markers are lost.
- Bind to `127.0.0.1` only. The process holds an API key; it must never listen on a public
  interface.
- All Python runs through `uv run` — do not use a manually activated venv or bare `python`.
- No frontend build step. If something seems to need npm, it does not belong here.
