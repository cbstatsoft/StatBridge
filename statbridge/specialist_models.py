# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated-subset specialist estimators, using installed scientific backends.

No command claims the full Stata estimator or postestimation interface.
"""
from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.anova import AnovaRM
from statsmodels.tsa.api import VAR

from .models import Model
from .syntax import StataError, options, qualifiers


def _positive_integer(value, name, minimum=1, maximum=1000):
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        raise StataError(f"{name}() requires an integer") from None
    if str(number) != str(value).strip() or not minimum <= number <= maximum:
        raise StataError(f"{name}() requires an integer from {minimum} to {maximum}")
    return number


class SpecialistModels:
    def cmd_clear(self, args, opt):
        result = super().cmd_clear(args, opt)
        self._specialist_var = None
        return result

    def cmd_mixed(self, args, opt):
        """Gaussian random-intercept or correlated random-intercept/slope model."""
        o = options(opt, ("group", "slope", "mle", "level"))
        if "group" not in o:
            raise StataError("Syntax: mixed y x ..., group(id) [slope(x) mle level(#)]")
        names, q = qualifiers(args)
        terms = names.split()
        if len(terms) < 2:
            raise StataError("mixed requires a response and at least one fixed-effect predictor")
        group_names = self.varlist(str(o["group"]))
        if len(group_names) != 1:
            raise StataError("group() requires one variable")
        group_name = group_names[0]
        slope_name = None
        if "slope" in o:
            slopes = self.varlist(str(o["slope"]), numeric=True)
            if len(slopes) != 1:
                raise StataError("slope() requires one numeric variable")
            slope_name = slopes[0]
        level = float(o.get("level", self.level))
        if not np.isfinite(level) or not 0 < level < 100:
            raise StataError("Invalid level()")

        frame = self.df.loc[self.mask(q)].copy()
        y = self.model_response(terms[0], frame)
        x = self.regressors(terms[1:], frame)
        if x.shape[1] == 0:
            raise StataError("mixed requires a fixed-effect predictor")
        if "_cons" in x:
            raise StataError("The fixed-effect predictor _cons is reserved")
        x.insert(0, "_cons", 1.0)
        valid = y.notna() & x.notna().all(axis=1) & frame[group_name].notna()
        if slope_name:
            valid &= frame[slope_name].notna()
        y, x = y.loc[valid], x.loc[valid]
        group = frame.loc[valid, group_name]
        if y.size < 30 or group.nunique() < 5 or group.value_counts().min() < 2:
            raise StataError("mixed needs >=30 observations, >=5 groups and >=2 observations in each group")
        if x.shape[1] > 30 or y.size <= 3 * x.shape[1]:
            raise StataError("Too many mixed predictors for this bounded implementation")
        if not np.isfinite(y.to_numpy(dtype=float)).all() or not np.isfinite(x.to_numpy(dtype=float)).all():
            raise StataError("mixed requires finite numerical data")
        if np.linalg.matrix_rank(x.to_numpy()) < x.shape[1]:
            raise StataError("Collinear fixed effects in mixed")
        z = pd.DataFrame({"_cons": np.ones(len(y))}, index=y.index)
        if slope_name:
            variation = frame.loc[valid].groupby(group_name)[slope_name].nunique()
            if (variation < 2).any() or group.nunique() < 10:
                raise StataError("Random slopes require within-group variation and >=10 groups")
            z[slope_name] = frame.loc[valid, slope_name].astype(float)
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = sm.MixedLM(y, x, groups=group, exog_re=z).fit(
                    reml="mle" not in o, method="lbfgs", maxiter=350, disp=False
                )
        except (ValueError, np.linalg.LinAlgError, ZeroDivisionError) as exc:
            raise StataError(f"Mixed-effects model failed: {exc}") from exc
        if not result.converged:
            raise StataError("Mixed-effects optimisation did not converge")
        params = result.fe_params.copy()
        covariance = result.cov_params().loc[params.index, params.index].copy()
        if (not np.isfinite(params).all() or not np.isfinite(covariance).all().all()
                or np.linalg.eigvalsh(covariance.to_numpy()).min() <= 0
                or not np.isfinite(result.scale) or result.scale <= 0):
            raise StataError("Mixed-effects variance/covariance invalid")
        extra = {
            "N_groups": int(group.nunique()),
            "var_residual": float(result.scale),
            "var_intercept": float(result.cov_re.iloc[0, 0]),
        }
        if slope_name:
            extra["var_slope"] = float(result.cov_re.iloc[1, 1])
            extra["cov_intercept_slope"] = float(result.cov_re.iloc[0, 1])
        fixed_prediction = x @ params
        model = Model(
            "mixed", result, params, covariance, y.index, y, x,
            fixed_prediction, y - fixed_prediction,
            None, "model-based", level,
            revision=self.revision,
            fit_extra=extra,
            metadata={"group": group_name, "random_slope": slope_name,
                      "reml": "mle" not in o, "predictions": "fixed-only"},
        )
        self.model = model
        self.report_model()
        for warning in caught:
            self.notice("MIXED_" + warning.category.__name__, str(warning.message))
        self.notice(
            "MIXED_SCOPE",
            "Gaussian independent-group mixed model with random intercept and optional "
            "correlated random slope, statsmodels ML/REML estimates, model-based fixed-effect "
            "normal intervals. Fitted values are fixed-component predictions, excluding BLUPs; "
            "no residual-df correction, weights, crossed/nested effects, non-Gaussian links, "
            "or Stata likelihood/numerical-parity guarantee.",
        )

    def cmd_anovarm(self, args, opt):
        """Complete, balanced one/two-way within-subject repeated-measures ANOVA."""
        o = options(opt, ("subject", "within"))
        if "subject" not in o or "within" not in o:
            raise StataError("Syntax: anovarm response, subject(id) within(time [condition])")
        head, q = qualifiers(args)
        resp = self.varlist(head, numeric=True)
        subject = self.varlist(str(o["subject"]))
        within = self.varlist(str(o["within"]))
        if len(resp) != 1 or len(subject) != 1 or not 1 <= len(within) <= 2:
            raise StataError("anovarm needs one outcome, one subject, and one or two within factors")
        y, sid = resp[0], subject[0]
        if len(set([y, sid] + within)) != len([y, sid] + within):
            raise StataError("Outcome, subject and within factors must be different variables")
        cols = [y, sid] + within
        frame = self.df.loc[self.mask(q), cols].copy()
        if frame.isna().any().any() or not np.isfinite(frame[y].to_numpy(dtype=float)).all():
            raise StataError("anovarm requires completely observed, finite outcomes and identifiers")
        if frame[sid].nunique() < 3 or frame.shape[0] > 50000:
            raise StataError("anovarm needs >=3 subjects and no more than 50,000 observations")
        levels = [frame[name].nunique() for name in within]
        cells = int(np.prod(levels))
        if any(n < 2 for n in levels) or cells > 40:
            raise StataError("anovarm requires 2+ levels per within factor, <=40 combinations")
        if frame.duplicated([sid] + within).any():
            raise StataError("Repeated subject/factor cells; aggregate explicitly before anovarm")
        if len(frame) != frame[sid].nunique() * cells:
            raise StataError("anovarm requires every subject observed in every within-factor cell")
        for name in [sid] + within:
            frame[name] = frame[name].astype("str")
        try:
            result = AnovaRM(frame, depvar=y, subject=sid, within=within).fit()
        except (ValueError, np.linalg.LinAlgError, ZeroDivisionError) as exc:
            raise StataError(f"Repeated-measures ANOVA failed: {exc}") from exc
        table = result.anova_table.copy()
        if not np.isfinite(table.to_numpy(dtype=float)).all():
            raise StataError("Undefined repeated-measures ANOVA F test")
        self.r = {"N": len(frame), "subjects": frame[sid].nunique(),
                  "within_factors": len(within)}
        self.results_table = table
        self.results_table_title = "Balanced repeated-measures ANOVA"
        self.out("Balanced repeated-measures ANOVA\n" + table.to_string(float_format=lambda v: f"{v:.6g}"))
        self.notice(
            "ANOVARM_SCOPE",
            "Classical balanced within-subject fixed-effects ANOVA. F tests assume "
            "sphericity for within effects with >2 levels; no Greenhouse-Geisser or "
            "Huynh-Feldt correction, between-subject factors, multivariate tests, "
            "weights, imputation or missing cells. Not a Stata repeated-anova clone.",
        )

    def cmd_var(self, args, opt):
        """Bounded Gaussian vector autoregression of a gapless tsset series."""
        o = options(opt, ("lags", "noconstant"))
        if not self.tsvar or self.panel is not None:
            raise StataError("var requires a single time series declared with tsset")
        names, q = qualifiers(args)
        if q:
            raise StataError("VAR if/in subsampling is refused; prepare a gapless series first")
        columns = self.varlist(names, numeric=True)
        if not 2 <= len(columns) <= 6 or len(set(columns)) != len(columns):
            raise StataError("var requires 2-6 distinct numeric variables")
        p = _positive_integer(o.get("lags", 1), "lags", 1, 12)
        ordered = self.df.sort_values(self.tsvar).copy()
        times = ordered[self.tsvar].to_numpy(dtype=float)
        if not np.isfinite(times).all() or not np.allclose(
            np.diff(times), self.time_delta, rtol=0, atol=1e-8
        ):
            raise StataError("VAR needs unique, consecutive tsset time values with no gaps")
        data = ordered[columns]
        if data.isna().any().any() or not np.isfinite(data.to_numpy(dtype=float)).all():
            raise StataError("VAR requires complete finite series; do not bridge gaps silently")
        n, k = data.shape
        if n - p <= k * p + 2 or n * k > 500000:
            raise StataError("VAR needs residual degrees of freedom and <=500,000 data cells")
        try:
            fit = VAR(data).fit(p, trend="n" if "noconstant" in o else "c")
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StataError(f"VAR fit failed: {exc}") from exc
        if fit.df_resid <= 0 or not np.isfinite(fit.params.to_numpy()).all():
            raise StataError("VAR coefficients undefined")
        self._specialist_var = {
            "fit": fit, "revision": self.revision,
            "names": columns, "last_time": float(times[-1]),
            "data": data.to_numpy(copy=True), "tsvar": self.tsvar,
            "delta": self.time_delta,
        }
        self.model = None
        self.e = {"N": int(fit.nobs), "lags": p, "equations": k,
                  "df_r": float(fit.df_resid), "aic": float(fit.aic),
                  "bic": float(fit.bic)}
        self.results_table = fit.params.copy()
        self.results_table_title = f"VAR({p}) coefficients"
        self.out(f"VAR({p}), N per equation={fit.nobs}, AIC={fit.aic:.6g}, BIC={fit.bic:.6g}\n"
                 + fit.params.to_string(float_format=lambda v: f"{v:.6g}"))
        self.notice(
            "VAR_SCOPE",
            "OLS vector autoregression with constant or no constant, complete equally spaced "
            "single series only. No VECM/cointegration, deterministic trends, exogenous "
            "regressors, heteroskedasticity corrections or Stata lag-selection parity. "
            "Inspect stationarity before interpreting forecasts.",
        )

    def _require_var(self):
        state = getattr(self, "_specialist_var", None)
        if not state:
            raise StataError("Fit a VAR model first")
        if (state["revision"] != self.revision or state["tsvar"] != self.tsvar
                or state["delta"] != self.time_delta):
            raise StataError("VAR model stale after changing data or time declaration; refit")
        return state

    def cmd_varstable(self, args, opt):
        options(opt, ())
        if args.strip():
            raise StataError("Syntax: varstable")
        state = self._require_var()
        fit = state["fit"]
        roots = np.asarray(fit.roots)
        table = pd.DataFrame({"Inverse root modulus": np.abs(roots)})
        stable = bool(fit.is_stable())
        self.r = {"stable": int(stable), "min_inverse_root": float(np.abs(roots).min())}
        self.results_table = table
        self.results_table_title = "VAR characteristic roots"
        self.out(("Stable" if stable else "Unstable") + " VAR (all inverse roots must lie outside the unit circle)\n"
                 + table.to_string(index=False))
        self.notice("VAR_STABILITY", "Stability of the estimated VAR is not proof of structural identification, stationarity of observed data or forecast validity.")

    def cmd_varforecast(self, args, opt):
        o = options(opt, ("steps",))
        if args.strip():
            raise StataError("Syntax: varforecast, steps(5)")
        state = self._require_var()
        steps = _positive_integer(o.get("steps", 5), "steps", 1, 60)
        fit = state["fit"]
        if not fit.is_stable():
            raise StataError("VAR forecasts require a stable fitted VAR; inspect varstable")
        values = fit.forecast(state["data"][-fit.k_ar:], steps=steps)
        if not np.isfinite(values).all():
            raise StataError("Nonfinite VAR forecast")
        time = state["last_time"] + state["delta"] * np.arange(1, steps + 1)
        table = pd.DataFrame(values, columns=state["names"])
        table.insert(0, state["tsvar"], time)
        self.r = {"steps": steps, "stable": 1}
        self.results_table = table
        self.results_table_title = "Point forecasts from fitted VAR"
        self.out(self.results_table_title + "\n" + table.to_string(index=False, float_format=lambda v: f"{v:.6g}"))
        self.notice(
            "VAR_FORECAST",
            "Conditional plug-in mean forecasts only. No forecast intervals, structural shocks, "
            "prediction uncertainty, exogenous paths or observed future values are included.",
        )
