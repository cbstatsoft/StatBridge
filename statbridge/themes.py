# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Material-inspired desktop colours, without an extra theme dependency."""

from __future__ import annotations
import re
from PySide6.QtGui import QColor, QPalette

LIGHT = dict(
    bg="#e9edf2",
    surface="#ffffff",
    raised="#e2e8ef",
    border="#ccd5df",
    text="#172839",
    muted="#536577",
    accent="#14679b",
    selection="#d9eafa",
    selected_text="#17354c",
    command="#123f68",
    error="#b42d37",
    warning="#996018",
    translation="#607080",
    string="#aa4c2a",
    comment="#536c55",
    macro="#9059a3",
    success="#237445",
    stripe="#f0f5f9",
    header="#dfeaf3",
    ghost="#536577",
)
DARK = dict(
    bg="#121212",
    surface="#1e1e1e",
    raised="#292929",
    border="#424242",
    text="#e6e1e5",
    muted="#c4bdca",
    accent="#d0bcff",
    selection="#4f378b",
    selected_text="#ffffff",
    command="#d0bcff",
    error="#f2b8b5",
    warning="#f2cc8f",
    translation="#a9b6c8",
    string="#e9b384",
    comment="#a5c9a5",
    macro="#e5b8f4",
    success="#a5d6a7",
    stripe="#26232b",
    header="#383044",
    ghost="#9e95aa",
)


def palette(colors):
    p = QPalette()
    for role, token in {
        "Window": "bg",
        "WindowText": "text",
        "Base": "surface",
        "AlternateBase": "stripe",
        "Text": "text",
        "Button": "raised",
        "ButtonText": "text",
        "ToolTipBase": "raised",
        "ToolTipText": "text",
        "Highlight": "selection",
        "HighlightedText": "selected_text",
        "Link": "accent",
        "LinkVisited": "macro",
        "PlaceholderText": "muted",
        "Light": "border",
        "Midlight": "raised",
        "Dark": "bg",
        "Mid": "border",
        "BrightText": "selected_text",
    }.items():
        p.setColor(getattr(QPalette.ColorRole, role), QColor(colors[token]))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["muted"]))
    return p


def stylesheet(c):
    return (
        """
    QWidget { color:%(text)s; }
    QMainWindow,QDialog,QWidget#learningPanel { background:%(bg)s; }
    QDockWidget::title { background:%(raised)s; padding:8px; font-weight:600; color:%(muted)s; }
    QTabWidget::pane { border:1px solid %(border)s; background:%(surface)s; }
    QTabBar::tab { padding:9px 18px; background:%(raised)s; color:%(muted)s; }
    QTabBar::tab:selected { background:%(surface)s; color:%(accent)s; border-top:2px solid %(accent)s; }
    QTextEdit,QPlainTextEdit,QTableView,QListView,QListWidget,QTreeView {
        background:%(surface)s; color:%(text)s; border:1px solid %(border)s;
        alternate-background-color:%(stripe)s; selection-background-color:%(selection)s;
        selection-color:%(selected_text)s; }
    QLineEdit,QComboBox { background:%(surface)s; border:1px solid %(border)s;
        padding:6px; border-radius:5px; color:%(text)s;
        selection-background-color:%(selection)s; selection-color:%(selected_text)s; }
    QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus,QListWidget:focus,QTableView:focus {
        border:2px solid %(accent)s; }
    QSpinBox { background:%(surface)s; color:%(text)s; padding:5px; border:1px solid %(border)s; }
    QPushButton { background:%(raised)s; border:1px solid %(border)s;
        border-radius:8px; padding:7px 14px; }
    QPushButton:hover,QToolButton:hover { background:%(selection)s; color:%(selected_text)s; }
    QPushButton:focus,QToolButton:focus { border:2px solid %(accent)s; }
    QPushButton[primary="true"] { background:%(selection)s; color:%(selected_text)s; border:1px solid %(accent)s; font-weight:600; }
    QPushButton[primary="true"]:focus { border:2px solid %(accent)s; }
    QPushButton:pressed,QToolButton:pressed { background:%(header)s; border:2px solid %(accent)s; }
    QCheckBox:focus { border:1px solid %(accent)s; }
    QPushButton:disabled,QToolButton:disabled { color:%(muted)s; background:%(bg)s; border:1px solid %(border)s; }
    QToolButton { background:%(raised)s; border:1px solid %(border)s; border-radius:6px; padding:6px; }
    QToolButton:checked { background:%(selection)s; color:%(selected_text)s; }
    QHeaderView::section { background:%(raised)s; color:%(muted)s; padding:6px;
        border:0; border-right:1px solid %(border)s; border-bottom:1px solid %(border)s; }
    QTableCornerButton::section { background:%(raised)s; border:0; }
    QStatusBar,QToolBar,QMenuBar { background:%(raised)s; color:%(text)s; }
    QToolBar { border:0; spacing:4px; padding:4px; }
    QMenu { background:%(raised)s; color:%(text)s; border:1px solid %(border)s; padding:5px; }
    QMenu::item { padding:6px 24px; }
    QMenu::item:selected,QMenuBar::item:selected { background:%(selection)s; color:%(selected_text)s; }
    QMenu::separator { height:1px; background:%(border)s; margin:5px; }
    QToolTip { background:%(raised)s; color:%(text)s; border:1px solid %(border)s; padding:5px; }
    QScrollBar { background:%(surface)s; }
    QScrollBar:vertical { width:12px; margin:0; }
    QScrollBar:horizontal { height:12px; margin:0; }
    QScrollBar::handle { background:%(border)s; border-radius:5px; min-width:24px; min-height:24px; }
    QScrollBar::add-line,QScrollBar::sub-line { width:0; height:0; }
    QScrollBar::add-page,QScrollBar::sub-page { background:none; }
    QProgressBar { background:%(surface)s; border:1px solid %(border)s; border-radius:4px; text-align:center; }
    QProgressBar::chunk { background:%(accent)s; }
    """
        % c
    )


def report_html(html, colors):
    """Recolour only markup attributes; escaped labels and values stay untouched."""
    replacements = {
        LIGHT[k]: colors[k]
        for k in ("command", "translation", "muted", "header", "stripe", "surface")
    }
    return re.sub(
        r"<[^>]+>",
        lambda tag: re.sub(
            r"#[0-9a-f]{6}", lambda color: replacements.get(color[0], color[0]), tag[0]
        ),
        html,
    )


def theme_icon(dark, color):
    """Draw the target theme: sun in dark mode, crescent in light mode."""
    import math
    from PySide6.QtCore import Qt, QPointF, QRectF
    from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPen, QPixmap

    icon = QIcon()
    for size in (24, 48, 96):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size / 24, size / 24)
        pen = QPen(QColor(color), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        if dark:
            painter.drawEllipse(QRectF(7.5, 7.5, 9, 9))
            for ray in range(8):
                angle = ray * math.pi / 4
                painter.drawLine(
                    QPointF(12 + 7 * math.cos(angle), 12 + 7 * math.sin(angle)),
                    QPointF(12 + 10 * math.cos(angle), 12 + 10 * math.sin(angle)),
                )
        else:
            moon = QPainterPath()
            moon.addEllipse(QRectF(3, 3, 18, 18))
            cutout = QPainterPath()
            cutout.addEllipse(QRectF(9, 0, 17, 17))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.fillPath(moon.subtracted(cutout), QColor(color))
        painter.end()
        icon.addPixmap(pixmap)
    return icon
