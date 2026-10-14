#!/usr/bin/env python3
# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Launch this extracted release, even when an older installation is on sys.path."""
from pathlib import Path
import sys

RELEASE_VERSION = "0.7.1"


def main():
    root = Path(__file__).resolve().parent
    package = root / "statbridge"
    if not all((package / name).is_file() for name in ("__init__.py", "__main__.py", "ui.py")):
        print("The bundled StatBridge files are missing. Extract the complete ZIP and run its launcher.", file=sys.stderr)
        return 2
    sys.path.insert(0, str(root))
    import statbridge

    if Path(statbridge.__file__).resolve().parent != package or statbridge.__version__ != RELEASE_VERSION:
        print(f"Release mismatch: expected bundled StatBridge {RELEASE_VERSION}, found {statbridge.__version__} at {statbridge.__file__}. Extract the complete release into a new folder.", file=sys.stderr)
        return 2
    from statbridge.__main__ import main as application

    return application()


if __name__ == "__main__":
    raise SystemExit(main())
