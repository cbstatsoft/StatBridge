# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Bounded local path completion for file-argument positions."""

import os
from pathlib import Path
import re


def path_completions(text, cursor, cwd):
    if cwd is None:
        return None
    left, right = text[:cursor], text[cursor:]
    match = re.match(
        r"^\s*(?:(?:quietly|qui|capture|cap|noisily)\s+)*(cd|chdir|ls|dir|do|run|use|save|mkdir)\s+(.*)$",
        left,
    )
    if not match:
        match = re.match(
            r"^\s*(?:(?:quietly|qui|capture|cap|noisily)\s+)*(import\s+(?:excel|delimited|auto|spss|sav|zsav|por|sas|xport|sasxport|rdata|rda|rds|parquet|feather|arrow|ipc|json|jsonl|workbook|ods|sqlite|mat|matlab|hdf5|hdf|mtp|stata|dta|csv|tsv)(?:\s+using)?|export\s+(?:excel|delimited|results|spss|sav|zsav|por|sas|xport|sasxport|rdata|rda|rds|parquet|feather|arrow|ipc|json|jsonl|workbook|ods|sqlite|mat|matlab|hdf5|hdf|mtp|stata|dta|csv|tsv)\s+(?:[A-Za-z_][\w*? -]*?\s+)?using|graph\s+export)\s+(.*)$",
            left,
        )
    if not match:
        match = re.match(r'^\s*(?:(?:quietly|qui|capture|cap|noisily)\s+)*dtabnk\s+(?:using\s+)?((?:(?:"[^"]*"|[^\s",]+)\s+)*)(.*)$', left)
        if match:
            prefix, arg = match.groups()
            # Rebase to a synthetic single-path match while preserving prior paths.
            offset = match.start(2)
            # Source inputs have different extensions; handled below instead.
            command = 'dtabnk'
            start = offset
        else:
            return None
    else:
        command, arg = match.groups()
        start = match.start(2)
    if command in ("ls", "dir"):
        flags = re.match(r"(?:(?:-[alh]+|--)\s+)*", arg)[0]
        start += len(flags)
        arg = arg[len(flags) :]
    if "$" in arg or "`" in arg or any(c in arg for c in "*?"):
        return None
    quoted = arg.startswith('"')
    if quoted:
        if '"' in arg[1:]:
            return None
        typed = arg[1:]
    else:
        if "," in arg:
            return None
        typed = arg
    if os.name == "nt":
        typed = typed.replace("\\", "/")
    head, sep, leaf = typed.rpartition("/")
    prefix = head + sep
    directory = Path(prefix or ".").expanduser()
    if not directory.is_absolute():
        directory = Path(cwd) / directory
    entries = []
    try:
        with os.scandir(directory) as scan:
            for i, item in enumerate(scan):
                if i >= 5000 or len(entries) >= 200:
                    break
                if item.name.startswith(".") and not leaf.startswith("."):
                    continue
                name = item.name.casefold() if os.name == "nt" else item.name
                partial = leaf.casefold() if os.name == "nt" else leaf
                if not name.startswith(partial) or any(c in item.name for c in '\n\r"'):
                    continue
                try:
                    isdir = item.is_dir()
                except OSError:
                    continue
                if not isdir:
                    if command in ("cd", "chdir", "mkdir"):
                        continue
                    extension = (
                        ".do"
                        if command in ("do", "run")
                        else ".dta"
                        if command == "save"
                        else None
                    )
                    from .format_io import EXTENSIONS, ALIASES
                    if command == "use" or command.startswith("import auto"):
                        extension = tuple(x for exts in EXTENSIONS.values() for x in exts)
                    elif command.startswith(("import ", "export ")) and len(command.split()) > 1 and ALIASES.get(command.split()[1], command.split()[1]) in EXTENSIONS:
                        extension = EXTENSIONS[ALIASES.get(command.split()[1], command.split()[1])]
                    if command == "dtabnk":
                        extension = (".csv", ".xlsx", ".xls")
                    elif "excel" in command:
                        extension = ".xlsx"
                    elif "delimited" in command:
                        extension = (".csv", ".tsv", ".txt")
                    elif "results" in command:
                        extension = (".csv", ".html", ".htm", ".tex")
                    elif command.startswith("graph"):
                        extension = (".png", ".pdf", ".svg")
                    if extension and not item.name.lower().endswith(extension):
                        continue
                entries.append((not isdir, item.name.casefold(), item.name, isdir))
    except OSError:
        return []
    if quoted:
        end = right.find('"')
        suffix = right[end + 1 :] if end >= 0 else ""
    else:
        remaining = re.match(r'[^\s,"]*', right)[0]
        suffix = right[len(remaining) :]
    results = []
    for _, _, name, isdir in sorted(entries):
        value = '"' + prefix + name + ("/" if isdir else "") + '"'
        full = text[:start] + value + suffix
        position = start + len(value) - (1 if isdir else 0)
        results.append((full, position))
    return results
