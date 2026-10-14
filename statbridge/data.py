# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
from __future__ import annotations
import re
import numpy as np
import pandas as pd
import pyreadstat
from scipy import stats
from .syntax import StataError, options, qualifiers, words, unquote


class DataCommands:
    @staticmethod
    def write_guard(path, replace):
        if path.exists() and not replace:
            raise StataError(f"File already exists: {path}; specify replace", 602)
        if not path.parent.is_dir():
            raise StataError(f"Directory not found: {path.parent}", 601)

    def read_data(self, path):
        if not path.is_file():
            raise self.missing_file(path)
        if path.suffix.lower() != ".dta":
            raise StataError("Expected a .dta file; use import delimited for CSV")
        df, meta = pyreadstat.read_dta(
            str(path),
            apply_value_formats=False,
            user_missing=True,
            disable_datetime_conversion=True,
        )
        if meta.missing_user_values:
            self.notice(
                "DTA_MISSING",
                "Extended missing values .a-.z are converted to ordinary missing; distinctions will not survive export.",
            )
            for c, tags in meta.missing_user_values.items():
                df[c] = pd.to_numeric(
                    df[c].mask(df[c].isin(tags), np.nan), errors="raise"
                )
        self.notice(
            "DTA_METADATA",
            "Variable/value labels and display formats are retained. Dataset characteristics, notes, sort markers, strL storage and original storage widths are not guaranteed to round-trip. Dates remain Stata numeric units.",
        )
        return df, meta

    def cmd_use(self, args, opt):
        o = options(opt, ("clear",))
        if self.dirty and "clear" not in o:
            raise StataError("Data in memory changed; specify clear to replace", 4)
        df, meta = self.read_data(self.path(args, ".dta"))
        self.df = df
        self.labels = meta.column_names_to_labels.copy()
        self.value_labels = meta.variable_value_labels.copy()
        self.formats = meta.original_variable_types.copy()
        self.file_label = meta.file_label or ""
        self.panel = None
        self.tsvar = None
        self.label_sets = dict(meta.value_labels)
        self.changed()
        self.filename = self.path(args, ".dta")
        self.dirty = False
        self.out(
            f"{len(df):,} observations, {len(df.columns)} variables loaded from {self.filename.name}"
        )

    def cmd_save(self, args, opt):
        o = options(opt, ("replace", "version"))
        path = self.path(args, ".dta") if args else self.filename
        if path is None:
            raise StataError("Specify a filename")
        self.write_guard(path, "replace" in o)
        version = int(o.get("version", 15))
        if version not in (13, 14, 15):
            raise StataError("Supported write versions: 13, 14, 15")
        self.notice(
            "DTA_WRITE",
            "ReadStat writes the selected Stata format. Original storage widths/characteristics/notes are not preserved; numeric values use double precision. Date formats are retained without calendar conversion.",
        )
        # Write beside destination first so a failed export cannot corrupt an existing file.
        import tempfile, os

        fd, tmp = tempfile.mkstemp(suffix=".dta", dir=path.parent)
        os.close(fd)
        try:
            data = self.df.copy()
            for c in data:
                if pd.api.types.is_bool_dtype(data[c]):
                    data[c] = data[c].astype(float)
            pyreadstat.write_dta(
                data,
                tmp,
                file_label=self.file_label,
                column_labels=self.labels,
                variable_value_labels=self.value_labels,
                variable_format=self.formats,
                version=version,
            )
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        self.filename = path
        self.dirty = False
        self.out(f"Saved {path}")

    def cmd_import(self, args, opt):
        o = options(opt, ("clear", "delimiter", "encoding"))
        if not args.startswith("delimited "):
            raise StataError("Only import delimited is implemented")
        if self.dirty and "clear" not in o:
            raise StataError("Data changed; specify clear", 4)
        path = args[len("delimited ") :]
        if path.startswith("using "):
            path = path[6:]
        df = pd.read_csv(
            self.path(path),
            sep=o.get("delimiter", ","),
            encoding=o.get("encoding", "utf-8"),
        )
        if any(not re.fullmatch(r"[A-Za-z_]\w{0,31}", str(c)) for c in df.columns):
            raise StataError(
                "CSV headers must be unique Stata-compatible variable names"
            )
        self.notice(
            "CSV",
            "pandas type inference and missing-string recognition may differ from import delimited in Stata.",
        )
        self.df = df
        self.labels = {}
        self.value_labels = {}
        self.formats = {}
        self.file_label = ""
        self.panel = None
        self.tsvar = None
        self.filename = None
        self.changed()
        self.out(f"Imported {len(df):,} observations")

    def cmd_export(self, args, opt):
        o = options(opt, ("replace", "delimiter"))
        if not args.startswith("delimited using "):
            raise StataError('Syntax: export delimited using "file.csv", replace')
        p = self.path(args[len("delimited using ") :])
        self.write_guard(p, "replace" in o)
        self.df.to_csv(p, index=False, sep=o.get("delimiter", ","))
        self.out(f"Exported {p}")

    def cmd_clear(self, args, opt):
        if args not in ("", "all") or opt:
            raise StataError("Syntax: clear [all]")
        self.df = pd.DataFrame()
        self.labels = {}
        self.value_labels = {}
        self.formats = {}
        self.label_sets = {}
        self.file_label = ""
        self.panel = None
        self.tsvar = None
        self.filename = None
        self.changed()
        self.dirty = False
        if args == "all":
            self.locals = {}
            self.globals = {}
            self.scalars = {}
            self.stored = {}
            self.r = {}
            self.preserved = None

    def cmd_set(self, args, opt):
        if opt:
            raise StataError("set does not take comma options")
        parts = args.split()
        if len(parts) != 2:
            raise StataError("Syntax: set obs|seed|level|more|databackend value")
        key, value = parts
        if key == "databackend":
            if value not in ("auto", "polars", "pandas"):
                raise StataError("databackend must be auto, polars or pandas")
            self.data_backend = value
            self.out(
                f"Data backend: {value}. Applies to sort, gsort, duplicates, collapse and grouped egen."
            )
        elif key == "obs":
            n = int(value)
            if n < len(self.df) or n < 0:
                raise StataError("set obs cannot reduce observation count")
            self.df = self.df.reindex(range(n))
            self.changed()
        elif key == "seed":
            self.rng = np.random.default_rng(int(value))
            self.notice(
                "RNG",
                "Seed sets NumPy PCG64, not Stata’s generator. Identical seed numbers do not produce identical draws.",
            )
        elif key == "level":
            level = float(value)
            if not 0 < level < 100:
                raise StataError("Confidence level must be between 0 and 100")
            self.level = level
        elif key == "more" and value in ("on", "off"):
            self.notice(
                "PAGINATION", "Output is scrollable; Stata pagination is not used."
            )
        else:
            raise StataError(f"Unsupported setting: {args}")

    def cmd_describe(self, args, opt):
        options(opt, ())
        cols = self.varlist(args, default=True)
        self.out(
            f"Observations: {len(self.df):,}   Variables: {len(self.df.columns)}\n"
            + pd.DataFrame(
                [
                    {
                        "variable": c,
                        "type": str(self.df[c].dtype),
                        "format": self.formats.get(c, ""),
                        "label": self.labels.get(c, ""),
                    }
                    for c in cols
                ]
            ).to_string(index=False)
        )

    def cmd_codebook(self, args, opt):
        options(opt, ())
        self.out(
            "\n".join(
                f"{c}: {self.df[c].dtype}, missing={self.df[c].isna().sum()}, unique={self.df[c].nunique()}\n  {self.df[c].dropna().unique()[:8]}"
                for c in self.varlist(args, default=True)
            )
        )

    def cmd_list(self, args, opt):
        options(opt, ())
        head, q = qualifiers(args)
        frame = self.df.loc[self.mask(q), self.varlist(head, default=True)]
        self.out(frame.head(500).rename(index=lambda x: x + 1).to_string())
        if len(frame) > 500:
            self.out(
                f"Display truncated at 500 of {len(frame):,} rows; use in or the Data tab."
            )

    def cmd_count(self, args, opt):
        options(opt, ())
        head, q = qualifiers(args)
        if head:
            raise StataError("count takes only if/in qualifiers")
        self.r = {"N": int(self.mask(q).sum())}
        self.out(self.r["N"])

    def cmd_summarize(self, args, opt):
        from .weights import extract_weight, summarize_weighted

        if extract_weight(args)[1] is not None:
            return summarize_weighted(self, args, opt)
        o = options(opt, ("detail", "meanonly"))
        head, q = qualifiers(args)
        frame = self.df.loc[self.mask(q)]
        rows = []
        for c in self.varlist(head, default=True):
            if not pd.api.types.is_numeric_dtype(frame[c]):
                continue
            x = frame[c].dropna()
            n = len(x)
            row = {
                "Variable": c,
                "Obs": n,
                "Mean": x.mean(),
                "Std. dev.": x.std(ddof=1),
                "Min": x.min(),
                "Max": x.max(),
            }
            rows.append(row)
            self.r = {
                "N": n,
                "mean": x.mean(),
                "sd": x.std(ddof=1),
                "Var": x.var(ddof=1),
                "min": x.min(),
                "max": x.max(),
                "sum": x.sum(),
                "sum_w": n,
            }
            if "detail" in o and n:
                ps = [1, 5, 10, 25, 50, 75, 90, 95, 99]
                vals = np.percentile(x, ps, method="averaged_inverted_cdf")
                self.r.update({f"p{p}": float(v) for p, v in zip(ps, vals)})
                self.r.update(
                    skewness=float(stats.skew(x, bias=True)),
                    kurtosis=float(stats.kurtosis(x, fisher=False, bias=True)),
                )
                self.out(
                    f"{c}\n"
                    + pd.Series({f"{p}%": v for p, v in zip(ps, vals)}).to_string()
                    + f"\nSkewness {self.r['skewness']:.6g}; Kurtosis {self.r['kurtosis']:.6g}"
                )
        if "meanonly" not in o:
            self.out(pd.DataFrame(rows).to_string(index=False))

    def cmd_generate(self, args, opt):
        self.assign(args, opt, False)

    def cmd_replace(self, args, opt):
        self.assign(args, opt, True)

    def assign(self, args, opt, replace):
        options(opt, ())
        head, q = qualifiers(args)
        m = re.fullmatch(
            r"(?:(double|float|byte|int|long|str\d+)\s+)?([A-Za-z_]\w*)\s*=\s*(.+)",
            head,
        )
        if not m:
            raise StataError("Syntax: generate/replace name = expression [if ...]")
        storage, name, expression = m.groups()
        if replace:
            if storage:
                raise StataError("Storage type is not accepted by replace")
            if name not in self.df:
                raise StataError(f"Variable {name} not found", 111)
        else:
            self.newvar(name)
        value = self.expr(expression)
        mask = self.mask(q)
        value = (
            value.reindex(self.df.index)
            if isinstance(value, pd.Series)
            else pd.Series(value, index=self.df.index)
        )
        isstr = pd.api.types.is_string_dtype(value) or value.dtype == object
        if storage and storage.startswith("str"):
            if not isstr:
                raise StataError("String storage requires string expression")
            if value.fillna("").str.len().max() > int(storage[3:]):
                raise StataError(
                    "String exceeds declared width; truncation is not performed"
                )
        elif storage and isstr:
            raise StataError("Numeric storage requires numeric expression")
        if not isstr and storage != "double":
            self.notice(
                "STORAGE",
                "In-memory numeric columns use float64; Stata float/integer rounding and overflow are not emulated. String widths are validated but not stored as fixed-width types.",
            )
        if replace and isstr != not_numeric(self.df[name]):
            raise StataError("type mismatch", 109)
        new = self.df.copy()
        if not replace:
            new[name] = "" if isstr else np.nan
        if not isstr:
            new[name] = new[name].astype(float)
            value = value.astype(float)
        new.loc[mask, name] = value.loc[mask]
        self.df = new
        self.changed()
        self.out(f"{int(mask.sum()):,} observations assigned to {name}")

    def cmd_egen(self, args, opt):
        o = options(opt, ("by",))
        head, q = qualifiers(args)
        m = re.fullmatch(r"(\w+)\s*=\s*(\w+)\((.*)\)", head)
        if not m:
            raise StataError("Syntax: egen new = function(varlist), by(group)")
        name, fun, source = m.groups()
        self.newvar(name)
        mask = self.mask(q)
        df = self.df.loc[mask]
        funcs = {
            "mean": "mean",
            "sum": "sum",
            "total": "sum",
            "sd": "std",
            "min": "min",
            "max": "max",
            "median": "median",
            "count": "count",
        }
        cols = self.varlist(source)
        if fun == "group":
            if "by" in o:
                raise StataError("by() not allowed with group()")
            valid = df[cols].notna().all(axis=1) & ~df[cols].eq("").any(axis=1)
            values = pd.Series(np.nan, index=df.index)
            values.loc[valid] = (
                pd.factorize(pd.MultiIndex.from_frame(df.loc[valid, cols]), sort=True)[
                    0
                ]
                + 1
            )
        elif fun in ("rowmean", "rowtotal"):
            self.varlist(source, numeric=True)
            if "by" in o:
                raise StataError("by() is not supported for row functions")
            values = df[cols].mean(axis=1) if fun == "rowmean" else df[cols].sum(axis=1)
        elif fun in funcs and len(cols) == 1:
            if fun == "count" and not_numeric(df[cols[0]]):
                df = df.copy()
                df[cols[0]] = df[cols[0]].replace("", None)
            keys = self.varlist(str(o["by"])) if "by" in o else None
            if keys:
                values = self.data_ops.transform(df, keys, cols[0], funcs[fun])
            else:
                values = pd.Series(df[cols[0]].agg(funcs[fun]), index=df.index)
        else:
            raise StataError("Unsupported egen function or arguments")
        self.df[name] = values.reindex(self.df.index)
        self.changed()

    def cmd_drop(self, args, opt):
        self.keepdrop(args, opt, False)

    def cmd_keep(self, args, opt):
        self.keepdrop(args, opt, True)

    def keepdrop(self, args, opt, keep):
        options(opt, ())
        head, q = qualifiers(args)
        if head and q:
            raise StataError("Specify variables OR if/in")
        if q:
            self.df = self.df.loc[self.mask(q) if keep else ~self.mask(q)].copy()
        elif head:
            cols = self.varlist(head)
            self.df = self.df[cols].copy() if keep else self.df.drop(columns=cols)
        else:
            raise StataError("Specify variables or a qualifier")
        self.changed()

    def cmd_rename(self, args, opt):
        options(opt, ())
        parts = args.split()
        if len(parts) != 2:
            raise StataError("Syntax: rename old new")
        old, new = parts
        old = self.varlist(old)[0]
        self.newvar(new)
        self.df = self.df.rename(columns={old: new})
        if self.tsvar == old:
            self.tsvar = new
        for d in (self.labels, self.value_labels, self.formats):
            if old in d:
                d[new] = d.pop(old)
        if self.panel:
            self.panel = tuple(new if p == old else p for p in self.panel)
        self.changed()

    def cmd_order(self, args, opt):
        options(opt, ())
        cols = self.varlist(args)
        self.df = self.df[cols + [c for c in self.df if c not in cols]]
        self.changed()

    def cmd_sort(self, args, opt):
        options(opt, ())
        cols = self.varlist(args)
        if not cols:
            raise StataError("Specify sort variables")
        self.df = self.data_ops.sort(self.df, cols)
        self.changed()
        self.notice(
            "SORT",
            "Ties use stable input order, which can differ from Stata sort tie ordering.",
        )

    def cmd_gsort(self, args, opt):
        options(opt, ())
        cols = []
        asc = []
        for token in args.split():
            cols.extend(self.varlist(token.lstrip("+-")))
            asc.append(not token.startswith("-"))
        if len(cols) != len(asc):
            raise StataError("Use explicit variable names with gsort")
        self.df = self.data_ops.sort(self.df, cols, ascending=asc)
        self.changed()
        self.notice(
            "SORT",
            "Stable ties and missing-last ordering are used, including descending sorts; Stata ordering can differ.",
        )

    def cmd_duplicates(self, args, opt):
        o = options(opt, ("force", "generate"))
        sub, _, vs = args.partition(" ")
        if "generate" in o and sub != "tag":
            raise StataError("generate() requires duplicates tag")
        cols = self.varlist(vs, default=True)
        duplicate, surplus = self.data_ops.duplicates(self.df, cols)
        if sub == "tag":
            if "generate" not in o or "force" in o:
                raise StataError("Syntax: duplicates tag [varlist], generate(name)")
            self.newvar(o["generate"])
            self.df[o["generate"]] = (
                self.df.groupby(cols, dropna=False)[cols[0]].transform("size") - 1
            )
            self.changed()
        elif sub == "report":
            self.out(
                f"{int(duplicate.sum())} observations in duplicate groups; {int(surplus.sum())} surplus observations."
            )
        elif sub == "list":
            self.out(self.df.loc[duplicate].head(500).to_string())
        elif sub == "drop":
            if vs and "force" not in o:
                raise StataError("Specify force to drop based on a subset of columns")
            self.df = self.df.loc[~surplus]
            self.changed()
        else:
            raise StataError("Syntax: duplicates report|list|drop [varlist]")

    def cmd_isid(self, args, opt):
        options(opt, ())
        cols = self.varlist(args)
        if (
            not cols
            or self.df[cols].isna().any().any()
            or self.df[cols].eq("").any().any()
            or self.df.duplicated(cols).any()
        ):
            raise StataError(
                "Variables do not uniquely identify nonmissing observations", 459
            )
        self.out("Variables uniquely identify observations.")

    def cmd_assert(self, args, opt):
        options(opt, ())
        head, q = qualifiers(args)
        from .syntax import Expression

        value = Expression(self).truth(self.expr(head))
        failed = int((~value & self.mask(q)).sum())
        if failed:
            raise StataError(f"{failed} contradictions", 9)

    def cmd_preserve(self, args, opt):
        if args or opt:
            raise StataError("Syntax: preserve")
        if self.preserved is not None:
            raise StataError("Already preserved", 621)
        self.preserved = self.snapshot()

    def cmd_restore(self, args, opt):
        if args or opt:
            raise StataError("Syntax: restore")
        if self.preserved is None:
            raise StataError("Nothing to restore", 622)
        self.load_snapshot(self.preserved)
        self.preserved = None

    def cmd_append(self, args, opt):
        options(opt, ())
        if not args.startswith("using "):
            raise StataError('Syntax: append using "data.dta"')
        other, meta = self.read_data(self.path(args[6:], ".dta"))
        for c in self.df.columns.intersection(other.columns):
            if not_numeric(self.df[c]) != not_numeric(other[c]):
                raise StataError(f"type mismatch for {c}", 109)
        result = pd.concat([self.df, other], ignore_index=True)
        for c in result:
            if not_numeric(result[c]):
                result[c] = result[c].fillna("")
        self.df = result
        for c in other:
            self.labels.setdefault(c, meta.column_names_to_labels.get(c, ""))
            if c in meta.variable_value_labels:
                self.value_labels.setdefault(c, meta.variable_value_labels[c])
        self.notice(
            "APPEND_LABELS",
            "Master label definitions take precedence; conflicting using-file labels are not reconciled.",
        )
        self.changed()

    def cmd_merge(self, args, opt):
        o = options(opt, ("nogen", "generate", "keep", "assert", "keepusing"))
        m = re.fullmatch(r"(1:1|1:m|m:1)\s+(.+?)\s+using\s+(.+)", args)
        if not m:
            raise StataError('Syntax: merge 1:1|1:m|m:1 keys using "file.dta"')
        how, keys, path = m.groups()
        keys = self.varlist(keys)
        other, meta = self.read_data(self.path(path, ".dta"))
        indicator = o.get("generate", "_merge")
        if "generate" in o and "nogen" in o:
            raise StataError("Choose generate() or nogen")
        if not re.fullmatch(r"[A-Za-z_]\w{0,31}", indicator):
            raise StataError("Invalid merge indicator name")
        if "nogen" not in o and (indicator in self.df or indicator in other):
            raise StataError(f"{indicator} already exists", 110)
        if "nogen" in o:
            indicator = "__sb_merge"
            while indicator in self.df or indicator in other:
                indicator += "_"
        statuses = {}
        for option in ("keep", "assert"):
            if option in o:
                mapping = {
                    "master": 1,
                    "using": 2,
                    "match": 3,
                    "matched": 3,
                    "1": 1,
                    "2": 2,
                    "3": 3,
                }
                tokens = o[option].split()
                if not tokens or any(t not in mapping for t in tokens):
                    raise StataError(
                        f"{option}() accepts master, using, match or 1 2 3"
                    )
                statuses[option] = {mapping[t] for t in tokens}
        if "keepusing" in o:
            import fnmatch

            selected = list(keys)
            for token in o["keepusing"].split():
                matches = [c for c in other if fnmatch.fnmatchcase(c, token)]
                if not matches:
                    raise StataError(f"Using variable {token} not found", 111)
                selected.extend(c for c in matches if c not in selected)
            if any(k not in other for k in keys):
                raise StataError("Merge key absent in using data")
            other = other[selected]
        if any(k not in other for k in keys):
            raise StataError("Merge key absent in using data")
        overlap = [c for c in other if c in self.df and c not in keys]
        # Internal suffix names cannot collide with user variables.
        if any(c + "__using" in self.df or c + "__using" in other for c in overlap):
            raise StataError("Reserved merge suffix collision: __using")
        result = self.df.merge(
            other,
            on=keys,
            how="outer",
            validate={"1:1": "one_to_one", "1:m": "one_to_many", "m:1": "many_to_one"}[
                how
            ],
            indicator=indicator,
            suffixes=("", "__using"),
            sort=False,
        )
        right = result[indicator] == "right_only"
        for c in overlap:
            result.loc[right, c] = result.loc[right, c + "__using"]
            result = result.drop(columns=c + "__using")
        result[indicator] = (
            result[indicator]
            .map({"left_only": 1, "right_only": 2, "both": 3})
            .astype(float)
        )
        counts = result[indicator].value_counts().sort_index()
        if (
            "assert" in statuses
            and not result[indicator].isin(statuses["assert"]).all()
        ):
            raise StataError("Merge assertion failed; original data retained", 459)
        if "keep" in statuses:
            result = result.loc[result[indicator].isin(statuses["keep"])].copy()
        if "nogen" in o:
            result = result.drop(columns=indicator)
        self.df = result
        for c in other:
            if c not in self.labels:
                self.labels[c] = meta.column_names_to_labels.get(c, "")
            if c not in self.value_labels and c in meta.variable_value_labels:
                self.value_labels[c] = meta.variable_value_labels[c]
        if "nogen" not in o:
            self.value_labels[indicator] = {
                1: "Master only",
                2: "Using only",
                3: "Matched",
            }
        self.notice(
            "MERGE",
            "Master values win overlapping variables for matched rows. Missing keys match missing keys. Row order and label-conflict handling may differ from Stata.",
        )
        self.changed()
        self.r = {f"N_{i}": int(counts.get(i, 0)) for i in (1, 2, 3)}
        self.out(counts.to_string())

    def cmd_collapse(self, args, opt):
        o = options(opt, ("by",))
        head, q = qualifiers(args)
        df = self.df.loc[self.mask(q)]
        matches = list(re.finditer(r"\((\w+)\)\s*([^()]+)", head))
        if not matches or "".join(m[0] for m in matches).replace(
            " ", ""
        ) != head.replace(" ", ""):
            raise StataError(
                "Use explicit (stat) groups, e.g. collapse (mean) x (sum) y, by(id)"
            )
        funcs = {
            "mean": "mean",
            "sum": "sum",
            "count": "count",
            "sd": "std",
            "min": "min",
            "max": "max",
            "median": "median",
            "first": "first",
            "last": "last",
        }
        agg = {}
        for m in matches:
            if m[1] not in funcs:
                raise StataError("Unsupported collapse statistic")
            for token in m[2].split():
                name, source = token.split("=", 1) if "=" in token else (token, token)
                self.varlist(source)
                if name in agg:
                    raise StataError("Duplicate output name; use new=old")
                agg[name] = (source, funcs[m[1]])
        keys = self.varlist(str(o["by"])) if "by" in o else []
        if set(keys) & set(agg):
            raise StataError("Grouping variable conflicts with collapsed output name")
        result = self.data_ops.collapse(df, keys, agg)
        self.df = result
        self.value_labels = {}
        self.formats = {}
        self.panel = None
        self.tsvar = None
        self.changed()
        self.notice(
            "COLLAPSE",
            "Median uses the midpoint convention; first/last skip missing values and may differ from Stata first/last. Recheck grouped missing-value conventions.",
        )

    def cmd_reshape(self, args, opt):
        o = options(opt, ("i", "j"))
        if not all(k in o and isinstance(o[k], str) for k in ("i", "j")):
            raise StataError("reshape requires i() and j()")
        sub, _, stubs = args.partition(" ")
        stubs = stubs.split()
        ids = self.varlist(o["i"])
        j = o["j"]
        if sub == "long":
            result = pd.wide_to_long(
                self.df, stubnames=stubs, i=ids, j=j, sep="", suffix=r"\d+"
            ).reset_index()
        elif sub == "wide":
            if (
                self.df[ids + [j]].isna().any().any()
                or self.df.duplicated(ids + [j]).any()
            ):
                raise StataError(
                    "i() and j() must uniquely identify nonmissing observations"
                )
            if (
                not pd.api.types.is_numeric_dtype(self.df[j])
                or (self.df[j] % 1 != 0).any()
            ):
                raise StataError("Numeric integer j() values are required")
            constants = [c for c in self.df if c not in ids + [j] + stubs]
            if (
                constants
                and self.df.groupby(ids)[constants]
                .nunique(dropna=False)
                .gt(1)
                .any()
                .any()
            ):
                raise StataError("Non-reshaped variables are not constant within i()")
            result = self.df.pivot(index=ids, columns=j, values=stubs)
            result.columns = [f"{a}{int(b)}" for a, b in result.columns]
            result = result.reset_index()
            if constants:
                result = result.merge(
                    self.df[ids + constants].drop_duplicates(ids),
                    on=ids,
                    validate="one_to_one",
                )
        else:
            raise StataError("reshape must be long or wide")
        self.df = result
        self.panel = None
        self.tsvar = None
        self.changed()
        self.notice(
            "RESHAPE",
            "Numeric suffixes only; labels/formats for newly reshaped variables are not inferred.",
        )

    def cmd_encode(self, args, opt):
        o = options(opt, ("generate",))
        name = o.get("generate")
        if not isinstance(name, str):
            raise StataError("generate(newvar) is required")
        self.newvar(name)
        cols = self.varlist(args)
        if len(cols) != 1 or not not_numeric(self.df[cols[0]]):
            raise StataError("encode requires one string variable")
        s = self.df[cols[0]].fillna("")
        levels = sorted(x for x in s.unique() if x != "")
        mapping = {v: i + 1 for i, v in enumerate(levels)}
        self.df[name] = s.map(mapping).astype(float)
        self.value_labels[name] = {v: k for k, v in mapping.items()}
        self.changed()
        self.notice(
            "ENCODE",
            "String ordering uses Python Unicode ordering; locale-specific Stata ordering may differ.",
        )

    def cmd_decode(self, args, opt):
        o = options(opt, ("generate",))
        name = o.get("generate")
        if not isinstance(name, str):
            raise StataError("generate(newvar) is required")
        self.newvar(name)
        cols = self.varlist(args)
        if len(cols) != 1 or cols[0] not in self.value_labels:
            raise StataError("decode requires one value-labelled variable")
        c = cols[0]
        labels = self.value_labels[c]
        self.df[name] = self.df[c].map(
            lambda x: "" if pd.isna(x) else labels.get(x, format(x, "g"))
        )
        self.changed()

    def cmd_destring(self, args, opt):
        o = options(opt, ("replace", "ignore", "force"))
        if "replace" not in o:
            raise StataError("This version requires destring, replace")
        result = self.df.copy()
        for c in self.varlist(args):
            s = result[c].astype(str)
            for char in str(o.get("ignore", "")):
                s = s.str.replace(char, "", regex=False)
            s = s.replace({"": None, ".": None, "nan": None})
            result[c] = pd.to_numeric(s, errors="coerce" if "force" in o else "raise")
        self.df = result
        self.changed()

    def cmd_label(self, args, opt):
        options(opt, ())
        p = words(args)
        if len(p) == 2 and p[0] == "data":
            self.file_label = unquote(p[1])
        elif len(p) == 3 and p[0] == "variable":
            c = self.varlist(p[1])[0]
            self.labels[c] = unquote(p[2])
        elif len(p) >= 4 and p[0] == "define" and len(p) % 2 == 0:
            self.label_sets[p[1]] = {
                float(p[i]): unquote(p[i + 1]) for i in range(2, len(p), 2)
            }
        elif len(p) == 3 and p[0] == "values":
            cols = self.varlist(p[1])
            if p[2] not in self.label_sets:
                raise StataError("Undefined value label")
            for c in cols:
                self.value_labels[c] = self.label_sets[p[2]].copy()
        else:
            raise StataError("Unsupported label syntax; see help label")
        self.dirty = True

    def cmd_format(self, args, opt):
        options(opt, ())
        vs, _, fmt = args.rpartition(" ")
        if not fmt.startswith("%"):
            raise StataError("Expected Stata display format")
        for c in self.varlist(vs):
            self.formats[c] = fmt
        self.dirty = True
        self.notice(
            "DISPLAY_FORMAT",
            "Format is retained for .dta export; the data grid and results use general numeric formatting.",
        )

    def cmd_sample(self, args, opt):
        self.resample(args, opt, False)

    def cmd_bsample(self, args, opt):
        self.resample(args, opt, True)

    def resample(self, args, opt, replace):
        o = options(opt, ("count",) if not replace else ())
        n = len(self.df)
        if not n:
            raise StataError("no observations", 2000)
        amount = float(args or n) if replace else float(args)
        if replace or "count" in o:
            if amount != int(amount):
                raise StataError("Sample count must be integer")
            size = int(amount)
        else:
            if not 0 <= amount <= 100:
                raise StataError("Percentage must be 0..100")
            size = int(np.floor(n * amount / 100 + 0.5))
        if size < 0 or (not replace and size > n):
            raise StataError("Invalid sample size")
        indices = self.rng.choice(n, size, replace=replace)
        if not replace:
            indices.sort()
        self.notice(
            "RNG",
            "Sampling uses NumPy PCG64 and choice; selected observations differ from Stata for the same seed.",
        )
        self.df = self.df.iloc[indices].copy()
        self.changed()
        self.out(f"{size} observations sampled")


def not_numeric(s):
    return not pd.api.types.is_numeric_dtype(s)
