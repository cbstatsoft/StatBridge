# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import time
import pytest
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from statbridge.ui import MainWindow, CommandLine


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path_factory.mktemp("settings")),
    )
    return app


def finish(app, window):
    deadline = time.monotonic() + 15
    while window.worker is not None and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert window.worker is None, "Worker did not finish"
    app.processEvents()


def test_completion_right_arrow_history_and_tab(app):
    line = CommandLine()
    line.show()
    line.setFocus()
    line.suggestions.history = ["regress y x, robust"]
    line.suggestions.variables = ["income"]
    line.setText("reg")
    QTest.keyClick(line, Qt.Key.Key_Right)
    assert line.text() == "regress y x, robust"
    line.clear()
    QTest.keyClick(line, Qt.Key.Key_Up)
    assert line.text() == "regress y x, robust"
    QTest.keyClick(line, Qt.Key.Key_Down)
    assert line.text() == ""
    line.setText("summarize inc")
    QTest.keyClick(line, Qt.Key.Key_Tab)
    assert line.text() == "summarize income"
    line.close()


def test_worker_editor_data_edit_and_graph(app):
    w = MainWindow()
    w.show()
    w.editor.setPlainText(
        "clear\nset obs 20\ngenerate x = _n\ngenerate y = 3+2*x+sin(x)\nregress y x, robust\nscatter y x"
    )
    w.run_editor()
    finish(app, w)
    assert len(w.engine.df) == 20
    assert w.engine.model is not None
    assert "Linear regression" in w.results.toPlainText()
    assert "Observations" in w.results.toPlainText()
    assert w.tabs.currentIndex() == 3
    w.data_model.setData(w.data_model.index(0, 0), "42")
    finish(app, w)
    assert w.engine.df.x.iloc[0] == 42
    assert w.data_model.rowCount() == 20
    assert w.command.isEnabled()
    assert not w.stop_button.isEnabled()
    assert w.engine.notices
    w.engine.dirty = False
    w.editor.document().setModified(False)
    w.close()


def test_learning_mode_is_optional_and_opening_lesson_preserves_data(app):
    import pandas as pd
    from statbridge.learning import LESSONS

    w = MainWindow()
    w.show()
    w.learning_dock.hide()
    w.engine.df = pd.DataFrame({"my_data": [1.0, 2.0]})
    before = w.engine.df.copy()
    w.learning_action.trigger()
    app.processEvents()
    assert w.learning_dock.isVisible()
    w.open_learning_example(LESSONS[0].script)
    pd.testing.assert_frame_equal(before, w.engine.df)
    assert "StatBridge lesson: summaries" in w.editor.toPlainText()
    assert w.editor.document().isModified()
    w.run_editor()
    finish(app, w)
    w.start(LESSONS[0].solution)
    finish(app, w)
    w.learning.check()
    assert "matches the exercise check" in w.learning.feedback.text()
    original = w.engine.df.copy()
    model = w.engine.model
    w.learning_action.trigger()
    app.processEvents()
    pd.testing.assert_frame_equal(original, w.engine.df)
    assert model is w.engine.model
    w.engine.dirty = False
    w.editor.document().setModified(False)
    w.close()


def test_tab_completes_in_full_window_without_moving_focus(app):
    w = MainWindow()
    w.show()
    w.activateWindow()
    w.command.suggestions.history = []
    w.command.suggestions.variables = ["income"]
    w.command.setText("summarize inc")
    w.command.setFocus()
    app.processEvents()
    QTest.keyClick(w.command, Qt.Key.Key_Tab)
    assert w.command.text() == "summarize income"
    assert w.command.hasFocus()
    assert w.worker is None
    w.engine.dirty = False
    w.editor.document().setModified(False)
    w.close()


def test_tab_extends_common_prefix_then_selects_popup_completion(app):
    line = CommandLine()
    line.show()
    line.activateWindow()
    line.setFocus()
    line.suggestions.variables = ["income", "income_tax"]
    line.setText("summarize inc")
    QTest.keyClick(line, Qt.Key.Key_Tab)
    assert line.text() == "summarize income"
    line.suggestions.variables = ["income_net", "income_tax"]
    line.setText("summarize income_")
    QTest.keyClick(line, Qt.Key.Key_Tab)
    app.processEvents()
    assert line.completer.popup().isVisible()
    # Simulate a keyboard selection, then accept it using Tab on the popup.
    popup = line.completer.popup()
    popup.setCurrentIndex(line.completer.completionModel().index(1, 0))
    QTest.keyClick(popup, Qt.Key.Key_Tab)
    assert line.text() == "summarize income_tax"
    assert not popup.isVisible()
    line.close()


