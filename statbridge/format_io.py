# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Explicit, atomic tabular interchange shared by desktop and terminal commands."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd
import pyreadstat
from .syntax import StataError, options, qualifiers, unquote
from .result_tables import atomic_write

EXTENSIONS = {
    "sav": (".sav", ".zsav"),
    "por": (".por",),
    "sas": (".sas7bdat",),
    "xport": (".xpt", ".xport"),
    "rdata": (".rdata", ".rda"),
    "rds": (".rds",),
    "parquet": (".parquet", ".pq"),
    "feather": (".feather",),
    "arrow": (".arrow", ".ipc"),
    "delimited": (".csv", ".tsv", ".txt"),
    "json": (".json",),
    "jsonl": (".jsonl", ".ndjson"),
    "stata": (".dta",),
    "workbook": (".xlsx", ".xls", ".xlsm", ".xlsb", ".ods"),
    "sqlite": (".sqlite", ".sqlite3", ".db"),
    "mat": (".mat",),
    "hdf5": (".h5", ".hdf5"),
    "mtp": (".mtp",),
}
ALIASES = {
    "spss": "sav",
    "zsav": "sav",
    "sasxport": "xport",
    "rda": "rdata",
    "ipc": "arrow",
    "csv": "delimited",
    "tsv": "delimited",
    "dta": "stata",
    "ods": "workbook",
    "matlab": "mat",
    "hdf": "hdf5",
}
ARROW = {"parquet", "feather", "arrow"}
META_KEY = b"statbridge.metadata.v1"


def detect(path):
    ext = Path(path).suffix.lower()
    for kind, suffixes in EXTENSIONS.items():
        if ext in suffixes:
            return kind
    if ext in (".dta", ".xlsx"):
        return "stata" if ext == ".dta" else "excel"
    raise StataError("Unknown file extension; specify an import format explicitly")


def r_backend():
    try:
        import pyreadr

        return pyreadr
    except ImportError:
        raise StataError(
            'RData/RDS requires pyreadr. Install or repair with: python -m pip install "statbridge-qt[rdata]"'
        ) from None


def _empty_meta():
    return dict(labels={}, value_labels={}, formats={}, file_label="")


def _decode_meta(raw):
    """Treat embedded metadata as untrusted data, never executable objects."""
    if len(raw) > 16 * 1024 * 1024:
        raise StataError("StatBridge metadata exceeds 16 MB")
    try:
        obj = json.loads(raw)
        if obj["version"] != 1:
            raise ValueError("version")
        meta = _empty_meta()
        for key in ("labels", "formats"):
            if not isinstance(obj[key], dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in obj[key].items()
            ):
                raise ValueError(key)
            meta[key] = obj[key]
        if not isinstance(obj["file_label"], str):
            raise ValueError("file_label")
        meta["file_label"] = obj["file_label"]
        for col, pairs in obj["value_labels"].items():
            if not isinstance(col, str) or not isinstance(pairs, list):
                raise ValueError("value_labels")
            labels = {}
            for key, value in pairs:
                if not isinstance(key, (str, int, float)) or not isinstance(value, str):
                    raise ValueError("value_labels")
                labels[key] = value
            meta["value_labels"][col] = labels
        return meta
    except (ValueError, KeyError, TypeError, AttributeError):
        raise StataError("Invalid embedded StatBridge metadata") from None


