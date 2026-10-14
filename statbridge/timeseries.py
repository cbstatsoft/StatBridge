# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Gap-aware Stata time-series operators shared by expressions and designs."""

from __future__ import annotations
from collections import defaultdict
from math import comb
import re
import pandas as pd
from .syntax import StataError

TIME_TERM = re.compile(r"((?:[LFDSlfds]\d*)+)\.([A-Za-z_]\w*)")


def time_values(engine, term, frame=None):
    match = TIME_TERM.fullmatch(term)
    if not match:
        raise StataError(f"Invalid time-series operator: {term}")
    operators, name = match.groups()
    frame = engine.df if frame is None else frame
    if name not in engine.df:
        raise StataError(f"Variable {name} not found", 111)
    if not pd.api.types.is_numeric_dtype(engine.df[name]):
        raise StataError("Time-series operators require numeric data", 109)
    if engine.tsvar:
        entity, time = None, engine.tsvar
    elif engine.panel and engine.panel[1]:
        entity, time = engine.panel
    else:
        raise StataError("Declare tsset time or xtset panel time first")
    keys = [entity, time] if entity else [time]
    if engine.df[keys].isna().any().any() or engine.df.duplicated(keys).any():
        raise StataError(
            "Time index is missing or no longer unique; correct data and declare it again"
        )
    # Polynomial in the lag operator. D2=(1-L)^2; S2=1-L^2.
    poly = {0: 1}
    for op, num in re.findall(r"([LFDSlfds])(\d*)", operators):
        op = op.upper()
        n = int(num or 1)
        if n < 1 or n > 1000:
            raise StataError("Time-series operator order must be 1..1000")
        if op == "D" and n > 20:
            raise StataError("Difference order above 20 is not supported")
        terms = (
            {n: 1}
            if op == "L"
            else {-n: 1}
            if op == "F"
            else {0: 1, n: -1}
            if op == "S"
            else {j: (-1) ** j * comb(n, j) for j in range(n + 1)}
        )
        nxt = defaultdict(int)
        for a, x in poly.items():
            for b, y in terms.items():
                nxt[a + b] += x * y
        poly = {k: v for k, v in nxt.items() if v}
        if len(poly) > 4096:
            raise StataError("Time-series operator is too large")
    source = engine.df.set_index(keys)[name]
    out = pd.Series(0.0, index=frame.index)
    for lag, coefficient in poly.items():
        target_time = frame[time] - lag * engine.time_delta
        index = (
            pd.MultiIndex.from_arrays([frame[entity], target_time])
            if entity
            else pd.Index(target_time)
        )
        out += coefficient * pd.Series(
            source.reindex(index).to_numpy(), index=frame.index, dtype=float
        )
    return out
