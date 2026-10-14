# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Dataset format chooser with explicit options and asynchronous preview."""

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QCheckBox,
    QLabel,
    QFileDialog,
    QDialogButtonBox,
    QListWidget,
    QAbstractItemView,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from .format_io import EXTENSIONS, detect, ARROW
from .databank_ui import PreviewWorker, quoted

TITLES = {
    "mtp": "Minitab portable numeric columns (.mtp), import only",
    "stata": "Stata (.dta)",
    "sav": "SPSS / PSPP (.sav, .zsav)",
    "por": "SPSS portable (.por)",
    "sas": "SAS dataset (.sas7bdat), import only",
    "xport": "SAS transport (.xpt)",
    "rdata": "R workspace (.RData, .rda)",
    "rds": "R object (.rds)",
    "parquet": "Parquet (.parquet)",
    "feather": "Feather (.feather)",
    "arrow": "Arrow IPC (.arrow)",
    "delimited": "Delimited text (.csv, .tsv)",
    "json": "JSON records (.json)",
    "jsonl": "JSON lines (.jsonl)",
    "workbook": "Spreadsheet (.xlsx, .xls, .xlsm, .xlsb, .ods)",
    "sqlite": "SQLite (.sqlite, .db)",
    "mat": "MATLAB numeric vectors (.mat)",
    "hdf5": "HDF5 numeric vectors (.h5)",
}


