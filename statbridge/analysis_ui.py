# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Small form-based front ends to the same auditable command engine."""

import re
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QCheckBox,
)
from .icons import action_icon


class AnalysisDialog(QDialog):
    TITLES = {
        "regress": "Linear regression",
        "xtreg": "Panel fixed effects",
        "logit": "Binary logit",
        "ivregress": "Instrumental variables (2SLS)",
        "histogram": "Histogram",
        "mean": "Means and confidence intervals",
        "mlogit": "Multinomial logistic regression",
        "ologit": "Ordered logistic regression",
        "oprobit": "Ordered probit regression",
        "newey": "Newey-West time-series regression",
        "stcox": "Cox survival regression",
        "svymean": "Survey means",
    }

    def __init__(self, engine, kind, parent=None):
        super().__init__(parent)
        self.engine, self.kind = engine, kind
        self.source = ""
        self.insert_only = False
        self.setWindowTitle(self.TITLES[kind])
        self.resize(580, 600 if kind != "histogram" else 400)
        layout = QVBoxLayout(self)
        caption = QLabel(
            "Choose variables, then run the analysis or insert its syntax in your do-file."
        )
        caption.setWordWrap(True)
        layout.addWidget(caption)
        form = QFormLayout()
        layout.addLayout(form)
        self.numeric = [
            c
            for c in engine.df.columns
            if re.fullmatch(r"[A-Za-z_]\w*", c)
            and pd.api.types.is_numeric_dtype(engine.df[c])
        ]
        simple = kind in ("histogram", "mean", "svymean")
        self.outcome = self.combo(self.numeric)
        form.addRow(
            (
                "&Duration:"
                if kind == "stcox"
                else "&Variable:" if simple else "&Outcome:"
            ),
            self.outcome,
        )
        self.predictors = self.checklist(self.numeric, "Predictors")
        if not simple:
            form.addRow("&Predictors:", self.predictors)
        else:
            self.predictors.hide()
        self.panel = self.combo(self.numeric)
        self.time = self.combo(self.numeric, optional=True)
        if kind == "xtreg":
            form.addRow("Panel &identifier:", self.panel)
            form.addRow("&Time variable (optional):", self.time)
            if engine.panel:
                self.panel.setCurrentText(engine.panel[0])
                if engine.panel[1]:
                    self.time.setCurrentText(engine.panel[1])
        elif kind == "newey":
            self.panel.hide()
            form.addRow("&Time variable:", self.time)
            if engine.tsvar:
                self.time.setCurrentText(engine.tsvar)
        else:
            self.panel.hide()
            self.time.hide()
        self.endogenous = self.checklist(self.numeric, "Endogenous variables")
        self.instruments = self.checklist(self.numeric, "Excluded instruments")
        if kind == "ivregress":
            form.addRow("&Endogenous variables:", self.endogenous)
            form.addRow("&Excluded instruments:", self.instruments)
        else:
            self.endogenous.hide()
            self.instruments.hide()
        self.covariance = self.combo(["Conventional", "Robust", "Clustered"])
        self.covariance.setCurrentIndex(1)  # index zero is the required blank item
        self.cluster = self.combo(self.numeric)
        if kind in ("regress", "xtreg", "logit", "ivregress"):
            form.addRow("Standard &errors:", self.covariance)
            form.addRow("&Cluster variable:", self.cluster)
        else:
            self.covariance.hide()
            self.cluster.hide()
        self.bins = QSpinBox(self)
        self.bins.setRange(1, 500)
        self.bins.setValue(20)
        self.frequency = QCheckBox("Show frequencies instead of density", self)
        if kind == "histogram":
            form.addRow("&Bins:", self.bins)
            form.addRow(self.frequency)
        else:
            self.bins.hide()
            self.frequency.hide()
        self.failure = self.combo(self.numeric)
        self.psu = self.combo(list(engine.df.columns))
        self.weight = self.combo(self.numeric, optional=True)
        self.strata = self.combo(list(engine.df.columns), optional=True)
        self.subpop = self.combo(self.numeric, optional=True)
        self.lag = QSpinBox(self)
        self.lag.setRange(0, 10000)
        self.lag.setValue(1)
        for control in (
            self.failure,
            self.psu,
            self.weight,
            self.strata,
            self.subpop,
            self.lag,
        ):
            control.hide()
        if kind == "newey":
            self.lag.show()
            form.addRow("HAC &lag:", self.lag)
        if kind == "stcox":
            self.failure.show()
            self.strata.show()
            form.addRow("&Failure indicator (0/1):", self.failure)
            form.addRow("&Strata (optional):", self.strata)
            note = QLabel(
                "One row per subject; right censoring, origin zero, model-based standard errors. Proportional-hazards diagnostics are not yet available."
            )
            note.setWordWrap(True)
            form.addRow(note)
        if kind == "svymean":
            for label, control in [
                ("Primary sampling &unit:", self.psu),
                ("Sampling &weight (optional):", self.weight),
                ("&Strata (optional):", self.strata),
                ("Sub&population 0/1 (optional):", self.subpop),
            ]:
                control.show()
                form.addRow(label, control)
            note = QLabel(
                "One-stage with-replacement Taylor variance. Each stratum needs at least two PSUs. Select a subpopulation instead of filtering rows."
            )
            note.setWordWrap(True)
            form.addRow(note)
        self.condition = QLineEdit(self)
        self.condition.setPlaceholderText("Optional, e.g. age >= 18")
        if kind != "svymean":
            form.addRow("Include rows &if:", self.condition)
        else:
            self.condition.hide()
        preview_label = QLabel("Stata syntax preview")
        layout.addWidget(preview_label)
        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.preview.setMaximumHeight(90)
        self.preview.setAccessibleName("Stata syntax preview")
        layout.addWidget(self.preview)
        self.validation = QLabel(self)
        self.validation.setWordWrap(True)
        layout.addWidget(self.validation)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, self)
        self.run_button = self.buttons.addButton(
            "Run analysis", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.run_button.setProperty("primary", True)
        self.run_button.setDefault(True)
        self.insert_button = self.buttons.addButton(
            "Insert in do-file", QDialogButtonBox.ButtonRole.ActionRole
        )
        colors = getattr(
            parent,
            "colors",
            {"text": "#172839", "muted": "#536577", "selected_text": "#17354c"},
        )
        self.run_button.setIcon(action_icon("run", colors["text"], colors["muted"]))
        self.insert_button.setIcon(
            action_icon("script", colors["text"], colors["muted"])
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.insert_button.clicked.connect(self.insert)
        layout.addWidget(self.buttons)
        for control in (
            self.outcome,
            self.panel,
            self.time,
            self.covariance,
            self.cluster,
            self.failure,
            self.psu,
            self.weight,
            self.strata,
            self.subpop,
        ):
            control.currentIndexChanged.connect(self.update_preview)
        for control in (self.predictors, self.endogenous, self.instruments):
            control.itemChanged.connect(self.update_preview)
        self.condition.textChanged.connect(self.update_preview)
        self.bins.valueChanged.connect(self.update_preview)
        self.lag.valueChanged.connect(self.update_preview)
        self.frequency.toggled.connect(self.update_preview)
        self.update_preview()

    def combo(self, values, optional=False):
        box = QComboBox(self)
        box.addItem("None" if optional else "Choose…", "")
        for value in values:
            box.addItem(value, value)
        return box

    def checklist(self, values, label):
        widget = QListWidget(self)
        widget.setAccessibleName(label)
        widget.setMaximumHeight(105)
        for value in values:
            item = QListWidgetItem(value, widget)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(self.engine.labels.get(value, value))
        return widget

    @staticmethod
    def selected(widget):
        return [
            widget.item(i).text()
            for i in range(widget.count())
            if widget.item(i).checkState() == Qt.CheckState.Checked
        ]

    def build_source(self):
        y = self.outcome.currentData()
        if not y:
            raise ValueError(
                "Choose a numeric variable."
                if self.kind == "histogram"
                else "Choose an outcome variable."
            )
        x = self.selected(self.predictors)
        condition = self.condition.text().strip()
        if any(token in condition for token in ("\n", "\r", ";", "//", "/*", "*/")):
            raise ValueError(
                "Use one condition, without comments or command separators."
            )
        if condition:
            # Validate with the engine's restricted parser, without executing commands.
            # Random functions are excluded so the preview cannot consume RNG state.
            if re.search(r"\b(?:runiform|rnormal)\s*\(", condition):
                raise ValueError(
                    "Generate random values first, then filter on that variable."
                )
            try:
                self.engine.mask({"if": condition})
            except Exception as exc:
                raise ValueError(f"Check the row condition: {exc}") from exc
        qualifier = f" if {condition}" if condition else ""
        if self.kind == "histogram":
            return f"histogram {y}{qualifier}, bin({self.bins.value()})" + (
                " frequency" if self.frequency.isChecked() else ""
            )
        if self.kind == "mean":
            return f"mean {y}{qualifier}"
        if self.kind == "svymean":
            psu = self.psu.currentData()
            weight = self.weight.currentData()
            strata = self.strata.currentData()
            subpop = self.subpop.currentData()
            if not psu:
                raise ValueError("Choose the primary sampling unit.")
            declaration = (
                f"svyset {psu}"
                + (f" [pw={weight}]" if weight else "")
                + (f", strata({strata})" if strata else "")
            )
            return (
                declaration
                + "\nsvy"
                + (f", subpop({subpop})" if subpop else "")
                + f": mean {y}"
            )
        if self.kind == "stcox":
            failure = self.failure.currentData()
            strata = self.strata.currentData()
            if not failure or not x:
                raise ValueError(
                    "Choose a failure indicator and at least one predictor."
                )
            if y in x or failure in x:
                raise ValueError("Duration and failure indicator cannot be predictors.")
            return (
                f"stset {y}, failure({failure})\nstcox "
                + " ".join(x)
                + qualifier
                + (f", strata({strata})" if strata else "")
            )
        if self.kind in ("mlogit", "ologit", "oprobit") and not x:
            raise ValueError("Choose at least one predictor.")
        if y in x:
            raise ValueError("The outcome cannot also be a predictor.")
        covariance = self.covariance.currentData()
        if not covariance:
            raise ValueError("Choose a standard-error method.")
        options = []
        if covariance == "Robust":
            options.append("robust")
        elif covariance == "Clustered":
            cluster = self.cluster.currentData()
            if not cluster:
                raise ValueError("Choose the cluster variable.")
            options.append(f"vce(cluster {cluster})")
        terms = " ".join([y] + x)
        prefix = ""
        if self.kind == "xtreg":
            panel, time = self.panel.currentData(), self.time.currentData()
            if not panel:
                raise ValueError("Choose the panel identifier.")
            if panel == time:
                raise ValueError("Panel identifier and time variable must differ.")
            prefix = "xtset " + panel + (f" {time}" if time else "") + "\n"
            options.insert(0, "fe")
        if self.kind == "newey":
            time = self.time.currentData()
            if not time:
                raise ValueError("Choose a time variable.")
            prefix = f"tsset {time}\n"
            options.append(f"lag({self.lag.value()})")
        if self.kind == "ivregress":
            endog, instruments = (
                self.selected(self.endogenous),
                self.selected(self.instruments),
            )
            if not endog or len(instruments) < len(endog):
                raise ValueError(
                    "Select endogenous variables and at least as many excluded instruments."
                )
            groups = [{y}, set(x), set(endog), set(instruments)]
            if any(a & b for i, a in enumerate(groups) for b in groups[i + 1 :]):
                raise ValueError(
                    "Outcome, predictors, endogenous variables and excluded instruments must be distinct."
                )
            terms = (
                "2sls "
                + terms
                + " ("
                + " ".join(endog)
                + " = "
                + " ".join(instruments)
                + ")"
            )
        return (
            prefix
            + self.kind
            + " "
            + terms
            + qualifier
            + (", " + " ".join(options) if options else "")
        )

    def update_preview(self, *_):
        self.cluster.setEnabled(self.covariance.currentData() == "Clustered")
        try:
            self.source = self.build_source()
            self.preview.setPlainText(self.source)
            self.validation.setText(
                "Ready. The engine checks the data and model when you run."
            )
        except ValueError as exc:
            self.source = ""
            self.preview.clear()
            self.validation.setText(str(exc))
        self.run_button.setEnabled(bool(self.source))
        self.insert_button.setEnabled(bool(self.source))

    def accept(self):
        self.update_preview()
        if self.source:
            super().accept()

    def insert(self):
        self.insert_only = True
        self.accept()
