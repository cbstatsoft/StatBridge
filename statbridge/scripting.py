# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Preflighted do-file blocks with scoped exit and source line diagnostics."""

from __future__ import annotations
from dataclasses import dataclass, field
import re
import pandas as pd
from .syntax import StataError, logical_lines


class DoExit(Exception):
    """Exit the current do-file, including nested loops/conditionals."""


@dataclass
class Node:
    line: int
    text: str
    kind: str = "command"
    children: list = field(default_factory=list)
    otherwise: list = field(default_factory=list)


def compile_script(source):
    lines = list(logical_lines(source))

    def block(position, depth=0):
        if depth > 20:
            raise StataError("Do-file block nesting exceeds 20 levels")
        nodes = []
        while position < len(lines):
            number, text = lines[position]
            if text == "}":
                if not depth:
                    raise StataError(f"line {number}: unexpected closing brace")
                return nodes, position + 1
            if text.startswith("else"):
                raise StataError(
                    f"line {number}: else without an immediately preceding if block"
                )
            opener = re.match(r"^(foreach|forvalues|if)\s+(.+)\{$", text)
            if opener:
                node = Node(number, text[:-1].strip(), opener[1])
                node.children, position = block(position + 1, depth + 1)
                if (
                    node.kind == "if"
                    and position < len(lines)
                    and lines[position][1].startswith("else")
                ):
                    n, other = lines[position]
                    if other == "else {":
                        node.otherwise, position = block(position + 1, depth + 1)
                    elif other.startswith("else if ") and other.endswith("{"):
                        # Parse an else-if as a nested conditional and retain the rest.
                        lines[position] = (n, other[5:])
                        nested, position = one_if(position, depth)
                        node.otherwise = [nested]
                    else:
                        raise StataError(
                            f"line {n}: expected else {{ or else if expression {{"
                        )
                nodes.append(node)
            else:
                if text.startswith(("if ", "foreach ", "forvalues ")):
                    raise StataError(
                        f"line {number}: control blocks require an opening brace at the end of their line"
                    )
                nodes.append(Node(number, text))
                position += 1
        if depth:
            raise StataError("Missing closing brace in do-file; no commands executed")
        return nodes, position

    def one_if(position, depth):
        number, text = lines[position]
        node = Node(number, text[:-1].strip(), "if")
        node.children, position = block(position + 1, depth + 1)
        if position < len(lines) and lines[position][1].startswith("else"):
            n, other = lines[position]
            if other == "else {":
                node.otherwise, position = block(position + 1, depth + 1)
            elif other.startswith("else if ") and other.endswith("{"):
                lines[position] = (n, other[5:])
                nested, position = one_if(position, depth + 1)
                node.otherwise = [nested]
            else:
                raise StataError(f"line {n}: malformed else block")
        return node, position

    nodes, _ = block(0)
    return nodes


def run_nodes(engine, nodes, echo=True):
    for node in nodes:
        if engine.stop.is_set():
            engine.emit("error", "Execution interrupted between commands.")
            return False
        text = engine.expand(node.text)
        if text == "exit":
            raise DoExit()
        if node.kind == "command":
            previous = engine.quiet
            if not echo:
                engine.quiet = True
            try:
                good = engine.execute(node.text, node.line)
            finally:
                engine.quiet = previous
            if not good:
                return False
            continue
        try:
            if node.kind == "if":
                value = engine.expr(text[3:].strip())
                if isinstance(value, pd.Series):
                    if value.empty:
                        raise StataError("if control expression has no observations")
                    engine.notice(
                        "IF_CONTROL",
                        "A variable expression in an if block tests its first observation, as Stata does. Use a command if qualifier to filter rows.",
                    )
                    value = value.iloc[0]
                if isinstance(value, str):
                    raise StataError("if control condition must be numeric")
                selected = (
                    node.children if pd.isna(value) or value != 0 else node.otherwise
                )
                if not run_nodes(engine, selected, echo):
                    return False
            else:
                name, values = engine.loop_values(text)
                for value in values:
                    engine.locals[name] = str(value)
                    if not run_nodes(engine, node.children, echo):
                        return False
        except DoExit:
            raise
        except Exception as exc:
            engine.scalars["_rc"] = exc.code if isinstance(exc, StataError) else 498
            engine.emit(
                "error", f"line {node.line}: {exc}\nr({engine.scalars['_rc']});"
            )
            return False
    return True
