# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for Linux XDG application integration; no desktop session required."""
from pathlib import Path
import tempfile
import unittest
import sys

from tools.linux_shortcut import (
    DESKTOP_FILENAME, desktop_path, install_shortcut, render_desktop_entry,
    uninstall_shortcut,
)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux desktop entry tests")
class LinuxShortcutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "StatBridge source with spaces"
        for path in (
            self.root / ".venv" / "bin" / "python",
            self.root / "launch.py",
            self.root / "statbridge" / "assets" / "statbridge.svg",
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder", encoding="utf-8")
        self.home = self.base / "xdg-data"

    def test_register_repeat_and_uninstall(self):
        dest = install_shortcut(root=self.root, data_home=self.home)
        self.assertEqual(dest, self.home / "applications" / DESKTOP_FILENAME)
        self.assertEqual(dest, desktop_path(self.home))
        entry = dest.read_text(encoding="utf-8")
        self.assertIn('Exec="' + str(self.root / ".venv/bin/python") + '"', entry)
        self.assertIn(' "' + str(self.root / "launch.py") + '"', entry)
        self.assertIn("TryExec=" + str(self.root / ".venv/bin/python"), entry)
        self.assertIn("Icon=" + str(self.root / "statbridge/assets/statbridge.svg"), entry)
        self.assertIn("Terminal=false", entry)
        self.assertIn("Categories=Education;Science;Math;", entry)
        self.assertEqual(install_shortcut(root=self.root, data_home=self.home), dest)
        self.assertTrue(uninstall_shortcut(data_home=self.home))
        self.assertFalse(uninstall_shortcut(data_home=self.home))

    def test_does_not_overwrite_or_delete_unmanaged_shortcut(self):
        dest = desktop_path(self.home)
        dest.parent.mkdir(parents=True)
        dest.write_text("[Desktop Entry]\nName=Another project\n", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            install_shortcut(root=self.root, data_home=self.home)
        with self.assertRaises(ValueError):
            uninstall_shortcut(data_home=self.home)
        self.assertIn("Another project", dest.read_text(encoding="utf-8"))

    def test_missing_environment_does_not_register(self):
        (self.root / ".venv" / "bin" / "python").unlink()
        with self.assertRaises(FileNotFoundError):
            install_shortcut(root=self.root, data_home=self.home)
        self.assertFalse(desktop_path(self.home).exists())

    def test_exec_percent_and_shell_characters_are_escaped(self):
        special_root = self.base / 'a $ dollar % percent "quote"'
        for component in (".venv/bin/python", "launch.py", "statbridge/assets/statbridge.svg"):
            path = special_root / component
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        entry = render_desktop_entry(special_root)
        exec_line = next(line for line in entry.splitlines() if line.startswith("Exec="))
        self.assertIn("%%", exec_line)
        self.assertIn(r"\\$", exec_line)
        self.assertIn(r'\\"', exec_line)

    def test_rejects_control_characters(self):
        broken_root = self.base / "line\nbreak"
        with self.assertRaises(ValueError):
            render_desktop_entry(broken_root)


if __name__ == "__main__":
    unittest.main()
