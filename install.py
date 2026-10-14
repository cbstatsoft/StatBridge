# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Create a local environment and run this source release. Standard library only."""

import os
from pathlib import Path
import subprocess
import sys
import venv


def main():
    if not (3, 11) <= sys.version_info[:2] < (3, 14):
        print(
            "This beta supports Python 3.11 to 3.13; Python 3.12 is recommended.\n"
            "Windows: py -3.12 install.py\nmacOS/Linux: python3.12 install.py",
            file=sys.stderr,
        )
        return 2
    root = Path(__file__).resolve().parent
    executable = (
        root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    try:
        if not executable.is_file():
            print("Creating local Python environment...", flush=True)
            venv.EnvBuilder(with_pip=True).create(root / ".venv")
        result = subprocess.run(
            [
                str(executable),
                "-c",
                "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 2)",
            ],
            check=False,
        )
        if result.returncode:
            print(
                "Existing .venv uses an unsupported Python. Extract into a fresh folder and reinstall.",
                file=sys.stderr,
            )
            return 2
        extra = (
            ".[terminal]" if "--terminal" in sys.argv or "--tui" in sys.argv else "."
        )
        subprocess.run(
            [str(executable), "-m", "pip", "install", "-e", extra], cwd=root, check=True
        )
        return subprocess.run(
            [str(executable), str(root / "launch.py"), *sys.argv[1:]],
            cwd=root,
            check=False,
        ).returncode
    except (OSError, subprocess.CalledProcessError) as exc:
        print(
            f"Installation failed: {exc}\nCheck Python, your network and the package error above.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
