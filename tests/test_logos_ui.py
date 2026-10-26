# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional Logos desktop and contextual completion smoke tests."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from statbridge.engine import Engine
from statbridge.ui import MainWindow
from statbridge.completion import Suggestions


def test_logos_completions_follow_selected_syntax():
    e = Engine()
    e.df["income"] = [10.0, 20.0]
    completion = Suggestions()
    completion.sync(e)
    assert any(c.startswith("regress") for c in completion.candidates("reg"))
    assert e.execute("syntax logos")
    completion.sync(e)
    assert "regress " in completion.candidates("reg")
    assert "regress income" in completion.candidates("regress inc")
    assert any(x.startswith("count rows") for x in completion.candidates("count"))
    assert e.execute("syntax stata")
    completion.sync(e)
    assert completion.syntax_mode == "stata"


def test_desktop_language_menu_and_persistent_preference(tmp_path):
    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope,
        str(tmp_path / "settings")
    )
    w = MainWindow(syntax="stata")
    assert w.engine.syntax_mode == "stata"
    assert w.stata_language_action.isChecked()
    w.logos_language_action.trigger()
    assert w.engine.syntax_mode == "logos"
    assert w.logos_language_action.isChecked()
    w.close()

    other = MainWindow()
    assert other.engine.syntax_mode == "logos"
    assert other.logos_language_action.isChecked()
    other.stata_language_action.trigger()
    assert other.engine.syntax_mode == "stata"
    other.close()
