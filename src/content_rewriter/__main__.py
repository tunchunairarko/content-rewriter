import os
import sys
import threading
import webbrowser

import uvicorn

HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    port = _port(argv)
    url = f"http://{HOST}:{port}"

    if "--self-check" in argv:
        from content_rewriter.web import app

        return 0 if any(route.path == "/api/rewrite" for route in app.routes) else 1

    if "--no-browser" not in argv:
        threading.Timer(0.7, webbrowser.open, args=(url,)).start()

    print(f"Content Rewriter running at {url}")
    uvicorn.run("content_rewriter.web:app", host=HOST, port=port, log_level="warning")
    return 0


def _port(argv):
    if "--port" in argv:
        return int(argv[argv.index("--port") + 1])
    return int(os.getenv("PORT", DEFAULT_PORT))


if __name__ == "__main__":
    sys.exit(main())
