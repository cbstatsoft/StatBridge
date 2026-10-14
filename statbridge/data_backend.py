# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Polars kernels with pandas boundaries and auditable backend selection.

Only columns used by a kernel cross the boundary. Row-selection kernels return
positions so untouched columns, labels and dtypes never undergo conversion.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl
import pyarrow as pa
from .syntax import StataError

AUTO_MIN_ROWS = 100_000


class DataBackend:
    def __init__(self, engine):
        self.engine = engine

    def record(self, operation, backend, reason):
        if self.engine.ledger and self.engine.ledger[-1]["status"] == "running":
            self.engine.ledger[-1].setdefault("data_backends", []).append(
                {"operation": operation, "backend": backend, "reason": reason}
            )
        self.engine.emit("translation", f"↳ {operation}: {backend} ({reason})")

    def frame(self, df, columns, operation, numeric=()):
        mode = self.engine.data_backend
        if mode == "pandas" or (mode == "auto" and len(df) < AUTO_MIN_ROWS):
            self.record(
                operation,
                "pandas",
                "requested"
                if mode == "pandas"
                else "small dataset; avoid conversion overhead",
            )
            return None
        columns = list(dict.fromkeys(columns))
        reason = None
        for c in columns:
            dtype = df[c].dtype
            if (
                isinstance(dtype, pd.CategoricalDtype)
                or pd.api.types.is_datetime64_any_dtype(dtype)
                or pd.api.types.is_timedelta64_dtype(dtype)
                or pd.api.types.is_complex_dtype(dtype)
            ):
                reason = f"unsupported accelerated dtype in {c}: {dtype}"
                break
        if not reason and any(
            not pd.api.types.is_numeric_dtype(df[c]) for c in numeric
        ):
            reason = "aggregation acceleration requires numeric source variables"
        if not reason:
            try:
                converted = pl.from_pandas(df[columns], nan_to_null=True)
                if any(
                    t.is_nested() or t == pl.Object or t == pl.Binary
                    for t in converted.dtypes
                ):
                    reason = "unsupported accelerated object type"
            except (
                pa.ArrowException,
                pl.exceptions.PolarsError,
                TypeError,
                ValueError,
            ) as exc:
                reason = f"conversion is not supported: {exc}"
        if reason:
            if mode == "polars":
                raise StataError(
                    "Polars backend: "
                    + reason
                    + ". Use set databackend pandas for this operation."
                )
            self.record(operation, "pandas", reason)
            return None
        self.record(
            operation,
            "polars",
            "requested" if mode == "polars" else f"at least {AUTO_MIN_ROWS:,} rows",
        )
        return converted

    def sort(self, df, keys, ascending=True):
        frame = self.frame(df, keys, "sort")
        if frame is None:
            return df.sort_values(
                keys, ascending=ascending, kind="stable", na_position="last"
            )
        # Rename keys locally so no user variable can collide with the row index.
        names = [f"k{i}" for i in range(len(keys))]
        frame = (
            frame.select(keys).rename(dict(zip(keys, names))).with_row_index("__row")
        )
        descending = (
            not ascending if isinstance(ascending, bool) else [not a for a in ascending]
        )
        positions = frame.sort(
            names, descending=descending, nulls_last=True, maintain_order=True
        )["__row"].to_numpy()
        return df.iloc[positions]

    def duplicates(self, df, keys):
        frame = self.frame(df, keys, "duplicates")
        if frame is None:
            return df.duplicated(keys, keep=False).to_numpy(), df.duplicated(
                keys
            ).to_numpy()
        if not keys:
            return np.zeros(len(df), dtype=bool), np.zeros(len(df), dtype=bool)
        row = pl.struct(pl.all())
        flags = frame.select(
            row.is_duplicated().alias("all"),
            (~row.is_first_distinct()).alias("surplus"),
        )
        return flags["all"].to_numpy(), flags["surplus"].to_numpy()

    @staticmethod
    def aggregate(source, fun):
        col = pl.col(source)
        if fun == "count":
            return col.count().cast(pl.Int64)
        if fun == "std":
            return col.std(ddof=1)
        if fun in ("first", "last"):
            return getattr(col.drop_nulls(), fun)()
        return getattr(col, fun)()

    def collapse(self, df, keys, aggregations):
        sources = [source for source, _ in aggregations.values()]
        frame = self.frame(df, keys + sources, "collapse", numeric=sources)
        if frame is None:
            if keys:
                return (
                    df.groupby(keys, dropna=False, sort=True)
                    .agg(**aggregations)
                    .reset_index()
                )

            def scalar(source, fun):
                if fun in ("first", "last"):
                    observed = df[source].dropna()
                    return (
                        observed.iloc[0 if fun == "first" else -1]
                        if len(observed)
                        else np.nan
                    )
                return df[source].agg(fun)

            return pd.DataFrame(
                [
                    {
                        name: scalar(source, fun)
                        for name, (source, fun) in aggregations.items()
                    }
                ]
            )
        expressions = [
            self.aggregate(source, fun).alias(name)
            for name, (source, fun) in aggregations.items()
        ]
        result = (
            frame.group_by(keys).agg(expressions).sort(keys, nulls_last=True)
            if keys
            else frame.select(expressions)
        )
        output = result.to_pandas()
        for key in keys:
            if output[key].dtype == object:
                output[key] = output[key].where(output[key].notna(), np.nan)
        return output

    def transform(self, df, keys, source, fun):
        frame = self.frame(
            df, keys + [source], "egen grouped aggregate", numeric=[source]
        )
        if frame is None:
            return df.groupby(keys, dropna=False)[source].transform(fun)
        values = frame.select(self.aggregate(source, fun).over(keys).alias("__result"))[
            "__result"
        ].to_numpy()
        return pd.Series(values, index=df.index)