def normalize(frame, meta, rename, notice):
    """Convert supported scalar columns to the engine's flat dataset contract."""
    old = list(frame.columns)
    names, used = [], set()
    for raw in old:
        name = str(raw)
        valid = bool(re.fullmatch(r"[A-Za-z_]\w{0,31}", name)) and name not in used
        if not valid and not rename:
            raise StataError(
                "Column names must be unique Stata identifiers; specify rename to sanitize them"
            )
        if not valid:
            stem = re.sub(r"\W", "_", name)
            if not stem or not re.match(r"[A-Za-z_]", stem):
                stem = "v_" + stem
            stem = stem[:32]
            name, i = stem, 2
            while name in used:
                suffix = "_" + str(i)
                name = stem[: 32 - len(suffix)] + suffix
                i += 1
        used.add(name)
        names.append(name)
    frame = frame.copy()
    frame.columns = names
    mapping = dict(zip(old, names))
    for key in ("labels", "value_labels", "formats"):
        meta[key] = {mapping[c]: v for c, v in meta[key].items() if c in mapping}
    if old != names:
        notice(
            "IO_RENAME",
            "Renamed source columns: "
            + ", ".join(f"{a!r} → {b}" for a, b in zip(old, names) if a != b),
        )
    for col in frame:
        s = frame[col]
        if isinstance(s.dtype, pd.CategoricalDtype):
            # Keep category values, never expose arbitrary category codes as numbers.
            frame[col] = s.astype(object)
            notice(
                "IO_FACTOR",
                "Factor values retained; unused levels and factor ordering are not retained.",
            )
            s = frame[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            if isinstance(s.dtype, pd.DatetimeTZDtype):
                s = s.dt.tz_convert("UTC").dt.tz_localize(None)
                notice(
                    "IO_TIMEZONE",
                    "Timezone-aware timestamps converted to UTC; timezone identity is lost.",
                )
            frame[col] = (s - pd.Timestamp("1960-01-01")).dt.total_seconds() * 1000
            meta["formats"][col] = "%tc"
            continue
        if pd.api.types.is_timedelta64_dtype(s):
            raise StataError(
                f"{col}: duration columns are unsupported; convert explicitly before import"
            )
        if pd.api.types.is_complex_dtype(s):
            raise StataError(f"{col}: complex numbers are unsupported")
        if pd.api.types.is_numeric_dtype(s):
            continue
        values = s.dropna().tolist()
        if any(isinstance(v, (list, dict, tuple, np.ndarray, bytes)) for v in values):
            raise StataError(
                f"{col}: nested or binary columns are unsupported; flatten before import"
            )
        if values and all(isinstance(v, (dt.datetime, dt.date)) for v in values):
            clock = any(isinstance(v, dt.datetime) for v in values)

            def date_number(value):
                if pd.isna(value):
                    return np.nan
                if isinstance(value, dt.datetime):
                    if value.tzinfo is not None:
                        value = value.astimezone(dt.timezone.utc).replace(tzinfo=None)
                        notice(
                            "IO_TIMEZONE",
                            "Timezone-aware timestamps converted to UTC; timezone identity is lost.",
                        )
                else:
                    value = dt.datetime.combine(value, dt.time())
                delta = value - dt.datetime(1960, 1, 1)
                return delta.total_seconds() * 1000 if clock else delta.days

            frame[col] = s.map(date_number)
            meta["formats"][col] = "%tc" if clock else "%td"
        elif values and all(isinstance(v, dt.time) for v in values):
            frame[col] = s.map(
                lambda v: (
                    np.nan
                    if pd.isna(v)
                    else ((v.hour * 60 + v.minute) * 60 + v.second) * 1000
                    + v.microsecond / 1000
                )
            )
            meta["formats"][col] = "%tcHH:MM:SS"
            notice(
                "IO_TIME",
                "Time-only values represented as milliseconds since midnight on 1 Jan 1960.",
            )
        elif not values or all(isinstance(v, str) for v in values):
            if s.isna().any():
                notice(
                    "IO_STRING_NULL",
                    "Null strings converted to empty strings, the Stata string-missing convention.",
                )
            frame[col] = s.fillna("")
        elif all(isinstance(v, (int, float, bool, np.number)) for v in values):
            if all(isinstance(v, (int, bool, np.integer)) for v in values):
                frame[col] = pd.array(
                    s,
                    dtype=(
                        "UInt64" if any(int(v) > 2**63 - 1 for v in values) else "Int64"
                    ),
                )
            else:
                frame[col] = pd.to_numeric(s)
        else:
            raise StataError(
                f"{col}: mixed or unsupported scalar types; convert explicitly before import"
            )
    return frame, meta


def read_table(path, kind, opts, notice):
    meta = _empty_meta()
    if kind == "stata":
        frame, source_meta = pyreadstat.read_dta(
            str(path), disable_datetime_conversion=True
        )
        meta.update(
            labels={k: v for k, v in source_meta.column_names_to_labels.items() if v},
            value_labels=source_meta.variable_value_labels or {},
            formats=source_meta.original_variable_types or {},
            file_label=source_meta.file_label or "",
        )
        notice(
            "IO_DTA",
            "Stata labels and date formats retained. Extended missing codes become ordinary missing; characteristics, notes and original storage widths are not retained.",
        )
    elif kind in ARROW:
        import pyarrow as pa
        import pyarrow.parquet as pq
        import pyarrow.feather as feather

        if kind == "parquet":
            table = pq.read_table(path)
        elif kind == "feather":
            table = feather.read_table(path)
        else:
            with pa.memory_map(str(path), "r") as source:
                try:
                    table = pa.ipc.open_file(source).read_all()
                except pa.ArrowInvalid:
                    source.seek(0)
                    table = pa.ipc.open_stream(source).read_all()
        for field in table.schema:
            if (
                pa.types.is_nested(field.type)
                or pa.types.is_binary(field.type)
                or pa.types.is_large_binary(field.type)
                or pa.types.is_decimal(field.type)
            ):
                raise StataError(
                    f"{field.name}: nested, binary and decimal Arrow types require explicit conversion"
                )
        raw = (table.schema.metadata or {}).get(META_KEY)
        if raw:
            meta = _decode_meta(raw)
        # Nullable integer types prevent missing values from forcing lossy float conversion.
        mapper = {
            pa.int8(): pd.Int8Dtype(),
            pa.int16(): pd.Int16Dtype(),
            pa.int32(): pd.Int32Dtype(),
            pa.int64(): pd.Int64Dtype(),
            pa.uint8(): pd.UInt8Dtype(),
            pa.uint16(): pd.UInt16Dtype(),
            pa.uint32(): pd.UInt32Dtype(),
            pa.uint64(): pd.UInt64Dtype(),
        }
        frame = table.to_pandas(types_mapper=mapper.get)
    elif kind in ("sav", "por", "sas", "xport"):
        reader = {
            "sav": pyreadstat.read_sav,
            "por": pyreadstat.read_por,
            "sas": pyreadstat.read_sas7bdat,
            "xport": pyreadstat.read_xport,
        }[kind]
        frame, source_meta = reader(str(path))
        meta["labels"] = {
            k: v for k, v in source_meta.column_names_to_labels.items() if v
        }
        meta["value_labels"] = source_meta.variable_value_labels or {}
        meta["file_label"] = source_meta.file_label or ""
        notice(
            "IO_STAT_METADATA",
            "Supported variable/value labels retained. User-defined missing values become ordinary missing. Original display formats, storage widths, notes and file-specific metadata are not retained; dates are converted to Stata units. SAS catalogs are not applied.",
        )
    elif kind in ("rdata", "rds"):
        backend = r_backend()
        objects = backend.read_r(str(path))
        selected = opts.get("object")
        if selected is not None:
            if selected not in objects:
                raise StataError(
                    "R object not found. Available: "
                    + ", ".join(str(x) for x in objects)
                )
            frame = objects[selected]
        elif len(objects) == 1:
            frame = next(iter(objects.values()))
        else:
            raise StataError(
                "Select object(name). Available: " + ", ".join(str(x) for x in objects)
            )
        if not isinstance(frame, pd.DataFrame):
            raise StataError(
                "Selected R object is not a supported two-dimensional table"
            )
        notice(
            "IO_R",
            "R import is limited to tables supported by pyreadr. Row names, arbitrary attributes and Stata labels are not retained; no R code is executed.",
        )
    elif kind == "mtp":
        from .legacy_io import read_mtp

        frame = read_mtp(path)
        notice(
            "IO_MTP",
            "Legacy Minitab portable numeric columns only. Values are read as stored, without the six-significant-digit rounding used by R foreign. Modern MTW/MPJ/MPX workspaces are unsupported.",
        )
    elif kind == "workbook":
        frame = pd.read_excel(
            path, sheet_name=opts.get("sheet", 0), engine="calamine", header=None
        )
        if frame.empty:
            raise StataError("Workbook sheet is empty")
        frame.columns = list(frame.iloc[0])
        frame = frame.iloc[1:].reset_index(drop=True).infer_objects(copy=False)
        notice(
            "IO_WORKBOOK",
            "First row used as variable names; cached formula values only. Workbook styling, macros, formulas and metadata are not imported. Mixed-type columns must be converted explicitly.",
        )
    elif kind == "sqlite":
        import sqlite3

        with sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro", uri=True
        ) as connection:
            names = [
                r[0]
                for r in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            ]
            name = opts.get("table")
            if name is None and len(names) == 1:
                name = names[0]
            if name not in names:
                raise StataError("Select table(name). Available: " + ", ".join(names))
            quoted = '"' + name.replace('"', '""') + '"'
            frame = pd.read_sql_query(
                "SELECT * FROM " + quoted, connection, dtype_backend="numpy_nullable"
            )
        notice(
            "IO_SQLITE",
            "SQLite table imported without indexes, constraints, labels or date formats. No views or arbitrary SQL are evaluated.",
        )
    elif kind in ("mat", "hdf5"):
        if kind == "mat":
            from scipy.io import loadmat

            try:
                data = {
                    k: v for k, v in loadmat(path).items() if not k.startswith("__")
                }
            except NotImplementedError:
                raise StataError(
                    "MATLAB v7.3 requires HDF5: import hdf5 using the .mat path. Only flat numeric vectors are supported."
                ) from None
        else:
            import h5py

            with h5py.File(path, "r") as source:
                group = source[opts.get("group", "/")]
                if not isinstance(group, h5py.Group):
                    raise StataError(
                        "group() must select a group of numeric vector datasets"
                    )
                data = {}
                for k in group:
                    if not isinstance(group.get(k, getlink=True), h5py.HardLink):
                        raise StataError("HDF5 external/soft links are not followed")
                    v = group[k]
                    if not isinstance(v, h5py.Dataset):
                        raise StataError(
                            "Select a flat group of vector datasets with group(path)"
                        )
                    if v.is_virtual or v.external:
                        raise StataError(
                            "HDF5 virtual/external datasets are not supported"
                        )
                    data[k] = v[()]
        vectors = {}
        for k, value in data.items():
            value = np.asarray(value)
            if (
                value.dtype.kind not in "biuf"
                or value.ndim > 2
                or (value.ndim == 2 and min(value.shape) > 1)
            ):
                raise StataError(
                    f"{k}: only real numeric vectors are supported; convert matrices, cells, structs and tables to equal-length columns first"
                )
            vectors[k] = value.reshape(-1)
        if not vectors or len({len(v) for v in vectors.values()}) != 1:
            raise StataError("Expected nonempty equal-length numeric vectors")
        frame = pd.DataFrame(vectors)
        notice(
            "IO_ARRAY",
            "Numeric vectors become columns. Array attributes, labels and date formats are not imported; arbitrary MATLAB tables/objects are unsupported.",
        )
    elif kind == "delimited":
        sep = opts.get("delimiter", "\t" if path.suffix.lower() == ".tsv" else ",")
        if sep == "\\t":
            sep = "\t"
        if len(sep) != 1:
            raise StataError("delimiter() must be one character or \\t")
        encoding = opts.get("encoding", "utf-8")
        frame = pd.read_csv(path, sep=sep, encoding=encoding)
        import csv

        with path.open(encoding=encoding, newline="") as stream:
            headers = next(
                (row for row in csv.reader(stream, delimiter=sep) if row), []
            )
        if len(headers) != len(frame.columns):
            raise StataError("Delimited file header does not match its data width")
        if headers:
            headers[0] = headers[0].removeprefix("\ufeff")
        frame.columns = headers
        notice(
            "IO_CSV",
            "Delimited text uses pandas type and missing-value inference, which can differ from Stata. Text files do not carry labels or date formats.",
        )
    else:
        with path.open(encoding="utf-8") as stream:
            records = (
                json.load(stream)
                if kind == "json"
                else [json.loads(line) for line in stream if line.strip()]
            )
        if not isinstance(records, list) or not all(
            isinstance(x, dict) for x in records
        ):
            raise StataError(
                "JSON must contain an array of flat records; JSONL one flat record per line"
            )
        frame = pd.DataFrame(records, dtype=object)
        notice(
            "IO_JSON",
            "JSON imports flat records only. Labels/date formats and original numeric storage types are absent.",
        )
    return normalize(frame, meta, "rename" in opts, notice)


