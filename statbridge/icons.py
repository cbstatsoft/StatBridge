# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Small original vector toolbar glyphs, recoloured with the application theme."""

from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

SHAPES = {
    "open": '<path d="M3 8V5h7l2 3h9v12H3z M3 11h18"/>',
    "save": '<path d="M4 3h13l4 4v14H3V3z M7 3v6h9V3 M7 21v-8h10v8"/>',
    "folder": '<path d="M3 8V5h7l2 3h9v12H3z M9 14h6 M12 11v6"/>',
    "run": '<path d="M7 4l13 8-13 8z"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="1"/>',
    "analyse": '<path d="M4 3v17h17 M7 15l4-6 4 3 5-7"/><circle cx="11" cy="9" r="1"/>',
    "learn": '<path d="M12 5C8 2 5 3 2 4v15c4-1 7-1 10 1 3-2 6-2 10-1V4c-3-1-6-2-10 1v15"/>',
    "script": '<path d="M5 2h10l4 4v16H5z M15 2v5h4 M9 11l-2 3 2 3 M15 11l2 3-2 3"/>',
    "clear": '<path d="M4 6h16 M9 6V3h6v3 M6 6l1 15h10l1-15 M10 10v7 M14 10v7"/>',
}


def action_icon(name, color, disabled):
    icon = QIcon()
    for mode, stroke in ((QIcon.Mode.Normal, color), (QIcon.Mode.Disabled, disabled)):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'<g fill="none" stroke="{stroke}" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round">{SHAPES[name]}</g></svg>'
        )
        renderer = QSvgRenderer(QByteArray(svg.encode()))
        for size in (24, 48, 96):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            icon.addPixmap(pixmap, mode)
    return icon
