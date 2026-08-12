import asyncio
import json
import os
import queue
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from markdown_it import MarkdownIt
from pydantic import BaseModel

from content_rewriter.documents import Kind, kind_of, load, output_path_for, save
from content_rewriter.pipeline import Stage, run_text, write_error_log
from content_rewriter.rewriter import Rewriter, Settings

STATIC = Path(__file__).parent / "static"

MAX_UPLOAD_BYTES = 5 * 1024 * 1024

STAGE_PROGRESS = {
    Stage.READING: 12,
    Stage.CLEANING: 26,
    Stage.REWRITING: 62,
    Stage.POLISHING: 86,
    Stage.WRITING: 94,
    Stage.DONE: 100,
}

renderer = MarkdownIt("commonmark", {"html": False, "linkify": False})

app = FastAPI(title="Content Rewriter")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class DownloadRequest(BaseModel):
    text: str
    filename: str


def build_rewriter():
    return Rewriter(Settings.from_env())


def same_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and urlparse(origin).netloc != request.headers.get("host"):
        raise HTTPException(status_code=403, detail="Cross-origin requests are not allowed.")


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.post("/api/preview", dependencies=[Depends(same_origin)])
async def preview(file: UploadFile):
    try:
        text = _read_upload(file.filename, await _read_capped(file))
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    kind = kind_of(file.filename)
    return {
        "kind": kind.value,
        "name": Path(file.filename).name,
        "text": text,
        "html": _render(text, kind),
    }


@app.post("/api/rewrite", dependencies=[Depends(same_origin)])
async def rewrite(
    text: str = Form(default=""),
    keywords: str = Form(default=""),
    file: UploadFile | None = None,
):
    upload = None
    if file is not None and file.filename:
        upload = (file.filename, await _read_capped(file))

    return StreamingResponse(
        _stream(text, upload, _split_keywords(keywords)), media_type="application/x-ndjson"
    )


@app.post("/api/download", dependencies=[Depends(same_origin)])
def download(request: DownloadRequest):
    name = Path(request.filename).name or "rewritten.txt"

    workspace = tempfile.mkdtemp()
    try:
        written = save(Path(workspace) / name, request.text)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return FileResponse(written, filename=name, background=_cleanup(workspace))


async def _stream(text, upload, keywords):
    events = queue.Queue()
    worker = threading.Thread(target=_run, args=(text, upload, keywords, events), daemon=True)
    worker.start()

    while True:
        event = await asyncio.to_thread(events.get)
        if event is None:
            return
        yield json.dumps(event) + "\n"


def _run(text, upload, keywords, events):
    def report(stage):
        if stage is not Stage.DONE:
            events.put(
                {"stage": stage.name, "label": stage.value, "progress": STAGE_PROGRESS[stage]}
            )

    try:
        source_name = upload[0] if upload else None
        if upload:
            report(Stage.READING)
            text = _read_upload(*upload)

        result = run_text(text, build_rewriter(), progress=report, keywords=keywords)
        kind = kind_of(source_name)
        events.put(
            {
                "done": True,
                "kind": kind.value,
                "text": result.text,
                "html": _render(result.text, kind),
                "filename": _download_name(source_name),
                "missing_keywords": list(result.missing_keywords),
            }
        )
    except BaseException as error:
        events.put(_failure(error))
    finally:
        events.put(None)


def _split_keywords(raw: str) -> list:
    parts = [part.strip() for chunk in raw.splitlines() for part in chunk.split(",")]
    seen = {}
    for part in parts:
        if part:
            seen.setdefault(part.casefold(), part)
    return list(seen.values())


async def _read_capped(file: UploadFile) -> bytes:
    payload = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"That file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )
    return payload


def _read_upload(name, payload):
    with tempfile.TemporaryDirectory() as workspace:
        path = Path(workspace) / Path(name).name
        path.write_bytes(payload)
        return load(path)


def _render(text, kind):
    if kind is Kind.MARKDOWN:
        return renderer.render(text)
    return f"<pre>{_escape(text)}</pre>"


def _escape(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _download_name(source_name):
    if not source_name:
        return "rewritten.txt"
    return output_path_for(Path(source_name).name).name


def _failure(error):
    payload = {"error": f"{type(error).__name__}: {error}"}
    try:
        payload["log"] = write_error_log(error, directory=_log_directory()).name
    except Exception:
        pass
    return payload


def _log_directory():
    configured = os.getenv("LOG_DIR", "").strip()
    return Path(configured).expanduser() if configured else Path.cwd()


def _cleanup(workspace):
    from starlette.background import BackgroundTask
    import shutil

    return BackgroundTask(shutil.rmtree, workspace, ignore_errors=True)
