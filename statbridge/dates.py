# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Stata numeric dates, with explicit masks and no locale-dependent inference."""

import calendar
import datetime as dt
import re
import numpy as np
import pandas as pd
from .syntax import StataError

EPOCH = dt.datetime(1960, 1, 1)
DATE_FUNCTIONS = {
    "date",
    "daily",
    "monthly",
    "quarterly",
    "clock",
    "mdy",
    "ym",
    "yq",
    "year",
    "month",
    "day",
    "dow",
    "dofm",
    "mofd",
    "dofq",
    "qofd",
    "dofc",
    "cofd",
}
MONTHS = {
    name.lower(): i
    for i in range(1, 13)
    for name in (calendar.month_name[i], calendar.month_abbr[i])
}


def date_call(name, args, index):
    counts = {
        "date": 2,
        "daily": 2,
        "monthly": 2,
        "quarterly": 2,
        "clock": 2,
        "mdy": 3,
        "ym": 2,
        "yq": 2,
    }
    if len(args) != counts.get(name, 1):
        raise StataError(f"Wrong number of arguments to {name}()")
    if name in ("date", "daily", "monthly", "quarterly", "clock"):
        if not isinstance(args[1], str):
            raise StataError("Date mask must be a quoted constant")
        allowed = {
            "date": ("YMD", "DMY", "MDY"),
            "daily": ("YMD", "DMY", "MDY"),
            "monthly": ("YM", "MY"),
            "quarterly": ("YQ", "QY"),
            "clock": ("YMDhms", "DMYhms", "MDYhms"),
        }
        if args[1] not in allowed[name]:
            raise StataError("Supported masks: " + ", ".join(allowed[name]))
    series = [
        a.reindex(index) if isinstance(a, pd.Series) else pd.Series(a, index=index)
        for a in args
    ]

    def one(values):
        try:
            if any(pd.isna(v) for v in values):
                return np.nan
            if name in ("date", "daily", "monthly", "quarterly", "clock"):
                string, mask = values
                tokens = re.findall(
                    r"\d+(?:\.\d+)?|[A-Za-z]+" if name == "clock" else r"\d+|[A-Za-z]+",
                    str(string),
                )
                if name in ("monthly", "quarterly"):
                    tokens = [t for t in tokens if t.lower() not in ("m", "q")]
                if len(tokens) != len(mask):
                    return np.nan
                parts = {}
                for key, value in zip(mask, tokens):
                    if key == "M" and value.lower() in MONTHS:
                        parts[key] = MONTHS[value.lower()]
                    else:
                        parts[key] = float(value) if key == "s" else int(value)
                if len(str(parts["Y"])) != 4:
                    return np.nan
                if name == "monthly":
                    return (
                        (parts["Y"] - 1960) * 12 + parts["M"] - 1
                        if 1 <= parts["M"] <= 12
                        else np.nan
                    )
                if name == "quarterly":
                    return (
                        (parts["Y"] - 1960) * 4 + parts["Q"] - 1
                        if 1 <= parts["Q"] <= 4
                        else np.nan
                    )
                sec = parts.get("s", 0)
                whole = int(sec)
                stamp = dt.datetime(
                    parts["Y"],
                    parts["M"],
                    parts["D"],
                    parts.get("h", 0),
                    parts.get("m", 0),
                    whole,
                    round((sec - whole) * 1e6),
                )
                delta = stamp - EPOCH
                return delta.total_seconds() * 1000 if name == "clock" else delta.days
            if name in ("mdy", "ym", "yq", "dofm", "dofq") and any(
                float(x) != int(float(x)) for x in values
            ):
                return np.nan
            v = float(values[0])
            if not np.isfinite(v):
                return np.nan
            if name == "mdy":
                return (
                    dt.datetime(int(values[2]), int(values[0]), int(values[1])) - EPOCH
                ).days
            if name == "ym":
                return (
                    (int(v) - 1960) * 12 + int(values[1]) - 1
                    if 1 <= float(values[1]) <= 12
                    else np.nan
                )
            if name == "yq":
                return (
                    (int(v) - 1960) * 4 + int(values[1]) - 1
                    if 1 <= float(values[1]) <= 4
                    else np.nan
                )
            if name == "cofd":
                return v * 86400000
            if name == "dofc":
                return np.floor(v / 86400000)
            if name in ("dofm", "dofq"):
                divisor = 12 if name == "dofm" else 4
                year = 1960 + int(np.floor(v / divisor))
                month = (int(v) % divisor) * (1 if divisor == 12 else 3) + 1
                return (dt.datetime(year, month, 1) - EPOCH).days
            stamp = EPOCH + dt.timedelta(days=v)
            return {
                "year": lambda: stamp.year,
                "month": lambda: stamp.month,
                "day": lambda: stamp.day,
                "dow": lambda: (stamp.weekday() + 1) % 7,
                "mofd": lambda: (stamp.year - 1960) * 12 + stamp.month - 1,
                "qofd": lambda: (stamp.year - 1960) * 4 + (stamp.month - 1) // 3,
            }[name]()
        except (ValueError, TypeError, OverflowError, KeyError):
            return np.nan

    values = [one(v) for v in zip(*(a.tolist() for a in series))]
    return pd.Series(values, index=index, dtype=float)


def display_date(value, fmt):
    if fmt not in ("%td", "%tm", "%tq", "%tc"):
        return None
    if pd.isna(value):
        return "."
    try:
        v = float(value)
        if fmt == "%td":
            d = EPOCH + dt.timedelta(days=v)
            return f"{d.day:02}{calendar.month_abbr[d.month].lower()}{d.year:04}"
        if fmt == "%tm":
            return f"{1960+int(np.floor(v/12)):04}m{int(v)%12+1}"
        if fmt == "%tq":
            return f"{1960+int(np.floor(v/4)):04}q{int(v)%4+1}"
        if fmt == "%tc":
            d = EPOCH + dt.timedelta(milliseconds=v)
            return f"{d.day:02}{calendar.month_abbr[d.month].lower()}{d.year:04} {d:%H:%M:%S}.{d.microsecond//1000:03}"
    except (ValueError, OverflowError, TypeError):
        return "."
    return None
