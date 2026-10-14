#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x .venv/bin/python ]; then
  printf '%s\n' 'Run ./install-and-run.sh first.'
  exit 1
fi
exec .venv/bin/python launch.py "$@"
