#!/usr/bin/env sh
# install.sh — POSIX thin wrapper. Just locates a Python interpreter and execs install.py.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  printf '%s\n' "python3 is required (python3 not found on PATH)" >&2
  exit 127
fi

exec "$PY" "$ROOT/install.py" "$@"
