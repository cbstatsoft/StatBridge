# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded multiple imputation by chained equations and Rubin pooling.

Unlike single imputation, MICE is stochastic and estimates within- and
between-imputation uncertainty. This extension intentionally supports only
continuous, numeric OLS models; it is not Stata's general mi framework.
"""
from __future__ import annotations

from threading import Lock

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from statsmodels.imputation.mice import MICEData

from .syntax import StataError, options

_MICE_RANDOM_LOCK = Lock()


def rubin_pool(coefficients, covariances):
    """Rubin's classical large-sample combination, with per-term old df."""
    estimates = np.asarray(coefficients, dtype=float)
    within = np.asarray(covariances, dtype=float)
    if estimates.ndim != 2 or within.shape != (len(estimates), estimates.shape[1], estimates.shape[1]):
        raise ValueError("Mismatched imputation coefficients/covariances")
    m, p = estimates.shape
    if m < 2 or p < 1:
        raise ValueError("At least two complete imputations are necessary")
    if not np.isfinite(estimates).all() or not np.isfinite(within).all():
        raise ValueError("Nonfinite imputation estimates")
    qbar = estimates.mean(axis=0)
    w = within.mean(axis=0)
    b = np.cov(estimates, rowvar=False, ddof=1)
    b = np.atleast_2d(b).reshape(p, p)
    t = w + (1 + 1 / m) * b
    if not np.isfinite(t).all() or np.linalg.eigvalsh(t).min() < -1e-9:
        raise ValueError("Invalid pooled covariance")
    v = np.diag(t)
    if np.any(v <= 0) or np.any(np.diag(w) <= 0):
        raise ValueError("Non-positive pooled variances")
    r = ((1 + 1 / m) * np.diag(b)) / np.diag(w)
    df = np.full(p, np.inf)
    positive = r > 1e-12
    df[positive] = (m - 1) * (1 + 1 / r[positive]) ** 2
    return qbar, t, df, r


class MultipleImputationCommands:
    def cmd_mi(self, args, opt):
        """StatBridge extension: mi regress y x ..., m(#) burnin(#) seed(#)."""
        terms = args.strip().split()
        if len(terms) < 3 or terms[0] != "regress":
            raise StataError(
                "Syntax: mi regress response numeric_predictors, "
                "m(10) burnin(10) between(5) seed(42) level(95)"
            )
        o = options(opt, ("m", "burnin", "between", "seed", "level"))
        from .specialist_models import _positive_integer

        m = _positive_integer(o.get("m", 10), "m", 5, 30)
        burnin = _positive_integer(o.get("burnin", 10), "burnin", 3, 50)
        between = _positive_integer(o.get("between", 5), "between", 1, 20)
        seed = _positive_integer(o.get("seed", 42), "seed", 0, 2_147_483_647)
        level = float(o.get("level", self.level))
        if not np.isfinite(level) or not 0 < level < 100:
            raise StataError("Invalid level()")
        variables = terms[1:]
        if any(not v.isidentifier() for v in variables):
            raise StataError("mi regress supports only plain numeric variable names; no factors/interactions")
        if len(set(variables)) != len(variables) or len(variables) > 12:
            raise StataError("mi regress needs distinct variables and at most 11 predictors")
        self.varlist(" ".join(variables), numeric=True)
        data = self.df.loc[:, variables].copy()
        if data.shape[0] < 40 or data.size > 100000:
            raise StataError("mi regress requires >=40 rows and <=100,000 data cells")
        if data.notna().all().all():
            raise StataError("No missing values in the selected MI variables")
        if any(
            not np.isfinite(data[c].dropna().to_numpy(dtype=float)).all()
            or data[c].dropna().nunique() < 6
            for c in variables
        ):
            raise StataError(
                "mi regress requires finite continuous variables with >=6 observed distinct values; "
                "categorical imputation is not implemented"
            )
        # PMM requires enough donors; the complete response can be imputed but
        # this is not the recommended analysis for outcomes missing by design.
        if any(data[c].notna().sum() < 20 for c in variables):
            raise StataError("Each imputed variable needs at least 20 observed donor values")
        if len(data) < 4 * len(variables):
            raise StataError("Insufficient rows for stable continuous imputation regressions")
        try:
            estimates = []
            covariances = []
            with _MICE_RANDOM_LOCK:
                saved_random_state = np.random.get_state()
                try:
                    np.random.seed(seed)
                    mice = MICEData(data.reset_index(drop=True))
                    for _ in range(burnin):
                        mice.update_all(1)
                    for _ in range(m):
                        mice.update_all(between)
                        complete = mice.data
                        x = sm.add_constant(complete[variables[1:]], has_constant="add")
                        x.columns = ["_cons"] + variables[1:]
                        fit = sm.OLS(complete[variables[0]], x).fit()
                        if (fit.df_resid <= 0 or
                                not np.isfinite(fit.params).all() or
                                not np.isfinite(fit.cov_params()).all().all()):
                            raise StataError("Invalid regression within an imputation")
                        estimates.append(fit.params.to_numpy(dtype=float))
                        covariances.append(fit.cov_params().to_numpy(dtype=float))
                finally:
                    np.random.set_state(saved_random_state)
            pooled, covariance, dfs, r = rubin_pool(estimates, covariances)
        except (ValueError, np.linalg.LinAlgError, ZeroDivisionError) as exc:
            raise StataError(f"MI regression or pooling failed: {exc}") from exc
        se = np.sqrt(np.diag(covariance))
        t = pooled / se
        pval = 2 * stats.t.sf(np.abs(t), dfs)
        crit = stats.t.ppf(0.5 + level / 200, dfs)
        table = pd.DataFrame({
            "Coef.": pooled, "Std. err.": se, "t": t,
            "P>|t|": pval, "df": dfs,
            "CI lower": pooled - crit * se,
            "CI upper": pooled + crit * se,
            "Relative increase": r,
        }, index=["_cons"] + variables[1:])
        self.model = None
        self.e = {"N": len(data), "M": m, "df_m": len(variables) - 1}
        self.r = {"N": len(data), "M": m, "burnin": burnin, "between": between,
                  "seed": seed, "max_relative_increase": float(max(r))}
        self.results_table = table
        self.results_table_title = "Rubin-pooled OLS after continuous MICE"
        self.out(
            f"Predictive-mean-matching chained equations; m={m}, burn-in={burnin}, "
            f"steps between imputations={between}, seed={seed}\n"
            + table.to_string(float_format=lambda v: f"{v:.6g}")
        )
        self.notice(
            "MI_SCOPE",
            "StatBridge extension, not Stata's mi syntax. Continuous numeric OLS "
            "only, chained-equation PMM, stochastic imputation, Rubin large-sample "
            "pooling and original Rubin df approximation. No small-sample Barnard-Rubin "
            "df, survey/cluster VCE, passive transformations, noncontinuous imputation, "
            "diagnostic trace convergence tests or general MAR justification. "
            "Imputed datasets are not written into the workspace. This is exploratory, "
            "not a validated general-purpose missing-data analysis.",
        )
