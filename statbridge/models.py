# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
from __future__ import annotations
import itertools
import re
import warnings
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from linearmodels.panel import PanelOLS, RandomEffects
from linearmodels.iv import IV2SLS
from .syntax import StataError, options, qualifiers, split_top


@dataclass
class Model:
    command: str
    result: object
    params: pd.Series
    cov: pd.DataFrame
    sample: pd.Index
    y: pd.Series
    x: pd.DataFrame
    predicted: pd.Series
    residual: pd.Series
    df: float | None
    covariance: str
    level: float
    revision: int = -1
    linear_prediction: pd.Series | None = None
    weight_type: str | None = None
    nobs: float | None = None
    fit_extra: dict | None = None
    prediction_terms: list[str] | None = None
    metadata: dict | None = None


class ModelCommands:
    def regressors(self, tokens, frame):
        """Explicit numeric design: i./c./ib#., #/##, and gap-aware L./F./D. operators."""
        columns = {}

        def atomic(term):
            from .timeseries import TIME_TERM, time_values

            if TIME_TERM.fullmatch(term):
                return {term: time_values(self, term, frame)}
            m = re.fullmatch(r"(i|c|ib-?\d+)\.(\w+)", term)
            if m:
                kind, name = m.groups()
                if name not in frame:
                    raise StataError(f"Variable {name} not found", 111)
                s = frame[name]
                if kind == "c":
                    return {name: s.astype(float)}
                if (
                    not pd.api.types.is_numeric_dtype(s)
                    or (s.dropna() % 1 != 0).any()
                    or (s.dropna() < 0).any()
                ):
                    raise StataError(
                        "Factor variables must contain nonnegative integers"
                    )
                levels = sorted(s.dropna().unique())
                base = (
                    float(kind[2:])
                    if kind.startswith("ib")
                    else (levels[0] if levels else 0)
                )
                if levels and base not in levels:
                    raise StataError(f"Base level {base:g} absent from {name}")
                return {
                    f"{v:g}.{name}": pd.Series(
                        np.where(s.isna(), np.nan, (s == v).astype(float)),
                        index=s.index,
                    )
                    for v in levels
                    if v != base
                }
            names = self.varlist(term, numeric=True)
            return {name: frame[name].astype(float) for name in names}

        for token in tokens:
            if "#" in token:
                self.notice(
                    "FACTOR_INTERACTION",
                    "Interactions are explicit products of treatment-coded columns. Omitted/base-cell conventions may differ from Stata, especially # without main effects.",
                )
            if "##" in token:
                atoms = token.split("##")
                groups = [
                    g
                    for n in range(1, len(atoms) + 1)
                    for g in itertools.combinations(atoms, n)
                ]
            else:
                groups = [tuple(token.split("#"))]
            for group in groups:
                pieces = [atomic(t) for t in group]
                for combination in itertools.product(
                    *[list(p.items()) for p in pieces]
                ):
                    name = "#".join(c[0] for c in combination)
                    val = combination[0][1]
                    for _, v in combination[1:]:
                        val = val * v
                    columns[name] = val
        return pd.DataFrame(columns, index=frame.index)

    def model_response(self, term, frame):
        from .timeseries import TIME_TERM, time_values

        if TIME_TERM.fullmatch(term):
            value = time_values(self, term, frame)
            value.name = term
            return value
        names = self.varlist(term, numeric=True)
        if len(names) != 1:
            raise StataError("One dependent variable is required")
        return frame[names[0]].astype(float)

    def estimation_sample(self, frame=None):
        m = self.require_model()
        if m.revision != self.revision:
            raise StataError(
                "Data changed since estimation; e(sample) is no longer valid"
            )
        frame = self.df if frame is None else frame
        return pd.Series(frame.index.isin(m.sample).astype(float), index=frame.index)

    def fit_model(self, cmd, args, opt):
        from .weights import extract_weight, fit_weighted

        _, weight = extract_weight(args)
        if weight is not None:
            if cmd != "regress":
                raise StataError("Weights supported for regress only")
            return fit_weighted(self, args, opt)
        allowed = ["vce", "robust", "noconstant", "level"]
        if cmd == "xtreg":
            allowed += ["fe", "re"]
        if cmd == "qreg":
            allowed += ["quantile"]
        if cmd in ("poisson", "nbreg"):
            allowed += ["exposure", "offset", "irr"]
        if cmd == "glm":
            allowed += ["family", "link", "exposure", "offset"]
        o = options(opt, allowed)
        head, q = qualifiers(args)
        vs = head.split()
        if not vs:
            raise StataError("Specify dependent and independent variables")
        frame = self.df.loc[self.mask(q)].copy()
        y = self.model_response(vs[0], frame)
        x = self.regressors(vs[1:], frame)
        if "noconstant" not in o:
            x.insert(0, "_cons", 1.0)
        level = float(o.get("level", self.level))
        if not 0 < level < 100:
            raise StataError("level() must be between 0 and 100")
        covariance = str(o.get("vce", "robust" if "robust" in o else "ols"))
        if "robust" in o and "vce" in o:
            raise StataError("Specify robust OR vce()")
        cluster = None
        if covariance.startswith("cluster "):
            keys = self.varlist(covariance[8:].strip())
            if len(keys) != 1:
                raise StataError("One cluster variable is supported")
            cluster = frame[keys[0]]
        elif covariance not in (
            ("ols", "robust", "hc2", "hc3") if cmd == "regress" else ("ols", "robust")
        ):
            raise StataError("vce() supports robust or cluster variable")
        valid = y.notna() & x.notna().all(axis=1)
        for factor in re.findall(r"(?:^|[# ])(?:i|c|ib-?\d+)\.(\w+)", head):
            valid &= frame[factor].notna()
        if cluster is not None:
            valid &= cluster.notna()
        extra = {}
        if "exposure" in o and "offset" in o:
            raise StataError("Specify exposure OR offset")
        for key in ("exposure", "offset"):
            if key in o:
                names = self.varlist(str(o[key]), numeric=True)
                if len(names) != 1:
                    raise StataError(f"{key}() requires one numeric variable")
                z = frame[names[0]].astype(float)
                valid &= z.notna()
                if key == "exposure" and (z.dropna() <= 0).any():
                    raise StataError("Exposure must be strictly positive")
                extra[key] = z
        if cmd == "xtreg":
            if not self.panel:
                raise StataError("Declare panel with xtset first")
            valid &= frame[self.panel[0]].notna()
        y, x = y.loc[valid], x.loc[valid]
        if len(y) <= x.shape[1] or x.shape[1] == 0:
            raise StataError(
                "Insufficient complete observations or no regressors", 2001
            )
        if not np.isfinite(x.to_numpy()).all() or not np.isfinite(y).all():
            raise StataError("Nonfinite model data")
        if np.linalg.matrix_rank(x.to_numpy()) < x.shape[1]:
            raise StataError(
                "Collinear design: remove redundant regressors. Automatic Stata omission rules are not emulated."
            )
        for key in extra:
            extra[key] = extra[key].loc[valid]
        if cluster is not None:
            cluster = cluster.loc[valid]
            if cluster.nunique() < 2:
                raise StataError("At least two clusters required")
        df = None
        fitkw = {}
        if covariance in ("robust", "hc2", "hc3"):
            fitkw = {
                "cov_type": "HC1" if covariance == "robust" else covariance.upper()
            }
        elif cluster is not None:
            fitkw = {
                "cov_type": "cluster",
                "cov_kwds": {
                    "groups": cluster.to_numpy(),
                    "use_correction": True,
                    "df_correction": True,
                },
            }
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            if cmd == "regress":
                result = sm.OLS(y, x).fit(use_t=True, **fitkw)
                df = cluster.nunique() - 1 if cluster is not None else result.df_resid
            elif cmd in ("logit", "logistic", "probit", "poisson", "nbreg"):
                if cmd in ("logit", "logistic", "probit") and not y.isin([0, 1]).all():
                    raise StataError("Binary outcomes must be coded 0 and 1")
                if cmd in ("poisson", "nbreg") and (
                    (y < 0).any() or (y % 1 != 0).any()
                ):
                    raise StataError("Count outcomes must be nonnegative integers")
                klass = {
                    "logit": sm.Logit,
                    "logistic": sm.Logit,
                    "probit": sm.Probit,
                    "poisson": sm.Poisson,
                    "nbreg": sm.NegativeBinomial,
                }[cmd]
                if covariance == "robust":
                    fitkw = {"cov_type": "HC0"}
                    self.notice(
                        "ML_ROBUST",
                        "Likelihood models use statsmodels HC0 sandwich covariance; finite-sample scaling can differ from Stata.",
                    )
                result = klass(y, x, **extra).fit(disp=False, maxiter=200, **fitkw)
                if not result.mle_retvals.get("converged", True):
                    raise StataError(
                        "Likelihood optimisation did not converge; model not accepted"
                    )
                if cmd == "nbreg":
                    self.notice(
                        "NBREG",
                        "NB2 alpha is reported directly rather than Stata /lnalpha. Initialisation, convergence and likelihood constants may differ.",
                    )
            elif cmd == "qreg":
                if covariance != "ols":
                    raise StataError("qreg vce options are not implemented")
                quantile = float(o.get("quantile", 0.5))
                if not 0 < quantile < 1:
                    raise StataError("quantile() must lie between 0 and 1")
                result = sm.QuantReg(y, x).fit(q=quantile, vcov="robust", max_iter=2000)
                df = result.df_resid
                self.notice(
                    "QREG",
                    "QuantReg uses a kernel density estimate, Epanechnikov kernel and Hall-Sheather bandwidth. Stata quantile-regression SEs and convergence can differ.",
                )
            elif cmd == "glm":
                families = {
                    "gaussian": sm.families.Gaussian,
                    "binomial": sm.families.Binomial,
                    "poisson": sm.families.Poisson,
                    "gamma": sm.families.Gamma,
                }
                links = {
                    "identity": sm.families.links.Identity,
                    "log": sm.families.links.Log,
                    "logit": sm.families.links.Logit,
                    "probit": sm.families.links.Probit,
                    "inverse": sm.families.links.InversePower,
                }
                fam = str(o.get("family", "gaussian")).lower()
                link = str(
                    o.get(
                        "link",
                        {
                            "gaussian": "identity",
                            "binomial": "logit",
                            "poisson": "log",
                            "gamma": "inverse",
                        }.get(fam, ""),
                    )
                )
                if fam not in families or link not in links:
                    raise StataError("Unsupported GLM family or link")
                if fam == "binomial" and not y.between(0, 1).all():
                    raise StataError("Binomial response must be in [0,1]")
                if covariance == "robust":
                    fitkw = {"cov_type": "HC0"}
                result = sm.GLM(
                    y, x, family=families[fam](link=links[link]()), **extra
                ).fit(**fitkw)
                if not result.converged:
                    raise StataError("GLM did not converge")
                self.notice(
                    "GLM",
                    "GLM uses statsmodels IRLS, scale and deviance conventions; finite-sample covariance and likelihood reporting may differ from Stata.",
                )
            elif cmd == "xtreg":
                if ("fe" in o) == ("re" in o):
                    raise StataError("Choose exactly one of fe or re")
                entity, time = self.panel
                ef = frame.loc[valid, entity]
                tf = (
                    frame.loc[valid, time]
                    if time
                    else frame.loc[valid].groupby(entity).cumcount()
                )
                index = pd.MultiIndex.from_arrays(
                    [ef, tf], names=[entity, time or "_time"]
                )
                px = x.copy()
                py = y.copy()
                px.index = index
                py.index = index
                covkw = {"cov_type": "unadjusted"}
                if covariance == "robust":
                    covkw = {"cov_type": "clustered", "cluster_entity": True}
                elif cluster is not None:
                    covkw = {
                        "cov_type": "clustered",
                        "clusters": pd.DataFrame(
                            {"cluster": pd.factorize(cluster)[0]}, index=index
                        ),
                    }
                klass = (
                    PanelOLS(py, px, entity_effects=True, drop_absorbed=True)
                    if "fe" in o
                    else RandomEffects(py, px)
                )
                result = klass.fit(debiased=True, **covkw)
                self.notice(
                    "PANEL",
                    "Panel estimates use linearmodels. Absorbed-regressor handling, singleton treatment, variance components, R² and degrees-of-freedom adjustments may differ from xtreg. Panel robust uses clustering by entity; inference uses backend residual degrees of freedom.",
                )
                params = result.params
                cov = result.cov
                df = result.df_resid
                predicted = pd.Series(
                    result.fitted_values.iloc[:, 0].to_numpy(), index=y.index
                )
                residual = pd.Series(result.resids.to_numpy(), index=y.index)
                self.model = Model(
                    cmd,
                    result,
                    params,
                    cov,
                    y.index,
                    y,
                    x,
                    predicted,
                    residual,
                    df,
                    covariance,
                    level,
                )
                self.report_model()
                self.emit_warnings(caught)
                return
            else:
                raise StataError("Unsupported model")
            self.emit_warnings(caught)
        params = pd.Series(
            result.params, index=getattr(result.params, "index", list(x.columns))
        )
        cov = pd.DataFrame(
            result.cov_params(), index=params.index, columns=params.index
        )
        predicted = pd.Series(np.asarray(result.predict()), index=y.index)
        self.model = Model(
            cmd,
            result,
            params,
            cov,
            y.index,
            y,
            x,
            predicted,
            y - predicted,
            df,
            covariance,
            level,
        )
        self.model.prediction_terms = [
            re.sub(
                r"(?<![\w.])i\.(\w+)",
                lambda match: f"ib{frame[match[1]].dropna().min():g}.{match[1]}",
                term,
            )
            for term in vs[1:]
        ]
        self.model.linear_prediction = x @ params[x.columns]
        if "offset" in extra:
            self.model.linear_prediction += extra["offset"]
        if "exposure" in extra:
            self.model.linear_prediction += np.log(extra["exposure"])
        self.notice(
            "ESTIMATION",
            "Python backend optimisation and tolerances are used. Exact Stata numerical parity has not been certified. Complete-case selection includes all model and cluster/offset variables.",
        )
        if cluster is not None:
            self.notice(
                "CLUSTER",
                "One-way cluster sandwich with backend small-sample correction. OLS uses t(G-1); nonlinear models use normal inference. Check against the required Stata estimator/version.",
            )
        self.report_model(cmd == "logistic" or "irr" in o)

    def emit_warnings(self, caught):
        for w in caught:
            self.notice("BACKEND_" + w.category.__name__, str(w.message))

    def report_model(self, exponentiate=False):
        m = self.require_model()
        if m.revision < 0:
            m.revision = self.revision
        se = np.sqrt(np.diag(m.cov))
        b = m.params.to_numpy()
        statistic = b / se
        dist = stats.t(m.df) if m.df is not None else stats.norm
        p = 2 * dist.sf(np.abs(statistic))
        crit = dist.ppf(1 - (1 - m.level / 100) / 2)
        low = b - crit * se
        high = b + crit * se
        transform = np.full(len(b), exponentiate, dtype=bool)
        if m.command == "nbreg":
            transform &= m.params.index != "alpha"
        # np.where evaluates both branches before selecting. In particular,
        # np.where(False, np.exp(large_OLS_coefficient), coefficient) still
        # overflows for an ordinary (non-exponentiated) OLS fit. Only evaluate
        # the ratio scale for coefficients that actually require it.
        shown = b.copy()
        shown_se = se.copy()
        shown_low = low.copy()
        shown_high = high.copy()
        if transform.any():
            # Floating-point overflow in a genuinely exponentiated parameter
            # is meaningful; keep the inf/zero result and issue a notice
            # instead of emitting a raw NumPy warning or clipping a ratio.
            with np.errstate(over="ignore", under="ignore", invalid="ignore"):
                ratios = np.exp(b[transform])
                ratio_se = ratios * se[transform]
                ratio_low = np.exp(low[transform])
                ratio_high = np.exp(high[transform])
            shown[transform] = ratios
            shown_se[transform] = ratio_se
            shown_low[transform] = ratio_low
            shown_high[transform] = ratio_high
            if (
                not all(np.isfinite(v).all() for v in (ratios, ratio_se, ratio_low, ratio_high))
                or any(
                    np.any((v == 0) & np.isfinite(raw))
                    for v, raw in (
                        (ratios, b[transform]),
                        (ratio_low, low[transform]),
                        (ratio_high, high[transform]),
                    )
                )
            ):
                self.notice(
                    "EXP_COEFFICIENT_RANGE",
                    "An exponentiated estimate or interval is beyond finite "
                    "floating-point range; zero or infinity is shown as applicable. "
                    "Underlying coefficients and inference are unchanged.",
                )
        table = pd.DataFrame(
            {
                "Ratio / alpha"
                if exponentiate and m.command == "nbreg"
                else "Ratio"
                if exponentiate
                else "Coef.": shown,
                "Std. err.": shown_se,
                "t" if m.df is not None else "z": statistic,
                "P>|stat|": p,
                "CI lower": shown_low,
                "CI upper": shown_high,
            },
            index=m.params.index,
        )
        self.e = {
            "N": m.nobs if m.nobs is not None else len(m.sample),
            "df_m": len(m.params) - int("_cons" in m.params),
            "df_r": m.df if m.df is not None else np.nan,
        }
        if m.fit_extra:
            self.e.update(m.fit_extra)
        for target, source in [
            ("r2", "rsquared"),
            ("r2_a", "rsquared_adj"),
            ("ll", "llf"),
            ("aic", "aic"),
            ("bic", "bic"),
        ]:
            try:
                self.e[target] = float(getattr(m.result, source))
            except (AttributeError, TypeError, ValueError):
                pass
        from .reporting import model_report

        plain, html = model_report(m, table, self.e)
        if not self.quiet:
            self.emit("output", plain, {"html": html})
        self.results_table = table.copy()
        self.results_table_title = m.command + " coefficient table"
        self.emit("model", "", {"table": table, "command": m.command})

    def require_model(self):
        if self.model is None:
            raise StataError("No active estimation results", 301)
        return self.model

    def cmd_regress(self, a, o):
        self.fit_model("regress", a, o)

    def cmd_logit(self, a, o):
        self.fit_model("logit", a, o)

    def cmd_logistic(self, a, o):
        self.fit_model("logistic", a, o)

    def cmd_probit(self, a, o):
        self.fit_model("probit", a, o)

    def cmd_poisson(self, a, o):
        self.fit_model("poisson", a, o)

    def cmd_nbreg(self, a, o):
        self.fit_model("nbreg", a, o)

    def cmd_qreg(self, a, o):
        self.fit_model("qreg", a, o)

    def cmd_glm(self, a, o):
        self.fit_model("glm", a, o)

    def cmd_xtreg(self, a, o):
        self.fit_model("xtreg", a, o)

    def cmd_tsset(self, args, opt):
        o = options(opt, ("delta",))
        cols = self.varlist(args, numeric=True)
        if len(cols) != 1:
            raise StataError("Syntax: tsset timevar")
        s = self.df[cols[0]]
        if s.isna().any() or s.duplicated().any():
            raise StataError("Time values must be unique and nonmissing")
        delta = float(o.get("delta", 1))
        if not np.isfinite(delta) or delta <= 0:
            raise StataError("delta() must be finite and positive")
        self.time_delta = delta
        self.tsvar = cols[0]
        self.panel = None
        self.out(f"Time variable: {self.tsvar}; lag delta: {self.time_delta:g}")

    def cmd_xtset(self, args, opt):
        o = options(opt, ("delta",))
        cols = self.varlist(args)
        if len(cols) not in (1, 2):
            raise StataError("Syntax: xtset panel [time]")
        if self.df[cols].isna().any().any():
            raise StataError("Panel/time identifiers contain missing values")
        if len(cols) == 2:
            if self.df.duplicated(cols).any():
                raise StataError("Repeated time values within panel", 451)
            if not pd.api.types.is_numeric_dtype(self.df[cols[1]]):
                raise StataError("Numeric time variable required")
        delta = float(o.get("delta", 1))
        if not np.isfinite(delta) or delta <= 0:
            raise StataError("delta() must be finite and positive")
        self.time_delta = delta
        self.tsvar = None
        self.panel = (cols[0], cols[1] if len(cols) == 2 else None)
        self.out(f"Panel variable: {cols[0]}; time: {self.panel[1] or 'not specified'}")

    def cmd_ivregress(self, args, opt):
        o = options(opt, ("vce", "robust", "noconstant", "level"))
        head, q = qualifiers(args)
        m = re.fullmatch(r"2sls\s+(\w+)\s*(.*?)\s*\(([^=]+)=([^)]*)\)", head)
        if not m:
            raise StataError(
                "Syntax: ivregress 2sls y exogenous (endogenous = instruments)"
            )
        dep, exog, endog, instruments = m.groups()
        frame = self.df.loc[self.mask(q)].copy()
        self.varlist(dep, numeric=True)
        x = self.regressors(exog.split(), frame)
        if "noconstant" not in o:
            x.insert(0, "_cons", 1.0)
        en = self.varlist(endog, numeric=True)
        ins = self.varlist(instruments, numeric=True)
        y = frame[dep]
        end = frame[en]
        inst = frame[ins]
        vce = str(o.get("vce", "robust" if "robust" in o else "unadjusted"))
        if "vce" in o and "robust" in o:
            raise StataError("Specify robust or vce()")
        valid = (
            y.notna()
            & x.notna().all(axis=1)
            & end.notna().all(axis=1)
            & inst.notna().all(axis=1)
        )
        for factor in re.findall(r"(?:^|[# ])(?:i|c|ib-?\d+)\.(\w+)", head):
            valid &= frame[factor].notna()
        kwargs = {}
        if vce.startswith("cluster "):
            clusters = self.varlist(vce[8:])
            if len(clusters) != 1:
                raise StataError("One cluster variable is supported")
            c = clusters[0]
            valid &= frame[c].notna()
            kwargs = {"clusters": pd.factorize(frame.loc[valid, c])[0]}
            cov = "clustered"
        elif vce in ("robust", "unadjusted", "ols"):
            cov = "unadjusted" if vce == "ols" else vce
        else:
            raise StataError("Unsupported IV covariance")
        if not 0 < float(o.get("level", self.level)) < 100:
            raise StataError("level() must be between 0 and 100")
        if "clusters" in kwargs and len(np.unique(kwargs["clusters"])) < 2:
            raise StataError("At least two clusters required")
        y, x, end, inst = y[valid], x[valid], end[valid], inst[valid]
        result = IV2SLS(y, x, end, inst).fit(cov_type=cov, debiased=False, **kwargs)
        pred = result.fitted_values.iloc[:, 0]
        residual = result.resids
        self.model = Model(
            "ivregress",
            result,
            result.params,
            result.cov,
            y.index,
            y,
            pd.concat([x, end], axis=1),
            pred,
            residual,
            None,
            vce,
            float(o.get("level", self.level)),
        )
        self.notice(
            "IV",
            "IV2SLS uses non-debiased linearmodels covariance and normal inference. Small-sample corrections, diagnostics and rank tolerances may differ from Stata.",
        )
        self.report_model()

    def cmd_estimates(self, args, opt):
        options(opt, ())
        p = args.split()
        sub = p[0] if p else ""
        if sub == "store" and len(p) == 2:
            self.stored[p[1]] = self.require_model()
        elif sub == "restore" and len(p) == 2:
            if p[1] not in self.stored:
                raise StataError("Stored model not found")
            self.model = self.stored[p[1]]
            self.report_model()
        elif sub == "dir" and len(p) == 1:
            self.out(
                "\n".join(
                    f"{k}: {v.command}, N={len(v.sample)}"
                    for k, v in self.stored.items()
                )
            )
        elif sub == "table":
            names = p[1:] or list(self.stored)
            if any(k not in self.stored for k in names):
                raise StataError("Stored model not found")
            self.out(
                pd.DataFrame({k: self.stored[k].params for k in names}).to_string()
            )
        else:
            raise StataError(
                "Syntax: estimates store|restore name, dir, or table [names]"
            )

    def cmd_hausman(self, args, opt):
        options(opt, ())
        p = args.split()
        if len(p) != 2 or any(k not in self.stored for k in p):
            raise StataError("Specify two stored models: consistent efficient")
        a, b = (self.stored[k] for k in p)
        if a.weight_type or b.weight_type:
            raise StataError("Hausman for weighted fits is not implemented")
        if any(m.covariance not in ("ols", "unadjusted") for m in (a, b)):
            raise StataError(
                "Classical Hausman is invalid with robust/clustered covariance; test refused"
            )
        if (
            not a.sample.equals(b.sample)
            or not a.y.equals(b.y)
            or a.revision != b.revision
        ):
            raise StataError(
                "Hausman models must use the same outcome, data revision and estimation sample"
            )
        names = [k for k in a.params.index.intersection(b.params.index) if k != "_cons"]
        if not names:
            raise StataError("No common slopes")
        d = (a.params[names] - b.params[names]).to_numpy()
        v = (a.cov.loc[names, names] - b.cov.loc[names, names]).to_numpy()
        eig = np.linalg.eigvalsh(v)
        tol = max(abs(eig).max(), 1) * 1e-10
        if eig.min() <= tol:
            raise StataError(
                "Covariance difference is not positive definite; refusing a misleading Hausman statistic"
            )
        chi = float(d @ np.linalg.solve(v, d))
        pval = float(stats.chi2.sf(chi, len(d)))
        self.r = {"chi2": chi, "df": len(d), "p": pval}
        self.notice(
            "HAUSMAN",
            "Classical covariance-difference test on common slopes only; no sigmamore/sigmaless adjustment or robust Hausman variant.",
        )
        self.out(f"Hausman chi2({len(d)}) = {chi:.7g}; p = {pval:.7g}")

    def cmd_predict(self, args, opt):
        o = options(opt, ("xb", "residuals", "pr"))
        m = self.require_model()
        if len(o) > 1:
            raise StataError("Choose one prediction statistic")
        self.newvar(args)
        if not m.sample.isin(self.df.index).all():
            raise StataError("Estimation sample is no longer available")
        # Stored models cannot silently predict into a changed/reordered dataset.
        if m.revision != self.revision or not np.array_equal(
            self.model_response(m.y.name, self.df.loc[m.sample]).to_numpy(),
            m.y.to_numpy(),
            equal_nan=True,
        ):
            raise StataError("Data changed since estimation; refit before prediction")
        if "residuals" in o:
            value = m.residual
        elif "xb" in o and m.command == "arima":
            raise StataError("ARIMA xb prediction is not implemented")
        elif "xb" in o and m.linear_prediction is not None:
            value = m.linear_prediction
        elif "xb" in o:
            value = (
                m.x[m.params.index.intersection(m.x.columns)]
                @ m.params[m.params.index.intersection(m.x.columns)]
            )
        else:
            value = m.predicted
        if "pr" in o and m.command not in ("logit", "logistic", "probit"):
            raise StataError("pr is supported only for binary models")
        self.df[args] = value.reindex(self.df.index)
        self.dirty = True
        self.notice(
            "PREDICT",
            "Predictions are filled only for the estimation sample; other observations remain missing. Panel predictions exclude fixed/random effects unless residuals are requested.",
        )

    def cmd_test(self, args, opt):
        options(opt, ())
        m = self.require_model()
        names = args.split()
        if not names or any(n not in m.params for n in names):
            raise StataError(
                "test accepts explicit estimated coefficient names, each tested equal to zero"
            )
        b = m.params[names].to_numpy()
        v = m.cov.loc[names, names].to_numpy()
        rank = np.linalg.matrix_rank(v)
        if rank < len(names):
            raise StataError("Singular covariance for test")
        w = float(b @ np.linalg.solve(v, b))
        if m.df is not None:
            stat = w / rank
            p = stats.f.sf(stat, rank, m.df)
            label = f"F({rank},{m.df:g})"
            self.r = {"F": stat, "df": rank, "df_r": m.df, "p": p}
        else:
            stat = w
            p = stats.chi2.sf(w, rank)
            label = f"chi2({rank})"
            self.r = {"chi2": stat, "df": rank, "p": p}
        self.out(f"{label} = {stat:.7g}; p = {p:.7g}")

    def cmd_lincom(self, args, opt):
        options(opt, ())
        m = self.require_model()
        # A deliberately narrow grammar avoids treating arbitrary expressions as hypotheses.
        expression = args.replace(" ", "")
        tokens = re.findall(r"([+-]?)(?:(\d+(?:\.\d+)?)\*)?([\w.#]+)", expression)
        reconstructed = "".join(
            sign + (co + "*" if co else "") + name for sign, co, name in tokens
        )
        if reconstructed != expression or not tokens:
            raise StataError(
                "lincom supports signed coefficient names and numeric multipliers, e.g. 2*x - z"
            )
        weights = pd.Series(0.0, index=m.params.index)
        for sign, co, name in tokens:
            if name not in weights:
                raise StataError(f"Coefficient {name} not found")
            weights[name] += (-1 if sign == "-" else 1) * float(co or 1)
        estimate = float(weights @ m.params)
        se = float(np.sqrt(weights @ m.cov @ weights))
        if not np.isfinite(se) or se <= 0:
            raise StataError("Linear combination has zero or invalid variance")
        dist = stats.t(m.df) if m.df else stats.norm
        critical = dist.ppf(1 - (1 - m.level / 100) / 2)
        p = 2 * dist.sf(abs(estimate / se))
        self.r = {
            "estimate": estimate,
            "se": se,
            "p": p,
            "lb": estimate - critical * se,
            "ub": estimate + critical * se,
        }
        self.out(pd.Series(self.r).to_string())

    def cmd_estat(self, args, opt):
        options(opt, ())
        m = self.require_model()
        if m.weight_type:
            raise StataError(
                "estat diagnostics for weighted fits are not yet implemented"
            )
        if args == "vif" and m.command == "regress":
            from statsmodels.stats.outliers_influence import variance_inflation_factor

            self.out(
                pd.Series(
                    {
                        c: variance_inflation_factor(m.x.to_numpy(), i)
                        for i, c in enumerate(m.x.columns)
                        if c != "_cons"
                    },
                    name="VIF",
                ).to_string()
            )
        elif args == "hettest" and m.command == "regress":
            from statsmodels.stats.diagnostic import het_breuschpagan

            # Stata default uses fitted values and normal-error BP.
            lm, p, _, _ = het_breuschpagan(
                m.residual, sm.add_constant(m.predicted), robust=False
            )
            self.r = {"chi2": lm, "p": p}
            self.out(f"Breusch-Pagan chi2(1) = {lm:.7g}; p = {p:.7g}")
        elif args == "ic":
            values = {k: getattr(m.result, k, np.nan) for k in ("aic", "bic", "llf")}
            self.out(pd.Series(values).to_string())
            self.notice(
                "IC",
                "Information-criterion parameter counts and likelihood constants follow the Python backend.",
            )
        else:
            raise StataError(
                "estat supports vif/hettest after regress, and ic where backend provides it"
            )

    def cmd_margins(self, args, opt):
        o = options(opt, ("dydx",))
        m = self.require_model()
        if (
            args
            or o.get("dydx") != "*"
            or m.command not in ("logit", "logistic", "probit")
        ):
            raise StataError("Supported: margins, dydx(*) after logit/probit")
        if any("#" in c or "." in c for c in m.params.index):
            raise StataError(
                "margins is implemented only for numeric main effects; factor variables and interactions require unsupported joint counterfactual construction"
            )
        self.out(
            m.result.get_margeff(at="overall", method="dydx", dummy=True)
            .summary()
            .as_text()
        )
        self.notice(
            "MARGINS",
            "Backend average marginal effects treat binary design columns as discrete changes, which may differ from Stata continuous-variable defaults. Factor variables and interactions are rejected.",
        )

    def cmd_correlate(self, args, opt):
        options(opt, ())
        h, q = qualifiers(args)
        cols = self.varlist(h, numeric=True)
        df = self.df.loc[self.mask(q), cols].dropna()
        self.r = {"N": len(df)}
        self.out(f"N = {len(df)}\n" + df.corr().to_string())

    def cmd_pwcorr(self, args, opt):
        o = options(opt, ("sig", "obs"))
        h, q = qualifiers(args)
        cols = self.varlist(h, numeric=True)
        df = self.df.loc[self.mask(q), cols]
        self.out(df.corr().to_string())
        counts = pd.DataFrame(index=cols, columns=cols, dtype=float)
        pvalues = counts.copy()
        for a in cols:
            for b in cols:
                x = df[[a, b]].dropna()
                counts.loc[a, b] = len(x)
                pvalues.loc[a, b] = (
                    stats.pearsonr(x.iloc[:, 0], x.iloc[:, 1]).pvalue
                    if len(x) > 2
                    else np.nan
                )
        if "sig" in o:
            self.out("Two-sided p-values\n" + pvalues.to_string())
        if "obs" in o:
            self.out("Pairwise observations\n" + counts.to_string())

    def cmd_tabulate(self, args, opt):
        o = options(opt, ("missing", "chi2", "row", "col"))
        h, q = qualifiers(args)
        cols = self.varlist(h)
        df = self.df.loc[self.mask(q), cols]
        if len(cols) not in (1, 2):
            raise StataError("tabulate requires one or two variables")
        if "missing" in o:
            df = df.astype(object).where(df.notna(), "<missing>")
        else:
            df = df.dropna()
            df = df.loc[~df.eq("").any(axis=1)]
        if len(cols) == 1:
            if any(k in o for k in ("chi2", "row", "col")):
                raise StataError("chi2/row/col need two variables")
            counts = df[cols[0]].value_counts(dropna=False, sort=False).sort_index()
            self.out(
                pd.DataFrame(
                    {"Freq.": counts, "Percent": 100 * counts / counts.sum()}
                ).to_string()
            )
        else:
            table = pd.crosstab(df[cols[0]], df[cols[1]])
            self.out(table.to_string())
            if "row" in o:
                self.out(
                    "Row percentages\n"
                    + (100 * table.div(table.sum(axis=1), axis=0)).to_string()
                )
            if "col" in o:
                self.out(
                    "Column percentages\n"
                    + (100 * table.div(table.sum(axis=0), axis=1)).to_string()
                )
            if "chi2" in o:
                chi, p, dof, _ = stats.chi2_contingency(table, correction=False)
                self.r = {"chi2": chi, "p": p, "df": dof}
                self.out(f"Pearson chi2({dof}) = {chi:.7g}; p = {p:.7g}")

    def cmd_ttest(self, args, opt):
        o = options(opt, ("by", "unequal", "level"))
        h, q = qualifiers(args)
        frame = self.df.loc[self.mask(q)]
        if "by" in o:
            cols = self.varlist(h, numeric=True)
            if len(cols) != 1:
                raise StataError("One response variable required")
            group = self.varlist(str(o["by"]))[0]
            groups = sorted(frame[group].dropna().unique())
            if len(groups) != 2:
                raise StataError("by() must have exactly two nonmissing groups")
            a = frame.loc[frame[group] == groups[0], cols[0]].dropna()
            b = frame.loc[frame[group] == groups[1], cols[0]].dropna()
            res = stats.ttest_ind(a, b, equal_var="unequal" not in o)
        else:
            if "unequal" in o:
                raise StataError("unequal requires by()")
            m = re.fullmatch(r"(\w+)\s*==\s*(.+)", h)
            if not m:
                raise StataError(
                    "Syntax: ttest x == number|variable, or ttest x, by(group)"
                )
            self.varlist(m[1], numeric=True)
            if m[2] in frame:
                self.varlist(m[2], numeric=True)
                pair = frame[[m[1], m[2]]].dropna()
                res = stats.ttest_rel(pair.iloc[:, 0], pair.iloc[:, 1])
            else:
                res = stats.ttest_1samp(frame[m[1]].dropna(), float(m[2]))
        level = float(o.get("level", self.level)) / 100
        if not 0 < level < 1:
            raise StataError("Invalid confidence level")
        ci = res.confidence_interval(level)
        self.r = {
            "t": float(res.statistic),
            "p": float(res.pvalue),
            "df_t": float(res.df),
            "lb": ci.low,
            "ub": ci.high,
        }
        self.out(pd.Series(self.r).to_string())

    def cmd_ranksum(self, args, opt):
        o = options(opt, ("by",))
        h, q = qualifiers(args)
        cols = self.varlist(h, numeric=True)
        if len(cols) != 1 or "by" not in o:
            raise StataError("Syntax: ranksum x, by(group)")
        g = self.varlist(str(o["by"]))[0]
        df = self.df.loc[self.mask(q), [cols[0], g]].dropna()
        groups = sorted(df[g].unique())
        if len(groups) != 2:
            raise StataError("Exactly two groups required")
        r = stats.mannwhitneyu(
            df.loc[df[g] == groups[0], cols[0]],
            df.loc[df[g] == groups[1], cols[0]],
            alternative="two-sided",
            method="asymptotic",
            use_continuity=True,
        )
        self.r = {"U": float(r.statistic), "p": float(r.pvalue)}
        self.out(pd.Series(self.r).to_string())
        self.notice(
            "RANKSUM",
            "Reports Mann-Whitney U with asymptotic tie correction and continuity correction; Stata ranksum reports a rank-sum/z statistic and p-values may differ.",
        )

    def cmd_signrank(self, args, opt):
        options(opt, ())
        h, q = qualifiers(args)
        m = re.fullmatch(r"(\w+)\s*=\s*(\w+)", h)
        if not m:
            raise StataError("Syntax: signrank x = y")
        cols = self.varlist(" ".join(m.groups()), numeric=True)
        df = self.df.loc[self.mask(q), cols].dropna()
        r = stats.wilcoxon(
            df.iloc[:, 0], df.iloc[:, 1], method="approx", correction=True
        )
        self.r = {"W": float(r.statistic), "p": float(r.pvalue)}
        self.out(pd.Series(self.r).to_string())
        self.notice(
            "SIGNRANK",
            "SciPy Wilcoxon uses wilcox zero handling and continuity-corrected asymptotic p-values; ties/zeros and reported statistic can differ from Stata.",
        )

    def cmd_swilk(self, args, opt):
        options(opt, ())
        h, q = qualifiers(args)
        frame = self.df.loc[self.mask(q)]
        for c in self.varlist(h, numeric=True):
            x = frame[c].dropna()
            if len(x) < 3:
                raise StataError("Shapiro-Wilk needs at least three observations")
            r = stats.shapiro(x)
            self.r = {"W": float(r.statistic), "p": float(r.pvalue)}
            self.out(f"{c}: W={r.statistic:.7g}, p={r.pvalue:.7g}")
        self.notice(
            "SWILK",
            "SciPy Shapiro-Wilk approximation is used; large-sample p-values and Stata z/V output are not equivalent.",
        )

    def cmd_pca(self, args, opt):
        o = options(opt, ("components", "covariance"))
        h, q = qualifiers(args)
        cols = self.varlist(h, numeric=True)
        df = self.df.loc[self.mask(q), cols].dropna()
        x = df - df.mean()
        if "covariance" not in o:
            x = x / df.std(ddof=1)
        if not np.isfinite(x.to_numpy()).all():
            raise StataError("PCA contains constant/nonfinite columns")
        _, singular, vt = np.linalg.svd(x.to_numpy(), full_matrices=False)
        eigen = singular**2 / (len(df) - 1)
        k = int(o.get("components", len(eigen)))
        if not 1 <= k <= len(eigen):
            raise StataError("Invalid components()")
        self.out(
            pd.DataFrame(
                {"Eigenvalue": eigen[:k], "Proportion": (eigen / eigen.sum())[:k]},
                index=[f"PC{i + 1}" for i in range(k)],
            ).to_string()
        )
        self.out(
            "Loadings\n"
            + pd.DataFrame(
                vt[:k].T, index=cols, columns=[f"PC{i + 1}" for i in range(k)]
            ).to_string()
        )
        self.model = None
        self.e = {}
        self.r = {"N": len(df), "components": k}
        self.notice(
            "PCA",
            "SVD eigenvector signs are arbitrary and can differ from Stata. PCA clears previous estimation results; predict after pca is not implemented.",
        )

    def time_series(self, args):
        if self.tsvar:
            entity, time = None, self.tsvar
        elif self.panel and self.panel[1]:
            entity, time = self.panel
        else:
            raise StataError("Declare tsset time or xtset panel time first")
        if entity and self.df[entity].nunique() != 1:
            raise StataError("Time-series models currently require one panel")
        frame = self.df.sort_values(time)
        if not np.all(np.diff(frame[time].to_numpy()) == self.time_delta):
            raise StataError(
                "Time-series models require consecutive times at the declared delta"
            )
        names = self.varlist(args, numeric=True)
        if len(names) != 1 or frame[names[0]].isna().any():
            raise StataError("One complete numeric series is required")
        return frame[names[0]]

    def cmd_dfuller(self, args, opt):
        o = options(opt, ("lags", "trend", "noconstant"))
        if "trend" in o and "noconstant" in o:
            raise StataError("trend and noconstant conflict")
        y = self.time_series(args)
        from statsmodels.tsa.stattools import adfuller

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = adfuller(
                y,
                maxlag=int(o.get("lags", 0)),
                regression="ct" if "trend" in o else "n" if "noconstant" in o else "c",
                autolag=None,
            )
            self.emit_warnings(caught)
        stat, p, lag, n, crit = result[:5]
        self.r = {"Zt": stat, "p": p, "lags": lag, "N": n}
        self.out(pd.Series(self.r).to_string() + "\nCritical values " + str(crit))
        self.notice(
            "ADF",
            "statsmodels ADF uses MacKinnon approximations; critical-value interpolation and finite-sample p-values can differ from Stata.",
        )

    def cmd_arima(self, args, opt):
        o = options(opt, ("arima", "noconstant"))
        if "arima" not in o:
            raise StataError("arima(p,d,q) is required")
        order = tuple(int(x.strip()) for x in str(o["arima"]).split(","))
        if len(order) != 3 or min(order) < 0:
            raise StataError("Invalid arima order")
        y = self.time_series(args)
        from statsmodels.tsa.arima.model import ARIMA

        trend = (
            "n"
            if "noconstant" in o
            else ("c" if order[1] == 0 else "t" if order[1] == 1 else "n")
        )
        result = ARIMA(y.to_numpy(), order=order, trend=trend).fit()
        if not result.mle_retvals.get("converged", True):
            raise StataError("ARIMA failed to converge")
        names = result.param_names
        params = pd.Series(result.params, index=names)
        cov = pd.DataFrame(result.cov_params(), index=names, columns=names)
        pred = pd.Series(result.fittedvalues, index=y.index)
        self.model = Model(
            "arima",
            result,
            params,
            cov,
            y.index,
            y,
            pd.DataFrame(index=y.index),
            pred,
            y - pred,
            None,
            "backend",
            self.level,
        )
        self.notice(
            "ARIMA",
            "State-space likelihood, initialisation, trend parameterisation, covariance and stationarity constraints differ from Stata arima. No seasonal/exogenous specification or out-of-sample forecasting yet.",
        )
        self.report_model()

    def cmd_histogram(self, a, o):
        self.plot("histogram", a, o)

    def cmd_scatter(self, a, o):
        self.plot("scatter", a, o)

    def cmd_line(self, a, o):
        self.plot("line", a, o)

    def plot(self, kind, args, opt):
        allowed = (
            ("title", "bin", "frequency", "percent", "density")
            if kind == "histogram"
            else ("title", "sort")
            if kind == "line"
            else ("title",)
        )
        o = options(opt, allowed)
        h, q = qualifiers(args)
        cols = self.varlist(h, numeric=True)
        df = self.df.loc[self.mask(q), cols].dropna()
        if len(cols) != (1 if kind == "histogram" else 2):
            raise StataError("Wrong number of plot variables")
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        fig = Figure(figsize=(8, 5), dpi=120)
        FigureCanvasAgg(fig)
        ax = fig.subplots()
        if kind == "histogram":
            if sum(k in o for k in ("frequency", "percent", "density")) > 1:
                raise StataError("Choose frequency, percent or density")
            percent = "percent" in o
            density = "frequency" not in o and not percent
            ax.hist(
                df[cols[0]],
                bins=int(o["bin"]) if "bin" in o else "auto",
                density=density,
                weights=np.ones(len(df)) * 100 / len(df)
                if percent and len(df)
                else None,
                color="#287aac",
                edgecolor="white",
            )
            ax.set(
                xlabel=cols[0],
                ylabel="Percent" if percent else "Density" if density else "Frequency",
            )
            self.notice(
                "HISTOGRAM",
                "Automatic bins use NumPy/matplotlib rules and can differ from Stata. Specify bin() for explicit count.",
            )
        else:
            if "sort" in o:
                df = df.sort_values(cols[1])
            getattr(ax, kind if kind == "scatter" else "plot")(
                df[cols[1]], df[cols[0]], color="#287aac"
            )
            ax.set(xlabel=cols[1], ylabel=cols[0])
        ax.set_title(str(o.get("title", "")))
        ax.grid(alpha=0.18)
        fig.tight_layout()
        self.figure = fig
        self.emit("graph", "Graph ready", fig)

    def cmd_graph(self, args, opt):
        o = options(opt, ("replace",))
        if not args.startswith("export ") or self.figure is None:
            raise StataError('Create a graph, then graph export "file.png"')
        path = self.path(args[7:])
        self.write_guard(path, "replace" in o)
        if path.suffix.lower() not in (".png", ".svg", ".pdf"):
            raise StataError("Supported graph formats: png, svg, pdf")
        self.figure.savefig(path)
        self.out(f"Saved {path}")

    def bootstrap(self, text):
        pieces = split_top(text, ":")
        if len(pieces) != 2:
            raise StataError("Syntax: bootstrap _b[x], reps(100): regress y x")
        left, command = pieces
        from .weights import extract_weight

        if extract_weight(command)[1] is not None:
            raise StataError("Weights are not supported with bootstrap")
        spec = split_top(left[len("bootstrap ") :])
        m = re.fullmatch(r"_b\[([^]]+)\]", spec[0])
        if not m:
            raise StataError("This version bootstraps one _b[coefficient]")
        o = options(spec[1] if len(spec) == 2 else "", ("reps", "seed", "level"))
        reps = int(o.get("reps", 100))
        level = float(o.get("level", self.level))
        if reps < 2 or reps > 10000 or not 0 < level < 100:
            raise StataError("reps must be 2..10000 and level between 0 and 100")
        from .catalog import ALIASES

        cmd = ALIASES.get(command.split()[0], command.split()[0])
        if cmd not in ("regress", "logit", "probit", "poisson", "nbreg", "qreg", "glm"):
            raise StataError(
                "Bootstrap supports independent-observation regression commands only"
            )
        self.dispatch(command)
        original_model = self.require_model()
        original = self.df
        original_e = self.e.copy()
        if m[1] not in original_model.params:
            raise StataError("Bootstrap coefficient not found")
        # Resample only the complete estimation sample, not all rows with later omissions.
        source = original.loc[original_model.sample].copy()
        draws = []
        failures = 0
        rng = np.random.default_rng(int(o["seed"])) if "seed" in o else self.rng
        oldquiet = self.quiet
        self.quiet = True
        try:
            for i in range(reps):
                if self.stop.is_set():
                    raise StataError("Bootstrap interrupted", 1)
                self.df = source.iloc[
                    rng.choice(len(source), len(source), replace=True)
                ].reset_index(drop=True)
                try:
                    self.dispatch(command)
                    value = self.require_model().params[m[1]]
                    if not np.isfinite(value):
                        raise ValueError("Nonfinite estimate")
                    draws.append(value)
                except Exception:
                    failures += 1
                if i % 10 == 0:
                    self.emit(
                        "progress",
                        f"Bootstrap {i + 1}/{reps}",
                        int(100 * (i + 1) / reps),
                    )
        finally:
            self.df = original
            self.model = original_model
            self.e = original_e
            self.quiet = oldquiet
        if len(draws) < 2:
            raise StataError("Fewer than two bootstrap fits succeeded")
        se = float(np.std(draws, ddof=1))
        estimate = float(original_model.params[m[1]])
        critical = stats.norm.ppf(1 - (1 - level / 100) / 2)
        self.r = {
            "estimate": estimate,
            "se": se,
            "reps": len(draws),
            "failed": failures,
            "lb": estimate - critical * se,
            "ub": estimate + critical * se,
        }
        self.notice(
            "BOOTSTRAP",
            "IID PCG64 resampling of the complete estimation sample; Stata draws and CIs differ. Reports normal-based CI, no BCa/percentile/studentisation/cluster resampling. Failed fits are counted and excluded.",
        )
        self.out(pd.Series(self.r).to_string())
