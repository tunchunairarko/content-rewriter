import os
import sys
import threading
import webbrowser

import uvicorn

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--self-check" in argv:
        from content_rewriter.web import app

        return 0 if any(route.path == "/api/rewrite" for route in app.routes) else 1

    host = resolve_host(argv)
    port = resolve_port(argv)

    if "--no-browser" not in argv:
        threading.Timer(0.7, webbrowser.open, args=(f"http://{host}:{port}",)).start()

    print(f"Content Rewriter running at http://{host}:{port}", flush=True)
    uvicorn.run("content_rewriter.web:app", host=host, port=port, log_level="warning")
    return 0


def resolve_host(argv):
    if "--host" in argv:
        return argv[argv.index("--host") + 1]
    return os.getenv("HOST", "").strip() or DEFAULT_HOST


def resolve_port(argv):
    if "--port" in argv:
        return int(argv[argv.index("--port") + 1])
    return int(os.getenv("PORT", "").strip() or DEFAULT_PORT)


if __name__ == "__main__":
    sys.exit(main())
