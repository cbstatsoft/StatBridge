# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Logos: deterministic English and predicate-logic syntax for StatBridge.

This is a documented, deliberately bounded command language, not an LLM or an
open-ended natural-language interpreter. Unrecognised or ambiguous statements
are rejected before the statistical engine is called.
"""
from __future__ import annotations

import re
from .syntax import StataError

NAME = r"[A-Za-z_][A-Za-z_0-9]*"
VARS = rf"{NAME}(?:\s*(?:,|\+|\band\b|\s)\s*{NAME})*"
_EXPR_SPLIT = re.compile(r'("(?:[^"]|"")*")')


def _identifiers(text):
    text = re.sub(r"\s*(?:,|\+|\band\b)\s*", " ", text.strip(), flags=re.I)
    names = text.split()
    if not names or not all(re.fullmatch(NAME, name, flags=re.ASCII) for name in names):
        raise StataError("Logos expects plain variable names separated by spaces, commas or 'and'")
    if len(names) != len(set(names)):
        raise StataError("Logos: duplicate variable names are ambiguous")
    return " ".join(names)


def _predicate(text):
    """Translate logical connectives without changing quoted string literals."""
    text = text.strip()
    if not text or "\n" in text or ";" in text:
        raise StataError("Logos: a where predicate must be a single nonempty expression")
    output = []
    for part in _EXPR_SPLIT.split(text):
        if part.startswith('"'):
            output.append(part)
            continue
        part = re.sub(
            rf"\b({NAME})\s+is\s+not\s+missing\b",
            r"!missing(\1)", part, flags=re.I
        )
        part = re.sub(
            rf"\b({NAME})\s+is\s+missing\b",
            r"missing(\1)", part, flags=re.I
        )
        part = re.sub(r"\bis\s+at\s+least\b|\bat\s+least\b", ">=", part, flags=re.I)
        part = re.sub(r"\bis\s+at\s+most\b|\bat\s+most\b", "<=", part, flags=re.I)
        part = re.sub(r"\bis\s+greater\s+than\b|\bgreater\s+than\b", ">", part, flags=re.I)
        part = re.sub(r"\bis\s+less\s+than\b|\bless\s+than\b", "<", part, flags=re.I)
        part = re.sub(r"\bis\s+not\s+equal\s+to\b|\bnot\s+equal\s+to\b", "!=", part, flags=re.I)
        part = re.sub(r"\bis\s+equal\s+to\b|\bequals\b|\bequal\s+to\b", "==", part, flags=re.I)
        part = part.translate(str.maketrans({"∧": "&", "∨": "|", "¬": "!", "≥": ">=", "≤": "<=", "≠": "!=", "＝": "=="}))
        part = re.sub(r"\band\b", "&", part, flags=re.I)
        part = re.sub(r"\bor\b", "|", part, flags=re.I)
        part = re.sub(r"\bnot\s+(?=\()", "!", part, flags=re.I)
        # Lone = is a comparison in predicate logic. Never rewrite !=, <=, >=, ==.
        part = re.sub(r"(?<![!<>=])=(?!=)", "==", part)
        if re.search(r"\b(?:and|or|not)\b", part, re.I):
            raise StataError("Logos: write not(...) or use ∧, ∨ and ¬ for logical negation")
        output.append(part)
    return "".join(output)


def _split_where(text):
    parts = re.split(r"\s+(?:where|such\s+that)\s+", text, maxsplit=1, flags=re.I)
    return parts[0].strip(), (" if " + _predicate(parts[1]) if len(parts) == 2 else "")


def translate_logos(statement):
    """Return a single canonical StatBridge command, or a clear syntax error."""
    source = statement.strip()
    if not source or len(source) > 8192 or "\n" in source or ";" in source:
        raise StataError("Logos expects one command (at most 8192 characters)")
    source = source.rstrip(".").strip()
    if not source:
        raise StataError("Empty Logos statement")
    if re.fullmatch(r"(?:show|list)\s+(?:variables|columns)", source, re.I):
        return "describe"
    if re.fullmatch(r"(?:describe|show)\s+(?:data|dataset)", source, re.I):
        return "describe"
    if re.fullmatch(r"(?:count\s+(?:rows|observations)|how\s+many\s+(?:rows|observations))", source, re.I):
        return "count"
    # Bounded quantification is over rows in the active dataset only.
    m = re.fullmatch(
        r"(?:∀\s*rows\s*:\s*|for\s+all\s+rows\s*[, :]\s*|every\s+row\s+satisfies\s+)(.+)",
        source, re.I
    )
    if m:
        return "assert " + _predicate(m[1])
    m = re.fullmatch(
        r"(?:∃\s*(?:row|rows)\s*:\s*|there\s+exists\s+(?:a\s+)?row\s+(?:where|such\s+that)\s+|exists\s+(?:a\s+)?row\s+(?:where|such\s+that)\s+)(.+)",
        source, re.I
    )
    if m:
        return "logosexists " + _predicate(m[1])
    m = re.fullmatch(r"(?:count\s+(?:rows|observations)|how\s+many\s+(?:rows|observations))\s+(?:where|such\s+that)\s+(.+)", source, re.I)
    if m:
        return "count if " + _predicate(m[1])
    m = re.fullmatch(r"(keep|drop)\s+(?:rows|observations)\s+(?:where|such\s+that)\s+(.+)", source, re.I)
    if m:
        return m[1].lower() + " if " + _predicate(m[2])
    m = re.fullmatch(r"(?:summarize|summarise|summary\s+of|describe\s+variables?)\s+(.+)", source, re.I)
    if m:
        body, where = _split_where(m[1])
        return "summarize " + _identifiers(body) + where
    m = re.fullmatch(r"(?:mean|average)\s+of\s+(.+)", source, re.I)
    if m:
        body, where = _split_where(m[1])
        return "mean " + _identifiers(body) + where
    m = re.fullmatch(r"(?:list|show)\s+(?:rows\s+with\s+|values\s+of\s+)(.+)", source, re.I)
    if m:
        body, where = _split_where(m[1])
        return "list " + _identifiers(body) + where
    m = re.fullmatch(r"(?:regress|estimate\s+linear\s+regression\s+of)\s+("+NAME+r")\s+on\s+(.+)", source, re.I)
    if m:
        body, where = _split_where(m[2])
        return "regress " + m[1] + " " + _identifiers(body) + where
    m = re.fullmatch(r"fit\s+(linear|logistic|probit)\s+(?:model|regression)\s+("+NAME+r")\s*~\s*(.+)", source, re.I)
    if m:
        body, where = _split_where(m[3])
        command = {"linear": "regress", "logistic": "logit", "probit": "probit"}[m[1].lower()]
        return command + " " + m[2] + " " + _identifiers(body) + where
    m = re.fullmatch(r"(?:logistic\s+regression|logit)\s+("+NAME+r")\s+on\s+(.+)", source, re.I)
    if m:
        body, where = _split_where(m[2])
        return "logit " + m[1] + " " + _identifiers(body) + where
    m = re.fullmatch(r"(?:create|generate)\s+("+NAME+r")\s+(?:as|from)\s+(.+)", source, re.I)
    if m:
        return "generate " + m[1] + " = " + _predicate(m[2])
    m = re.fullmatch(r"let\s+("+NAME+r")\s*:=\s*(.+)", source, re.I)
    if m:
        return "generate " + m[1] + " = " + _predicate(m[2])
    m = re.fullmatch(r"(?:tabulate|frequency\s+of)\s+("+NAME+r")", source, re.I)
    if m:
        return "tabulate " + m[1]
    m = re.fullmatch(r"(?:correlate|correlation\s+of)\s+(.+)", source, re.I)
    if m:
        return "correlate " + _identifiers(m[1])
    m = re.fullmatch(r"(?:plot\s+histogram\s+of|histogram\s+of)\s+("+NAME+r")", source, re.I)
    if m:
        return "histogram " + m[1]
    m = re.fullmatch(r"(?:predict|save)\s+(fitted\s+values|residuals)\s+as\s+("+NAME+r")", source, re.I)
    if m:
        return "predict " + m[2] + (", residuals" if m[1].lower()=="residuals" else ", xb")
    m = re.fullmatch(r"(?:help|explain)\s+("+NAME+r")", source, re.I)
    if m:
        return "help " + m[1]
    raise StataError(
        "Logos could not interpret this statement. Use 'help logos' for its "
        "documented grammar, or prefix a Stata command with 'stata:'. "
        "Logos never guesses an unsupported analysis."
    )
