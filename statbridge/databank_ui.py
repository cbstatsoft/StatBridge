# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Panel import controls and asynchronous, non-destructive preview."""

from pathlib import Path
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QWidget,
    QTabWidget,
    QListWidget,
    QPushButton,
    QFileDialog,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QLabel,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QDialogButtonBox,
    QHeaderView,
)
from .databank import LAYOUTS


def quoted(text):
    if any(x in text for x in ('"', "\n", "\r", "`", "$")):
        raise ValueError(
            "Paths and mappings containing quotes, newlines or macro markers are unsupported."
        )
    return '"' + text + '"'


class PreviewWorker(QThread):
    def __init__(self, command, cwd, parent=None):
        super().__init__(parent)
        from .engine import Engine

        self.engine = Engine(cwd=cwd)
        self.command = command
        self.result = None
        self.message = ""

    def run(self):
        try:
            self.engine.run(self.command)
            errors = [e["text"] for e in self.engine.events if e["kind"] == "error"]
            if errors:
                self.message = "\n".join(errors)
            else:
                self.result = self.engine.results_table
                self.message = "\n".join(
                    e["text"]
                    for e in self.engine.events
                    if e["kind"] in ("warning", "output") and e.get("payload") is None
                )
        except Exception as exc:
            self.message = str(exc)


