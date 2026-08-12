# Content Rewriter

A local web app that strips the machine tells out of text and rewrites it so it reads as though a
person wrote it in one sitting.

It removes invisible Unicode, em and en dashes, curly quotes, ellipsis characters, emoji and
everything else outside plain ASCII, then sends the result through
[OpenRouter](https://openrouter.ai) with a prompt that preserves meaning while varying rhythm and
adding a very small amount of natural grammatical noise. The reply is cleaned a second time,
because models cheerfully reintroduce em dashes.

Documents keep their shape. A `.docx` with headings, lists and bold comes back as a `.docx` with
headings, lists and bold.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- An OpenRouter API key

## Setup

```bash
git clone <your-repo> content-rewriter
cd content-rewriter
uv sync
cp .env.example .env
```

Put your key in `.env`, then start it:

```bash
uv run content-rewriter
```

The server listens on `http://127.0.0.1:8765` and opens a browser tab.

## Using it

Paste text into the left pane, or drop a `.txt`, `.md` or `.docx` file onto it. Press **Humanise**
(or `Cmd`/`Ctrl` + `Enter`).

Progress runs along the bottom as the text is cleaned, sent to the model, and cleaned again. When it
finishes, **Copy** puts the raw text on your clipboard and **Download** gives you a file in the
original format.

Markdown and `.docx` sources are shown rendered, since that is their actual format. A `.txt` file
and text you type are shown verbatim, markers and all.

Failures never crash the app: the banner explains what went wrong and names a `log_<timestamp>.txt`
written with the full traceback.

## Configuration

All of it lives in `.env`, which is never committed.

| Variable | Default | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Required. Without it the first run shows an error banner. |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Any model slug OpenRouter accepts. |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Point at another OpenAI-compatible endpoint if you like. |
| `REWRITE_TEMPERATURE` | `0.85` | Higher wanders further from the original phrasing. |
| `REWRITE_TOP_P` | `1.0` | Nucleus sampling. Lower values narrow the token pool. |
| `REWRITE_FREQUENCY_PENALTY` | `0.0` | Discourages reusing the same words. Omitted from the request when zero. |
| `REWRITE_PRESENCE_PENALTY` | `0.0` | Pushes toward introducing new wording. Omitted from the request when zero. |
| `LOG_DIR` | working directory | Where error logs are written. |
| `HOST` | `127.0.0.1` | Bind address. See the warning below before changing it. |
| `PORT` | `8765` | Port to listen on. |

The system prompt is deliberately **not** configurable from the environment. It is product
behaviour rather than deployment config, so it lives in
[`src/content_rewriter/prompt.py`](src/content_rewriter/prompt.py) — edit it there.

## Self-hosting with pm2

To keep it running on an always-on machine:

```bash
cp .env.example .env      # add your key
pm2 start ecosystem.config.js
pm2 save
pm2 startup               # follow the command it prints, to survive reboots
```

`start.sh` resolves `uv` explicitly, because pm2's environment usually lacks `~/.local/bin` on
`PATH`. Set `UV_BIN` if yours lives somewhere unusual. The script refuses to start without a `.env`
and `exec`s the server so pm2 supervises the real process rather than a wrapper shell.

`pm2 logs content-rewriter` shows output; application error logs land in `logs/`.

### A warning about exposing it

`ecosystem.config.js` sets `HOST=0.0.0.0` so the app is reachable from other machines on the same
network. **The app has no authentication.** Anyone who can reach that port can spend your OpenRouter
credit. That is fine on a private network you control. Do not expose it to the internet without
putting an authenticating reverse proxy in front.

## Security

- Cross-origin requests are rejected, so a page you visit cannot quietly drive the app on your
  behalf.
- Model output is rendered to HTML server-side by `markdown-it-py` with raw HTML disabled, so a
  reply containing `<script>` is escaped rather than executed.
- Uploads are capped at 5 MB, and `.docx` archives that expand beyond 64 MB are refused, so a
  malformed document cannot exhaust memory on a small machine.
- The API key is only ever read from the environment. It is never written into the page, the logs,
  or any build artifact.

## Development

Tests come first in this codebase. The pipeline has no web framework import anywhere, so most of it
is tested as plain Python; routes are tested with FastAPI's `TestClient` and a stubbed rewriter, so
the suite never touches the network.

```bash
uv run pytest
uv run pytest tests/test_cleaning.py::test_clean   # a single test
uv run content-rewriter --no-browser --port 8791   # for scripted checks
```

| Module | Responsibility |
|---|---|
| `cleaning.py` | The single text transform. Markdown-safe: indentation and thematic breaks survive. |
| `documents.py` | `.txt`/`.md`/`.docx` in and out, with markdown as the intermediate representation. |
| `prompt.py` | The static system prompt. |
| `rewriter.py` | OpenRouter through the OpenAI SDK. |
| `pipeline.py` | Stages, orchestration, error logs. |
| `web.py` | FastAPI routes and the NDJSON progress stream. |
| `static/` | The whole front end. No npm, no build step. |

`.doc` is not supported and will not be: reading it needs LibreOffice, which is a large dependency
for a format you can convert once by hand.

## Licence

Copyright (C) 2026 tunchunairarko

This program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
[GNU General Public License](LICENSE) for more details.