def test_tab_no_match_keeps_command_focus(app):
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton

    host = QWidget()
    layout = QVBoxLayout(host)
    line = CommandLine()
    layout.addWidget(line)
    layout.addWidget(QPushButton("Next control"))
    host.show()
    host.activateWindow()
    line.setFocus()
    line.setText("nonexistent_command")
    app.processEvents()
    QTest.keyClick(line, Qt.Key.Key_Tab)
    assert line.text() == "nonexistent_command"
    assert line.hasFocus()
    host.close()


def test_tab_on_command_accepts_visible_popup_without_execution(app):
    line = CommandLine()
    line.show()
    line.suggestions.variables = ["price", "profit"]
    line.setText("summarize pr")
    executed = []
    line.returnPressed.connect(lambda: executed.append(True))
    QTest.keyClick(line, Qt.Key.Key_Tab)
    app.processEvents()
    assert line.completer.popup().isVisible()
    QTest.keyClick(line, Qt.Key.Key_Tab)
    assert line.text() == "summarize price"
    assert not executed
    line.close()


def test_context_completion_uses_live_variables_and_preserves_command_tail(app):
    import pandas as pd

    w = MainWindow()
    w.show()
    w.engine.df = pd.DataFrame(
        {"income": [1.0, 2.0], "age": [3.0, 4.0], "name": ["a", "b"]}
    )
    w.refresh()
    w.command.suggestions.history = []
    w.command.setText("regress inc age, vce(robust)")
    w.command.setCursorPosition(len("regress inc"))
    QTest.keyClick(w.command, Qt.Key.Key_Tab)
    assert w.command.text() == "regress income age, vce(robust)"
    assert w.command.cursorPosition() == len("regress income")
    assert not w.command.suggestions.candidates("regress income na")
    w.command.setText("encode na")
    QTest.keyClick(w.command, Qt.Key.Key_Tab)
    assert w.command.text() == "encode name"
    assert w.engine.execute("rename income wage")
    w.refresh()
    assert not w.command.suggestions.candidates("summarize inc")
    assert "summarize wage" in w.command.suggestions.candidates("summarize wa")
    w.engine.dirty = False
    w.editor.document().setModified(False)
    w.close()


def test_context_popup_preserves_tail_and_closes_when_input_changes(app):
    line = CommandLine()
    line.show()
    line.suggestions.variables = ["income_net", "income_tax", "age"]
    line.setText("regress income_ age")
    line.setCursorPosition(len("regress income_"))
    QTest.keyClick(line, Qt.Key.Key_Tab)
    app.processEvents()
    assert line.completer.popup().isVisible()
    popup = line.completer.popup()
    popup.setCurrentIndex(line.completer.completionModel().index(1, 0))
    QTest.keyClick(popup, Qt.Key.Key_Tab)
    assert line.text() == "regress income_tax age"
    assert line.cursorPosition() == len("regress income_tax")
    line.setText("regress income_")
    QTest.keyClick(line, Qt.Key.Key_Tab)
    assert line.completer.popup().isVisible()
    line.setText("regress age")
    assert not line.completer.popup().isVisible()
    line.close()


def test_context_popup_keyboard_navigation_accepts_without_execution(app):
    line = CommandLine()
    line.show()
    line.activateWindow()
    line.setFocus()
    line.suggestions.variables = ["income_net", "income_tax"]
    line.setText("summarize income_")
    executed = []
    line.returnPressed.connect(lambda: executed.append(True))
    QTest.keyClick(line, Qt.Key.Key_Tab)
    popup = line.completer.popup()
    assert popup.isVisible()
    QTest.keyClick(popup, Qt.Key.Key_Down)
    QTest.keyClick(popup, Qt.Key.Key_Return)
    assert line.text() == "summarize income_tax"
    assert not executed
    assert not popup.isVisible()
    QTest.keyClick(line, Qt.Key.Key_Return)
    assert executed == [True]
    line.close()


