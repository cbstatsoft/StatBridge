# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Frequently used data-preparation commands with explicit, bounded syntax."""

from __future__ import annotations
import copy
import re
import numpy as np
import pandas as pd
from .syntax import StataError, options, qualifiers, words, unquote


def missing(frame):
    return frame.isna() | frame.eq("")


def quantiles(values, probabilities):
    values = pd.Series(values).dropna().to_numpy(dtype=float)
    if not len(values):
        raise StataError("No nonmissing observations", 2000)
    if not np.isfinite(values).all():
        raise StataError("Infinite values are not supported")
    return np.quantile(values, probabilities, method="averaged_inverted_cdf")


class CommonDataCommands:
    def newvars(self, names):
        if len(names) != len(set(names)):
            raise StataError("Duplicate output variable names")
        for name in names:
            self.newvar(name)

    def cmd_clonevar(self, args, opt):
        options(opt, ())
        head, q = qualifiers(args)
        m = re.fullmatch(r"(\w+)\s*=\s*(\w+)", head)
        if not m:
            raise StataError("Syntax: clonevar new = old [if ...] [in ...]")
        name, source = m.groups()
        self.newvar(name)
        self.varlist(source)
        value = self.df[source].copy()
        value.loc[~self.mask(q)] = (
            np.nan if pd.api.types.is_numeric_dtype(value) else ""
        )
        self.df[name] = value
        for metadata in (self.labels, self.value_labels, self.formats):
            if source in metadata:
                metadata[name] = copy.deepcopy(metadata[source])
        self.changed()

    def cmd_recode(self, args, opt):
        o = options(opt, ("generate", "prefix", "copyrest"))
        head, q = qualifiers(args)
        start = head.find("(")
        if start < 0:
            raise StataError(
                "Syntax: recode varlist (old=new) [(low/high=new)] [, generate(names)]"
            )
        cols = self.varlist(head[:start], numeric=True)
        ruletext = head[start:]
        rules = re.findall(r'\(([^()]*?(?:"[^"\n]*"[^()]*)?)\)', ruletext)
        if not cols or not rules or re.sub(r"\([^()]*\)", "", ruletext).strip():
            raise StataError("Recode rules must be enclosed in parentheses")
        if "generate" in o and "prefix" in o:
            raise StataError("Choose generate() or prefix()")
        names = (
            o["generate"].split()
            if "generate" in o
            else [o.get("prefix", "") + c for c in cols]
        )
        creating = "generate" in o or "prefix" in o
        if len(names) != len(cols):
            raise StataError("One output name is required for each input variable")
        if creating:
            self.newvars(names)
        elif "copyrest" in o:
            raise StataError("copyrest requires generate() or prefix()")
        mask = self.mask(q)
        results, labels = {}, {}
        for name, col in zip(names, cols):
            source = self.df[col].astype(float)
            target = source.copy()
            if creating and "copyrest" not in o:
                target.loc[~mask] = np.nan
            used = pd.Series(False, index=source.index)
            extrema = {"min": source.loc[mask].min(), "max": source.loc[mask].max()}

            def value(token):
                if token in extrema:
                    return extrema[token]
                if token == ".":
                    return np.nan
                if re.fullmatch(r"\.[a-z]", token):
                    raise StataError("Extended missing values are not supported")
                try:
                    number = float(token)
                except ValueError:
                    raise StataError(f"Invalid recode value: {token}") from None
                if not np.isfinite(number):
                    raise StataError("Recode values must be finite or .")
                return number

            tail = False
            fallback = set()
            for rule in rules:
                match = re.fullmatch(
                    r'\s*(.+?)\s*=\s*([^\s"]+)(?:\s+"([^"]*)")?\s*', rule
                )
                if not match:
                    raise StataError("Invalid rule; labels must be quoted")
                left, right, label = match.groups()
                selected = pd.Series(False, index=source.index)
                special = left in ("else", "*", "missing", "nonmissing")
                if special:
                    key = "else" if left == "*" else left
                    if (
                        key in fallback
                        or (key == "else" and fallback)
                        or "else" in fallback
                    ):
                        raise StataError("Conflicting or repeated fallback rules")
                    fallback.add(key)
                    tail = True
                    selected[:] = True if key == "else" else False
                    if key == "missing":
                        selected = source.isna()
                    if key == "nonmissing":
                        selected = source.notna()
                else:
                    if tail:
                        raise StataError(
                            "missing/nonmissing/else rules must follow numeric rules"
                        )
                    for token in left.split():
                        ends = token.split("/")
                        if len(ends) == 2:
                            lo, hi = map(value, ends)
                            if np.isnan(lo) or np.isnan(hi) or lo > hi:
                                raise StataError(
                                    "Recode ranges require ascending nonmissing bounds"
                                )
                            selected |= source.between(lo, hi)
                        elif len(ends) == 1:
                            v = value(token)
                            selected |= source.isna() if np.isnan(v) else source.eq(v)
                        else:
                            raise StataError("Invalid recode range")
                newvalue = value(right)
                selected &= mask & ~used
                target.loc[selected] = newvalue
                used |= selected
                if label is not None:
                    if (
                        not creating
                        or not np.isfinite(newvalue)
                        or newvalue != int(newvalue)
                    ):
                        raise StataError(
                            "Quoted labels require new variables and integer nonmissing output codes"
                        )
                    if (
                        newvalue in labels.setdefault(name, {})
                        and labels[name][newvalue] != label
                    ):
                        raise StataError("Conflicting labels for the same output code")
                    labels[name][newvalue] = label
            results[name] = target
        for name, value in results.items():
            self.df[name] = value
            if name in labels:
                self.value_labels[name] = labels[name]
            elif not creating and name in self.value_labels:
                self.notice(
                    "RECODE_LABELS",
                    "Existing value labels are retained after in-place recoding; check their meanings.",
                )
        self.changed()

    def cmd_tostring(self, args, opt):
        o = options(opt, ("generate", "replace", "format", "force"))
        cols = self.varlist(args, numeric=True)
        if ("generate" in o) == ("replace" in o) or not cols:
            raise StataError("Specify generate(names) or replace")
        names = o["generate"].split() if "generate" in o else cols
        if len(names) != len(cols):
            raise StataError("One generated name per input variable is required")
        if "generate" in o:
            self.newvars(names)
        fmt = o.get("format", "%.15g")
        if not re.fullmatch(r"%\d*\.\d+[fge]", fmt):
            raise StataError("Supported numeric formats: %width.precisionf, g or e")
        result = {}
        for name, col in zip(names, cols):
            x = self.df[col]
            value = x.map(lambda v: "." if pd.isna(v) else (fmt % v).strip())
            roundtrip = pd.to_numeric(value.replace(".", np.nan), errors="coerce")
            if "force" not in o and not np.array_equal(
                x.to_numpy(dtype=float), roundtrip.to_numpy(), equal_nan=True
            ):
                raise StataError(
                    f"{col} would lose numeric precision; choose a wider format or specify force"
                )
            result[name] = value
        for name, value in result.items():
            self.df[name] = value
            self.value_labels.pop(name, None)
            self.formats.pop(name, None)
        self.changed()

    def cmd_split(self, args, opt):
        o = options(opt, ("parse", "generate", "limit", "destring", "notrim"))
        head, q = qualifiers(args)
        cols = self.varlist(head)
        if len(cols) != 1 or pd.api.types.is_numeric_dtype(self.df[cols[0]]):
            raise StataError("split requires one string variable")
        source = cols[0]
        prefix = o.get("generate", source)
        limit = int(o.get("limit", 0))
        if limit < 0:
            raise StataError("limit() must be positive")
        mask = self.mask(q)
        values = self.df[source].fillna("").astype(str)
        if "notrim" in o and "parse" not in o:
            raise StataError("notrim requires parse()")
        if "notrim" not in o:
            values = values.str.strip()
        delimiters = [unquote(x) for x in words(o["parse"])] if "parse" in o else None
        if delimiters is not None and (
            not delimiters or any(not x for x in delimiters)
        ):
            raise StataError("parse() requires nonempty delimiters")
        pattern = (
            "|".join(re.escape(x) for x in sorted(delimiters, key=len, reverse=True))
            if delimiters
            else None
        )
        pieces = values.loc[mask].map(
            lambda s: re.split(pattern, s) if pattern else s.split()
        )
        count = max((len(p) for p in pieces), default=0)
        if limit:
            count = min(count, limit)
        if count == 0:
            raise StataError("No strings to split", 2000)
        if count > 1000:
            raise StataError("split is limited to 1,000 output variables")
        names = [f"{prefix}{i}" for i in range(1, count + 1)]
        self.newvars(names)
        result = {}
        for i, name in enumerate(names):
            value = pieces.map(lambda p: p[i] if i < len(p) else "").reindex(
                self.df.index, fill_value=""
            )
            if "destring" in o:
                try:
                    value = pd.to_numeric(
                        value.replace({"": np.nan, ".": np.nan}), errors="raise"
                    )
                except ValueError:
                    pass  # Stata's split, destring keeps non-convertible columns as strings.
            result[name] = value
        for name, value in result.items():
            self.df[name] = value
        self.changed()
        self.r = {"k_new": count, "varlist": " ".join(names)}
        self.notice(
            "SPLIT",
            "Default separators use Python whitespace rules; parse() uses literal separator strings and retains empty fields. Converted numeric columns use double precision; Stata storage widths and Unicode/whitespace conventions may differ.",
        )

    def cmd_mvdecode(self, args, opt):
        o = options(opt, ("mv",))
        if "mv" not in o:
            raise StataError("Specify mv(numeric_values)")
        head, q = qualifiers(args)
        cols = [
            c for c in self.varlist(head) if pd.api.types.is_numeric_dtype(self.df[c])
        ]
        vals = [
            float(v)
            for token in o["mv"].split()
            for v in (self.number_range(token) if "/" in token else [token])
        ]
        if not vals or not np.isfinite(vals).all():
            raise StataError(
                "mv() requires finite values; tagged missing mappings are unsupported"
            )
        mask = self.mask(q)
        new = self.df.copy()
        for col in cols:
            new.loc[mask & new[col].isin(vals), col] = np.nan
        self.df = new
        self.changed()

    def cmd_mvencode(self, args, opt):
        o = options(opt, ("mv", "override"))
        if "mv" not in o:
            raise StataError("Specify mv(one_numeric_value)")
        head, q = qualifiers(args)
        cols = [
            c for c in self.varlist(head) if pd.api.types.is_numeric_dtype(self.df[c])
        ]
        v = float(o["mv"])
        if not np.isfinite(v):
            raise StataError("mv() must be finite")
        mask = self.mask(q)
        if "override" not in o and self.df.loc[mask, cols].eq(v).any().any():
            raise StataError(
                "Replacement code already occurs in the selected data; specify override"
            )
        new = self.df.copy()
        for col in cols:
            new.loc[mask & new[col].isna(), col] = v
        self.df = new
        self.changed()

    def cmd_misstable(self, args, opt):
        options(opt, ("all",))
        sub, _, rest = args.partition(" ")
        head, q = qualifiers(rest)
        cols = self.varlist(head, default=True)
        df = self.df.loc[self.mask(q), cols]
        miss = missing(df)
        if sub == "summarize":
            table = pd.DataFrame({"Missing": miss.sum(), "Nonmissing": (~miss).sum()})
            if "all" not in options(opt, ("all",)):
                table = table.loc[table.Missing > 0]
            self.out(table.to_string() if len(table) else "No missing values.")
        elif sub == "patterns":
            table = (
                miss.astype(int)
                .value_counts(sort=True)
                .rename("Frequency")
                .reset_index()
            )
            self.out("1 = missing, 0 = observed\n" + table.to_string(index=False))
        else:
            raise StataError(
                "Supported: misstable summarize|patterns [varlist] [, all]"
            )
        self.r = {"N": len(df), "N_complete": int((~miss.any(axis=1)).sum())}
        self.notice(
            "MISSTABLE",
            "Numeric missing and empty strings are both counted; extended missing tags were normalised on import. Display and stored results are a StatBridge subset.",
        )

    def cmd_ds(self, args, opt):
        o = options(opt, ("has", "not"))
        cols = self.varlist(args, default=True)
        if "has" in o:
            kind = o["has"]
            if kind not in ("type numeric", "type string"):
                raise StataError("Supported filters: has(type numeric|string)")
            cols = [
                c
                for c in cols
                if pd.api.types.is_numeric_dtype(self.df[c]) == (kind == "type numeric")
            ]
        if "not" in o:
            cols = [c for c in self.df if c not in cols]
        self.r = {"varlist": " ".join(cols)}
        self.out(self.r["varlist"])

    def cmd_levelsof(self, args, opt):
        o = options(opt, ("local", "missing", "clean", "separate"))
        head, q = qualifiers(args)
        cols = self.varlist(head)
        if len(cols) != 1:
            raise StataError("levelsof requires one variable")
        x = self.df.loc[self.mask(q), cols[0]]
        numeric = pd.api.types.is_numeric_dtype(x)
        hasmissing = bool((x.isna() | x.eq("")).any())
        x = x.loc[~(x.isna() | x.eq(""))]
        vals = sorted(x.unique())
        if not numeric and any('"' in str(v) or "`" in str(v) for v in vals):
            raise StataError(
                "Embedded quotes/backticks in string levels require unsupported compound quoting"
            )
        rendered = [
            f"{v:.16g}" if numeric else str(v) if "clean" in o else f'"{v}"'
            for v in vals
        ]
        if hasmissing and "missing" in o:
            rendered.append("." if numeric else '""')
        result = o.get("separate", " ").join(rendered)
        if "local" in o:
            if not re.fullmatch(r"[A-Za-z_]\w*", o["local"]):
                raise StataError("Invalid local macro name")
            self.locals[o["local"]] = result
        self.r = {"levels": result, "r": len(rendered)}
        self.out(result)

    def _cutpoints(self, args, opt, categories):
        o = options(
            opt,
            ("nquantiles", "nq", "altdef", "genp")
            if not categories
            else ("nquantiles", "nq", "altdef", "cutpoints"),
        )
        head, q = qualifiers(args)
        match = re.fullmatch(r"(\w+)\s*=\s*(.+)", head)
        if not match:
            raise StataError("Syntax: xtile|pctile new = expression [, nquantiles(#)]")
        name, expression = match.groups()
        self.newvar(name)
        mask = self.mask(q)
        x = pd.Series(self.expr(expression), index=self.df.index, dtype=float)
        if "nq" in o and "nquantiles" in o:
            raise StataError("Specify nquantiles() once")
        n = int(o.get("nquantiles", o.get("nq", 2)))
        if n < 2 or n > 10000:
            raise StataError("nquantiles() must be between 2 and 10,000")
        probs = np.arange(1, n) / n
        if "cutpoints" in o:
            if any(k in o for k in ("nq", "nquantiles", "altdef")):
                raise StataError("cutpoints() cannot be combined with quantile options")
            cols = self.varlist(o["cutpoints"], numeric=True)
            if len(cols) != 1:
                raise StataError("cutpoints() requires one variable")
            cuts = np.sort(self.df[cols[0]].dropna().to_numpy())
            if not len(cuts) or not np.isfinite(cuts).all():
                raise StataError("No finite cutpoints")
        else:
            values = x.loc[mask].dropna()
            cuts = (
                np.quantile(values, probs, method="weibull")
                if "altdef" in o and len(values)
                else quantiles(values, probs)
            )
        if categories:
            result = pd.Series(np.nan, index=self.df.index)
            valid = mask & x.notna()
            result.loc[valid] = np.searchsorted(cuts, x.loc[valid], side="left") + 1
        else:
            if len(cuts) > len(self.df):
                raise StataError("Not enough observations to store the cutpoints")
            result = pd.Series(np.nan, index=self.df.index)
            result.iloc[: len(cuts)] = cuts
            if "genp" in o:
                self.newvars([name, o["genp"]])
        self.df[name] = result
        if "genp" in o:
            self.df[o["genp"]] = np.nan
            self.df.loc[self.df.index[: len(cuts)], o["genp"]] = probs * 100
        self.changed()
        self.r = {f"r{i + 1}": float(v) for i, v in enumerate(cuts)}
        self.notice(
            "QUANTILES",
            "Unweighted quantiles use averaged-inverted-CDF (Stata default definition); altdef uses Weibull interpolation. Ties remain together and may produce unequal or empty bins. Exact Stata parity has not been certified.",
        )

    def cmd_xtile(self, args, opt):
        self._cutpoints(args, opt, True)

    def cmd_pctile(self, args, opt):
        self._cutpoints(args, opt, False)

    def cmd_expand(self, args, opt):
        o = options(opt, ("generate",))
        head, q = qualifiers(args)
        n = pd.Series(self.expr(head), index=self.df.index, dtype=float)
        if np.isinf(n).any():
            raise StataError("Expansion counts must be finite")
        n = np.floor(n.fillna(1).clip(lower=1) + 0.5)
        n.loc[~self.mask(q)] = 1
        if n.sum() > 5_000_000:
            raise StataError("expand would exceed the 5,000,000-row allocation limit")
        if "generate" in o:
            self.newvar(o["generate"])
        # Originals first, then added copies, preserving original row order.
        extra = np.repeat(np.arange(len(self.df)), n.astype(int).to_numpy() - 1)
        new = pd.concat([self.df, self.df.iloc[extra]], ignore_index=True)
        if "generate" in o:
            new[o["generate"]] = np.r_[np.zeros(len(self.df)), np.ones(len(extra))]
        self.df = new
        self.changed()
        self.notice(
            "EXPAND_ORDER",
            "Original rows precede added copies; ordering of added copies may differ from Stata. Counts below one or missing retain one original row.",
        )

    def cmd_contract(self, args, opt):
        o = options(opt, ("freq", "percent", "nomiss"))
        head, q = qualifiers(args)
        cols = self.varlist(head)
        if not cols:
            raise StataError("Specify variables to contract")
        freq = o.get("freq", "_freq")
        names = [freq] + ([o["percent"]] if "percent" in o else [])
        if len(set(cols + names)) != len(cols + names):
            raise StataError(
                "Output names conflict with grouping variables or each other"
            )
        for name in names:
            if not re.fullmatch(r"[A-Za-z_]\w{0,31}", name):
                raise StataError("Invalid output variable name")
        df = self.df.loc[self.mask(q), cols]
        if "nomiss" in o:
            df = df.loc[~missing(df).any(axis=1)]
        result = df.groupby(cols, dropna=False, sort=True).size().reset_index(name=freq)
        if "percent" in o:
            result[o["percent"]] = 100 * result[freq] / len(df)
        self.df = result
        self.panel = self.tsvar = None
        self.changed()

    def cmd_tabstat(self, args, opt):
        o = options(opt, ("statistics", "stat", "by", "missing", "columns"))
        if "statistics" in o and "stat" in o:
            raise StataError("Specify statistics() once")
        if "columns" in o and o["columns"] not in ("variables", "statistics"):
            raise StataError("columns() accepts variables or statistics")
        head, q = qualifiers(args)
        cols = self.varlist(head, default=True, numeric=True)
        keys = self.varlist(o["by"]) if "by" in o else []
        if len(keys) > 1:
            raise StataError("by() accepts one grouping variable")
        df = self.df.loc[self.mask(q)]
        stats = o.get("statistics", o.get("stat", "mean")).split()
        allowed = {
            "n",
            "count",
            "mean",
            "sd",
            "variance",
            "var",
            "min",
            "max",
            "sum",
            "median",
            "p1",
            "p5",
            "p10",
            "p25",
            "p50",
            "p75",
            "p90",
            "p95",
            "p99",
            "iqr",
            "semean",
        }
        if not stats or set(stats) - allowed:
            raise StataError("Unsupported tabstat statistic")

        def calculate(x, stat):
            x = x.dropna()
            if stat in ("n", "count"):
                return len(x)
            if not len(x):
                return np.nan
            if stat == "semean":
                return x.std(ddof=1) / np.sqrt(len(x))
            if stat == "iqr":
                return float(np.diff(quantiles(x, [0.25, 0.75]))[0])
            if stat.startswith("p"):
                return quantiles(x, int(stat[1:]) / 100)
            return getattr(x, {"sd": "std", "variance": "var"}.get(stat, stat))()

        groups = [("Total", df)]
        if keys:
            selected = df if "missing" in o else df.loc[~missing(df[keys]).any(axis=1)]
            groups = list(selected.groupby(keys[0], dropna=False, sort=True)) + [
                ("Total", selected)
            ]
        for label, group in groups:
            table = pd.DataFrame(
                {c: {s: calculate(group[c], s) for s in stats} for c in cols}
            )
            if o.get("columns", "statistics") == "statistics":
                table = table.T
            self.out(f"{label}\n" + table.to_string(float_format=lambda v: f"{v:.6g}"))
        self.r = {"N": len(groups[-1][1])}

    def cmd__pctile(self, args, opt):
        o = options(opt, ("percentiles", "p", "nquantiles", "nq", "altdef"))
        head, q = qualifiers(args)
        cols = self.varlist(head, numeric=True)
        if len(cols) != 1:
            raise StataError("_pctile requires one numeric variable")
        if sum(k in o for k in ("percentiles", "p", "nquantiles", "nq")) > 1:
            raise StataError("Choose one of percentiles() or nquantiles()")
        if "percentiles" in o or "p" in o:
            probs = np.array(
                [float(p) / 100 for p in o.get("percentiles", o.get("p")).split()]
            )
            if (
                not len(probs)
                or not np.isfinite(probs).all()
                or ((probs <= 0) | (probs >= 1)).any()
            ):
                raise StataError("Percentiles must be strictly between 0 and 100")
        else:
            n = int(o.get("nquantiles", o.get("nq", 2)))
            if not 2 <= n <= 10000:
                raise StataError("nquantiles() must be between 2 and 10,000")
            probs = np.arange(1, n) / n
        x = self.df.loc[self.mask(q), cols[0]].dropna()
        result = (
            np.quantile(x, probs, method="weibull")
            if "altdef" in o and len(x)
            else quantiles(x, probs)
        )
        self.r = {"N": len(x), **{f"r{i + 1}": float(v) for i, v in enumerate(result)}}
        self.out(pd.Series(self.r).to_string())

    def cmd_egen(self, args, opt):
        head, q = qualifiers(args)
        match = re.fullmatch(r"(?:double\s+|float\s+)?(\w+)\s*=\s*(\w+)\((.*)\)", head)
        if not match:
            return super().cmd_egen(args, opt)
        name, fun, source = match.groups()
        extra = {
            "rowmiss",
            "rownonmiss",
            "rowmin",
            "rowmax",
            "rowsd",
            "std",
            "tag",
            "rank",
            "pctile",
            "concat",
        }
        if fun not in extra and not (fun == "group" and "missing" in opt):
            return super().cmd_egen(re.sub(r"^(double|float)\s+", "", args), opt)
        allowed = {
            "std": ("by", "mean", "std"),
            "tag": ("missing",),
            "group": ("missing",),
            "rank": ("by",),
            "pctile": ("by", "p"),
            "concat": ("punct",),
        }.get(fun, ())
        o = options(opt, allowed)
        self.newvar(name)
        cols = self.varlist(
            source,
            numeric=fun not in ("tag", "group", "concat", "rowmiss", "rownonmiss"),
        )
        if not cols:
            raise StataError("Specify source variables")
        mask = self.mask(q)
        df = self.df.loc[mask]
        keys = self.varlist(o["by"]) if "by" in o else []
        if fun in ("std", "rank", "pctile"):
            if len(cols) != 1:
                raise StataError(f"{fun}() requires one source variable")

            def calculate(x):
                if fun == "std":
                    targetmean, targetstd = (
                        float(o.get("mean", 0)),
                        float(o.get("std", 1)),
                    )
                    if not np.isfinite([targetmean, targetstd]).all() or targetstd <= 0:
                        raise StataError("std() must be positive and mean() finite")
                    return (x - x.mean()) / x.std(ddof=1) * targetstd + targetmean
                if fun == "rank":
                    return x.rank(method="average", na_option="keep")
                p = float(o.get("p", 50))
                if not 0 < p < 100:
                    raise StataError("p() must be between 0 and 100")
                return quantiles(x, p / 100) if x.notna().any() else np.nan

            value = (
                df.groupby(keys, dropna=False)[cols[0]].transform(calculate)
                if keys
                else calculate(df[cols[0]])
            )
            if np.isscalar(value):
                value = pd.Series(value, index=df.index)
        elif fun in ("tag", "group"):
            valid = (
                pd.Series(True, index=df.index)
                if "missing" in o
                else ~missing(df[cols]).any(axis=1)
            )
            value = pd.Series(0.0 if fun == "tag" else np.nan, index=df.index)
            if fun == "tag":
                value.loc[valid] = (~df.loc[valid, cols].duplicated()).astype(float)
            else:
                value.loc[valid] = (
                    pd.factorize(
                        pd.MultiIndex.from_frame(df.loc[valid, cols]), sort=True
                    )[0]
                    + 1
                )
        elif fun == "concat":
            converted = df[cols].copy()
            for c in cols:
                converted[c] = converted[c].map(
                    lambda v: (
                        "."
                        if pd.isna(v)
                        else f"{v:.15g}"
                        if isinstance(v, (float, int))
                        else str(v)
                    )
                )
            value = converted.agg(o.get("punct", "").join, axis=1)
        elif fun in ("rowmiss", "rownonmiss"):
            value = (
                missing(df[cols]).sum(axis=1)
                if fun == "rowmiss"
                else (~missing(df[cols])).sum(axis=1)
            )
        else:
            value = getattr(
                df[cols], {"rowmin": "min", "rowmax": "max", "rowsd": "std"}[fun]
            )(axis=1)
        self.df[name] = value.reindex(
            self.df.index, fill_value="" if fun == "concat" else np.nan
        )
        self.changed()
