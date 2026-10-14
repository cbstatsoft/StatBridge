# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run after installing the wheel, from any unrelated working directory."""

from pathlib import Path
import sys
import tempfile

import statbridge
from statbridge.engine import Engine
from statbridge.learning import LESSONS, check_lesson
from statbridge.legal import license_text


def main():
    source = Path(__file__).resolve().parents[1]
    if len(sys.argv) > 1 and not Path(statbridge.__file__).resolve().is_relative_to(
        Path(sys.argv[1]).resolve()
    ):
        raise RuntimeError("The requested wheel installation was not loaded")
    if Path(statbridge.__file__).resolve().is_relative_to(source):
        raise RuntimeError(
            "This check requires an installed wheel outside the source tree"
        )
    assert "Copyright (C) 2026 Connor Baird" in license_text()
    with tempfile.TemporaryDirectory(prefix="statbridge-smoke-") as temp:
        for lesson in LESSONS:
            cwd = Path(temp) / lesson.key
            cwd.mkdir()
            engine = Engine(cwd=cwd)
            try:
                assert engine.run(lesson.script), (lesson.key, engine.events)
                assert engine.run(lesson.solution), (lesson.key, engine.events)
                assert check_lesson(engine, lesson)[0], lesson.key
            finally:
                engine.close()
        for name in ("demo.do", "everyday_coverage.do", "file_formats.do"):
            cwd = Path(temp) / name
            cwd.mkdir()
            engine = Engine(cwd=cwd)
            try:
                assert engine.run(
                    (source / "examples" / name).read_text()
                ), engine.events
            finally:
                engine.close()
    print(
        f"Installed StatBridge {statbridge.__version__}: {len(LESSONS)} lessons and 3 example do-files passed."
    )


if __name__ == "__main__":
    main()
