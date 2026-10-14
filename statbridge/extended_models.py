# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Categorical models, HAC OLS and basic right-censored survival analysis."""

import re
import numpy as np
import pandas as pd
import statsmodels.api as sm
from .models import Model
from .syntax import StataError, options, qualifiers
from .everyday import level_option


class ExtendedModelCommands:
    def cmd_clear(self, args, opt):
        result = super().cmd_clear(args, opt)
        self.survey_design = None
        self.survival_set = False
        return result

    def cmd_import(self, args, opt):
        revision = self.revision
        result = super().cmd_import(args, opt)
        if self.revision != revision:
            self.survey_design = None
            self.survival_set = False
        return result

    def cmd_use(self, args, opt):
        result = super().cmd_use(args, opt)
        self.survey_design = None
        self.survival_set = False
        return result

    def cmd_newey(self, args, opt):
        o = options(opt, ("lag", "level", "noconstant"))
        if "lag" not in o:
            raise StataError("lag(#) is required")
        lag = int(o["lag"])
        level = level_option(self, o)
        if lag < 0:
            raise StataError("lag() must be nonnegative")
        head, q = qualifiers(args)
        terms = head.split()
        if not terms:
            raise StataError("Specify outcome and regressors")
        time = self.tsvar or (self.panel[1] if self.panel else None)
        if not time or (self.panel and self.df[self.panel[0]].nunique() > 1):
            raise StataError("newey requires one declared time series")
        frame = self.df.loc[self.mask(q)].sort_values(time)
        y = self.model_response(terms[0], frame)
        x = self.regressors(terms[1:], frame)
        if "noconstant" not in o:
            x.insert(0, "_cons", 1.0)
        valid = y.notna() & x.notna().all(axis=1)
        y = y.loc[valid]
        x = x.loc[valid]
        times = frame.loc[valid, time]
        if len(y) <= x.shape[1] or lag >= len(y) or not x.shape[1]:
            raise StataError("Insufficient data or excessive lag")
        if not np.allclose(np.diff(times), self.time_delta):
            raise StataError(
                "Require consecutive times in the complete estimation sample"
            )
        if (
            not np.isfinite(x.to_numpy()).all()
            or not np.isfinite(y).all()
            or np.linalg.matrix_rank(x) < x.shape[1]
        ):
            raise StataError("Collinear or nonfinite design")
        result = sm.OLS(y, x).fit(
            cov_type="HAC",
            cov_kwds={"maxlags": lag, "use_correction": True},
            use_t=True,
        )
        params = pd.Series(result.params, index=x.columns)
        cov = pd.DataFrame(result.cov_params(), index=x.columns, columns=x.columns)
        pred = pd.Series(result.predict(), index=y.index)
        self.model = Model(
            "newey",
            result,
            params,
            cov,
            y.index,
            y,
            x,
            pred,
            y - pred,
            len(y) - x.shape[1],
            "HAC",
            level,
            fit_extra={"lag": lag},
        )
        self.report_model()
        self.notice(
            "NEWEY",
            "Bartlett HAC with N/(N-k) correction and residual-df t inference. Regular complete sample only; no force, prewhitening, automatic bandwidth or panel HAC.",
        )

    def _categorical(self, kind, args, opt):
        o = options(
            opt, ("level", "baseoutcome", "rrr") if kind == "mlogit" else ("level",)
        )
        level = level_option(self, o)
        head, q = qualifiers(args)
        terms = head.split()
        if len(terms) < 2:
            raise StataError("Specify categorical outcome and regressors")
        frame = self.df.loc[self.mask(q)]
        y = self.model_response(terms[0], frame)
        x = self.regressors(terms[1:], frame)
        valid = y.notna() & x.notna().all(axis=1)
        y = y.loc[valid]
        x = x.loc[valid]
        if (
            not np.isfinite(y).all()
            or not np.isfinite(x.to_numpy()).all()
            or (y % 1 != 0).any()
        ):
            raise StataError("Require integer categories and finite regressors")
        categories = sorted(y.unique())
        if not 2 <= len(categories) <= 50:
            raise StataError("Require 2..50 observed categories")
        if (
            len(y) <= x.shape[1] + len(categories)
            or not x.shape[1]
            or np.linalg.matrix_rank(x) < x.shape[1]
        ):
            raise StataError("Insufficient data or collinear design")
        if kind == "mlogit":
            counts = y.value_counts()
            base = (
                float(o["baseoutcome"])
                if "baseoutcome" in o
                else min(counts[counts == counts.max()].index)
            )
            if base not in categories:
                raise StataError("baseoutcome() is not observed")
            categories = [base] + [c for c in categories if c != base]
            x.insert(0, "_cons", 1.0)
            if np.linalg.matrix_rank(x) < x.shape[1]:
                raise StataError("Collinear design including constant")
            codes = y.map({v: i for i, v in enumerate(categories)})
            result = sm.MNLogit(codes, x).fit(method="newton", disp=False, maxiter=200)
            names = [f"{c:g}:{name}" for c in categories[1:] for name in x.columns]
            params = pd.Series(
                np.asarray(result.params).reshape(-1, order="F"), index=names
            )
            cov = pd.DataFrame(
                np.asarray(result.cov_params()), index=names, columns=names
            )
        else:
            from statsmodels.miscmodels.ordinal_model import OrderedModel

            codes = y.map({v: i for i, v in enumerate(categories)})
            result = OrderedModel(
                codes, x, distr="logit" if kind == "ologit" else "probit"
            ).fit(method="bfgs", disp=False, maxiter=500)
            raw = np.asarray(result.params)
            p = x.shape[1]
            cuts = result.model.transform_threshold_params(raw)[1:-1]
            names = list(x.columns) + [f"/cut{i+1}" for i in range(len(cuts))]
            params = pd.Series(np.r_[raw[:p], cuts], index=names)
            jac = np.eye(len(raw))
            jac[p:, p:] = 0
            for i in range(len(cuts)):
                jac[p + i, p] = 1
                for j in range(1, i + 1):
                    jac[p + i, p + j] = np.exp(raw[p + j])
            cov = pd.DataFrame(
                jac @ np.asarray(result.cov_params()) @ jac.T,
                index=names,
                columns=names,
            )
        if (
            not result.mle_retvals.get("converged", True)
            or not np.isfinite(params).all()
            or not np.isfinite(cov.to_numpy()).all()
        ):
            raise StataError("Categorical fit did not converge to finite estimates")
        probabilities = np.asarray(result.predict())
        pred = pd.Series(probabilities @ np.array(categories), index=y.index)
        self.model = Model(
            kind,
            result,
            params,
            cov,
            y.index,
            y,
            x,
            pred,
            y - pred,
            None,
            "oim",
            level,
            metadata={"categories": categories, "probabilities": probabilities},
            fit_extra={
                "df_m": (
                    (x.shape[1] - 1) * (len(categories) - 1)
                    if kind == "mlogit"
                    else x.shape[1]
                )
            },
        )
        self.report_model("rrr" in o)
        self.notice(
            "CATEGORICAL",
            "Unweighted maximum likelihood, model-based covariance only. Optimizer, separation detection and convergence differ from Stata. Ordered cutpoints and covariance are transformed to latent-scale thresholds. Sample-only probabilities; no margins for these models.",
        )

    def cmd_mlogit(self, a, o):
        self._categorical("mlogit", a, o)

    def cmd_ologit(self, a, o):
        self._categorical("ologit", a, o)

    def cmd_oprobit(self, a, o):
        self._categorical("oprobit", a, o)

    def cmd_stset(self, args, opt):
        o = options(opt, ("failure", "id", "scale", "clear"))
        if "clear" in o:
            if args or len(o) > 1:
                raise StataError("Use stset, clear alone")
            self.survival_set = False
            return
        if not args and not opt:
            self.out(
                "Right-censored survival data declared"
                if self.survival_set
                else "Survival data not declared"
            )
            return
        head, q = qualifiers(args)
        cols = self.varlist(head, numeric=True)
        if len(cols) != 1 or "failure" not in o:
            raise StataError("stset duration, failure(binary) [id(subject) scale(#)]")
        time = self.df[cols[0]].astype(float)
        fail = self.expr(o["failure"])
        if not isinstance(fail, pd.Series) or not fail.dropna().isin([0, 1]).all():
            raise StataError("failure() must reference a 0/1 variable or expression")
        scale = float(o.get("scale", 1))
        if not np.isfinite(scale) or scale <= 0:
            raise StataError("scale() must be finite and positive")
        valid = (
            self.mask(q)
            & time.notna()
            & fail.notna()
            & (time > 0)
            & np.isfinite(time / scale)
        )
        if "id" in o:
            ids = self.varlist(o["id"])
            if (
                len(ids) != 1
                or self.df.loc[valid, ids[0]].isna().any()
                or self.df.loc[valid, ids[0]].eq("").any()
                or self.df.loc[valid, ids[0]].duplicated().any()
            ):
                raise StataError("Only one record per nonmissing subject id supported")
        if not valid.any():
            raise StataError("No eligible positive finite survival times")
        frame = self.df.copy()
        frame["_t"] = time / scale
        frame["_t0"] = 0.0
        frame["_d"] = fail.astype(float)
        frame["_st"] = valid.astype(float)
        self.df = frame
        self.changed()
        self.survival_set = True
        self.r = {
            "N": int(valid.sum()),
            "N_fail": int(fail[valid].sum()),
            "N_excluded": int((~valid).sum()),
        }
        self.out(str(self.r))
        self.notice(
            "STSET",
            "Single-record right-censored origin-zero data only. Invalid times excluded; _t, _t0, _d, _st created/replaced. No delayed entry, repeated records, competing risks or interval censoring.",
        )

    def _survival_data(self):
        if not self.survival_set or not {"_t", "_t0", "_d", "_st"}.issubset(self.df):
            raise StataError("Declare stset first")
        data = self.df.loc[self.df["_st"].eq(1)]
        if (
            data.empty
            or not data["_d"].isin([0, 1]).all()
            or not np.isfinite(data["_t"]).all()
            or not data["_t"].gt(0).all()
            or not data["_t0"].eq(0).all()
        ):
            raise StataError("Survival variables changed; declare stset again")
        return data

    def cmd_stsum(self, args, opt):
        o = options(opt, ("by",))
        data = self._survival_data()
        groups = self.varlist(o["by"]) if "by" in o else []
        if args or len(groups) > 1:
            raise StataError("stsum [, by(group)]")
        rows = []
        for g, part in data.groupby(groups[0]) if groups else [("All", data)]:
            sf = sm.SurvfuncRight(part["_t"], part["_d"])
            rows.append(
                {
                    "Group": g,
                    "N": len(part),
                    "Failures": int(part["_d"].sum()),
                    "Time at risk": part["_t"].sum(),
                    "Median survival": sf.quantile(0.5),
                }
            )
        self.show_table("Survival summary", pd.DataFrame(rows))
        self.r = {"N": len(data), "N_fail": int(data["_d"].sum())}

    def cmd_sts(self, args, opt):
        kind, _, text = args.partition(" ")
        if kind not in ("list", "graph", "test"):
            raise StataError("sts list|graph [, by(group)] or sts test group")
        o = options(
            opt,
            () if kind == "test" else ("by", "title") if kind == "graph" else ("by",),
        )
        data = self._survival_data()
        groups = self.varlist(text if kind == "test" else o.get("by", ""))
        if (
            len(groups) > 1
            or (kind == "test" and len(groups) != 1)
            or (kind != "test" and text)
        ):
            raise StataError("One grouping variable supported")
        if groups and (data[groups[0]].isna().any() or data[groups[0]].eq("").any()):
            raise StataError("Survival group must be nonmissing")
        if kind == "test":
            from statsmodels.duration.survfunc import survdiff

            codes, levels = pd.factorize(data[groups[0]])
            if len(levels) < 2:
                raise StataError("At least two groups required")
            chi, p = survdiff(data["_t"], data["_d"], codes)
            self.r = {"chi2": float(chi), "df": len(levels) - 1, "p": float(p)}
            self.show_table("Log-rank test", pd.DataFrame([self.r]))
            return
        rows = []
        if kind == "graph":
            fig, ax = self._figure()
        for g, part in data.groupby(groups[0]) if groups else [("All", data)]:
            sf = sm.SurvfuncRight(part["_t"], part["_d"])
            for t, s, se, n, d in zip(
                sf.surv_times, sf.surv_prob, sf.surv_prob_se, sf.n_risk, sf.n_events
            ):
                rows.append(
                    {
                        "Group": g,
                        "Time": t,
                        "At risk": n,
                        "Failures": d,
                        "Survival": s,
                        "Std. err.": se,
                    }
                )
            if kind == "graph":
                ax.step(
                    np.r_[0, sf.surv_times, part["_t"].max()],
                    np.r_[
                        1, sf.surv_prob, sf.surv_prob[-1] if len(sf.surv_prob) else 1
                    ],
                    where="post",
                    label=str(g),
                )
        if kind == "list":
            self.show_table("Kaplan-Meier survival", pd.DataFrame(rows))
        else:
            ax.set(
                xlabel="Analysis time", ylabel="Survival probability", ylim=(0, 1.02)
            )
            ax.legend()
            self._graph_ready(fig, ax, o.get("title", "Kaplan-Meier survival"))
        self.notice(
            "SURVIVAL_KM",
            "Kaplan-Meier at event times, Greenwood SEs. Independent right censoring assumed. No censor marks, confidence bands or full sts options.",
        )

    def cmd_stcox(self, args, opt):
        o = options(opt, ("ties", "nohr", "level", "strata"))
        level = level_option(self, o)
        head, q = qualifiers(args)
        frame = self._survival_data().loc[self.mask(q)]
        x = self.regressors(head.split(), frame)
        valid = x.notna().all(axis=1)
        strata = None
        if "strata" in o:
            names = self.varlist(o["strata"])
            if len(names) != 1:
                raise StataError("One strata variable supported")
            strata = frame[names[0]]
            valid &= strata.notna() & ~strata.eq("")
        x = x.loc[valid]
        frame = frame.loc[valid]
        if (
            x.empty
            or not np.isfinite(x.to_numpy()).all()
            or np.linalg.matrix_rank(x) < x.shape[1]
            or frame["_d"].sum() <= x.shape[1]
        ):
            raise StataError(
                "Require full-rank design and more failures than coefficients"
            )
        if np.linalg.matrix_rank(np.column_stack([np.ones(len(x)), x])) == x.shape[1]:
            raise StataError("Cox cannot include a constant")
        ties = o.get("ties", "breslow")
        if ties not in ("breslow", "efron"):
            raise StataError("ties() supports breslow or efron")
        result = sm.PHReg(
            frame["_t"],
            x,
            status=frame["_d"],
            strata=strata.loc[valid] if strata is not None else None,
            ties=ties,
        ).fit(disp=False)
        params = pd.Series(result.params, index=x.columns)
        cov = pd.DataFrame(result.cov_params(), index=x.columns, columns=x.columns)
        if (
            not np.isfinite(params).all()
            or not np.isfinite(cov.to_numpy()).all()
            or np.max(np.abs(result.model.score(result.params)))
            > 1e-4 * max(1, len(frame))
        ):
            raise StataError("Cox fit did not reach a finite converged solution")
        xb = x @ params
        self.model = Model(
            "stcox",
            result,
            params,
            cov,
            x.index,
            frame["_t"],
            x,
            np.exp(xb),
            pd.Series(np.nan, index=x.index),
            None,
            "oim",
            level,
            linear_prediction=xb,
            fit_extra={"N_fail": int(frame["_d"].sum())},
        )
        self.report_model("nohr" not in o)
        self.notice(
            "COX",
            "Cox partial likelihood, selected ties, model-based covariance. Hazard ratios by default. No weights, clustered VCE, time-varying effects, baseline predictions or proportional-hazards diagnostic yet.",
        )

    def cmd_predict(self, args, opt):
        m = self.require_model()
        if (m.metadata or {}).get("summary"):
            raise StataError("predict is not defined for descriptive estimates")
        if m.command not in (
            "newey",
            "mlogit",
            "ologit",
            "oprobit",
            "stcox",
            "svy: regress",
        ):
            return super().cmd_predict(args, opt)
        opt = re.sub(r"\bresid\b", "residuals", opt)
        o = options(opt, ("xb", "pr", "outcome", "residuals", "hr"))
        head, q = qualifiers(args)
        name = re.sub(r"^(?:double|float)\s+", "", head.strip())
        self.newvar(name)
        if m.revision != self.revision:
            raise StataError("Data changed since estimation")
        if sum(k in o for k in ("xb", "pr", "residuals", "hr")) > 1:
            raise StataError("Choose one prediction type")
        if m.command in ("mlogit", "ologit", "oprobit"):
            if any(k in o for k in ("xb", "residuals", "hr")) or "outcome" not in o:
                raise StataError("Categorical prediction requires pr outcome(category)")
            category = float(o["outcome"])
            categories = m.metadata["categories"]
            if category not in categories:
                raise StataError("Outcome category not present at estimation")
            values = pd.Series(
                m.metadata["probabilities"][:, categories.index(category)],
                index=m.sample,
            )
        elif m.command == "stcox":
            if any(k in o for k in ("pr", "residuals", "outcome")):
                raise StataError("Cox prediction supports xb or hr")
            values = m.linear_prediction if "xb" in o else m.predicted
        else:
            if any(k in o for k in ("pr", "hr", "outcome")):
                raise StataError("Linear prediction supports xb or residuals")
            values = m.residual if "residuals" in o else m.predicted
        self.df[name] = values.reindex(self.df.index).where(self.mask(q))
        self.dirty = True
        self.notice(
            "PREDICT_SAMPLE",
            "Predictions restricted to original estimation sample; other observations missing.",
        )
