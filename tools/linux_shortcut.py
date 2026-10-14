# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install or remove StatBridge's per-user Linux application-menu shortcut.

Uses the freedesktop Desktop Entry Specification and XDG_DATA_HOME. No root,
system-wide package installation, or external Python dependencies are required.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

DESKTOP_ID = "io.github.cbstatsoft.StatBridge"
DESKTOP_FILENAME = DESKTOP_ID + ".desktop"
MANAGED_MARKER = "X-StatBridge-Managed=true"


def _data_home() -> Path:
    configured = os.environ.get("XDG_DATA_HOME", "")
    if configured and Path(configured).is_absolute():
        return Path(configured)
    return Path.home() / ".local" / "share"


def desktop_path(data_home: Path | None = None) -> Path:
    return (data_home if data_home is not None else _data_home()) / "applications" / DESKTOP_FILENAME


def _check_text(value: str) -> str:
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("Control characters in a file path cannot be used in a desktop entry")
    return value


def _desktop_string(value: str) -> str:
    """Escape the Desktop Entry string value layer."""
    return _check_text(value).replace("\\", "\\\\")


def _exec_argument(value: str) -> str:
    """Quote a single Exec argument through command and desktop-file escaping."""
    value = _check_text(value)
    value = (value.replace("\\", "\\\\")
                  .replace('"', '\\"')
                  .replace(chr(96), "\\" + chr(96))
                  .replace("$", "\\$")
                  .replace("%", "%%"))
    return '"' + value.replace("\\", "\\\\") + '"'


def render_desktop_entry(root: Path) -> str:
    root = root.resolve()
    python = root / ".venv" / "bin" / "python"
    launcher = root / "launch.py"
    icon = root / "statbridge" / "assets" / "statbridge.svg"
    for required in (python, launcher, icon):
        if not required.is_file():
            raise FileNotFoundError(
                f"Cannot install StatBridge shortcut; missing {required}. "
                "Install with ./install-and-run.sh first."
            )
    return "\n".join((
        "[Desktop Entry]",
        "Version=1.0",
        "Type=Application",
        "Name=StatBridge",
        "GenericName=Statistical Analysis",
        "Comment=Statistical analysis with a Stata-inspired Python workspace",
        "Exec=" + _exec_argument(str(python)) + " " + _exec_argument(str(launcher)),
        "TryExec=" + _desktop_string(str(python)),
        "Path=" + _desktop_string(str(root)),
        "Icon=" + _desktop_string(str(icon)),
        "Terminal=false",
        "StartupNotify=true",
        "Categories=Education;Science;Math;",
        "Keywords=statistics;econometrics;Stata;data;analysis;Python;",
        MANAGED_MARKER,
        "",
    ))


def _managed(path: Path) -> bool:
    return path.is_file() and MANAGED_MARKER in path.read_text(encoding="utf-8").splitlines()


def install_shortcut(root: Path | None = None, data_home: Path | None = None) -> Path:
    """Atomically register the current checkout in the user's application menu."""
    root = (root or Path(__file__).resolve().parents[1]).resolve()
    destination = desktop_path(data_home)
    content = render_desktop_entry(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not _managed(destination):
        raise FileExistsError(f"Refusing to overwrite an unmanaged shortcut: {destination}")
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=".statbridge-", suffix=".desktop", delete=False
        ) as stream:
            temp_name = stream.name
            stream.write(content)
        os.chmod(temp_name, 0o644)
        os.replace(temp_name, destination)
    finally:
        if temp_name is not None and os.path.exists(temp_name):
            os.unlink(temp_name)
    return destination


def uninstall_shortcut(data_home: Path | None = None) -> bool:
    """Remove only an application shortcut created by this tool."""
    path = desktop_path(data_home)
    if not path.exists():
        return False
    if not _managed(path):
        raise ValueError(f"Refusing to remove an unmanaged shortcut: {path}")
    path.unlink()
    return True


def main(argv: list[str] | None = None) -> int:
    if not sys.platform.startswith("linux"):
        print("Linux desktop shortcuts are supported on Linux only.", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description="Manage the per-user StatBridge launcher")
    parser.add_argument("action", choices=("install", "uninstall", "status"))
    args = parser.parse_args(argv)
    try:
        if args.action == "install":
            path = install_shortcut()
            print(f"StatBridge application shortcut installed: {path}")
            print("Open StatBridge from the application menu, or use Rofi: rofi -show drun")
        elif args.action == "uninstall":
            print("StatBridge shortcut removed." if uninstall_shortcut()
                  else "StatBridge shortcut was not installed.")
        else:
            path = desktop_path()
            print(f"Installed: {path}" if _managed(path)
                  else "No managed StatBridge shortcut is installed.")
        return 0
    except (OSError, ValueError) as error:
        print(f"StatBridge shortcut: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
