# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""World Bank panel import and merge, adapted from cbstatsoft/dtabnk.

Conversion completes before the active dataset is replaced. No runtime installs.
"""

from dataclasses import dataclass
from pathlib import Path
import csv
import re
import polars as pl
import pandas as pd
from ._vendor import dtabnk as core
from .syntax import StataError, options, words, unquote
from .result_tables import atomic_write

LAYOUTS = ("auto", "wide", "wide_header_series", "long", "year_rows")
VALUE_OPTIONS = (
    "layout",
    "id",
    "yearcol",
    "valuecol",
    "seriescol",
    "sheet",
    "headerrow",
    "delimiter",
    "minfree",
    "lazy",
    "parquet",
    "aggregate",
    "rows",
    "saving",
    "version",
    "on",
    "join",
    "conflicts",
)
FLAGS = ("clear", "preview", "safe", "long", "merge", "replace", "noload")


def integer(o, name, default, minimum=0, maximum=2**31 - 1):
    value = o.get(name, default)
    if value is None:
        return None
    if isinstance(value, bool) or not re.fullmatch(r"\d+", str(value)):
        raise StataError(f"{name}() requires a whole number")
    value = int(value)
    if not minimum <= value <= maximum:
        raise StataError(f"{name}() must be between {minimum} and {maximum}")
    return value


def header_index(rows, hints=()):
    """Recognise actual panel headers, not a two-cell metadata preamble."""
    wanted = {core.sanitise_one(x).lower() for x in hints}
    for i, row in enumerate(rows):
        cells = [str(x or "").strip() for x in row]
        lower = {core.sanitise_one(x).lower() for x in cells if x}
        years = any(core.is_year_like(x) for x in cells)
        year_alias = bool(lower & {x.lower() for x in core.YEAR_ALIASES})
        value_alias = bool(lower & {x.lower() for x in core.VALUE_ALIASES})
        entity = bool(
            lower
            & {"country_name", "country", "country_code", "economy", "region", "id"}
        )
        if len(cells) >= 2 and (
            (wanted and wanted.issubset(lower))
            or years
            and entity
            or year_alias
            and value_alias
            or cells[0].lower() in {"year", "time", "date", "period"}
        ):
            return i
    raise ValueError(
        "Cannot detect the header in the first 100 rows; specify headerrow(0-based row)."
    )


class Reader(core.SourceReader):
    def __init__(self, read_options, sheet=None, hints=()):
        super().__init__(read_options)
        self.sheet = sheet
        self.hints = hints

    def _find_header_row(self, path):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            rows = []
            for row in csv.reader(handle, delimiter=self.options.delimiter):
                rows.append(row)
                if len(rows) >= 100:
                    break
        return header_index(rows, self.hints)

    def _read_csv(self, path, file_size, lazy):
        kw = dict(
            skip_rows=self._skip_rows(path),
            separator=self.options.delimiter,
            infer_schema=False,
            low_memory=True,
        )
        if lazy:
            core.print("Using lazy Polars CSV scanning.")
            return pl.scan_csv(path, **kw)
        core.MemoryManager.ensure_headroom(
            "CSV read",
            file_size,
            3,
            self.options.minimum_free_ram_mb,
            self.options.safe_mode,
        )
        return pl.read_csv(path, **kw)

    def _csv_to_parquet(self, source_path, parquet_path, file_size):
        frame = self._read_csv(source_path, file_size, True)
        core.strip_bottom_metadata(frame).sink_parquet(parquet_path, compression="zstd")

    def _read_excel_compat(self, path):
        # Read cells as strings so late '..' or text values cannot break inference.
        engine = "xlrd" if Path(path).suffix.lower() == ".xls" else "openpyxl"
        with pd.ExcelFile(path, engine=engine) as book:
            sheet = self.sheet if self.sheet is not None else book.sheet_names[0]
            if sheet not in book.sheet_names:
                raise ValueError(f"Worksheet not found: {sheet}")
            row = self.options.header_row
            if row is None:
                sample = pd.read_excel(
                    book,
                    sheet_name=sheet,
                    header=None,
                    nrows=100,
                    dtype=str,
                    keep_default_na=False,
                )
                row = header_index(sample.values.tolist(), self.hints)
            frame = pd.read_excel(
                book, sheet_name=sheet, header=row, dtype=str, keep_default_na=False
            )
        return pl.from_pandas(frame)


class Transformer(core.PanelTransformer):
    def __init__(
        self, transform_options, file_size, keep_long=False, aggregate="error"
    ):
        super().__init__(transform_options, file_size)
        self.keep_long = keep_long
        self.aggregate = aggregate
        self.labels = {}
        self.pivoted = False

    def _drop_code_columns(self, frame):
        # Country and indicator codes are useful explicit keys, never drop them.
        return frame

    def _can_pivot(self, frame):
        return not self.keep_long and super()._can_pivot(frame)

    def _pivot_and_sanitise(self, frame, index, columns):
        data = core.collect_frame(frame)
        keys = index + [columns]
        duplicates = data.select(keys).is_duplicated().sum()
        if duplicates and self.aggregate != "mean":
            raise ValueError(
                f"{duplicates} rows share entity/year/series keys. Resolve duplicates or explicitly use aggregate(mean)."
            )
        if (
            data[columns].null_count()
            or data.filter(pl.col(columns).str.strip_chars() == "").height
        ):
            raise ValueError(
                "Missing indicator names; specify seriescol() or correct the source."
            )
        if duplicates:
            core.print(f"Explicitly averaging {duplicates} rows with duplicate keys.")
        series = data[columns].unique(maintain_order=True).to_list()
        # Reserve index names before generating indicator names to prevent collisions.
        reserved = list(dict.fromkeys(index + ["Country", "Year"]))
        names = core.sanitise(reserved + series)[len(reserved) :]
        self.labels.update(dict(zip(names, series)))
        data = data.with_columns(
            pl.col(columns).replace_strict(dict(zip(series, names)))
        )
        cells = data.select(index).unique().height * max(1, len(series))
        core.MemoryManager.ensure_headroom(
            "dense indicator pivot",
            max(data.estimated_size(), cells * 16),
            3,
            self.options.minimum_free_ram_mb,
            self.options.safe_mode,
        )
        self.pivoted = True
        return data.pivot(
            on=columns,
            index=index,
            values="Value",
            aggregate_function="mean" if duplicates else None,
        )


@dataclass
class Conversion:
    frame: pl.DataFrame
    labels: dict
    layout: str


def convert(path, o):
    reserve = integer(o, "minfree", 512)
    read = core.ReadOptions(
        integer(o, "lazy", None, 1),
        integer(o, "parquet", None, 1),
        reserve,
        "safe" in o,
        str(o.get("delimiter", ",")),
        integer(o, "headerrow", None),
        True,
        False,
    )
    if len(read.delimiter.encode("utf-8")) != 1 or read.delimiter in '\r\n"':
        raise StataError("delimiter() must be one single-byte separator")
    source = Reader(
        read,
        o.get("sheet"),
        [str(o[k]) for k in ("id", "yearcol", "valuecol", "seriescol") if k in o],
    ).read(str(path))
    try:
        original = core.get_columns(source.frame)
        normal = core.sanitise(original)
        raw = dict(zip(normal, original))
        forward = dict(zip(original, normal))
        o = dict(o)
        for key in ("id", "yearcol", "valuecol", "seriescol"):
            if key in o and o[key] in forward:
                o[key] = forward[o[key]]
        frame = source.frame.rename(dict(zip(original, normal)))
        layout = core.detect_layout(
            frame,
            str(o.get("layout", "auto")),
            o.get("yearcol"),
            o.get("valuecol"),
            raw,
        )
        if layout not in LAYOUTS:
            raise StataError(
                "layout() must be auto, wide, wide_header_series, long or year_rows"
            )
        frame = frame.filter(
            ~pl.all_horizontal(
                [
                    pl.col(c).cast(pl.String).fill_null("").str.strip_chars() == ""
                    for c in normal
                ]
            )
        )
        # Explicit mappings must resolve exactly; no fallback to an unrelated column.
        for name in ("id", "yearcol", "valuecol", "seriescol"):
            if name in o and not (layout == "year_rows" and name == "id"):
                if core.find_column_name(frame, [str(o[name])]) is None:
                    raise ValueError(
                        f'{name}({o[name]}) was not found. Available: {", ".join(original)}'
                    )
        id_column = str(o.get("id", "Country_Name"))
        if layout != "year_rows":
            id_match = core.find_column_name(
                frame, [id_column] if "id" in o else ["Country_Name", "Country"]
            )
            if id_match is None:
                raise ValueError(
                    "No Country or Country Name column; specify id(source column)."
                )
            bad = core.collect_frame(
                frame.select(
                    (
                        pl.col(id_match).is_null()
                        | (pl.col(id_match).cast(pl.String).str.strip_chars() == "")
                    ).sum()
                )
            )[0, 0]
            if bad:
                raise ValueError(
                    f"{bad} source rows have missing entity IDs; correct or remove them."
                )
            frame = frame.with_columns(
                pl.col(id_match).cast(pl.String).str.strip_chars()
            )
            id_column = id_match
        tx = Transformer(
            core.TransformOptions(
                id_column,
                layout,
                o.get("yearcol"),
                o.get("valuecol"),
                o.get("seriescol"),
                reserve,
                "safe" in o,
            ),
            source.file_size_bytes,
            "long" in o,
            str(o.get("aggregate", "error")),
        )
        result = tx.transform(frame, raw)
        # In year_rows the original headers are entity VALUES, not variable names.
        if layout == "year_rows":
            entity = core.sanitise_one(id_column)
            result = result.with_columns(pl.col(entity).replace(raw))
        result = core.Exporter.prepare(result)
        if (
            not tx.pivoted
            and "Series" in result.columns
            and result.filter(
                pl.col("Series").is_null() | (pl.col("Series").str.strip_chars() == "")
            ).height
        ):
            raise ValueError(
                "Missing indicator names; correct the source or specify seriescol()."
            )
        if not result.height:
            raise ValueError("Conversion produced no annual observations.")
        entity = (
            "Country"
            if id_column in ("Country_Name", "Country")
            else core.sanitise_one(id_column)
        )
        keys = [entity, "Year"] + [
            c
            for c in ("Series", "Series_Code")
            if not tx.pivoted and c in result.columns
        ]
        duplicates = result.select(keys).is_duplicated().sum()
        if duplicates:
            if o.get("aggregate") != "mean":
                raise ValueError(
                    f"{duplicates} rows share panel keys {keys}. Resolve duplicates or use aggregate(mean)."
                )
            measures = [c for c in result.columns if c not in keys]
            result = result.group_by(keys, maintain_order=True).agg(
                [pl.col(c).mean() for c in measures]
            )
            core.print(
                f"Explicitly averaged {duplicates} rows with duplicate panel keys."
            )
        return Conversion(result.sort(keys), tx.labels, layout)
    finally:
        source.cleanup()


def write_dataset(engine, frame, path, replace=False, version=15, labels=None):
    suffix = path.suffix.lower()
    if suffix not in (".dta", ".sav", ".parquet", ".rdata"):
        raise StataError("Output must end in .dta, .sav, .parquet or .RData")
    if suffix == ".rdata":
        try:
            import pyreadr
        except ImportError as exc:
            raise StataError(
                'RData export needs the optional rdata extra: pip install "statbridge-qt[rdata]"'
            ) from exc

    def writer(tmp):
        if suffix == ".parquet":
            frame.write_parquet(tmp, compression="zstd")
        elif suffix == ".rdata":
            pyreadr.write_rdata(tmp, frame.to_pandas(), df_name="df")
        else:
            import pyreadstat

            names = {
                k: str(v)[:80] for k, v in (labels or {}).items() if k in frame.columns
            }
            if suffix == ".dta":
                pyreadstat.write_dta(frame, tmp, version=version, column_labels=names)
            else:
                pyreadstat.write_sav(frame, tmp, column_labels=names)

    atomic_write(engine, path, replace, writer)


class DatabankCommands:
    def cmd_dtabnk(self, args, opt):
        o = options(opt, VALUE_OPTIONS + FLAGS)
        inputs = words(args)
        if inputs and inputs[0] == "using":
            inputs.pop(0)
        if not inputs:
            raise StataError(
                'Syntax: dtabnk "source.csv" ["second.xlsx"], [merge clear preview]'
            )
        if len(inputs) > 1 and "merge" not in o:
            raise StataError(
                "Multiple sources require merge; use a do-file loop for separate conversions"
            )
        if "merge" in o and len(inputs) < 2:
            raise StataError("merge requires at least two sources")
        if any(k in o for k in ("on", "join", "conflicts")) and "merge" not in o:
            raise StataError("on(), join() and conflicts() require merge")
        if o.get("aggregate", "error") not in ("error", "mean"):
            raise StataError("aggregate() must be error or mean")
        if "preview" in o and any(k in o for k in ("saving", "replace", "noload")):
            raise StataError(
                "preview cannot write files; omit saving(), replace and noload"
            )
        if "noload" in o and "saving" not in o:
            raise StataError("noload requires saving()")
        if "replace" in o and "saving" not in o:
            raise StataError("replace requires saving()")
        loading = not any(k in o for k in ("preview", "noload"))
        if loading and self.dirty and "clear" not in o:
            raise StataError(
                "Data changed; specify clear to replace the active dataset", 4
            )
        count = integer(o, "rows", 10, 1, 1000)
        version = integer(o, "version", 15, 11, 15)
        paths = [self.path(x) for x in inputs]
        for path in paths:
            if not path.is_file():
                raise StataError(f"File not found: {path}", 601)
        output = self.path(str(o["saving"])) if "saving" in o else None
        if output is not None:
            if output in paths:
                raise StataError("Output cannot overwrite an input source")
            self.write_guard(output, "replace" in o)
        report = lambda msg: self.out(
            msg.replace("--merge-on", "on()").replace(
                "--merge-conflicts suffix", "conflicts(suffix)"
            )
        )
        token = core.reporter.set(report)
        try:
            merger = (
                core.PanelMerger(
                    words(str(o.get("on", "Country Year"))),
                    str(o.get("join", "outer")),
                    str(o.get("conflicts", "suffix")),
                    integer(o, "minfree", 512),
                    "safe" in o,
                )
                if "merge" in o
                else None
            )
            result = None
            labels = {}
            layouts = []
            for path in paths:
                if self.stop.is_set():
                    raise StataError("Conversion cancelled", 1)
                converted = convert(path, o)
                layouts.append(converted.layout)
                result = (
                    merger.add(result, converted.frame, str(path))
                    if merger
                    else converted.frame
                )
                labels.update(
                    {
                        merger.column_mapping.get(k, k) if merger else k: v
                        for k, v in converted.labels.items()
                    }
                )
            reserve = integer(o, "minfree", 512)
            core.MemoryManager.ensure_headroom(
                "StatBridge import/export",
                result.estimated_size(),
                4,
                reserve,
                "safe" in o,
            )
            if self.stop.is_set():
                raise StataError("Conversion cancelled", 1)
            # Allocate before any mutation or disk write so allocation failure preserves data.
            frame = result.to_pandas() if loading else None
            if output is not None:
                write_dataset(self, result, output, "replace" in o, version, labels)
                self.out(f"Wrote {output}")
            if loading:
                self.df = frame
                self.labels = {c: labels.get(c, c) for c in frame.columns}
                self.value_labels = {}
                self.label_sets = {}
                self.formats = {}
                self.file_label = "dtabnk panel import"
                self.filename = None
                self.panel = None
                self.tsvar = None
                self.changed()
                self.margins_result = None
            self.show_table(
                "dtabnk preview" if "preview" in o else "dtabnk panel",
                result.head(count).to_pandas(),
            )
            self.r = {"N": result.height, "k": result.width, "sources": len(paths)}
            self.out(
                f'{result.height:,} observations, {result.width} variables; layouts: {", ".join(layouts)}'
            )
            self.notice(
                "DTABNK",
                "StatBridge extension based on dtabnk. Annual panel conversion uses Polars. Non-numeric values become missing; review conversion diagnostics. Duplicate keys require explicit aggregate(mean). Preview converts the full source but does not replace data or write files. Import finally materialises a pandas dataset; memory estimates are not hard limits.",
            )
        except (
            ValueError,
            RuntimeError,
            MemoryError,
            pl.exceptions.PolarsError,
        ) as exc:
            raise StataError(str(exc), 498) from exc
        finally:
            core.reporter.reset(token)

    def cmd_export(self, args, opt):
        match = re.fullmatch(r"(sav|parquet|rdata)\s+using\s+(.+)", args)
        if not match:
            return super().cmd_export(args, opt)
        o = options(opt, ("replace",))
        path = self.path(match[2])
        if path.suffix.lower() != "." + match[1]:
            raise StataError(f"Use .{match[1]} for this export")
        frame = pl.from_pandas(self.df)
        core.MemoryManager.ensure_headroom("dataset export", frame.estimated_size(), 3)
        write_dataset(self, frame, path, "replace" in o, labels=self.labels)
        self.out(f"Wrote {path}")
        self.notice(
            "DTABNK_EXPORT",
            "Data and available variable labels are exported. These additional formats do not preserve the complete Stata dataset metadata or estimation state.",
        )
