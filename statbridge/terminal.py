# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Curses workspace. Qt is never imported by this module."""

from __future__ import annotations

import json
import os
import queue
import sys
import tempfile
import threading
import unicodedata
from collections import deque
from pathlib import Path
from os.path import commonprefix
from . import __version__
from .completion import Suggestions
from .engine import Engine

HELP = """TERMINAL KEYS
Enter: run command; Tab: complete / cycle suggestions; Right at end: accept suggestion
Up / Down: recall history; Home / End: move cursor; Ctrl+U: clear command
Page Up / Page Down: scroll results; F7 / F8: pan results left / right
F1: this help; F2: list variables; F3: start a do-file command
Ctrl+C: request stop while running, or clear the command when idle
F10 or :quit: close terminal (asks before discarding unsaved data)

Use Stata commands, including do "analysis.do", cd, ls, use and save.
Enter syntax logos to use bounded English/formal logic; syntax stata switches back.
Use 'logos: ...' for one Logos command or 'stata: ...' inside Logos mode.
For the grammar, enter help logos after switching (or stata: help logos).
Use graph export "plot.png", replace to save a plot; graphics are not drawn here.
Use log using "session.log", text to retain full results beyond the scrollback.
:history clear | :history off | :history on   Control terminal history persistence
:cwd off | :cwd on                         Control remembered working folder
:clear                                     Clear visible results
Terminal settings are separate from desktop settings. History and folder are remembered
by default. Datasets are never saved automatically. No shell commands are executed.
"""


def state_path():
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "StatBridge" / "terminal.json"


def safe_text(text):
    """Keep terminal control sequences in data from becoming terminal instructions."""
    return "".join(c if c.isprintable() else " " for c in str(text).expandtabs(4))


def cell_width(text):
    return sum(
        0
        if unicodedata.combining(c)
        else 2
        if unicodedata.east_asian_width(c) in "WF"
        else 1
        for c in text
    )


def cell_slice(text, start, width):
    result, position = [], 0
    for char in safe_text(text):
        size = cell_width(char)
        if position >= start and position + size <= start + width:
            result.append(char)
        position += size
        if position > start + width:
            break
    return "".join(result)