def metadata(engine, columns):
    return dict(
        version=1,
        labels={
            c: v
            for c, v in engine.labels.items()
            if c in columns and isinstance(v, str)
        },
        formats={
            c: v
            for c, v in engine.formats.items()
            if c in columns and isinstance(v, str)
        },
        file_label=engine.file_label,
        value_labels={
            c: list(v.items()) for c, v in engine.value_labels.items() if c in columns
        },
    )


def statistical_frame(engine, frame):
    frame = frame.copy()
    for col in frame:
        s = frame[col]
        if pd.api.types.is_integer_dtype(s) and any(
            abs(int(x)) > 2**53 for x in s.dropna()
        ):
            raise StataError(
                f"{col}: integer exceeds exact double precision; use Parquet/Feather/Arrow or convert to string"
            )
        fmt = engine.formats.get(col, "")
        if fmt.startswith(("%td", "%tc")):

            def calendar(value):
                if pd.isna(value):
                    return None
                stamp = dt.datetime(1960, 1, 1) + dt.timedelta(
                    **(
                        {"days": float(value)}
                        if fmt.startswith("%td")
                        else {"milliseconds": float(value)}
                    )
                )
                return stamp.date() if fmt.startswith("%td") else stamp

            frame[col] = pd.Series(
                [calendar(v) for v in s], index=s.index, dtype=object
            )
        elif pd.api.types.is_numeric_dtype(s):
            frame[col] = s.astype(float)
            if fmt.startswith("%t"):
                engine.notice(
                    "IO_DATE_UNITS",
                    f"{col}: {fmt} exported as numeric Stata units; only daily/clock dates convert to calendar dates.",
                )
    return frame


