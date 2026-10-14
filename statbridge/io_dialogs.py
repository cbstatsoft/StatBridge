# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Real import controls with a reviewable command preview."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QCheckBox,
    QPlainTextEdit,
    QDialogButtonBox,
)


class ExcelImportDialog(QDialog):
    def __init__(self, path, sheets, parent=None):
        super().__init__(parent)
        self.path = path
        self.setWindowTitle("Import Excel")
        self.resize(550, 300)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.sheet = QComboBox()
        self.sheet.addItems(sheets)
        form.addRow("Worksheet", self.sheet)
        self.cells = QLineEdit()
        self.cells.setPlaceholderText("Optional: A1 or A1:D200")
        form.addRow("Cell range", self.cells)
        self.headers = QCheckBox("First row contains variable names")
        self.headers.setChecked(True)
        form.addRow(self.headers)
        self.strings = QCheckBox("Import all cells as strings")
        form.addRow(self.strings)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName("Import command preview")
        layout.addWidget(self.preview)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for signal in (
            self.sheet.currentTextChanged,
            self.cells.textChanged,
            self.headers.toggled,
            self.strings.toggled,
        ):
            signal.connect(self.update_preview)
        self.update_preview()

    def command(self):
        if '"' in self.path or '"' in self.sheet.currentText():
            raise ValueError(
                "Double quotes in paths or worksheet names are unsupported"
            )
        result = (
            f'import excel "{self.path}", sheet("{self.sheet.currentText()}") clear'
        )
        if self.cells.text().strip():
            result += " cellrange(" + self.cells.text().strip() + ")"
        if self.headers.isChecked():
            result += " firstrow"
        if self.strings.isChecked():
            result += " allstring"
        return result

    def update_preview(self, *_):
        try:
            self.preview.setPlainText(self.command())
        except ValueError as error:
            self.preview.setPlainText(str(error))