class DatabankDialog(QDialog):
    def __init__(self, paths=(), cwd=None, parent=None):
        super().__init__(parent)
        self.cwd = Path(cwd or Path.cwd())
        self.worker = None
        self.close_after_preview = False
        self.setWindowTitle("Import World Bank panel (dtabnk)")
        self.resize(850, 820)
        root = QVBoxLayout(self)
        intro = QLabel(
            "Convert annual CSV or Excel data into a panel. Select multiple sources to merge by country and year."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)
        self.files = QListWidget()
        self.files.setMaximumHeight(100)
        self.files.addItems([str(p) for p in paths])
        root.addWidget(self.files)
        row = QHBoxLayout()
        root.addLayout(row)
        self.add_button = QPushButton("Add files…")
        row.addWidget(self.add_button)
        self.remove_button = QPushButton("Remove selected")
        row.addWidget(self.remove_button)
        self.add_button.clicked.connect(self.add_files)
        self.remove_button.clicked.connect(self.remove_file)
        row.addStretch()
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        mapping = QWidget()
        form = QFormLayout(mapping)
        self.tabs.addTab(mapping, "Source and columns")
        self.layout_choice = QComboBox()
        self.layout_choice.addItems(LAYOUTS)
        form.addRow("Input layout", self.layout_choice)
        self.columns = {}
        for key, label, placeholder in [
            ("id", "Entity column", "Auto: Country Name or Country"),
            ("yearcol", "Year column", "Auto (long or year rows)"),
            ("valuecol", "Value column", "Auto (long layout)"),
            ("seriescol", "Indicator column", "Auto: Series Name or Indicator Name"),
            ("sheet", "Excel worksheet", "First worksheet"),
        ]:
            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            form.addRow(label, field)
            self.columns[key] = field
        self.headerrow = QSpinBox()
        self.headerrow.setRange(-1, 1000000)
        self.headerrow.setValue(-1)
        self.headerrow.setSpecialValueText("Detect automatically")
        form.addRow("Header row (starts at 0)", self.headerrow)
        self.delimiter = QComboBox()
        self.delimiter.addItems(["Comma", "Semicolon", "Tab", "Pipe"])
        form.addRow("CSV separator", self.delimiter)
        advanced = QWidget()
        settings = QFormLayout(advanced)
        self.tabs.addTab(advanced, "Merge and memory")
        self.keys = QLineEdit("Country Year")
        settings.addRow("Merge keys", self.keys)
        self.join = QComboBox()
        self.join.addItems(["outer", "inner", "left"])
        settings.addRow("Join type", self.join)
        self.conflicts = QComboBox()
        self.conflicts.addItems(["suffix", "error"])
        settings.addRow("Overlapping names", self.conflicts)
        self.aggregate = QComboBox()
        self.aggregate.addItems(
            ["Reject duplicate observations", "Average duplicate observations"]
        )
        settings.addRow("Duplicate source keys", self.aggregate)
        self.keep_long = QCheckBox(
            "Keep indicators in rows instead of separate columns"
        )
        settings.addRow(self.keep_long)
        self.safe = QCheckBox("Use conservative memory estimates")
        settings.addRow(self.safe)
        self.minfree = QSpinBox()
        self.minfree.setRange(0, 1048576)
        self.minfree.setValue(512)
        self.minfree.setSuffix(" MB")
        settings.addRow("RAM reserve", self.minfree)
        self.preview_button = QPushButton("Preview converted panel")
        root.addWidget(self.preview_button)
        self.preview_button.clicked.connect(self.preview)
        self.grid = QTableWidget()
        self.grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.grid.horizontalHeader().setStretchLastSection(True)
        self.grid.setMinimumHeight(130)
        root.addWidget(self.grid, 1)
        self.status = QPlainTextEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(85)
        self.status.setPlaceholderText(
            "Preview converts the full source but leaves your active dataset and files unchanged."
        )
        root.addWidget(self.status)
        self.command_view = QPlainTextEdit()
        self.command_view.setReadOnly(True)
        self.command_view.setMaximumHeight(65)
        self.command_view.setAccessibleName("dtabnk command preview")
        root.addWidget(self.command_view)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import panel")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        for field in self.columns.values():
            field.textChanged.connect(self.update_command)
        self.keys.textChanged.connect(self.update_command)
        for combo in (
            self.layout_choice,
            self.delimiter,
            self.join,
            self.conflicts,
            self.aggregate,
        ):
            combo.currentTextChanged.connect(self.update_command)
        for spin in (self.headerrow, self.minfree):
            spin.valueChanged.connect(self.update_command)
        self.keep_long.toggled.connect(self.update_command)
        self.safe.toggled.connect(self.update_command)
        self.update_command()

    def command(self, preview=False):
        paths = [self.files.item(i).text() for i in range(self.files.count())]
        if not paths:
            raise ValueError("Add at least one source file.")
        opts = [
            "preview" if preview else "clear",
            f"layout({self.layout_choice.currentText()})",
        ]
        for key, field in self.columns.items():
            if field.text().strip():
                opts.append(f"{key}({quoted(field.text().strip())})")
        if len(paths) > 1:
            keys = self.keys.text().strip()
            if not keys or any(not x.replace("_", "").isalnum() for x in keys.split()):
                raise ValueError("Enter space-separated merge key names.")
            opts += [
                "merge",
                f"on({keys})",
                f"join({self.join.currentText()})",
                f"conflicts({self.conflicts.currentText()})",
            ]
        if self.headerrow.value() >= 0:
            opts.append(f"headerrow({self.headerrow.value()})")
        separator = [",", ";", "\t", "|"][self.delimiter.currentIndex()]
        if separator != ",":
            opts.append(f"delimiter({quoted(separator)})")
        if self.keep_long.isChecked():
            opts.append("long")
        if self.safe.isChecked():
            opts.append("safe")
        if self.aggregate.currentIndex():
            opts.append("aggregate(mean)")
        opts.append(f"minfree({self.minfree.value()})")
        return "dtabnk " + " ".join(quoted(p) for p in paths) + ", " + " ".join(opts)

    def update_command(self, *_):
        try:
            self.command_view.setPlainText(self.command())
            valid = True
        except ValueError as exc:
            self.command_view.setPlainText(str(exc))
            valid = False
        busy = self.worker is not None
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            valid and not busy
        )
        self.preview_button.setEnabled(valid and not busy)
        for widget in (self.keys, self.join, self.conflicts):
            widget.setEnabled(self.files.count() > 1 and not busy)

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select panel sources",
            str(self.cwd),
            "Panel data (*.csv *.xlsx *.xls)",
        )
        existing = {self.files.item(i).text() for i in range(self.files.count())}
        self.files.addItems([p for p in paths if p not in existing])
        self.update_command()

    def remove_file(self):
        self.files.takeItem(self.files.currentRow())
        self.update_command()

    def preview(self):
        if self.worker is not None:
            return
        try:
            command = self.command(preview=True)
        except ValueError as exc:
            self.status.setPlainText(str(exc))
            return
        self.worker = PreviewWorker(command, self.cwd, self)
        self.worker.finished.connect(self.preview_finished)
        for widget in (self.tabs, self.add_button, self.remove_button):
            widget.setEnabled(False)
        self.grid.clear()
        self.grid.setRowCount(0)
        self.grid.setColumnCount(0)
        self.status.setPlainText("Converting and validating the source data…")
        self.update_command()
        self.worker.start()

    def preview_finished(self):
        worker = self.worker
        self.worker = None
        frame = worker.result
        if frame is not None:
            self.grid.setColumnCount(len(frame.columns))
            self.grid.setRowCount(len(frame))
            self.grid.setHorizontalHeaderLabels([str(c) for c in frame.columns])
            for i, row in enumerate(frame.itertuples(index=False, name=None)):
                for j, value in enumerate(row):
                    self.grid.setItem(i, j, QTableWidgetItem(str(value)))
            self.grid.resizeColumnsToContents()
        self.status.setPlainText(worker.message)
        worker.deleteLater()
        for widget in (self.tabs, self.add_button, self.remove_button):
            widget.setEnabled(True)
        self.update_command()
        if self.close_after_preview:
            super().reject()

    def reject(self):
        if self.worker is not None:
            self.close_after_preview = True
            self.worker.engine.stop.set()
            self.status.setPlainText("Cancelling after the current conversion stage…")
        else:
            super().reject()

    def closeEvent(self, event):
        if self.worker is not None:
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)