class FormatDialog(QDialog):
    def __init__(self, cwd, columns=(), exporting=False, path="", parent=None):
        super().__init__(parent)
        self.cwd, self.exporting = Path(cwd), exporting
        self.worker = None
        self.setWindowTitle(
            "Export dataset" if exporting else "Import dataset into workspace"
        )
        self.resize(780, 520 if exporting else 720)
        root = QVBoxLayout(self)
        form = self.form = QFormLayout()
        root.addLayout(form)
        self.kind = QComboBox()
        if not exporting:
            self.kind.addItem("Detect from filename", "auto")
        for kind, title in TITLES.items():
            if exporting and kind in ("sas", "mtp"):
                continue
            self.kind.addItem(title, kind)
        form.addRow("File format", self.kind)
        row = QHBoxLayout()
        self.path = QLineEdit(path)
        row.addWidget(self.path)
        self.browse = QPushButton("Browse…")
        row.addWidget(self.browse)
        form.addRow("File", row)
        self.selector = QLineEdit()
        self.selector.setPlaceholderText(
            "Default: single object/table, first sheet, or root group"
        )
        form.addRow("Object / table / sheet / group", self.selector)
        self.compression = QComboBox()
        form.addRow("Compression", self.compression)
        self.delimiter = QComboBox()
        self.delimiter.addItems(["Auto", "Comma", "Tab", "Semicolon", "Pipe"])
        form.addRow("Text separator", self.delimiter)
        self.rename = QCheckBox("Rename invalid column names and report the mapping")
        self.rename.setVisible(not exporting)
        root.addWidget(self.rename)
        self.variables = QListWidget()
        self.variables.addItems(list(columns))
        self.variables.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.variables.setMaximumHeight(100)
        self.variables.setVisible(exporting)
        if exporting:
            root.addWidget(
                QLabel(
                    "Variables: leave selection empty to export all; Ctrl/Shift selects several."
                )
            )
        root.addWidget(self.variables)
        self.note = QLabel()
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        self.preview_button = QPushButton("Preview first 20 rows")
        self.preview_button.setVisible(not exporting)
        root.addWidget(self.preview_button)
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().hide()
        self.table.setVisible(not exporting)
        root.addWidget(self.table, 1)
        self.message = QPlainTextEdit()
        self.message.setReadOnly(True)
        self.message.setMaximumHeight(105)
        root.addWidget(self.message)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Export" if exporting else "Import into workspace"
        )
        root.addWidget(self.buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.browse.clicked.connect(self.choose_file)
        self.preview_button.clicked.connect(self.preview)
        self.kind.currentIndexChanged.connect(self.update_options)
        self.path.textChanged.connect(self.update_options)
        self.update_options()

    def effective_kind(self):
        kind = self.kind.currentData()
        if kind == "auto":
            try:
                return detect(self.path.text())
            except Exception:
                return "auto"
        return kind

    def update_options(self):
        kind = self.effective_kind()
        self.selector.setEnabled(
            kind in ("rdata", "sqlite", "workbook")
            or (kind == "hdf5" and not self.exporting)
        )
        self.delimiter.setEnabled(kind == "delimited")
        self.form.setRowVisible(self.selector, self.selector.isEnabled())
        self.form.labelForField(self.selector).setText(
            {
                "rdata": "R object name",
                "sqlite": "Table name",
                "workbook": "Worksheet name",
                "hdf5": "Group path",
            }.get(kind, "Source selection")
        )
        self.form.setRowVisible(self.delimiter, kind == "delimited")
        self.form.setRowVisible(
            self.compression,
            self.exporting and kind in (ARROW | {"sav", "rdata", "rds"}),
        )
        previous = self.compression.currentText()
        self.compression.clear()
        choices = {
            "parquet": ["default", "snappy", "zstd", "gzip", "brotli", "lz4", "none"],
            "feather": ["default", "lz4", "zstd", "none"],
            "arrow": ["default", "lz4", "zstd", "none"],
            "sav": ["default", "none", "row", "zlib"],
            "rdata": ["default", "none", "gzip"],
            "rds": ["default", "none", "gzip"],
        }.get(kind, ["default"])
        self.compression.addItems(choices)
        if previous in choices:
            self.compression.setCurrentText(previous)
        self.compression.setEnabled(self.exporting and len(choices) > 1)
        info = "Imports replace the active dataset after validation. Preview leaves it unchanged and may read the entire file."
        if self.exporting:
            info = "Exports leave the active dataset unchanged. Replacing a file replaces its whole contents."
        if kind in ARROW:
            info += " Labels and Stata date formats are embedded for StatBridge round trips."
        elif kind in ("rdata", "rds"):
            info += " Uses pyreadr (included in the standard installation). R row names and arbitrary attributes are not retained."
        elif kind in ("mat", "hdf5"):
            info += " Equal-length real numeric vectors only; no matrices, structs or table objects."
        elif kind == "sqlite":
            info += " Select a table by name. Export creates a database containing only that table."
        elif kind == "workbook":
            info += " First row supplies headers. Import reads cached values; export supports .xlsx and .ods."
        else:
            info += " Format-specific losses are reported in Results."
        self.note.setText(info)

    def choose_file(self):
        kind = self.kind.currentData()
        if self.exporting:
            suffixes = (".xlsx", ".ods") if kind == "workbook" else EXTENSIONS[kind]
            filt = TITLES[kind] + " (" + " ".join("*" + x for x in suffixes) + ")"
            path, _ = QFileDialog.getSaveFileName(
                self, "Export dataset", str(self.cwd / ("data" + suffixes[0])), filt
            )
            if path and not Path(path).suffix:
                path += suffixes[0]
        else:
            extensions = sorted({x for values in EXTENSIONS.values() for x in values})
            filt = (
                "Supported datasets ("
                + " ".join("*" + x for x in extensions)
                + ");;All files (*)"
            )
            path, _ = QFileDialog.getOpenFileName(
                self, "Import dataset", str(self.cwd), filt
            )
        if path:
            self.path.setText(path)

    def command(self, preview=False):
        if not self.path.text().strip():
            raise ValueError("Choose a file first.")
        path = quoted(self.path.text().strip())
        kind = self.effective_kind()
        if kind == "auto":
            raise ValueError("Choose a supported file or select its format.")
        opts = (
            ["replace"]
            if self.exporting
            else (["preview", "rows(20)"] if preview else ["clear"])
        )
        selector = self.selector.text().strip()
        if self.selector.isEnabled() and selector:
            name = {
                "rdata": "object",
                "sqlite": "table",
                "workbook": "sheet",
                "hdf5": "group",
            }[kind]
            opts.append(name + "(" + quoted(selector) + ")")
        if self.delimiter.isEnabled() and self.delimiter.currentIndex():
            sep = {1: ",", 2: "\\t", 3: ";", 4: "|"}[self.delimiter.currentIndex()]
            opts.append("delimiter(" + quoted(sep) + ")")
        if self.exporting:
            if (
                self.compression.isEnabled()
                and self.compression.currentText() != "default"
            ):
                opts.append("compression(" + self.compression.currentText() + ")")
            cols = " ".join(item.text() for item in self.variables.selectedItems())
            if kind == "workbook" and Path(self.path.text()).suffix.lower() == ".xlsx":
                kind = "excel"
                opts.append("firstrow(variables)")
            return f"export {kind} {cols} using {path}, " + " ".join(opts)
        if self.rename.isChecked():
            opts.append("rename")
        return f"import {kind} {path}, " + " ".join(opts)

    def preview(self):
        if self.worker:
            return
        try:
            command = self.command(preview=True)
        except ValueError as exc:
            self.message.setPlainText(str(exc))
            return
        self.worker = PreviewWorker(command, self.cwd, self)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.preview_button.setEnabled(False)
        self.message.setPlainText("Reading file…")
        self.worker.finished.connect(self.preview_done)
        self.worker.start()

    def preview_done(self):
        import pandas as pd

        worker = self.worker
        frame = worker.result
        self.table.clear()
        self.table.setRowCount(0)
        if frame is not None:
            self.table.setColumnCount(len(frame.columns))
            self.table.setHorizontalHeaderLabels([str(c) for c in frame.columns])
            self.table.setRowCount(len(frame))
            for i, row in enumerate(frame.itertuples(index=False, name=None)):
                for j, value in enumerate(row):
                    self.table.setItem(
                        i, j, QTableWidgetItem("." if pd.isna(value) else str(value))
                    )
            self.table.resizeColumnsToContents()
        self.message.setPlainText(worker.message)
        worker.deleteLater()
        self.worker = None
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        self.preview_button.setEnabled(True)

    def accept(self):
        if self.worker:
            return
        try:
            self.command()
        except ValueError as exc:
            self.message.setPlainText(str(exc))
            return
        if self.exporting:
            from PySide6.QtWidgets import QMessageBox

            path = Path(self.path.text()).expanduser()
            if not path.is_absolute():
                path = self.cwd / path
            if (
                path.exists()
                and QMessageBox.question(
                    self,
                    "Replace entire file?",
                    f"Replace {path.name}? All existing contents will be replaced.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        super().accept()

    def reject(self):
        if self.worker:
            self.message.setPlainText(
                "Please wait for the current file read to finish before closing."
            )
            return
        super().reject()

    def closeEvent(self, event):
        if self.worker:
            event.ignore()
        else:
            super().closeEvent(event)
