# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Portable session-local file navigation. No shell invocation or process chdir."""

from datetime import datetime
import fnmatch
import os
from pathlib import Path
import re
from .syntax import StataError, options, unquote, words

LIST_LIMIT = 1000
SCAN_LIMIT = 20000


class FileCommands:
    def missing_file(self, path):
        return StataError(
            f"File not found: {path}\nWorking directory: {self.cwd}\n"
            f'Use ls to list this folder, or findfile "{path.name}" to search its subfolders. '
            "ZIP extraction may have created another folder inside this one.",
            601,
        )

    def cmd_pwd(self, args, opt):
        if args or opt:
            raise StataError("Syntax: pwd")
        self.out(str(self.cwd))

    def cmd_cd(self, args, opt):
        options(opt, ())
        if not args:
            return self.cmd_pwd("", "")
        if args.strip() == "-":
            if self.previous_cwd is None:
                raise StataError("No previous working directory")
            path = self.previous_cwd
        else:
            path = self.path(args)
        if not path.is_dir():
            raise StataError(
                f"Directory not found: {path}\nWorking directory: {self.cwd}\nUse ls to see available folders.",
                601,
            )
        self.previous_cwd, self.cwd = self.cwd, path
        self.out(str(path))

    def cmd_mkdir(self, args, opt):
        o = options(opt, ("parents",))
        if not args:
            raise StataError('Syntax: mkdir "folder" [, parents]')
        path = self.path(args)
        try:
            path.mkdir(parents="parents" in o)
        except FileExistsError:
            raise StataError(f"Already exists: {path}", 602)
        except OSError as exc:
            raise StataError(f"Could not create directory {path}: {exc}", 603)
        self.out(f"Created {path}")

    @staticmethod
    def file_size(size):
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024

    def cmd_ls(self, args, opt):
        o = options(opt, ("all",))
        include_hidden = "all" in o
        parts = words(args)
        while parts and parts[0].startswith("-"):
            flag = parts.pop(0)
            if flag == "--":
                break
            if not re.fullmatch(r"-[alh]+", flag):
                raise StataError(
                    'Supported ls flags: -a, -l, -h; or use ls "path", all'
                )
            include_hidden |= "a" in flag
        if len(parts) > 1:
            raise StataError(
                "Specify one path or pattern; quote paths containing spaces"
            )
        raw = unquote(parts[0]) if parts else "."
        path = self.path(raw)
        pattern = None
        if path.is_dir():
            directory = path
        elif path.exists():
            directory, pattern = path.parent, path.name
        elif any(c in path.name for c in "*?["):
            directory, pattern = path.parent, path.name
        else:
            raise self.missing_file(path)
        if not directory.is_dir():
            raise self.missing_file(directory)
        records = []
        truncated = False
        scanned = 0
        try:
            with os.scandir(directory) as entries:
                for item in entries:
                    if self.stop.is_set():
                        raise StataError("Directory listing stopped", 1)
                    scanned += 1
                    if scanned > SCAN_LIMIT:
                        truncated = True
                        break
                    if (
                        not include_hidden
                        and item.name.startswith(".")
                        and not (pattern and pattern.startswith("."))
                    ):
                        continue
                    if pattern and not fnmatch.fnmatch(item.name, pattern):
                        continue
                    try:
                        isdir = item.is_dir(follow_symlinks=False)
                        info = item.stat(follow_symlinks=False)
                        kind = (
                            "DIR" if isdir else "LINK" if item.is_symlink() else "FILE"
                        )
                        size = "-" if isdir else self.file_size(info.st_size)
                        modified = datetime.fromtimestamp(info.st_mtime).strftime(
                            "%Y-%m-%d %H:%M"
                        )
                        records.append(
                            (
                                not isdir,
                                item.name.casefold(),
                                f"{kind:4} {size:>10} {modified}  {item.name}{'/' if isdir else ''}",
                            )
                        )
                    except OSError:
                        records.append(
                            (
                                True,
                                item.name.casefold(),
                                f"???? {item.name} (unavailable)",
                            )
                        )
                    if len(records) >= LIST_LIMIT:
                        truncated = True
                        break
        except OSError as exc:
            raise StataError(f"Cannot list {directory}: {exc}", 603)
        records.sort(key=lambda x: x[:2])
        self.r = {"N": len(records), "truncated": int(truncated)}
        self.out(
            f"Working directory: {self.cwd}\nListing: {directory}"
            + (f" / {pattern}" if pattern else "")
        )
        self.out(
            "\n".join(row[2] for row in records) if records else "(No matching entries)"
        )
        self.out(
            f"{len(records)} entries shown."
            + (" Listing limited; narrow the path/pattern." if truncated else "")
        )

    def cmd_findfile(self, args, opt):
        o = options(opt, ("depth",))
        self.notice(
            "FIND_FILE",
            "StatBridge findfile searches under the working directory; it does not implement Stata's ado-path search.",
        )
        pattern = unquote(args)
        if not pattern or "/" in pattern or "\\" in pattern:
            raise StataError(
                'Syntax: findfile "filename-or-pattern" [, depth(4)]; searches from the working directory'
            )
        try:
            depth_limit = int(o.get("depth", 4))
        except ValueError:
            raise StataError("depth() must be an integer from 0 to 12")
        if not 0 <= depth_limit <= 12:
            raise StataError("depth() must be between 0 and 12")
        todo = [(self.cwd, 0)]
        matches, scanned, skipped = [], 0, 0
        limited = False
        while todo and not limited:
            folder, depth = todo.pop()
            try:
                with os.scandir(folder) as items:
                    for item in items:
                        if self.stop.is_set():
                            raise StataError("File search stopped", 1)
                        scanned += 1
                        if scanned > SCAN_LIMIT or len(matches) >= LIST_LIMIT:
                            limited = True
                            break
                        try:
                            if item.is_dir(follow_symlinks=False):
                                if depth < depth_limit:
                                    todo.append((Path(item.path), depth + 1))
                            elif item.is_file(
                                follow_symlinks=False
                            ) and fnmatch.fnmatch(item.name, pattern):
                                matches.append(Path(item.path))
                        except OSError:
                            skipped += 1
            except OSError:
                skipped += 1
        matches.sort(key=lambda p: str(p).casefold())
        self.r = {"N": len(matches), "truncated": int(limited), "skipped": skipped}
        if len(matches) == 1:
            self.r["fn"] = str(matches[0])
        self.out(f"Searching under {self.cwd}, through {depth_limit} subfolder levels")
        for path in matches:
            self.out(str(path.relative_to(self.cwd)))
        if len(matches) == 1:
            self.out(f'To work in the containing folder:\ncd "{matches[0].parent}"')
        self.out(
            f"{len(matches)} matching files."
            + (
                " Search limited by entry cap; narrow the working directory."
                if limited
                else ""
            )
            + (f" {skipped} inaccessible entries/folders skipped." if skipped else "")
        )
        if not matches:
            raise StataError(
                f"No matching file within the search limits: {pattern}", 601
            )