class FormatIOCommands:
    def cmd_use(self, args, opt):
        path = self.path(args, ".dta")
        if path.suffix.lower() == ".dta":
            return super().cmd_use(args, opt)
        return self.cmd_import("auto " + args, opt)

    def cmd_import(self, args, opt):
        bits = args.split(None, 1)
        if len(bits) != 2:
            return super().cmd_import(args, opt)
        kind, text = bits
        kind = ALIASES.get(kind, kind)
        if kind not in EXTENSIONS and kind != "auto":
            return super().cmd_import(args, opt)
        text = text[6:].strip() if text.startswith("using ") else text
        path = self.path(text)
        if kind == "auto":
            kind = detect(path)
        allowed = ["clear", "preview", "rows", "rename"]
        if kind == "rdata":
            allowed += ["object"]
        if kind == "workbook":
            allowed += ["sheet"]
        if kind == "sqlite":
            allowed += ["table"]
        if kind == "hdf5":
            allowed += ["group"]
        if kind == "delimited":
            allowed += ["delimiter", "encoding"]
        o = {
            k: unquote(v) if isinstance(v, str) else v
            for k, v in options(opt, allowed).items()
        }
        if "rows" in o and "preview" not in o:
            raise StataError("rows() requires preview")
        rows = int(o.get("rows", 20))
        if not 1 <= rows <= 1000:
            raise StataError("Preview rows must be 1..1000")
        if self.dirty and "clear" not in o and "preview" not in o:
            raise StataError("Data changed; specify clear", 4)
        if not path.is_file():
            raise self.missing_file(path)
        frame, meta = read_table(path, kind, o, self.notice)
        if "preview" in o:
            self.show_table(
                f"Preview: {path.name} ({len(frame):,} observations, {len(frame.columns)} variables)",
                frame.head(rows),
            )
            self.notice(
                "IO_PREVIEW",
                "Preview leaves the dataset unchanged; the reader may load the complete file into memory.",
            )
            return
        self.df = frame
        self.labels, self.value_labels = meta["labels"], meta["value_labels"]
        self.formats, self.file_label = meta["formats"], meta["file_label"]
        self.label_sets = {}
        self.panel = self.tsvar = self.filename = None
        self.changed()
        self.out(
            f"Imported {len(frame):,} observations, {len(frame.columns)} variables from {path.name}"
        )

    def cmd_export(self, args, opt):
        kind = args.split(None, 1)[0] if args else ""
        kind = ALIASES.get(kind, kind)
        if kind not in EXTENSIONS:
            return super().cmd_export(args, opt)
        if kind == "mtp":
            raise StataError(
                "Minitab portable is import-only; export CSV, Excel or Stata instead"
            )
        if kind == "sas":
            raise StataError(
                'SAS7BDAT is import-only; export xport using "file.xpt" instead'
            )
        match = re.fullmatch(r"\S+\s+(.*?)\busing\s+(.+)", args)
        if not match:
            raise StataError(
                'Syntax: export format [varlist] [if/in] using "file", replace'
            )
        allowed = ["replace"]
        if kind in ARROW or kind in ("sav", "rdata", "rds"):
            allowed += ["compression"]
        if kind == "rdata":
            allowed += ["object"]
        if kind in ("xport", "stata"):
            allowed += ["version"]
        if kind == "workbook":
            allowed += ["sheet"]
        if kind == "sqlite":
            allowed += ["table"]
        if kind == "delimited":
            allowed += ["delimiter", "encoding"]
        o = {
            k: unquote(v) if isinstance(v, str) else v
            for k, v in options(opt, allowed).items()
        }
        path = self.path(match[2])
        if path.suffix.lower() not in EXTENSIONS[kind]:
            raise StataError(f"{kind} export expects: " + ", ".join(EXTENSIONS[kind]))
        head, q = qualifiers(match[1])
        cols = self.varlist(head, default=True)
        frame = self.df.loc[self.mask(q), cols].copy()
        if not cols:
            raise StataError("No variables to export")
        self.write_guard(path, "replace" in o)
        labels = {c: v for c, v in self.labels.items() if c in cols}
        values = {c: v for c, v in self.value_labels.items() if c in cols}
        compression = o.get("compression")
        if kind == "stata":
            version = int(o.get("version", 15))
            if version not in (13, 14, 15):
                raise StataError("Stata version() expects 13, 14 or 15")
            for c in frame:
                if pd.api.types.is_integer_dtype(frame[c]) and any(
                    abs(int(x)) > 2**53 for x in frame[c].dropna()
                ):
                    raise StataError(
                        f"{c}: integer exceeds exact double precision; use Parquet/Feather/Arrow"
                    )
                if pd.api.types.is_numeric_dtype(frame[c]):
                    frame[c] = frame[c].astype(float)
            writer = lambda tmp: pyreadstat.write_dta(
                frame,
                tmp,
                column_labels=labels,
                variable_value_labels=values,
                variable_format={c: v for c, v in self.formats.items() if c in cols},
                file_label=self.file_label,
                version=version,
            )
            self.notice(
                "IO_DTA",
                "Stata variable/value labels and date formats retained; extended missing distinctions, characteristics, notes and original storage widths are not preserved.",
            )
        elif kind in ARROW:
            import pyarrow as pa
            import pyarrow.parquet as pq
            import pyarrow.feather as feather

            choices = (
                ("none", "snappy", "gzip", "brotli", "lz4", "zstd")
                if kind == "parquet"
                else ("none", "lz4", "zstd")
            )
            compression = compression or ("snappy" if kind == "parquet" else "lz4")
            if compression not in choices:
                raise StataError("compression() expects " + ", ".join(choices))
            table = pa.Table.from_pandas(frame, preserve_index=False)
            md = dict(table.schema.metadata or {})
            md[META_KEY] = json.dumps(metadata(self, cols), ensure_ascii=False).encode(
                "utf-8"
            )
            table = table.replace_schema_metadata(md)

            def writer(tmp):
                if kind == "parquet":
                    pq.write_table(
                        table,
                        tmp,
                        compression=None if compression == "none" else compression,
                    )
                elif kind == "feather":
                    feather.write_feather(
                        table,
                        tmp,
                        compression=(
                            "uncompressed" if compression == "none" else compression
                        ),
                    )
                else:
                    with pa.OSFile(tmp, "wb") as sink:
                        with pa.ipc.new_file(
                            sink,
                            table.schema,
                            options=pa.ipc.IpcWriteOptions(
                                compression=(
                                    None if compression == "none" else compression
                                )
                            ),
                        ) as target:
                            target.write_table(table)

            self.notice(
                "IO_ARROW",
                "StatBridge embeds labels and Stata date formats in schema metadata. Other software may ignore or discard them; characteristics, named label sets and estimation state are not exported.",
            )
        elif kind in ("sav", "por", "xport", "rdata", "rds"):
            frame = statistical_frame(self, frame)
            if kind == "sav":
                compression = compression or (
                    "zlib" if path.suffix.lower() == ".zsav" else "none"
                )
                if compression not in ("none", "row", "zlib"):
                    raise StataError("SPSS compression() expects none, row or zlib")
                if path.suffix.lower() == ".zsav" and compression != "zlib":
                    raise StataError(".zsav requires compression(zlib)")
                writer = lambda tmp: pyreadstat.write_sav(
                    frame,
                    tmp,
                    column_labels=labels,
                    variable_value_labels=values,
                    file_label=self.file_label,
                    compress=compression == "zlib",
                    row_compress=compression == "row",
                )
            elif kind == "por":
                if len({c.upper() for c in cols}) != len(cols):
                    raise StataError(
                        "POR uppercases names; case-only name collisions must be renamed first"
                    )
                self.notice(
                    "IO_POR",
                    "SPSS portable uppercases variable names and has limited character encoding and numeric/date precision. Prefer SAV for Unicode and higher fidelity.",
                )
                writer = lambda tmp: pyreadstat.write_por(
                    frame, tmp, column_labels=labels, file_label=self.file_label
                )
            elif kind == "xport":
                version = int(o.get("version", 8))
                if version not in (5, 8):
                    raise StataError("XPORT version() expects 5 or 8")
                writer = lambda tmp: pyreadstat.write_xport(
                    frame,
                    tmp,
                    column_labels=labels,
                    file_label=self.file_label,
                    file_format_version=version,
                )
            else:
                backend = r_backend()
                for col in frame:
                    fmt = self.formats.get(col, "")
                    if fmt.startswith(("%td", "%tc")):
                        frame[col] = frame[col].map(
                            lambda v: (
                                None
                                if pd.isna(v)
                                else (
                                    v.isoformat(timespec="microseconds", sep=" ")
                                    if isinstance(v, dt.datetime)
                                    else v.isoformat()
                                )
                            )
                        )
                compression = compression or "none"
                if compression not in ("none", "gzip"):
                    raise StataError("R compression() expects none or gzip")
                self.notice(
                    "IO_R_DATES",
                    "pyreadr writes daily/clock dates as ISO text, not native R Date/POSIXct. Fractional seconds are included; parse explicitly in R. Monthly/quarterly dates remain numeric Stata units.",
                )
                obj = o.get("object", "dataset")
                if not re.fullmatch(r"[A-Za-z_]\w*", obj):
                    raise StataError("object() expects a simple identifier")
                writer = lambda tmp: (
                    backend.write_rdata(
                        tmp,
                        frame,
                        df_name=obj,
                        compress=None if compression == "none" else compression,
                        datetimeformat="%Y-%m-%d %H:%M:%S.%f",
                    )
                    if kind == "rdata"
                    else backend.write_rds(
                        tmp,
                        frame,
                        compress=None if compression == "none" else compression,
                        datetimeformat="%Y-%m-%d %H:%M:%S.%f",
                    )
                )
            self.notice(
                "IO_LOSS",
                "Statistical export uses double precision. SPSS SAV retains variable/value labels; POR and XPORT retain variable labels only; R files do not retain Stata labels. Missing-value distinctions, original widths, notes, display formats and arbitrary attributes are not preserved. R date writing follows pyreadr conventions.",
            )
        elif kind == "workbook":
            if path.suffix.lower() != ".ods":
                raise StataError(
                    "Legacy/binary/macro Excel files are import-only; export excel to .xlsx, or export ods to .ods"
                )
            writer = lambda tmp: frame.to_excel(
                tmp, engine="odf", index=False, sheet_name=o.get("sheet", "Sheet1")
            )
            self.notice(
                "IO_WORKBOOK",
                "ODS exports one sheet with numeric Stata dates; labels, formats, formulas and workbook styling are omitted.",
            )
        elif kind == "sqlite":
            import sqlite3

            name = o.get("table", "dataset")
            if not name or name.lower().startswith("sqlite_"):
                raise StataError(
                    "Choose a nonempty table name without the sqlite_ prefix"
                )

            def writer(tmp):
                with sqlite3.connect(tmp) as connection:
                    frame.to_sql(name, connection, index=False, if_exists="fail")

            self.notice(
                "IO_SQLITE",
                "Export creates a new database with one table; replace replaces the entire file, including other tables. Labels/date formats, indexes and constraints are omitted.",
            )
        elif kind in ("mat", "hdf5"):
            if any(not pd.api.types.is_numeric_dtype(frame[c]) for c in frame):
                raise StataError(
                    "MAT/HDF5 export currently supports real numeric columns only; select numeric variables"
                )
            if kind == "mat" and any(c.startswith("_") for c in frame):
                raise StataError(
                    "MATLAB variable names cannot start with underscore; rename first"
                )
            arrays = {}
            for c in frame:
                col = frame[c]
                if (
                    pd.api.types.is_integer_dtype(col)
                    and col.isna().any()
                    and any(abs(int(x)) > 2**53 for x in col.dropna())
                ):
                    raise StataError(
                        "Missing wide integers require Parquet/Feather/Arrow"
                    )
                arrays[c] = (
                    col.to_numpy(dtype=float, na_value=np.nan)
                    if col.isna().any()
                    else np.asarray(col.tolist())
                )

            def writer(tmp):
                if kind == "mat":
                    from scipy.io import savemat

                    savemat(
                        tmp,
                        arrays,
                        appendmat=False,
                        oned_as="column",
                        do_compression=True,
                    )
                else:
                    import h5py

                    with h5py.File(tmp, "w") as target:
                        for c, array in arrays.items():
                            target.create_dataset(c, data=array)

            self.notice(
                "IO_ARRAY",
                "Numeric columns exported as vectors; dates remain Stata units and labels/formats are omitted. MAT output is v5, not v7.3.",
            )
        elif kind == "delimited":
            sep = o.get("delimiter", "\t" if path.suffix.lower() == ".tsv" else ",")
            if sep == "\\t":
                sep = "\t"
            if len(sep) != 1:
                raise StataError("delimiter() must be one character or \\t")
            writer = lambda tmp: frame.to_csv(
                tmp, index=False, sep=sep, encoding=o.get("encoding", "utf-8")
            )
            self.notice(
                "IO_TEXT",
                "Text export loses labels and formats. Dates remain numeric Stata units; spreadsheet applications may interpret text beginning with formula characters.",
            )
        else:

            def scalar(x):
                if pd.isna(x):
                    return None
                if isinstance(x, np.generic):
                    return x.item()
                return x

            records = [
                {c: scalar(v) for c, v in row.items()}
                for row in frame.to_dict("records")
            ]

            def writer(tmp):
                with open(tmp, "w", encoding="utf-8") as target:
                    if kind == "json":
                        json.dump(records, target, ensure_ascii=False, allow_nan=False)
                    else:
                        for record in records:
                            target.write(
                                json.dumps(record, ensure_ascii=False, allow_nan=False)
                                + "\n"
                            )

            self.notice(
                "IO_JSON",
                "JSON writes flat records, numeric Stata dates and null missing values. Labels/formats are omitted; other JSON consumers may round large integers.",
            )
        atomic_write(self, path, "replace" in o, writer)
        self.out(
            f"Exported {len(frame):,} observations, {len(cols)} variables to {path}"
        )
