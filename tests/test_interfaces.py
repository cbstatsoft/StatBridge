# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
import subprocess
import sys
import time
import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from statbridge.engine import Engine
from statbridge.analysis_ui import AnalysisDialog
from statbridge.terminal import TerminalSession, safe_text, cell_slice


@pytest.fixture
def engine(tmp_path):
    e = Engine(cwd=tmp_path)
    rng = np.random.default_rng(9)
    n = 120
    x, z, noise = rng.normal(size=(3, n))
    endog = z + noise
    e.df = pd.DataFrame(
        {
            "y": 2 + x + endog + rng.normal(size=n),
            "x": x,
            "z": z,
            "endog": endog,
            "binary": (x + noise > 0).astype(int),
            "id": np.repeat(np.arange(20), 6),
            "year": np.tile(np.arange(6), 20),
            "text": ["label"] * n,
            "sequence":np.arange(n),
            "duration":rng.exponential(2,size=n),
        }
    )
    yield e
    e.close()


@pytest.fixture
def app(tmp_path):
    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path)
    )
    return app


def choose(widget, *names):
    for i in range(widget.count()):
        widget.item(i).setCheckState(
            Qt.CheckState.Checked
            if widget.item(i).text() in names
            else Qt.CheckState.Unchecked
        )


@pytest.mark.parametrize("kind", list(AnalysisDialog.TITLES))
def test_analysis_forms_execute_real_engine(app, engine, kind):
    d = AnalysisDialog(engine, kind)
    assert not d.run_button.isEnabled()
    assert "text" not in d.numeric
    d.outcome.setCurrentText("binary" if kind in ("logit","mlogit","ologit","oprobit") else "duration" if kind=="stcox" else "y")
    choose(d.predictors, "x")
    if kind == "xtreg":
        d.panel.setCurrentText("id")
        d.time.setCurrentText("year")
    if kind=="newey":d.time.setCurrentText("sequence")
    if kind=="stcox":d.failure.setCurrentText("binary")
    if kind=="svymean":d.psu.setCurrentText("id")
    if kind == "ivregress":
        choose(d.endogenous, "endog")
        choose(d.instruments, "z")
    assert d.run_button.isEnabled(), d.validation.text()
    source = d.source
    assert engine.run(source), [e for e in engine.events if e["kind"] == "error"]
    assert engine.figure is not None if kind == "histogram" else engine.model is not None
    d.close()


def test_dialog_validation_and_cancel_do_not_mutate(app, engine):
    before = engine.df.copy(deep=True)
    rng = json.dumps(engine.rng.bit_generator.state)
    d = AnalysisDialog(engine, "regress")
    d.outcome.setCurrentText("y")
    choose(d.predictors, "y")
    assert not d.run_button.isEnabled()
    choose(d.predictors, "x")
    d.condition.setText("nonexistent > 0")
    assert not d.run_button.isEnabled()
    d.condition.setText("runiform() > .5")
    assert not d.run_button.isEnabled()
    d.condition.setText("x > 0")
    assert d.run_button.isEnabled()
    d.covariance.setCurrentText("Clustered")
    assert not d.run_button.isEnabled()
    d.cluster.setCurrentText("id")
    assert "vce(cluster id)" in d.source
    d.reject()
    pd.testing.assert_frame_equal(before, engine.df)
    assert json.dumps(engine.rng.bit_generator.state) == rng
    assert not engine.history


def test_gui_action_runs_dialog_and_toolbar_busy_states(app, engine, monkeypatch):
    from statbridge.ui import MainWindow

    w = MainWindow()
    w.engine.df = engine.df.copy()
    w.show()

    def accept(dialog):
        dialog.outcome.setCurrentText("y")
        choose(dialog.predictors, "x")
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(AnalysisDialog, "exec", accept)
    w.analysis_actions["regress"].trigger()
    assert w.worker is not None
    assert w.stop_action.isEnabled()
    assert not w.analysis_button.isEnabled()
    deadline = time.monotonic() + 10
    while w.worker and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert w.worker is None
    assert w.engine.model is not None
    assert "regress y x" in w.engine.history
    assert not w.stop_action.isEnabled()
    assert w.analysis_button.isEnabled()
    w.command.setFocus()
    QTest.keyClick(w.command, Qt.Key.Key_F6)
    assert w.results.hasFocus()
    QTest.keyClick(w.results, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)
    assert w.command.hasFocus()
    w.engine.dirty = False
    w.close()


def wait_session(s):
    deadline = time.monotonic() + 10
    while s.busy and time.monotonic() < deadline:
        s.drain()
        time.sleep(0.01)
    assert not s.busy


def test_terminal_execution_completion_history_and_dta(tmp_path):
    s = TerminalSession(cwd=tmp_path, settings_path=tmp_path / "settings.json")
    s.submit(
        'set obs 20\ngen income = _n\ngen wage = 2+3*income+sin(income)\nregress wage income\nsave "out.dta", replace'
    )
    wait_session(s)
    assert s.engine.model is not None
    assert (tmp_path / "out.dta").exists()
    assert any("Linear regression" in line for line, _ in s.lines)
    s.set_buffer("summarize inc")
    s.complete()
    assert s.buffer == "summarize income"
    s.set_buffer("regress wage inc if wage > 0", len("regress wage inc"))
    s.complete()
    assert s.buffer == "regress wage income if wage > 0"
    s.set_buffer("draft")
    s.recall(-1)
    assert "save" in s.buffer
    s.recall(1)
    assert s.buffer == "draft"
    s.close(tmp_path / "audit.json")
    report = json.loads((tmp_path / "audit.json").read_text())
    assert report["commands"]
    second = TerminalSession(settings_path=tmp_path / "settings.json")
    assert second.engine.cwd == tmp_path
    assert second.history == s.history
    second.local_command(":history off")
    assert "history" not in json.loads((tmp_path / "settings.json").read_text())
    second.local_command(":history clear")
    assert not second.history
    assert not second.suggestions.history
    second.close()


def test_terminal_do_error_then_recovery_and_no_persistence(tmp_path):
    do = tmp_path / "test.do"
    do.write_text("set obs 5\ngen x = _n\nassert x > 0\n")
    s = TerminalSession(
        cwd=tmp_path,
        settings_path=tmp_path / "prefs.json",
        no_history=True,
        no_cwd=True,
    )
    s.submit('do "test.do"')
    wait_session(s)
    assert len(s.engine.df) == 5
    s.submit("unknown_command")
    wait_session(s)
    assert any(kind == "error" for _, kind in s.lines)
    s.submit("summarize x")
    wait_session(s)
    assert s.engine.r["N"] == 5
    s.close()
    prefs = json.loads((tmp_path / "prefs.json").read_text())
    assert "cwd" not in prefs and "history" not in prefs


def test_terminal_control_sequences_and_wide_text():
    assert "\x1b" not in safe_text("\x1b[31mdanger")
    assert cell_slice("工资 abc", 0, 4) == "工资"
    assert cell_slice("工资 abc", 4, 4) == " abc"


def test_terminal_cli_without_tty_does_not_import_qt():
    code = "from statbridge.__main__ import main; import sys; sys.argv=['statbridge','--terminal']; assert main()==2; assert not any(x.startswith('PySide6') for x in sys.modules)"
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "interactive terminal" in proc.stderr
