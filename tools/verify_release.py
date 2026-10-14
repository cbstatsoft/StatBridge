# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Check packaged file hashes without importing the application."""

import hashlib
import json
from pathlib import Path
import sys


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / "RELEASE.json").read_text(encoding="utf-8"))
    failures = []
    for relative, expected in manifest["sha256"].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            failures.append(relative + ": missing or invalid path")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(relative + ": changed")
    return manifest, failures


def main():
    root = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    )
    try:
        manifest, failures = verify(root)
    except (OSError, ValueError, KeyError) as exc:
        print(f"Cannot verify release: {exc}", file=sys.stderr)
        return 1
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        f"StatBridge {manifest['version']}: {len(manifest['sha256'])} packaged files verified."
    )
    print("Integrity check only; this is not a publisher signature.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
