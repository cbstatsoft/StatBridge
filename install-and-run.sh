#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
for statbridge_python in python3.12 python3.13 python3.11 python3; do
  if command -v "$statbridge_python" >/dev/null 2>&1; then
    exec "$statbridge_python" install.py "$@"
  fi
done
printf '%s\n' 'Install Python 3.12 from python.org and run this installer again.' >&2
exit 2