class TerminalSession:
    def __init__(self, cwd=None, settings_path=None, no_history=False, no_cwd=False, syntax="stata"):
        self.settings_path = Path(settings_path) if settings_path else state_path()
        settings = {}
        try:
            if self.settings_path.stat().st_size <= 2_000_000:
                settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
                if not isinstance(settings, dict):
                    settings = {}
        except (OSError, ValueError):
            pass
        self.remember_history = (
            not no_history and settings.get("remember_history", True) is True
        )
        self.remember_cwd = not no_cwd and settings.get("remember_cwd", True) is True
        saved_cwd = settings.get("cwd")
        if (
            cwd is None
            and self.remember_cwd
            and isinstance(saved_cwd, str)
            and Path(saved_cwd).is_dir()
        ):
            cwd = saved_cwd
        self.engine = Engine(cwd=cwd, syntax_mode=syntax)
        self.events = queue.Queue()
        self.engine.emit_callback = self.events.put
        self.lines = deque(maxlen=10000)
        self.history = (
            [x for x in settings.get("history", []) if isinstance(x, str)][-1000:]
            if self.remember_history and isinstance(settings.get("history", []), list)
            else []
        )
        self.suggestions = Suggestions()
        self.worker = None
        self.buffer, self.cursor, self.draft = "", 0, ""
        self.history_position = len(self.history)
        self.completions, self.completion_index = [], -1
        self.status = "Ready"
        self.add(HELP)
        from .legal import NOTICE
        self.add("Public beta. " + NOTICE)
        self.sync()
        if no_history or no_cwd:
            self.save_settings()

    @property
    def busy(self):
        return self.worker is not None

    def add(self, text, kind="output"):
        for line in str(text).splitlines():
            self.lines.append((safe_text(line), kind))

    def sync(self):
        self.suggestions.sync(self.engine)
        self.suggestions.history = self.history.copy()
        self.dataset_status = (
            f"{len(self.engine.df):,} rows / {len(self.engine.df.columns)} variables"
        )
        self.folder = str(self.engine.cwd)
        self.dirty = self.engine.dirty

    def save_settings(self):
        data = {
            "remember_history": self.remember_history,
            "remember_cwd": self.remember_cwd,
        }
        if self.remember_history:
            data["history"] = self.history[-1000:]
        if self.remember_cwd:
            data["cwd"] = str(self.engine.cwd)
        name = None
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.settings_path.parent, delete=False
            ) as stream:
                name = stream.name
                json.dump(data, stream, ensure_ascii=False)
            os.replace(name, self.settings_path)
        except OSError as exc:
            self.add(f"Settings could not be saved: {exc}", "warning")
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def set_buffer(self, text, cursor=None):
        self.buffer = text
        self.cursor = len(text) if cursor is None else cursor
        self.completions, self.completion_index = [], -1

    def recall(self, direction):
        if self.history_position == len(self.history):
            self.draft = self.buffer
        self.history_position = max(
            0, min(len(self.history), self.history_position + direction)
        )
        self.set_buffer(
            self.history[self.history_position]
            if self.history_position < len(self.history)
            else self.draft
        )

    def complete(self):
        if not self.completions:
            edits = self.suggestions.complete(self.buffer, self.cursor)
            if not edits:
                return
            prefix = commonprefix([e.text[: e.cursor] for e in edits])
            if len(edits) > 1 and len(prefix) > self.cursor:
                self.set_buffer(prefix + edits[0].text[edits[0].cursor :], len(prefix))
                return
            self.completions = edits
        self.completion_index = (self.completion_index + 1) % len(self.completions)
        edit = self.completions[self.completion_index]
        self.buffer, self.cursor = edit.text, edit.cursor

    def submit(self, source):
        if self.busy or not source.strip():
            return
        source = source.strip()
        self.set_buffer("")
        self.draft = ""
        self.history_position = len(self.history)
        if source.startswith(":"):
            self.local_command(source)
            return
        self.history.append(source)
        self.history[:] = self.history[-1000:]
        self.history_position = len(self.history)
        self.status = "Running; Ctrl+C stops after the current backend call"
        self.engine.stop.clear()

        def run():
            try:
                success = self.engine.run(source)
                self.events.put(
                    {
                        "kind": "done",
                        "text": "Finished"
                        if success
                        else "Stopped or failed; see results",
                    }
                )
            except Exception as exc:
                self.events.put({"kind": "error", "text": str(exc)})
                self.events.put({"kind": "done", "text": "Failed; see results"})

        self.worker = threading.Thread(
            target=run, name="statbridge-terminal", daemon=True
        )
        self.worker.start()

    def local_command(self, source):
        if source in (":history on", ":history off"):
            self.remember_history = source.endswith("on")
            self.add(
                "History persistence "
                + ("on" if self.remember_history else "off; saved history removed")
            )
        elif source == ":history clear":
            self.history.clear()
            self.history_position = 0
            self.draft = ""
            self.add("Command history cleared")
        elif source in (":cwd on", ":cwd off"):
            self.remember_cwd = source.endswith("on")
            self.add(
                "Working-folder persistence " + ("on" if self.remember_cwd else "off")
            )
        elif source == ":clear":
            self.lines.clear()
        elif source == ":help":
            self.add(HELP)
            from .legal import NOTICE
            self.add("Public beta. " + NOTICE)
        else:
            self.add("Unknown terminal command. Press F1 for help.", "error")
        self.sync()
        self.save_settings()

    def drain(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event["kind"]
            if kind == "done":
                self.worker.join()
                self.worker = None
                self.status = event["text"]
                self.sync()
                self.save_settings()
            elif kind == "graph":
                self.add(
                    'Graph created. Use graph export "plot.png", replace to save it.',
                    "warning",
                )
            elif kind == "progress":
                self.status = event["text"]
            elif kind in ("command", "output", "warning", "error", "translation"):
                prefix = {
                    "warning": "Warning: ",
                    "error": "Error: ",
                    "translation": "Backend: ",
                }.get(kind, "")
                self.add(prefix + event["text"], kind)

    def close(self, audit=None):
        if self.busy:
            self.engine.stop.set()
            self.worker.join()
            self.drain()
        self.save_settings()
        if audit:
            Path(audit).write_text(
                json.dumps(
                    {
                        "versions": self.engine.versions,
                        "notices": self.engine.notices,
                        "commands": self.engine.ledger,
                    },
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
        self.engine.close()


def workspace(screen, session):
    import curses

    curses.raw()  # Ctrl+C/Q become application keys, not terminal signals/flow control.
    screen.keypad(True)
    screen.timeout(100)
    try:
        curses.curs_set(1)
    except curses.error:
        pass
    attributes = {}
    if curses.has_colors():
        try:
            curses.use_default_colors()
            for i, (kind, color) in enumerate(
                (
                    ("error", curses.COLOR_RED),
                    ("warning", curses.COLOR_YELLOW),
                    ("command", curses.COLOR_CYAN),
                    ("translation", curses.COLOR_GREEN),
                ),
                1,
            ):
                curses.init_pair(i, color, -1)
                attributes[kind] = curses.color_pair(i)
        except curses.error:
            pass
    scroll, horizontal, confirm_quit = 0, 0, False

    def put(row, column, text, attribute=0, width=None):
        height, columns = screen.getmaxyx()
        if not (0 <= row < height and 0 <= column < columns - 1):
            return
        try:
            screen.addstr(
                row,
                column,
                cell_slice(text, 0, min(width or columns, columns - column - 1)),
                attribute,
            )
        except curses.error:
            pass

    while True:
        session.drain()
        height, width = screen.getmaxyx()
        screen.erase()
        if height < 10 or width < 45:
            put(0, 0, "Resize to at least 45 columns x 10 rows.")
            put(1, 0, "F10: quit; Ctrl+C: stop")
        else:
            put(
                0,
                0,
                f"StatBridge {__version__} | {session.dataset_status}"
                + (" | Unsaved data" if session.dirty else ""),
                curses.A_REVERSE,
            )
            put(1, 0, session.folder, curses.A_DIM)
            visible = height - 7
            scroll = max(0, min(scroll, max(0, len(session.lines) - visible)))
            end = len(session.lines) - scroll
            rows = list(session.lines)[max(0, end - visible) : end]
            for row, (text, kind) in enumerate(rows, 2):
                put(
                    row,
                    0,
                    cell_slice(text, horizontal, width - 1),
                    attributes.get(kind, 0),
                )
            hint = (
                "Tab complete | Up/Down history | PgUp/Dn scroll | F1 help | F10 quit"
            )
            if session.completions:
                hint = f"Completion {session.completion_index + 1}/{len(session.completions)}: Tab cycles, Enter runs, Esc dismisses"
            put(height - 4, 0, hint, curses.A_DIM)
            status = (
                "Discard unsaved dataset and quit? Y / N"
                if confirm_quit
                else session.status
            )
            put(height - 3, 0, status, curses.A_REVERSE)
            position = cell_width(safe_text(session.buffer[: session.cursor]))
            offset = max(0, position - width + 5)
            put(height - 2, 0, ". " + cell_slice(session.buffer, offset, width - 3))
            if (
                not session.busy
                and session.cursor == len(session.buffer)
                and not session.completions
            ):
                edits = session.suggestions.complete(session.buffer, session.cursor)
                if edits and edits[0].text.startswith(session.buffer):
                    put(
                        height - 2,
                        2 + position - offset,
                        edits[0].text[len(session.buffer) :],
                        curses.A_DIM,
                    )
            put(
                height - 1,
                0,
                f"History {'saved' if session.remember_history else 'session only'} | Folder {'remembered' if session.remember_cwd else 'not remembered'} | F7/F8 pan: {horizontal}",
                curses.A_DIM,
            )
            try:
                screen.move(height - 2, min(width - 2, 2 + position - offset))
            except curses.error:
                pass
        screen.refresh()
        try:
            key = screen.get_wch()
        except curses.error:
            continue
        if key == curses.KEY_RESIZE:
            continue
        if confirm_quit:
            if key in ("y", "Y"):
                return
            confirm_quit = False
            continue
        if key in (curses.KEY_F10, "\x11") or (
            key in ("\n", "\r") and session.buffer.strip() in (":quit", "exit")
        ):
            if session.busy:
                session.engine.stop.set()
                session.status = "Stop requested; wait for completion, then quit"
            elif session.engine.dirty:
                confirm_quit = True
            else:
                return
        elif key == "\x03":
            if session.busy:
                session.engine.stop.set()
                session.status = "Stop requested; waiting for current backend call"
            else:
                session.set_buffer("")
        elif key == curses.KEY_PPAGE:
            scroll += max(1, height - 7)
        elif key == curses.KEY_NPAGE:
            scroll = max(0, scroll - max(1, height - 7))
        elif key == curses.KEY_F7:
            horizontal = max(0, horizontal - 16)
        elif key == curses.KEY_F8:
            horizontal += 16
        elif key == curses.KEY_F1:
            session.add(HELP)
            scroll = 0
        elif session.busy:
            continue
        elif key == curses.KEY_F2:
            session.add("Variables: " + ", ".join(session.suggestions.variables))
            scroll = 0
        elif key == curses.KEY_F3:
            session.set_buffer('do ""', 4)
        elif key in ("\n", "\r"):
            session.submit(session.buffer)
            scroll = 0
        elif key == "\t":
            session.complete()
        elif key == curses.KEY_UP:
            session.recall(-1)
        elif key == curses.KEY_DOWN:
            session.recall(1)
        elif key == curses.KEY_LEFT:
            session.set_buffer(session.buffer, max(0, session.cursor - 1))
        elif key == curses.KEY_RIGHT:
            if session.cursor == len(session.buffer):
                edits = session.suggestions.complete(session.buffer, session.cursor)
                if edits and edits[0].text.startswith(session.buffer):
                    session.set_buffer(edits[0].text, edits[0].cursor)
            else:
                session.set_buffer(session.buffer, session.cursor + 1)
        elif key in (curses.KEY_HOME, "\x01"):
            session.set_buffer(session.buffer, 0)
        elif key in (curses.KEY_END, "\x05"):
            session.set_buffer(session.buffer)
        elif key in (curses.KEY_BACKSPACE, "\x7f", "\b") and session.cursor:
            session.set_buffer(
                session.buffer[: session.cursor - 1] + session.buffer[session.cursor :],
                session.cursor - 1,
            )
        elif key == curses.KEY_DC:
            session.set_buffer(
                session.buffer[: session.cursor] + session.buffer[session.cursor + 1 :],
                session.cursor,
            )
        elif key == "\x15":
            session.set_buffer("")
        elif key == "\x1b":
            session.completions = []
        elif isinstance(key, str) and key.isprintable():
            session.set_buffer(
                session.buffer[: session.cursor]
                + key
                + session.buffer[session.cursor :],
                session.cursor + 1,
            )


def main(cwd=None, audit=None, no_history=False, no_cwd=False, syntax="stata"):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(
            "Terminal mode needs an interactive terminal. Use --batch FILE.do for redirected input/output.",
            file=sys.stderr,
        )
        return 2
    try:
        import curses
    except ImportError:
        print(
            'Curses is unavailable. On Windows run: python -m pip install windows-curses',
            file=sys.stderr,
        )
        return 2
    # Choose a non-GUI plotting backend before the engine creates any figures.
    import matplotlib

    matplotlib.use("Agg")
    session = TerminalSession(cwd=cwd, no_history=no_history, no_cwd=no_cwd, syntax=syntax)
    try:
        curses.wrapper(workspace, session)
    except curses.error as exc:
        print(
            f"Terminal could not initialise or redraw: {exc}. Check TERM and terminal support.",
            file=sys.stderr,
        )
        return 2
    finally:
        session.close(audit)
    return 0
