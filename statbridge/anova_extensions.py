# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded factorial ANOVA and pooled-variance post-hoc comparisons.

These are classical fixed-effect, unweighted OLS procedures. Unsupported
designs/options must fail instead of silently using a different estimator.
"""
from __future__ import annotations

import itertools
import re
from functools import wraps

import numpy as np
import pandas as pd
from scipy import stats

from .syntax import StataError, options, qualifiers


def _fitted_ss(y, x):
    """Return RSS and rank, using an explicit least-squares projection."""
    a = np.asarray(x, dtype=float)
    b = np.asarray(y, dtype=float)
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise StataError("ANOVA requires finite, complete numeric observations")
    beta, _, rank, _ = np.linalg.lstsq(a, b, rcond=None)
    resid = b - a @ beta
    return float(resid @ resid), int(rank)


def _anova_terms(tokens):
    """Subset: up to two integer-valued factors, # and ## interactions."""
    terms = []
    factors = []
    for token in tokens:
        if any(sign in token for sign in ("/", "|", "*", "(", ")")):
            raise StataError("Only a, b, a#b and a##b categorical terms are supported")
        token = re.sub(r"(?<!\w)i\.(?=[A-Za-z_])", "", token)
        if "##" in token:
            names = token.split("##")
            if len(names) != 2:
                raise StataError("Only two-factor interactions are supported")
            proposed = [names[0], names[1], "#".join(names)]
        else:
            proposed = [token]
        for term in proposed:
            atoms = term.split("#")
            if len(atoms) not in (1, 2) or any(
                not re.fullmatch(r"[A-Za-z_]\w*", a) for a in atoms
            ):
                raise StataError("Only named categorical factors and two-way interactions are supported")
            factors.extend(a for a in atoms if a not in factors)
            if term not in terms:
                terms.append(term)
    if not 1 <= len(factors) <= 2 or not terms:
        raise StataError("ANOVA supports one or two categorical factors")
    if any("#" in term and not set(term.split("#")).issubset(terms) for term in terms):
        raise StataError("Include both factor main effects before their interaction")
    return terms, factors


def _preserve_estimation_on_error(function):
    """A rejected ANOVA must not discard the preceding fitted model."""
    @wraps(function)
    def guarded(self, *args, **kwargs):
        model = self.model
        e = self.e.copy()
        r = self.r.copy()
        previous_table = getattr(self, "results_table", None)
        previous_title = getattr(self, "results_table_title", None)
        try:
            return function(self, *args, **kwargs)
        except Exception:
            self.model = model
            self.e = e
            self.r = r
            self.results_table = previous_table
            self.results_table_title = previous_title
            raise
    return guarded