def test_working_folder_actions_and_path_completion(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    folder = tmp_path / "Test Pack"
    folder.mkdir()
    script = folder / "test_analysis.do"
    script.write_text('display "loaded"')
    w = MainWindow()
    w.show()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(folder))
    w.choose_working_folder()
    finish(app, w)
    assert w.engine.cwd == folder
    assert w.command.suggestions.candidates("do test") == ['do "test_analysis.do"']
    w.command.setText("do test")
    QTest.keyClick(w.command, Qt.Key.Key_Tab)
    assert w.command.text() == 'do "test_analysis.do"'
    w.engine.cwd = tmp_path
    w.do_path = script
    w.use_do_folder()
    finish(app, w)
    assert w.engine.cwd == folder
    w.engine.dirty = False
    w.editor.document().setModified(False)
    w.close()


def test_rich_results_theme_switch_export_and_persistence(app, tmp_path, monkeypatch):
    from PySide6.QtGui import QTextTable, QTextCursor
    from PySide6.QtWidgets import QFileDialog
    from statbridge.themes import DARK

    w = MainWindow()
    w.settings.clear()
    w.dark_action.setChecked(False)
    w.show()
    w.start("clear\nset obs 30\ngen x = _n\ngen y = 2+3*x+sin(x)\nregress y x, robust")
    finish(app, w)
    tables = [
        f
        for f in w.results.document().rootFrame().childFrames()
        if isinstance(f, QTextTable)
    ]
    assert len(tables) == 2
    coefficient_table = tables[-1]
    assert coefficient_table.columns() == 7
    assert coefficient_table.rows() == 4  # two headers and two coefficients
    assert coefficient_table.cellAt(0, 5).columnSpan() == 2
    plain = "".join(w.results_plain)
    visible = w.results.toPlainText()
    model = w.engine.model
    covariance = model.cov.copy()
    original_records = len(w.results_records)
    w.dark_action.trigger()
    app.processEvents()
    assert w.dark_mode
    assert w.settings.value("dark_mode", type=bool)
    assert w.results.toPlainText() == visible
    assert "".join(w.results_plain) == plain
    assert len(w.results_records) == original_records
    tables = w.results.document().rootFrame().childFrames()
    assert (
        tables[-1].cellAt(0, 0).format().background().color().name() == DARK["header"]
    )
    assert (
        w.command.completer.popup().palette().base().color().name() == DARK["surface"]
    )
    assert w.highlighter.keyword.foreground().color().name() == DARK["accent"]
    assert w.engine.model is model
    assert model.cov.equals(covariance)
    end = QTextCursor(w.results.document())
    end.movePosition(QTextCursor.MoveOperation.End)
    assert end.currentTable() is None
    w.append_output(". summarize x", "command")
    assert (
        w.results.textCursor().charFormat().fontPointSize()
        == w.results.font().pointSize()
    )
    path = tmp_path / "results.txt"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **kw: (str(path), "")
    )
    w.save_results()
    assert path.read_text() == plain + ". summarize x\n"
    assert "<table" not in path.read_text()
    w.engine.dirty = False
    w.close()
    other = MainWindow()
    assert other.dark_mode
    assert other.dark_action.isChecked()
    other.dark_action.setChecked(False)
    other.close()


def test_clear_and_session_only_history_survive_refresh_and_restart(app):
    import json

    settings = QSettings("StatBridge", "StatBridge Qt")
    settings.clear()
    settings.setValue("history", json.dumps(["display 12", "display 13"]))
    w = MainWindow()
    w.show()
    assert w.review.count() == 2
    assert w.remember_history_box.isChecked()
    w.start("display 14")
    finish(app, w)
    w.command.setText("display ")
    QTest.keyClick(w.clear_history_button, Qt.Key.Key_Space)
    assert w.review.count() == 0
    assert w.command.suggestions.history == []
    assert not settings.contains("history")
    w.refresh()
    assert w.review.count() == 0
    assert w.command.ghost not in ("12", "13", "14")  # built-in suggestions still work
    w.start("display 15")
    finish(app, w)
    assert w.command.suggestions.history == ["display 15"]
    w.close()
    persisted = MainWindow()
    assert persisted.command.suggestions.history == ["display 15"]
    persisted.remember_history_box.setChecked(False)
    assert not persisted.remember_history_action.isChecked()
    assert not settings.contains("history")
    assert persisted.command.suggestions.history == ["display 15"]
    persisted.start("display 16")
    finish(app, persisted)
    assert persisted.command.suggestions.history == ["display 15", "display 16"]
    persisted.close()
    restarted = MainWindow()
    assert not restarted.remember_history_box.isChecked()
    assert restarted.command.suggestions.history == []
    assert restarted.review.count() == 0
    assert not settings.contains("history")
    restarted.close()
    settings.clear()


