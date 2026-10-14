"""Minitab portable numeric columns, a documented legacy interchange format.

Layout informed by R foreign/src/minitab.c (Douglas M. Bates and Saikat DebRoy,
1999, GPL-2.0-or-later). This implementation is distributed under StatBridge's
GPL-3.0-or-later license. See THIRD_PARTY_NOTICES.md.
"""

import re
import numpy as np
import pandas as pd
from .syntax import StataError


def read_mtp(path):
    with open(path, encoding="ascii") as source:
        first = source.readline()
        if not first.startswith("Minitab Portable Worksheet "):
            raise StataError("Not a Minitab portable worksheet")
        columns, names = [], []
        lines = iter(source)
        for line in lines:
            if not line.strip():
                continue
            if not line.startswith("%") or len(line.rstrip("\n")) < 38:
                raise StataError("Corrupt Minitab column header")
            try:
                kind, number, count, dtype = (
                    int(line[a:b]) for a, b in ((1, 8), (8, 15), (15, 22), (22, 29))
                )
            except ValueError:
                raise StataError("Invalid Minitab column descriptor") from None
            if kind != 3 or dtype != 0:
                raise StataError(
                    "MTP import supports numeric columns only; constants, matrices and text columns must be converted first"
                )
            if count < 0:
                raise StataError("Invalid negative Minitab column length")
            name = line[30:38].rstrip() or f"C{number}"
            values = []
            while len(values) < count:
                try:
                    data = next(lines)
                except StopIteration:
                    raise StataError("Truncated Minitab column") from None
                for word in data.split():
                    if not re.fullmatch(
                        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?|\*", word
                    ):
                        raise StataError("Invalid Minitab numeric value")
                    values.append(
                        np.nan if word == "*" else float(re.sub("[Dd]", "E", word))
                    )
                if len(values) > count:
                    raise StataError("Too many values in Minitab column")
            names.append(name)
            columns.append(values)
        if not columns or len({len(x) for x in columns}) != 1:
            raise StataError(
                "Minitab columns must have equal lengths for a rectangular dataset"
            )
        return pd.DataFrame(dict(enumerate(columns))).T.set_axis(names, axis=0).T
