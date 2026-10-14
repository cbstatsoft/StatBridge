# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Release checks cover real user failures and installed legal resources."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(ROOT / "launch.py"), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_licence_offline_without_dependencies(tmp_path):
    result = subprocess.run(
        [sys.executable, "-S", str(ROOT / "launch.py"), "--license"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    for text in (
        "Connor Baird",
        "ABSOLUTELY NO WARRANTY",
        "GNU GENERAL PUBLIC LICENSE",
        "Douglas M. Bates",
        "not affiliated",
        "Roche/pyreadstat",
    ):
        assert text in result.stdout


def test_diagnostics_report_missing_packages_without_importing_them(tmp_path):
    result = subprocess.run(
        [sys.executable, "-S", str(ROOT / "launch.py"), "--doctor", "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    assert result.returncode == 1
    assert "PySide6" in data["missing_required"]
    assert str(tmp_path) not in result.stdout
    assert str(Path.home()) not in result.stdout
    assert set(data) == {
        "application",
        "version",
        "channel",
        "python",
        "system",
        "architecture",
        "python_supported",
        "packages",
        "missing_required",
        "ok",
        "scope",
    }


def test_diagnostics_does_not_load_qt_or_engine():
    code = "from statbridge.diagnostics import report; import sys; report(); assert 'PySide6' not in sys.modules; assert 'statbridge.engine' not in sys.modules"
    p = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True
    )
    assert p.returncode == 0, p.stderr


@pytest.mark.parametrize(
    "args", [("--json",), ("--doctor", "--cwd", "."), ("--license", "--audit", "x")]
)
def test_invalid_cli_combinations(args):
    p = cli(*args)
    assert p.returncode == 2 and "Traceback" not in p.stderr


def test_batch_errors_and_input_preservation(tmp_path):
    script = tmp_path / "input.do"
    source = 'display "completed"\n'
    script.write_text(source)
    result = cli("--batch", str(script), "--audit", str(script))
    assert result.returncode == 2 and script.read_text() == source
    result = cli(
        "--batch", str(script), "--audit", str(tmp_path / "absent" / "audit.json")
    )
    assert result.returncode == 1 and "Cannot write audit" in result.stderr
    assert "Traceback" not in result.stderr
    result = cli("--batch", str(tmp_path / "absent.do"))
    assert result.returncode == 1 and "Cannot read do-file" in result.stderr
    result = cli("--batch", str(script), "--cwd", str(tmp_path / "missing"))
    assert result.returncode == 2 and "--cwd" in result.stderr


def test_batch_cli_paths_and_session_cwd(tmp_path):
    folder = tmp_path / "folder with spaces"
    folder.mkdir()
    (tmp_path / "test.do").write_text('pwd\ndisplay "finished"\n')
    result = cli(
        "--batch",
        "test.do",
        "--cwd",
        str(folder),
        "--audit",
        "audit.json",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert str(folder) in result.stdout
    assert (tmp_path / "audit.json").is_file()


def test_installer_rejects_unsupported_python_before_mutating(monkeypatch):
    installer = module_at("installer", ROOT / "install.py")
    monkeypatch.setattr(installer.sys, "version_info", (3, 10))
    monkeypatch.setattr(
        installer.venv,
        "EnvBuilder",
        lambda **kwargs: pytest.fail("Must not create environment"),
    )
    assert installer.main() == 2


def test_release_verifier_detects_changed_and_missing_files(tmp_path):
    verifier = module_at("verifier", ROOT / "tools/verify_release.py")
    file = tmp_path / "example.py"
    file.write_bytes(b"original")
    (tmp_path / "RELEASE.json").write_text(
        json.dumps(
            {
                "version": "test",
                "sha256": {"example.py": hashlib.sha256(b"original").hexdigest()},
            }
        )
    )
    assert verifier.verify(tmp_path)[1] == []
    file.write_bytes(b"changed")
    assert verifier.verify(tmp_path)[1] == ["example.py: changed"]
    file.unlink()
    assert "missing" in verifier.verify(tmp_path)[1][0]


def test_builder_rejects_mixed_versions(tmp_path):
    builder = module_at("builder", ROOT / "tools/build_release.py")
    assert builder.check_versions(ROOT) == "0.7.1"
    (tmp_path / "statbridge").mkdir()
    for relative in ("pyproject.toml", "launch.py", "statbridge/__init__.py"):
        (tmp_path / relative).write_bytes((ROOT / relative).read_bytes())
    (tmp_path / "launch.py").write_text('RELEASE_VERSION = "0.2.0"')
    with pytest.raises(ValueError, match="Launcher"):
        builder.check_versions(tmp_path)


def test_licence_command_and_support_dialogs(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QSettings
    from statbridge.ui import MainWindow

    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path)
    )
    window = MainWindow()
    shown = []
    monkeypatch.setattr(
        window, "show_text_dialog", lambda title, text: shown.append((title, text))
    )
    window.show_licence()
    window.show_diagnostics()
    assert "GNU GENERAL PUBLIC LICENSE" in shown[0][1]
    assert "No data, history" in shown[1][1]
    assert window.engine.run("license")
    assert not window.engine.run("license invalid")
    window.close()
    app.processEvents()
