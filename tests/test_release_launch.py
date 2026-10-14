# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Prevent an extracted release from silently launching a different installation."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def test_launcher_prefers_bundled_release_with_old_pythonpath(tmp_path):
    old = tmp_path / "old" / "statbridge"
    old.mkdir(parents=True)
    (old / "__init__.py").write_text('__version__ = "0.2.0"\n')
    (old / "__main__.py").write_text('raise RuntimeError("OLD COPY RAN")\n')
    env = dict(os.environ, PYTHONPATH=str(old.parent), PYTHONSAFEPATH="1")
    result = subprocess.run([sys.executable, str(PROJECT / "launch.py"), "--version"], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "StatBridge Qt 0.7.1"


def test_launcher_rejects_incomplete_extraction(tmp_path):
    shutil.copy2(PROJECT / "launch.py", tmp_path / "launch.py")
    result = subprocess.run([sys.executable, str(tmp_path / "launch.py"), "--version"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 2
    assert "bundled StatBridge files are missing" in result.stderr
