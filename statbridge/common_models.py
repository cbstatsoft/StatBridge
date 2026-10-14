# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Common course-level estimators and linear hypothesis tests."""

from __future__ import annotations
import ast
import fnmatch
import re
import numpy as np
import pandas as pd
from scipy import stats
from .syntax import StataError, options, qualifiers


def linear_expression(text, names):
    text = re.sub(r"_b\[([^\]]+)\]", r"\1", text.strip())
    names = list(names)
    mapping = {name: f"__coef_{i}" for i, name in enumerate(names)}
    pattern = (
        r"(?<![\w.])(?:"
        + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        + r")(?![\w.])"
    )
    text = re.sub(pattern, lambda m: mapping[m[0]], text)
    size = len(names)

    def walk(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return np.zeros(size), float(node.value)
        if isinstance(node, ast.Name) and node.id in mapping.values():
            v = np.zeros(size)
            v[int(node.id.removeprefix("__coef_"))] = 1
            return v, 0.0
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v, c = walk(node.operand)
            sign = -1 if isinstance(node.op, ast.USub) else 1
            return sign * v, sign * c
        if isinstance(node, ast.BinOp):
            a, ac = walk(node.left)
            b, bc = walk(node.right)
            if isinstance(node.op, ast.Add):
                return a + b, ac + bc
            if isinstance(node.op, ast.Sub):
                return a - b, ac - bc
            if isinstance(node.op, ast.Mult) and not (a.any() and b.any()):
                return a * bc + b * ac, ac * bc
            if isinstance(node.op, ast.Div) and not b.any() and bc != 0:
                return a / bc, ac / bc
        raise StataError(
            "Use a linear combination of estimated coefficients and numeric constants"
        )

    try:
        value = walk(ast.parse(text, mode="eval").body)
    except (SyntaxError, ValueError, OverflowError):
        raise StataError("Invalid linear coefficient expression") from None
    if not np.isfinite(value[0]).all() or not np.isfinite(value[1]):
        raise StataError("Nonfinite hypothesis")
    return value


class CommonModelCommands:
    def _wald(self, matrix, constants):
        m = self.require_model()
        matrix = np.asarray(matrix)
        value = matrix @ m.params.to_numpy() + np.asarray(constants)
        variance = matrix @ m.cov.to_numpy() @ matrix.T
        rank = np.linalg.matrix_rank(variance)
        if rank < len(value):
            raise StataError("Redundant restrictions or singular hypothesis covariance")
        statistic = float(value @ np.linalg.solve(variance, value))
        if statistic < 0:
            raise StataError("Invalid hypothesis covariance")
        if m.df is not None:
            f = statistic / rank
            self.r = {
                "F": f,
                "df": rank,
                "df_r": m.df,
                "p": float(stats.f.sf(f, rank, m.df)),
            }
            self.out(f"F({rank}, {m.df:g}) = {f:.6f}; p = {self.r['p']:.6g}")
        else:
            self.r = {
                "chi2": statistic,
                "df": rank,
                "p": float(stats.chi2.sf(statistic, rank)),
            }
            self.out(f"chi2({rank}) = {statistic:.6f}; p = {self.r['p']:.6g}")

    def cmd_test(self, args, opt):
        options(opt, ())
        m = self.require_model()
        if "=" not in args:
            return super().cmd_test(args, opt)
        if args.strip().startswith("("):
            constraints = re.findall(r"\(([^()]+)\)", args)
            if not constraints or re.sub(r"\([^()]+\)", "", args).strip():
                raise StataError("Use test (x=0) (z=1) with unnested restrictions")
        else:
            constraints = [args]
        matrix, constants = [], []
        for constraint in constraints:
            parts = constraint.split("=")
            if len(parts) != 2:
                raise StataError("Each restriction requires one =")
            a, ac = linear_expression(parts[0], m.params.index)
            b, bc = linear_expression(parts[1], m.params.index)
            matrix.append(a - b)
            constants.append(ac - bc)
        self._wald(matrix, constants)

    def cmd_testparm(self, args, opt):
        options(opt, ())
        m = self.require_model()
        chosen = []
        for term in args.split():
            parts = []
            for atom in term.split("#"):
                if re.fullmatch(r"i\.[A-Za-z_]\w*", atom):
                    parts.append("*." + atom[2:])
                elif atom.startswith("c."):
                    parts.append(atom[2:])
                else:
                    parts.append(atom)
            pattern = "#".join(parts)
            matches = [
                name
                for name in m.params.index
                if fnmatch.fnmatchcase(name, pattern)
                and name.count("#") == pattern.count("#")
            ]
            if not matches:
                raise StataError(f"No estimated coefficients match {term}")
            chosen.extend(name for name in matches if name not in chosen)
        if not chosen:
            raise StataError(
                "Specify coefficient names, wildcards, or i.variable terms"
            )
        return super().cmd_test(" ".join(chosen), "")

    def cmd_lincom(self, args, opt):
        o = options(opt, ("level", "eform"))
        m = self.require_model()
        weights, constant = linear_expression(args, m.params.index)
        b = float(weights @ m.params + constant)
        variance = float(weights @ m.cov @ weights)
        if not np.isfinite(variance) or variance <= 0:
            raise StataError("Combination has zero or invalid variance")
        se = np.sqrt(variance)
        level = float(o.get("level", m.level))
        if not 0 < level < 100:
            raise StataError("level() must lie between 0 and 100")
        dist = stats.t(m.df) if m.df is not None else stats.norm
        crit = dist.ppf(1 - (1 - level / 100) / 2)
        self.r = {
            "estimate": b,
            "se": se,
            "p": float(2 * dist.sf(abs(b / se))),
            "lb": b - crit * se,
            "ub": b + crit * se,
        }
        if "eform" in o:
            self.r.update(
                estimate=float(np.exp(b)),
                se=float(np.exp(b) * se),
                lb=float(np.exp(self.r["lb"])),
                ub=float(np.exp(self.r["ub"])),
            )
            self.notice(
                "LINCOM_EFORM",
                "Exponentiated estimate and limits; delta-method SE. The p-value tests the untransformed combination equal to zero.",
            )
        self.out(pd.Series(self.r).to_string(float_format=lambda v: f"{v:.6g}"))

    def _oneway(self, args, opt):
        o = options(opt, ("tabulate",))
        head, q = qualifiers(args)
        cols = self.varlist(head)
        if len(cols) != 2 or not pd.api.types.is_numeric_dtype(self.df[cols[0]]):
            raise StataError("Syntax: oneway response group [if ...] [, tabulate]")
        y, group = cols
        frame = self.df.loc[self.mask(q), cols].dropna()
        frame = frame.loc[frame[group].ne("")]
        groups = [part[y].to_numpy() for _, part in frame.groupby(group, sort=True)]
        n, k = len(frame), len(groups)
        if k < 2 or n <= k:
            raise StataError(
                "Need at least two groups and positive residual degrees of freedom",
                2001,
            )
        if not np.isfinite(frame[y].to_numpy()).all():
            raise StataError("ANOVA response must be finite")
        grand = frame[y].mean()
        ssb = sum(len(x) * (x.mean() - grand) ** 2 for x in groups)
        ssw = sum(((x - x.mean()) ** 2).sum() for x in groups)
        if ssw <= 0:
            raise StataError("Within-group variance is zero")
        f = ssb / (k - 1) / (ssw / (n - k))
        self.r = {
            "N": n,
            "F": float(f),
            "df_m": k - 1,
            "df_r": n - k,
            "p": float(stats.f.sf(f, k - 1, n - k)),
            "ss_m": float(ssb),
            "ss_r": float(ssw),
        }
        table = pd.DataFrame(
            {
                "SS": [ssb, ssw, ssb + ssw],
                "df": [k - 1, n - k, n - 1],
                "MS": [ssb / (k - 1), ssw / (n - k), (ssb + ssw) / (n - 1)],
            },
            index=["Between groups", "Within groups", "Total"],
        )
        self.out(
            "One-way analysis of variance\n"
            + table.to_string(float_format=lambda v: f"{v:.6g}")
            + f"\nF({k - 1}, {n - k}) = {f:.6g}; p = {self.r['p']:.6g}"
        )
        if "tabulate" in o:
            self.out(frame.groupby(group)[y].agg(["count", "mean", "std"]).to_string())
        self.notice(
            "ONEWAY",
            "Classical equal-variance ANOVA. Bartlett's test and multiple-comparison procedures are not produced; unsupported options fail explicitly.",
        )
        return y, group, q

    def cmd_oneway(self, args, opt):
        self._oneway(args, opt)

    def cmd_anova(self, args, opt):
        options(opt, ())
        head, q = qualifiers(args)
        parts = head.split()
        if len(parts) != 2:
            raise StataError(
                "anova currently supports one categorical factor; use regress with i./# terms for factorial models"
            )
        factor = parts[1].removeprefix("i.")
        self.varlist(factor, numeric=True)
        if (
            self.df[factor].dropna().lt(0).any()
            or (self.df[factor].dropna() % 1 != 0).any()
        ):
            raise StataError("anova factor must be a nonnegative integer variable")
        suffix = "".join(f" {key} {value}" for key, value in q.items())
        # Validate/sample the ANOVA before changing active estimation results.
        self._oneway(f"{parts[0]} {factor}{suffix}", "")
        oldquiet = self.quiet
        self.quiet = True
        try:
            self.fit_model("regress", f"{parts[0]} i.{factor}{suffix}", "")
        finally:
            self.quiet = oldquiet
        self.model.command = "anova"
        self.report_model()

    def cmd_areg(self, args, opt):
        o = options(opt, ("absorb", "vce", "robust", "level"))
        if "absorb" not in o:
            raise StataError("areg requires absorb(one_group_variable)")
        cols = self.varlist(o["absorb"], numeric=True)
        if len(cols) != 1:
            raise StataError("One absorbed group variable is supported")
        group = cols[0]
        head, q = qualifiers(args)
        ngroups = self.df.loc[self.mask(q), group].nunique()
        if ngroups > 500 or len(self.df) * (ngroups + len(head.split())) > 10_000_000:
            raise StataError(
                "areg's explicit-indicator backend is limited to 500 groups and 10 million design cells; use xtreg, fe for large one-way panels"
            )
        suffix = "".join(f" {key} {value}" for key, value in q.items())
        fitopt = " ".join(
            key if value is True else f"{key}({value})"
            for key, value in o.items()
            if key != "absorb"
        )
        oldquiet = self.quiet
        self.quiet = True
        try:
            self.fit_model("regress", f"{head} i.{group}{suffix}", fitopt)
        finally:
            self.quiet = oldquiet
        m = self.model
        nuisance = [
            c for c in m.params.index if re.fullmatch(rf"\d+\.{re.escape(group)}", c)
        ]
        keep = [c for c in m.params.index if c not in nuisance]
        transform = pd.DataFrame(0.0, index=keep, columns=m.params.index)
        for c in keep:
            transform.loc[c, c] = 1
        for c in nuisance:
            transform.loc["_cons", c] = m.x[c].mean()
        params = transform @ m.params
        cov = transform @ m.cov @ transform.T
        m.params, m.cov = params, cov
        m.x = m.x[keep]
        m.predicted = m.x @ m.params
        m.linear_prediction = m.predicted.copy()
        m.command = "areg"
        m.fit_extra = {
            "N_groups": self.df.loc[m.sample, group].nunique(),
            "df_absorb": len(nuisance),
        }
        self.notice(
            "AREG",
            "One absorbed factor is fitted by explicit indicator OLS. The intercept is normalised at sample group shares; covariance is transformed accordingly. Model R-squared includes absorbed effects. Predictions report xb without absorbed effects; residuals include them. Large-group problems should use xtreg, fe. Exact Stata parity is not certified.",
        )
        self.report_model()

    def cmd_spearman(self, args, opt):
        o = options(opt, ("pw", "stats"))
        if "stats" in o and set(o["stats"].split()) - {"rho", "p", "obs"}:
            raise StataError("stats() accepts rho p obs")
        head, q = qualifiers(args)
        cols = self.varlist(head, numeric=True)
        if len(cols) < 2:
            raise StataError("Specify at least two variables")
        df = self.df.loc[self.mask(q), cols]
        if "pw" not in o:
            df = df.dropna()
        corr = pd.DataFrame(np.nan, index=cols, columns=cols)
        p = corr.copy()
        n = corr.copy()
        for a in cols:
            for b in cols:
                valid = df[a].notna() & df[b].notna()
                x, y = df.loc[valid, a], df.loc[valid, b]
                n.loc[a, b] = len(x)
                if len(x) > 2 and x.nunique() > 1 and y.nunique() > 1:
                    result = stats.spearmanr(x, y)
                    corr.loc[a, b], p.loc[a, b] = result.statistic, result.pvalue
        wanted = o.get("stats", "rho").split()
        for key, table in (("rho", corr), ("p", p), ("obs", n)):
            if key in wanted:
                self.out(
                    key + "\n" + table.to_string(float_format=lambda v: f"{v:.6g}")
                )
        self.r = {"N": n.iloc[0, 1], "rho": corr.iloc[0, 1], "p": p.iloc[0, 1]}
        self.notice(
            "SPEARMAN",
            "Ranks use average ties and SciPy asymptotic two-sided p-values, not exact permutation inference. Small-sample inference may differ from Stata.",
        )

    def cmd_predict(self, args, opt):
        # Normalise familiar Stata abbreviations while keeping option rejection explicit.
        aliases = {"resid": "residuals", "residual": "residuals"}
        opt = " ".join(aliases.get(token, token) for token in opt.split())
        m = self.require_model()
        head, q = qualifiers(args)
        parts = head.split()
        name = parts[-1] if parts else ""
        if len(parts) > 2 or (len(parts) == 2 and parts[0] not in ("float", "double")):
            raise StataError(
                "Syntax: predict [double|float] new [if ...] [, statistic]"
            )
        # The existing guarded sample-only behaviour remains for other estimators.
        if m.command != "regress" or m.weight_type or m.prediction_terms is None:
            o = options(opt, ("xb", "residuals", "pr"))
            mask = self.mask(q)
            super().cmd_predict(name, opt)
            self.df.loc[~mask, name] = np.nan
            return
        o = options(
            opt,
            (
                "xb",
                "residuals",
                "stdp",
                "stdf",
                "hat",
                "leverage",
                "rstandard",
                "cooksd",
            ),
        )
        if len(o) > 1:
            raise StataError("Choose one prediction statistic")
        self.newvar(name)
        if m.revision != self.revision or not m.sample.isin(self.df.index).all():
            raise StataError("Data changed since estimation; refit before prediction")
        if not np.array_equal(
            self.model_response(m.y.name, self.df.loc[m.sample]).to_numpy(),
            m.y.to_numpy(),
            equal_nan=True,
        ):
            raise StataError("Fitted response changed; refit before prediction")
        mask = self.mask(q)
        frame = self.df.loc[mask]
        # Explicit base levels are fitted metadata, not rediscovered from the prediction subset.
        terms = []
        for term in m.prediction_terms:
            for atom in term.split("#"):
                match = re.fullmatch(r"(i|ib-?\d+)\.(\w+)", atom)
                if match:
                    original = self.df.loc[m.sample, match[2]].dropna()
                    allowed = original.unique()
                    if not frame[match[2]].dropna().isin(allowed).all():
                        raise StataError(
                            f"Prediction contains an unestimated level of {match[2]}"
                        )
            terms.append(term)
        # Rebuild on all rows so implicit factor bases match the original fit's frame.
        design = self.regressors(terms, self.df)
        if "_cons" in m.params:
            design.insert(0, "_cons", 1.0)
        if not set(m.params.index).issubset(design.columns):
            raise StataError("Fitted design columns are no longer available")
        design = design.loc[:, m.params.index]
        if not np.allclose(design.loc[m.sample], m.x, equal_nan=True):
            raise StataError("Fitted predictors changed; refit before prediction")
        design = design.loc[mask]
        valid = design.notna().all(axis=1)
        for factor in re.findall(r"(?:^|[# ])(?:i|ib-?\d+)\.(\w+)", " ".join(terms)):
            valid &= frame[factor].notna()
        design = design.loc[valid]
        statistic = next(iter(o), "xb")
        value = design @ m.params
        if statistic in ("stdp", "stdf"):
            variance = np.einsum("ij,jk,ik->i", design, m.cov, design)
            if statistic == "stdf":
                if m.covariance != "ols":
                    raise StataError(
                        "stdf is supported only for conventional unweighted OLS"
                    )
                variance += m.result.mse_resid
            value = pd.Series(np.sqrt(np.maximum(variance, 0)), index=design.index)
        elif statistic == "residuals":
            value = self.model_response(m.y.name, self.df.loc[design.index]) - value
        elif statistic in ("hat", "leverage", "rstandard", "cooksd"):
            if m.covariance != "ols":
                raise StataError(
                    "Influence diagnostics require conventional unweighted OLS"
                )
            influence = m.result.get_influence()
            values = {
                "hat": influence.hat_matrix_diag,
                "leverage": influence.hat_matrix_diag,
                "rstandard": influence.resid_studentized_internal,
                "cooksd": influence.cooks_distance[0],
            }
            value = pd.Series(values[statistic], index=m.sample).reindex(design.index)
        self.df[name] = value.reindex(self.df.index)
        self.dirty = True
        self.notice(
            "PREDICT_OLS",
            "OLS xb, residuals and prediction standard errors include eligible out-of-sample rows. Influence diagnostics are estimation-sample only. Unknown factor levels are rejected; storage remains double precision. Other estimators retain their documented sample-only prediction scope.",
        )

    def cmd_estat(self, args, opt):
        if args.strip() != "ovtest":
            return super().cmd_estat(args, opt)
        options(opt, ())
        m = self.require_model()
        if m.command != "regress" or m.weight_type or m.covariance != "ols":
            raise StataError("estat ovtest requires conventional unweighted OLS")
        if "_cons" not in m.params:
            raise StataError("estat ovtest requires a constant")
        from statsmodels.stats.diagnostic import linear_reset

        result = linear_reset(m.result, power=4, test_type="fitted", use_f=True)
        self.r = {
            "F": float(result.fvalue),
            "df": float(result.df_num),
            "df_r": float(result.df_denom),
            "p": float(result.pvalue),
        }
        self.out(
            f"Ramsey RESET F({self.r['df']:g}, {self.r['df_r']:g}) = {self.r['F']:.6g}; p = {self.r['p']:.6g}"
        )
        self.notice(
            "RESET",
            "Tests powers 2, 3 and 4 of fitted values with an augmented-model F test; backend scaling and rank tolerances may differ from Stata.",
        )
