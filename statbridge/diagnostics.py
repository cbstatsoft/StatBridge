# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Local metadata check without loading Qt, datasets or statistical packages."""

import importlib.metadata as metadata
import platform
import sys

DEPENDENCIES = (
    "numpy",
    "pandas",
    "polars",
    "pyarrow",
    "scipy",
    "statsmodels",
    "linearmodels",
    "pyreadstat",
    "pyreadr",
    "PySide6",
    "matplotlib",
    "openpyxl",
    "xlrd",
    "python-calamine",
    "odfpy",
    "h5py",
    "psutil",
    "jinja2",
)


def report():
    from . import __version__

    packages = {}
    for name in DEPENDENCIES + (("windows-curses",) if sys.platform == "win32" else ()):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    missing = [name for name in DEPENDENCIES if packages[name] is None]
    supported = (3, 11) <= sys.version_info[:2] < (3, 14)
    return {
        "application": "StatBridge Qt",
        "version": __version__,
        "channel": "public beta",
        "python": platform.python_version(),
        "system": platform.system(),
        "architecture": platform.machine(),
        "python_supported": supported,
        "packages": packages,
        "missing_required": missing,
        "ok": supported and not missing,
        "scope": "Metadata check only; does not test native libraries or a display.",
    }


def format_report(data):
    lines = [
        f"{data['application']} {data['version']} ({data['channel']})",
        f"Python {data['python']} | {data['system']} | {data['architecture']}",
    ]
    lines += [
        f"{name}: {version or 'NOT INSTALLED'}"
        for name, version in data["packages"].items()
    ]
    if not data["python_supported"]:
        lines.append("Use Python 3.11, 3.12 or 3.13 for this beta.")
    if data["missing_required"]:
        lines.append("Install missing dependencies using the bundled installer.")
    lines += [
        data["scope"],
        "No data, history, personal paths or network requests included.",
    ]
    return "\n".join(lines)
