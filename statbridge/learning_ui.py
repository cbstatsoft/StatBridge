# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Optional learning widgets, isolated from all statistical execution."""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QComboBox,
    QTabWidget,
    QTextBrowser,
    QPushButton,
    QLabel,
    QHBoxLayout,
    QLineEdit,
)
from .learning import LESSONS, lesson_html, check_lesson, explain_current
from .learning_reference import TEST_GUIDES, test_guide_html


class LearningPanel(QWidget):
    openExample = Signal(str)

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.setObjectName("learningPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.engine = engine
        self.theme_colors = None
        self.feedback_good = None
        self.busy = False
        self.setMinimumSize(330, 440)
        layout = QVBoxLayout(self)
        title = QLabel("Learn with your full workspace")
        title.setStyleSheet("font-weight:600;font-size:15px;")
        layout.addWidget(title)
        caption = QLabel("Optional, offline guidance. No account or licence key.")
        caption.setWordWrap(True)
        layout.addWidget(caption)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        lesson_page = QWidget()
        ll = QVBoxLayout(lesson_page)
        ll.setContentsMargins(0, 8, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find a lesson or command…")
        self.search.setAccessibleName("Search lessons")
        ll.addWidget(self.search)
        self.category = QComboBox()
        self.category.setAccessibleName("Lesson topic")
        self.category.addItems(["All topics"] + sorted({x.category for x in LESSONS}))
        ll.addWidget(self.category)
        self.selector = QComboBox()
        self.selector.setAccessibleName("Lesson")
        self.selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.selector.setMinimumContentsLength(20)
        for i, lesson in enumerate(LESSONS):
            self.selector.addItem(lesson.title, i)
        self.selector.currentIndexChanged.connect(self.show_lesson)
        ll.addWidget(self.selector)
        self.lesson_count = QLabel()
        ll.addWidget(self.lesson_count)
        self.guide = QTextBrowser()
        self.guide.setOpenExternalLinks(False)
        ll.addWidget(self.guide)
        self.open_button = QPushButton("Open in do-file editor")
        self.open_button.clicked.connect(
            lambda: self.openExample.emit(self.lesson.script) if self.lesson else None
        )
        ll.addWidget(self.open_button)
        row = QHBoxLayout()
        self.check_button = QPushButton("Check my result")
        self.check_button.clicked.connect(self.check)
        row.addWidget(self.check_button)
        self.solution_button = QPushButton("Show solution")
        self.solution_button.clicked.connect(
            lambda: self.guide.setHtml(lesson_html(self.lesson, True)) if self.lesson else None
        )
        row.addWidget(self.solution_button)
        ll.addLayout(row)
        self.feedback = QLabel("Checks inspect the current result without changing it.")
        self.feedback.setWordWrap(True)
        ll.addWidget(self.feedback)
        self.tabs.addTab(lesson_page, "Practice")
        self.tabs.setTabToolTip(0, "Guided practice")
        self.current = QTextBrowser()
        self.current.setOpenExternalLinks(False)
        self.tabs.addTab(self.current, "Explain")
        self.tabs.setTabToolTip(1, "Explain my command")
        reference_page = QWidget()
        rl = QVBoxLayout(reference_page)
        self.test_selector = QComboBox()
        self.test_selector.setAccessibleName("Test interpretation topic")
        self.test_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.test_selector.setMinimumContentsLength(20)
        self.test_selector.addItems([x.title for x in TEST_GUIDES])
        rl.addWidget(self.test_selector)
        self.reference = QTextBrowser()
        rl.addWidget(self.reference)
        self.test_selector.currentIndexChanged.connect(self.show_reference)
        self.tabs.addTab(reference_page, "Tests")
        self.tabs.setTabToolTip(2, "Interpret tests")
        self.search.textChanged.connect(self.filter_lessons)
        self.category.currentIndexChanged.connect(self.filter_lessons)
        self.filter_lessons()
        self.show_reference()
        self.refresh()

    @property
    def lesson(self):
        index = self.selector.currentData()
        return LESSONS[index] if index is not None else None

    def filter_lessons(self, *_):
        previous = self.selector.currentData()
        query = self.search.text().strip().casefold()
        category = self.category.currentText()
        self.selector.blockSignals(True)
        self.selector.clear()
        for i, lesson in enumerate(LESSONS):
            searchable = " ".join((lesson.title, lesson.objective, lesson.explanation, lesson.solution, lesson.key)).casefold()
            if (category == "All topics" or lesson.category == category) and query in searchable:
                self.selector.addItem(lesson.title, i)
        index = self.selector.findData(previous)
        if index >= 0:
            self.selector.setCurrentIndex(index)
        self.selector.blockSignals(False)
        self.lesson_count.setText(f"{self.selector.count()} of {len(LESSONS)} lessons")
        self.show_lesson()

    def show_reference(self, *_):
        self.reference.setHtml(test_guide_html(TEST_GUIDES[self.test_selector.currentIndex()]))

    def show_lesson(self, *_):
        self.guide.setHtml(lesson_html(self.lesson) if self.lesson else "<p>No matching lessons. Try another search or topic.</p>")
        self.set_busy(self.busy)
        self.feedback.setText("Checks inspect the current result without changing it.")
        self.feedback_good = None
        if self.theme_colors:
            self.apply_theme(self.theme_colors)

    def check(self):
        if self.lesson is None or self.busy:
            return
        good, message = check_lesson(self.engine, self.lesson)
        self.feedback.setText(("✓ " if good else "") + message)
        self.feedback_good = good
        if self.theme_colors:
            self.apply_theme(self.theme_colors)

    def apply_theme(self, colors):
        self.theme_colors = colors
        key = (
            "muted"
            if self.feedback_good is None
            else "success"
            if self.feedback_good
            else "warning"
        )
        self.feedback.setStyleSheet(f"color:{colors[key]};")

    def refresh(self):
        self.current.setHtml(explain_current(self.engine))

    def set_busy(self, busy):
        self.busy = busy
        available = self.lesson is not None
        self.open_button.setEnabled(not busy and available)
        self.check_button.setEnabled(not busy and available)
        self.solution_button.setEnabled(available)
