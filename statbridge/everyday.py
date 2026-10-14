# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Common descriptive, testing, panel preparation and graph workflows."""

import re
from types import SimpleNamespace
import numpy as np
import pandas as pd
from scipy import stats
from .syntax import StataError, options, qualifiers
from .models import Model


def level_option(engine, opts):
    level = float(opts.get("level", engine.level))
    if not 0 < level < 100:
        raise StataError("level() must be between 0 and 100")
    return level


class EverydayCommands:
    def cmd_coverage(self, args, opt):
        options(opt, ())
        if args:
            raise StataError("Use coverage without arguments")
        from .coverage import WORKFLOWS
        from .catalog import COMMANDS

        self.out(
            f"{len(COMMANDS)} catalog entries, including utilities and extensions. This is not a measured percentage of Stata usage."
        )
        self.show_table(
            "Workflow coverage and limits",
            pd.DataFrame(
                WORKFLOWS, columns=["Workflow", "Implemented scope", "Remaining limits"]
            ),
        )

    def _summary_estimate(self, kind, args, opt):
        o = options(opt, ("over", "level"))
        level = level_option(self, o)
        head, q = qualifiers(args)
        cols = self.varlist(head, numeric=kind != "proportion")
        groups = self.varlist(o["over"]) if "over" in o else []
        if not cols:
            raise StataError("Specify variables")
        data = self.df.loc[self.mask(q), list(dict.fromkeys(cols + groups))].dropna()
        if kind == "proportion":
            data = data.loc[~data[cols].eq("").any(axis=1)]
        elif not np.isfinite(data[cols].to_numpy(dtype=float)).all():
            raise StataError("Nonfinite data")
        if len(data) < 2:
            raise StataError("At least two complete observations required")
        estimates = {}
        influences = {}
        for group, part in (
            data.groupby(groups, sort=True) if groups else [(None, data)]
        ):
            suffix = "" if group is None else ":" + str(group)
            for col in cols:
                for category in (
                    sorted(part[col].unique()) if kind == "proportion" else [None]
                ):
                    name = (col if category is None else f"{category}.{col}") + suffix
                    y = (
                        (part[col] == category).astype(float)
                        if category is not None
                        else part[col].astype(float)
                    )
                    if len(y) < 2:
                        raise StataError(
                            "Every group requires at least two observations"
                        )
                    b = y.sum() if kind == "total" else y.mean()
                    u = pd.Series(0.0, index=data.index)
                    u.loc[part.index] = (
                        (y - y.mean())
                        * (1 if kind == "total" else 1 / len(y))
                        * np.sqrt(len(y) / (len(y) - 1))
                    )
                    estimates[name] = b
                    influences[name] = u
        params = pd.Series(estimates, dtype=float)
        u = pd.DataFrame(influences)
        zero = pd.Series(0.0, index=data.index)
        self.model = Model(
            kind,
            SimpleNamespace(),
            params,
            u.T @ u,
            data.index,
            zero,
            pd.DataFrame(index=data.index),
            zero,
            zero,
            len(data) - 1,
            "iid",
            level,
            metadata={"summary": True},
        )
        self.report_model()
        self.notice(
            "DESCRIPTIVE_ESTIMATE",
            "Unweighted complete-case IID estimates and joint covariance, symmetric t(N-1) intervals. over() uses domain influence vectors; group df and proportion interval conventions may differ from Stata. Use svy for survey designs.",
        )

    def cmd_mean(self, a, o):
        self._summary_estimate("mean", a, o)

    def cmd_total(self, a, o):
        self._summary_estimate("total", a, o)

    def cmd_proportion(self, a, o):
        self._summary_estimate("proportion", a, o)

    def cmd_ci(self, args, opt):
        sub, _, text = args.partition(" ")
        if sub not in ("means", "proportions"):
            raise StataError("ci means|proportions varlist [, level(#) exact wilson]")
        o = options(opt, ("level", "exact", "wilson"))
        level = level_option(self, o)
        alpha = 1 - level / 100
        if "exact" in o and "wilson" in o:
            raise StataError("Choose exact or wilson")
        if sub == "means" and ("exact" in o or "wilson" in o):
            raise StataError("exact/wilson apply to proportions only")
        from statsmodels.stats.proportion import proportion_confint

        head, q = qualifiers(text)
        rows = []
        for col in self.varlist(head, numeric=True):
            y = self.df.loc[self.mask(q), col].dropna().astype(float)
            n = len(y)
            if not n or not np.isfinite(y).all():
                raise StataError("No finite observations")
            b = y.mean()
            if sub == "means":
                if n < 2:
                    raise StataError("At least two observations required")
                se = y.sem()
                crit = stats.t.ppf(1 - alpha / 2, n - 1)
                lo, hi = b - crit * se, b + crit * se
            else:
                if not y.isin([0, 1]).all():
                    raise StataError("Proportions require 0/1 data")
                se = np.sqrt(b * (1 - b) / n)
                lo, hi = proportion_confint(
                    int(y.sum()),
                    n,
                    alpha=alpha,
                    method="wilson" if "wilson" in o else "beta",
                )
            rows.append(
                {
                    "Variable": col,
                    "N": n,
                    "Estimate": b,
                    "Std. err.": se,
                    "CI lower": lo,
                    "CI upper": hi,
                }
            )
        if not rows:
            raise StataError("Specify variables")
        self.show_table("Confidence intervals", pd.DataFrame(rows))
        last = rows[-1]
        self.r = {
            "N": last["N"],
            "mean": last["Estimate"],
            "se": last["Std. err."],
            "lb": last["CI lower"],
            "ub": last["CI upper"],
            "level": level,
        }
        self.notice(
            "CI",
            "Unweighted variablewise samples. Means use Student t; proportions use exact Clopper-Pearson intervals by default, or Wilson when requested.",
        )

    def cmd_prtest(self, args, opt):
        from statsmodels.stats.proportion import proportions_ztest

        o = options(opt, ("by", "level"))
        level = level_option(self, o)
        head, q = qualifiers(args)
        frame = self.df.loc[self.mask(q)]
        if "by" in o:
            cols = self.varlist(head, numeric=True)
            groups = self.varlist(o["by"])
            if len(cols) != 1 or len(groups) != 1:
                raise StataError("One outcome and one grouping variable required")
            data = frame[cols + groups].dropna()
            levels = sorted(data[groups[0]].unique())
            if len(levels) != 2:
                raise StataError("Exactly two groups required")
            ys = [data.loc[data[groups[0]].eq(v), cols[0]] for v in levels]
            null = 0.0
        else:
            parts = re.split(r"={1,2}", head)
            if len(parts) != 2:
                raise StataError("prtest binary = # or prtest binary, by(group)")
            cols = self.varlist(parts[0], numeric=True)
            null = float(parts[1])
            if len(cols) != 1 or not 0 < null < 1:
                raise StataError(
                    "One binary outcome and a null proportion between 0 and 1 required"
                )
            ys = [frame[cols[0]].dropna()]
        if any(not len(y) or not y.isin([0, 1]).all() for y in ys):
            raise StataError("Require nonempty 0/1 samples")
        ns = [len(y) for y in ys]
        z, p = proportions_ztest(
            [int(y.sum()) for y in ys],
            ns,
            value=null,
            prop_var=null if len(ys) == 1 else False,
        )
        b = ys[0].mean() - (ys[1].mean() if len(ys) > 1 else null)
        se = np.sqrt(sum(y.mean() * (1 - y.mean()) / len(y) for y in ys))
        crit = stats.norm.ppf(0.5 + level / 200)
        self.r = {
            "z": np.asarray(z).item(),
            "p": np.asarray(p).item(),
            "N": sum(ns),
            "difference": b,
            "lb": b - crit * se,
            "ub": b + crit * se,
        }
        self.show_table("Proportion z test", pd.DataFrame([self.r]))
        self.notice(
            "PRTEST",
            "Independent asymptotic z test; pooled null variance for two groups. Difference intervals use unpooled normal SEs. No paired or weighted tests.",
        )

    def _tab_args(self, cols, q):
        return " ".join(cols) + "".join(f" {k} {v}" for k, v in q.items())

    def cmd_tab1(self, args, opt):
        options(opt, ("missing",))
        head, q = qualifiers(args)
        cols = self.varlist(head)
        if not cols:
            raise StataError("Specify variables")
        for c in cols:
            self.cmd_tabulate(self._tab_args([c], q), opt)

    def cmd_tab2(self, args, opt):
        import itertools

        options(opt, ("missing", "chi2", "row", "col"))
        head, q = qualifiers(args)
        cols = self.varlist(head)
        if not 2 <= len(cols) <= 20:
            raise StataError("Specify 2..20 variables")
        for pair in itertools.combinations(cols, 2):
            self.cmd_tabulate(self._tab_args(pair, q), opt)

    def cmd_kwallis(self, args, opt):
        o = options(opt, ("by",))
        head, q = qualifiers(args)
        cols = self.varlist(head, numeric=True)
        groups = self.varlist(o.get("by", ""))
        if len(cols) != 1 or len(groups) != 1:
            raise StataError("kwallis outcome, by(group)")
        data = self.df.loc[self.mask(q), cols + groups].dropna()
        parts = [p[cols[0]].to_numpy() for _, p in data.groupby(groups[0])]
        if len(parts) < 2 or not np.isfinite(data[cols[0]]).all():
            raise StataError("Need at least two finite groups")
        h, p = stats.kruskal(*parts)
        self.r = {"N": len(data), "chi2": float(h), "df": len(parts) - 1, "p": float(p)}
        self.show_table("Kruskal-Wallis test", pd.DataFrame([self.r]))
        self.notice(
            "KWALLIS",
            "Tie-corrected SciPy H statistic, asymptotic chi-square inference; no exact or post-hoc tests.",
        )

    def cmd_sdtest(self, args, opt):
        o = options(opt, ("by", "level"))
        level = level_option(self, o)
        head, q = qualifiers(args)
        frame = self.df.loc[self.mask(q)]
        if "by" in o:
            cols = self.varlist(head, numeric=True)
            groups = self.varlist(o["by"])
            if len(cols) != 1 or len(groups) != 1:
                raise StataError("One outcome and group required")
            data = frame[cols + groups].dropna()
            ys = [p[cols[0]] for _, p in data.groupby(groups[0])]
        else:
            parts = re.split(r"={1,2}", head)
            if len(parts) != 2:
                raise StataError("sdtest x = y or sdtest outcome, by(group)")
            cols = [self.varlist(p.strip(), numeric=True) for p in parts]
            if any(len(c) != 1 for c in cols):
                raise StataError("Specify two variables")
            ys = [frame[c[0]].dropna() for c in cols]
        if len(ys) != 2 or any(
            len(y) < 2 or not np.isfinite(y).all() or y.var() <= 0 for y in ys
        ):
            raise StataError("Require two finite samples with positive variance")
        d1, d2 = [len(y) - 1 for y in ys]
        f = ys[0].var() / ys[1].var()
        alpha = 1 - level / 100
        self.r = {
            "F": f,
            "df_1": d1,
            "df_2": d2,
            "p": min(1.0, 2 * min(stats.f.cdf(f, d1, d2), stats.f.sf(f, d1, d2))),
            "ratio": np.sqrt(f),
            "lb": np.sqrt(f / stats.f.ppf(1 - alpha / 2, d1, d2)),
            "ub": np.sqrt(f / stats.f.ppf(alpha / 2, d1, d2)),
        }
        self.show_table("Independent variance-ratio test", pd.DataFrame([self.r]))
        self.notice(
            "SDTEST",
            "Normal-population independent-sample F test; interval is for the SD ratio. Not a paired test; sensitive to nonnormality.",
        )

    def cmd_inspect(self, args, opt):
        options(opt, ())
        rows = []
        for c in self.varlist(args, default=True):
            y = self.df[c]
            num = pd.api.types.is_numeric_dtype(y)
            rows.append(
                {
                    "Variable": c,
                    "N": len(y),
                    "Missing": int((y.isna() | y.eq("")).sum()),
                    "Distinct": y.nunique(),
                    "Negative": int((y < 0).sum()) if num else np.nan,
                    "Zero": int((y == 0).sum()) if num else np.nan,
                    "Positive": int((y > 0).sum()) if num else np.nan,
                }
            )
        self.show_table("Inspect variables", pd.DataFrame(rows))

    def cmd_compare(self, args, opt):
        options(opt, ())
        cols = self.varlist(args)
        if len(cols) != 2:
            raise StataError("compare x y")
        a, b = (self.df[c] for c in cols)
        missing = a.isna() | b.isna() | a.eq("") | b.eq("")
        equal = a.eq(b) & ~missing
        self.r = {
            "N": len(a),
            "equal": int(equal.sum()),
            "different": int((~equal & ~missing).sum()),
            "missing": int(missing.sum()),
        }
        self.show_table("Compare variables", pd.DataFrame([self.r]))

    def cmd_fillin(self, args, opt):
        options(opt, ())
        cols = self.varlist(args)
        self.newvar("_fillin")
        if len(cols) < 2:
            raise StataError("fillin requires at least two variables")
        levels = [self.df[c].drop_duplicates().tolist() for c in cols]
        if np.prod([len(x) for x in levels], dtype=float) > 2_000_000:
            raise StataError("fillin would exceed two million combinations")
        combinations = pd.MultiIndex.from_product(levels, names=cols).to_frame(
            index=False
        )
        # Avoid collision with an existing merge indicator.
        marker = "_sb_fill_source"
        while marker in self.df:
            marker += "x"
        result = combinations.merge(
            self.df, how="left", on=cols, indicator=marker, sort=False
        )
        result["_fillin"] = result.pop(marker).eq("left_only").astype(float)
        self.df = result
        self.changed()
        self.notice(
            "FILLIN",
            "Added absent combinations only; original duplicates remain. Non-key values on added rows are missing.",
        )

    def cmd_ipolate(self, args, opt):
        o = options(opt, ("generate", "epolate"))
        head, q = qualifiers(args)
        cols = self.varlist(head, numeric=True)
        if len(cols) != 2 or "generate" not in o:
            raise StataError("ipolate y x, generate(new) [epolate]")
        name = o["generate"]
        self.newvar(name)
        selected = self.mask(q)
        data = self.df.loc[selected, cols].dropna()
        if not np.isfinite(data.to_numpy()).all():
            raise StataError("Nonfinite interpolation data")
        source = data.groupby(cols[1])[cols[0]].mean().sort_index()
        if len(source) < 2:
            raise StataError("At least two distinct observed x values required")
        x = self.df.loc[selected, cols[1]].astype(float)
        if np.isinf(x).any():
            raise StataError("Nonfinite interpolation coordinates")
        y = np.interp(x, source.index, source.values, left=np.nan, right=np.nan)
        if "epolate" in o:
            for mask, a, b in [
                (x < source.index[0], 0, 1),
                (x > source.index[-1], -1, -2),
            ]:
                y[mask] = source.iloc[a] + (x[mask] - source.index[a]) * (
                    source.iloc[b] - source.iloc[a]
                ) / (source.index[b] - source.index[a])
        self.df[name] = np.nan
        self.df.loc[selected, name] = y
        self.changed()
        self.notice(
            "IPOLATE",
            "Linear interpolation, repeated x uses mean observed y. Extrapolation only with epolate. Interpolated values are not observed data.",
        )

    def cmd_tsfill(self, args, opt):
        o = options(opt, ("full",))
        if args:
            raise StataError("tsfill [, full]")
        entity, time = (None, self.tsvar) if self.tsvar else self.panel or (None, None)
        if not time:
            raise StataError("Declare tsset or xtset with time")
        keys = [entity, time] if entity else [time]
        if (
            self.df.empty
            or self.df[keys].isna().any().any()
            or self.df.duplicated(keys).any()
        ):
            raise StataError("Require nonempty unique nonmissing time keys")
        chunks = []
        count = 0
        delta = self.time_delta
        for group, part in (
            self.df.groupby(entity, sort=True) if entity else [(None, self.df)]
        ):
            lo, hi = (
                (self.df[time].min(), self.df[time].max())
                if "full" in o
                else (part[time].min(), part[time].max())
            )
            span = (hi - lo) / delta
            if (
                not np.isfinite(span)
                or not np.isclose(span, round(span))
                or not np.allclose(
                    (part[time] - lo) / delta, np.round((part[time] - lo) / delta)
                )
            ):
                raise StataError("Time values must lie on declared delta grid")
            n = int(round(span)) + 1
            count += n
            if count > 2_000_000:
                raise StataError("tsfill would exceed two million rows")
            new = (
                part.set_index(time)
                .reindex(lo + np.arange(n) * delta)
                .rename_axis(time)
                .reset_index()
            )
            if entity:
                new[entity] = group
            chunks.append(new)
        self.df = pd.concat(chunks, ignore_index=True)
        self.changed()
        self.notice(
            "TSFILL",
            "Missing time rows added; non-key values remain missing. full uses common observed range across panels.",
        )

    def cmd_xtdescribe(self, args, opt):
        options(opt, ())
        if args or not self.panel or self.df.empty:
            raise StataError("Declare a nonempty xtset panel, then xtdescribe")
        counts = self.df.groupby(self.panel[0]).size()
        self.r = {
            "N": len(self.df),
            "n": len(counts),
            "Tmin": int(counts.min()),
            "Tmax": int(counts.max()),
            "Tbar": float(counts.mean()),
        }
        self.show_table("Panel structure", pd.DataFrame([self.r]))
        self.notice(
            "XTDESCRIBE",
            "Panel counts only; equal counts do not establish common time support or no gaps. Pattern diagrams not reproduced.",
        )

    def cmd_xtsum(self, args, opt):
        options(opt, ())
        if not self.panel:
            raise StataError("Declare xtset first")
        entity, _ = self.panel
        head, q = qualifiers(args)
        rows = []
        cols = (
            self.varlist(head, numeric=True)
            if head
            else list(self.df.select_dtypes(include=["number", "bool"]).columns)
        )
        for c in cols:
            data = self.df.loc[self.mask(q), list(dict.fromkeys([entity, c]))].dropna()
            y = data[c]
            means = data.groupby(entity)[c].mean()
            within = y - data.groupby(entity)[c].transform("mean") + y.mean()
            for label, v in [("overall", y), ("between", means), ("within", within)]:
                rows.append(
                    {
                        "Variable": c,
                        "Variation": label,
                        "Mean": y.mean() if label == "overall" else np.nan,
                        "Std. dev.": v.std(ddof=1),
                        "Min": v.min(),
                        "Max": v.max(),
                        "N": len(v),
                    }
                )
        self.show_table("Panel summary", pd.DataFrame(rows))
        self.notice(
            "XTSUM",
            "Within values subtract panel means and add the observation-weighted overall mean. Between spread uses unweighted panel means; missingness may unbalance panels.",
        )

    def cmd_graph(self, args, opt):
        kind, _, text = args.partition(" ")
        if kind not in ("box", "bar"):
            return super().cmd_graph(args, opt)
        o = options(opt, ("over", "title"))
        head, q = qualifiers(text)
        stat = "mean"
        if kind == "bar" and head.startswith("("):
            m = re.fullmatch(r"\((mean|sum|count)\)\s*(.*)", head)
            if not m:
                raise StataError("graph bar supports (mean), (sum), (count)")
            stat, head = m.groups()
        cols = self.varlist(head, numeric=True)
        groups = self.varlist(o["over"]) if "over" in o else []
        if not cols or len(groups) > 1 or ("over" in o and len(cols) != 1):
            raise StataError(
                "Specify numeric variables; over() supports one group and one outcome"
            )
        data = self.df.loc[self.mask(q)]
        values = (
            [(str(g), p[cols[0]].dropna()) for g, p in data.groupby(groups[0])]
            if groups
            else [(c, data[c].dropna()) for c in cols]
        )
        if not values or any(not len(v) or not np.isfinite(v).all() for _, v in values):
            raise StataError("No finite data in a plotted group")
        fig, ax = self._figure()
        labels = [g for g, _ in values]
        if kind == "box":
            ax.boxplot([v for _, v in values])
            ax.set_xticks(range(1, len(labels) + 1), labels)
        else:
            ax.bar(labels, [getattr(v, stat)() for _, v in values])
            ax.set_ylabel(stat)
        self._graph_ready(fig, ax, o.get("title", ""))
        self.notice(
            "GRAPH_SUMMARY",
            "Matplotlib quartile/whisker and category-order conventions may differ. Only one over() group and documented statistics supported.",
        )