class AnovaExtensions:
    def _oneway_posthoc(self, frame, response, factor, *, mse, df_r, method, level):
        """Pooled-MSE comparisons; no paired, Welch or cluster adjustment."""
        groups = [(key, values[response].to_numpy(dtype=float))
                  for key, values in frame.groupby(factor, sort=True)]
        pairs = list(itertools.combinations(groups, 2))
        if len(pairs) > 4950:
            raise StataError("Too many factor levels for pairwise output (max 100 levels)")
        k = len(groups)
        m = len(pairs)
        alpha = 1 - level / 100
        rows = []
        for (left, a), (right, b) in pairs:
            diff = float(a.mean() - b.mean())
            se = float(np.sqrt(mse * (1 / len(a) + 1 / len(b))))
            t = abs(diff) / se
            raw = float(2 * stats.t.sf(t, df_r))
            if method == "bonferroni":
                p = min(1.0, m * raw)
                crit = float(stats.t.ppf(1 - alpha / (2 * m), df_r))
            elif method == "sidak":
                p = float(-np.expm1(m * np.log1p(-raw)))
                crit = float(stats.t.ppf((1 + (1 - alpha) ** (1 / m)) / 2, df_r))
            elif method == "tukey":
                # Tukey-Kramer for unequal group sizes.
                q = abs(diff) / (se / np.sqrt(2))
                p = float(stats.studentized_range.sf(q, k, df_r))
                crit = float(stats.studentized_range.ppf(1 - alpha, k, df_r) / np.sqrt(2))
            else:  # Scheffe's simultaneous F-family envelope
                f = t * t / (k - 1)
                p = float(stats.f.sf(f, k - 1, df_r))
                crit = float(np.sqrt((k - 1) * stats.f.ppf(1 - alpha, k - 1, df_r)))
            rows.append({
                "Group A": str(left), "Group B": str(right),
                "Mean diff.": diff, "Std. err.": se,
                "Adj. p": max(0.0, min(1.0, p)),
                "CI lower": diff - crit * se,
                "CI upper": diff + crit * se,
            })
        table = pd.DataFrame(rows)
        self.out(
            f"{method.capitalize()} pairwise group means ({level:g}% simultaneous intervals)\n"
            + table.to_string(index=False, float_format=lambda x: f"{x:.6g}")
        )
        self.results_table = table
        self.results_table_title = method.capitalize() + " pairwise mean comparisons"
        self.r["comparisons"] = len(pairs)
        self.r["mcompare"] = method
        self.notice(
            "POSTHOC_POOLED",
            "Pairwise tests assume independent observations, normal homoskedastic "
            "errors and a pooled within-group MSE. Intervals are simultaneous "
            "under the requested Tukey-Kramer, Bonferroni, Sidak or Scheffe adjustment; "
            "these are not Welch, clustered, or repeated-measures comparisons.",
        )

    def cmd_pwmean(self, args, opt):
        """Bounded unweighted group means and adjusted pairwise differences."""
        o = options(opt, ("over", "mcompare", "level"))
        if "over" not in o:
            raise StataError(
                "Syntax: pwmean response, over(group) [mcompare(tukey|bonferroni|sidak|scheffe)]"
            )
        head, q = qualifiers(args)
        vars_ = self.varlist(head, numeric=True)
        factor = self.varlist(o["over"])
        if len(vars_) != 1 or len(factor) != 1:
            raise StataError("pwmean requires one numeric response and one grouping variable")
        y, g = vars_[0], factor[0]
        level = float(o.get("level", self.level))
        if not 0 < level < 100:
            raise StataError("level() must be between 0 and 100")
        method = str(o.get("mcompare", "tukey")).lower()
        if method not in ("tukey", "bonferroni", "sidak", "scheffe"):
            raise StataError("mcompare() supports tukey, bonferroni, sidak, scheffe")
        frame = self.df.loc[self.mask(q), [y, g]].dropna()
        frame = frame.loc[frame[g].ne("")]
        groups = [sub[y].to_numpy(dtype=float) for _, sub in frame.groupby(g, sort=True)]
        k, n = len(groups), len(frame)
        if k < 2 or n <= k or k > 100:
            raise StataError("pwmean needs 2-100 groups and positive residual degrees of freedom")
        if any(not np.isfinite(values).all() for values in groups):
            raise StataError("pwmean requires finite numeric observations")
        sse = float(sum(np.sum((values - values.mean()) ** 2) for values in groups))
        if sse <= 0:
            raise StataError("Pooled residual variance is zero")
        mse = sse / (n - k)
        self.r = {"N": n, "df_r": n - k, "mse": mse}
        self.out("Group means\n" + frame.groupby(g)[y].agg(
            ["count", "mean", "std"]
        ).to_string(float_format=lambda v: f"{v:.6g}"))
        self._oneway_posthoc(frame, y, g, mse=mse, df_r=n - k, method=method, level=level)

    @_preserve_estimation_on_error
    def cmd_anova(self, args, opt):
        o = options(opt, ("partial", "sequential"))
        if "partial" in o and "sequential" in o:
            raise StataError("Choose partial OR sequential sums of squares")
        head, q = qualifiers(args)
        tokens = head.split()
        if len(tokens) < 2:
            raise StataError(
                "Syntax: anova response a [b] [a#b] [, partial|sequential]"
            )
        response = self.varlist(tokens[0], numeric=True)
        if len(response) != 1:
            raise StataError("One numeric response variable required")
        terms, factors = _anova_terms(tokens[1:])
        frame = self.df.loc[self.mask(q)]
        levels = {}
        for name in factors:
            self.varlist(name, numeric=True)
            raw = frame[name].dropna()
            if (not np.isfinite(raw.to_numpy(dtype=float)).all()
                    or raw.lt(0).any()
                    or raw.ne(np.floor(raw)).any()):
                raise StataError("ANOVA factors must be finite nonnegative integers")
            levels[name] = int(raw.nunique())
            if levels[name] < 2:
                raise StataError(f"Factor {name} needs at least two observed categories")
        width = 1
        for term in terms:
            width += int(np.prod([levels[a] - 1 for a in term.split("#")]))
        if width > 256 or len(frame) * width > 5_000_000:
            raise StataError(
                "ANOVA indicator design exceeds 256 columns or 5 million "
                "cells; reduce the sample/factor categories before fitting"
            )
        fit_tokens = ["i." + term.replace("#", "#i.") for term in terms]
        suffix = "".join(f" {key} {value}" for key, value in q.items())
        fit_args = " ".join([response[0], *fit_tokens]) + suffix
        old_quiet = self.quiet
        self.quiet = True
        try:
            self.fit_model("regress", fit_args, "")
        finally:
            self.quiet = old_quiet
        m = self.require_model()
        x = m.x
        y = m.y
        if "_cons" not in x.columns or m.df is None or m.df <= 0:
            raise StataError("ANOVA requires an intercept and positive residual df")
        term_columns = {}
        for term in terms:
            if "#" in term:
                a, b = term.split("#")
                pattern = rf"[^#]+\.{re.escape(a)}#[^#]+\.{re.escape(b)}"
            else:
                pattern = rf"[^#]+\.{re.escape(term)}"
            block = [col for col in x if re.fullmatch(pattern, col)]
            if not block:
                raise StataError(f"ANOVA term {term} has no estimable columns")
            term_columns[term] = block
        if set(["_cons", *(c for cols in term_columns.values() for c in cols)]) != set(x.columns):
            raise StataError("Unrecognised ANOVA design columns")
        rss_full, rank_full = _fitted_ss(y, x)
        df_r = len(y) - rank_full
        if df_r <= 0 or rss_full <= np.finfo(float).eps * max(float(y @ y), 1.0):
            raise StataError("ANOVA requires positive residual variance and degrees of freedom")
        mse = rss_full / df_r
        method = "sequential" if "sequential" in o else "partial"
        rows = []
        previous = ["_cons"]
        for term in terms:
            if method == "partial":
                reduced = [c for c in x if c not in term_columns[term]]
                rank_diff = rank_full
                rss_before, rank_before = _fitted_ss(y, x[reduced])
                df_term = rank_diff - rank_before
                ss_term = rss_before - rss_full
            else:
                added = previous + term_columns[term]
                rss_before, rank_before = _fitted_ss(y, x[previous])
                rss_after, rank_after = _fitted_ss(y, x[added])
                df_term = rank_after - rank_before
                ss_term = rss_before - rss_after
                previous = added
            if df_term <= 0 or ss_term < -1e-8 * max(rss_full, 1.0):
                raise StataError(f"ANOVA term {term} is not independently estimable")
            ss_term = max(0.0, ss_term)
            fvalue = (ss_term / df_term) / mse
            rows.append({
                "Term": term, "SS": ss_term, "df": df_term,
                "MS": ss_term / df_term, "F": fvalue,
                "P>F": float(stats.f.sf(fvalue, df_term, df_r)),
            })
        output = pd.DataFrame(rows).set_index("Term")
        self.model.command = "anova"
        self.e.update({"N": len(y), "df_r": df_r, "df_m": rank_full - 1})
        self.results_table = output
        self.results_table_title = method.capitalize() + " ANOVA"
        self.out(
            f"{method.capitalize()} sums of squares ANOVA, N={len(y)}, "
            f"residual df={df_r}, pooled MSE={mse:.6g}\n"
            + output.to_string(float_format=lambda val: f"{val:.6g}")
        )
        self.notice(
            "FACTORIAL_ANOVA",
            "Fixed-effects OLS with independent homoskedastic errors. "
            "Partial SS are drop-one-term comparisons under reference-level "
            "indicator coding; main effects with interactions depend on that "
            "coding and can differ from Stata's partial-SS conventions. "
            "Sequential SS are order-dependent. Repeated measures, nested "
            "factors, weights, missing cells and robust/clustered F tests are "
            "not supported.",
        )
