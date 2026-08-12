#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

resolve_uv() {
  if [ -n "${UV_BIN:-}" ] && [ -x "${UV_BIN}" ]; then
    printf '%s' "${UV_BIN}"
    return 0
  fi

  for candidate in \
    "$(command -v uv 2>/dev/null || true)" \
    "${HOME}/.local/bin/uv" \
    "${HOME}/.cargo/bin/uv" \
    /usr/local/bin/uv \
    /opt/uv/bin/uv; do
    if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then
      printf '%s' "${candidate}"
      return 0
    fi
  done

  return 1
}

if ! UV="$(resolve_uv)"; then
  echo "start.sh: uv not found on PATH. Install it, or set UV_BIN to its full path." >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "start.sh: no .env in $(pwd). Copy .env.example to .env and add OPENROUTER_API_KEY." >&2
  exit 1
fi

mkdir -p "${LOG_DIR:-logs}"

"${UV}" sync --frozen --no-dev

exec "${UV}" run --frozen --no-dev content-rewriter \
  --no-browser \
  --host "${HOST:-127.0.0.1}" \
  --port "${PORT:-8765}"