def test_theme_toolbar_icon_and_accessible_target_label(app):
    w = MainWindow()
    w.show()
    w.dark_action.setChecked(False)
    assert w.theme_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert not w.theme_button.icon().isNull()
    assert w.theme_button.width() == 36
    assert w.theme_button.accessibleName() == "Switch to dark mode"
    moon = w.theme_button.icon().cacheKey()
    QTest.mouseClick(w.theme_button, Qt.MouseButton.LeftButton)
    assert w.dark_mode
    assert w.theme_button.icon().cacheKey() != moon
    assert w.theme_button.accessibleName() == "Switch to light mode"
    assert w.theme_button.toolTip() == "Switch to light mode"
    w.dark_action.setChecked(False)
    w.close()


def test_optional_working_folder_persistence(app, tmp_path):
    from pathlib import Path

    settings = QSettings("StatBridge", "StatBridge Qt")
    settings.clear()
    settings.setValue("cwd", str(tmp_path))
    w = MainWindow()
    assert w.engine.cwd == tmp_path
    w.remember_cwd_action.setChecked(False)
    assert w.engine.cwd == tmp_path
    assert not settings.contains("cwd")
    w.close()
    fresh = MainWindow()
    assert not fresh.remember_cwd_action.isChecked()
    assert fresh.engine.cwd == Path.home()
    assert not settings.contains("cwd")
    fresh.engine.cwd = tmp_path
    fresh.remember_cwd_action.setChecked(True)
    fresh.close()
    restored = MainWindow()
    assert restored.engine.cwd == tmp_path
    assert restored.remember_cwd_action.isChecked()
    restored.close()
    settings.clear()


def test_learning_search_reference_and_busy_state(app):
    from statbridge.engine import Engine
    from statbridge.learning_ui import LearningPanel
    from statbridge.learning_reference import TEST_GUIDES
    widget = LearningPanel(Engine())
    widget.search.setText("hausman")
    assert widget.selector.count() >= 1
    assert any("Hausman" in widget.selector.itemText(i) for i in range(widget.selector.count()))
    widget.search.setText("no_such_lesson_999")
    assert widget.lesson is None and not widget.open_button.isEnabled()
    widget.check()
    widget.set_busy(True)
    widget.search.clear()
    assert widget.lesson is not None and not widget.check_button.isEnabled()
    widget.set_busy(False)
    assert widget.check_button.isEnabled()
    widget.category.setCurrentText("Tests and diagnostics")
    from statbridge.learning import LESSONS
    assert widget.selector.count() == sum(x.category=="Tests and diagnostics" for x in LESSONS)
    widget.test_selector.setCurrentIndex(next(i for i, x in enumerate(TEST_GUIDES) if x.key == "vif"))
    assert "no null hypothesis" in widget.reference.toPlainText()
    widget.close()


def test_date_display_table_clipboard_and_excel_form(app):
    import pandas as pd
    from statbridge.ui import FrameModel
    from statbridge.io_dialogs import ExcelImportDialog
    model=FrameModel();model.replace(pd.DataFrame({'day':[0.,-1.],'text':['a','b']}),{'day':'%td'})
    assert model.data(model.index(0,0))=='01jan1960'
    assert model.data(model.index(0,0),Qt.ItemDataRole.EditRole)=='0'
    assert model.data(model.index(0,1))=='a'
    dialog=ExcelImportDialog('book.xlsx',['One','Two']);dialog.sheet.setCurrentText('Two');dialog.cells.setText('B2:D10')
    assert 'sheet("Two")' in dialog.command() and 'cellrange(B2:D10)' in dialog.command()
    dialog.headers.setChecked(False);assert 'firstrow' not in dialog.command();dialog.close()
    w=MainWindow();w.engine.df=pd.DataFrame({'x':[1.,2.,3.]});assert w.engine.run('dtable x');w.refresh();w.copy_latest_table()
    assert 'Mean' in QApplication.clipboard().text() and w.export_table_action.isEnabled()
    assert w.engine.run('clear all');w.refresh();assert not w.export_table_action.isEnabled();w.close()
