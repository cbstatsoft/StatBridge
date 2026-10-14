# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import time
import pandas as pd
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from statbridge.format_dialog import FormatDialog


def test_import_controls_and_async_preview(tmp_path):
    app = QApplication.instance() or QApplication([])
    pd.DataFrame({"id": [1, 2], "score": [3.0, 4.0]}).to_parquet(
        tmp_path / "data.parquet"
    )
    dialog = FormatDialog(tmp_path, path=str(tmp_path / "data.parquet"))
    dialog.show()
    assert dialog.effective_kind() == "parquet"
    assert not dialog.selector.isEnabled()
    assert "clear" in dialog.command()
    dialog.preview()
    deadline = time.monotonic() + 15
    while dialog.worker is not None and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert dialog.worker is None
    assert dialog.table.rowCount() == 2 and dialog.table.columnCount() == 2
    dialog.close()


def test_export_variable_selection_compression_and_excel(tmp_path):
    app = QApplication.instance() or QApplication([])
    dialog = FormatDialog(tmp_path, columns=["id", "score"], exporting=True)
    dialog.kind.setCurrentIndex(dialog.kind.findData("parquet"))
    dialog.path.setText(str(tmp_path / "subset.parquet"))
    dialog.variables.item(1).setSelected(True)
    dialog.compression.setCurrentText("zstd")
    assert "export parquet score using" in dialog.command()
    assert "compression(zstd)" in dialog.command()
    dialog.kind.setCurrentIndex(dialog.kind.findData("workbook"))
    dialog.path.setText(str(tmp_path / "subset.xlsx"))
    assert "export excel score using" in dialog.command()
    assert "firstrow(variables)" in dialog.command()
    dialog.close()
