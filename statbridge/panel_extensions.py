# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Panel specification tests, absorbed regression and a bounded two-period DiD."""

import re
import warnings
import numpy as np
import pandas as pd
from scipy import stats
from linearmodels.panel import RandomEffects
from linearmodels.iv.absorbing import AbsorbingLS
from .models import Model
from .syntax import StataError, options, qualifiers


class PanelExtensions:
    def _cre(self, m):
        if m.command != "xtreg" or m.revision != self.revision:
            raise StataError("Mundlak requires an unchanged xtreg estimation sample")
        panel = (m.metadata or {}).get("panel")
        if not panel:
            raise StataError("Panel metadata unavailable; refit xtreg")
        entity, time = panel
        frame = self.df.loc[m.sample]
        ids = frame[entity]
        # Simple Mundlak means require explicit scope; no unbalanced-panel selection correction.
        counts = ids.value_counts()
        if counts.min() < 2 or counts.nunique() != 1:
            raise StataError(
                "CRE/Mundlak currently requires a balanced complete-case panel with at least two observations per panel"
            )
        if (
            time
            and frame.groupby(entity)[time].apply(lambda x: tuple(sorted(x))).nunique()
            != 1
        ):
            raise StataError(
                "CRE/Mundlak requires the same observed time grid across panels"
            )
        x = m.x.copy()
        if np.linalg.matrix_rank(x) < x.shape[1]:
            raise StataError("CRE design is collinear")
        added = []
        for column in m.x:
            if column == "_cons":
                continue
            means = m.x[column].groupby(ids).transform("mean")
            if np.allclose(m.x[column], means):
                continue
            candidate = x.copy()
            name = "mean:" + column
            candidate[name] = means
            if np.linalg.matrix_rank(candidate) > np.linalg.matrix_rank(x):
                x = candidate
                added.append(name)
        if not added:
            raise StataError(
                "No separately identified time-varying panel means to test"
            )
        index = pd.MultiIndex.from_arrays(
            [ids, frame[time] if time else frame.groupby(entity).cumcount()]
        )
        px = x.copy()
        py = m.y.copy()
        px.index = index
        py.index = index
        cov = m.covariance
        kwargs = {"cov_type": "unadjusted"}
        if cov == "robust":
            kwargs = {"cov_type": "clustered", "cluster_entity": True}
        elif cov.startswith("cluster "):
            c = cov[8:].strip()
            if c not in frame or frame[c].isna().any() or frame[c].nunique() < 2:
                raise StataError("Invalid cluster variable for Mundlak")
            kwargs = {
                "cov_type": "clustered",
                "clusters": pd.DataFrame(
                    {"cluster": pd.factorize(frame[c])[0]}, index=index
                ),
            }
        elif cov not in ("ols", "unadjusted"):
            raise StataError("Unsupported CRE covariance")
        result = RandomEffects(py, px).fit(debiased=True, **kwargs)
        model = Model(
            "xtreg",
            result,
            result.params,
            result.cov,
            m.sample,
            m.y,
            x,
            pd.Series(result.fitted_values.iloc[:, 0].to_numpy(), index=m.sample),
            pd.Series(result.resids.to_numpy(), index=m.sample),
            result.df_resid,
            cov,
            m.level,
            metadata={"panel": panel, "cre_means": added},
        )
        model.revision = self.revision
        return model

    def cmd_xtreg(self, args, opt):
        # Validate CRE options before any estimation is committed.
        requested = options(
            opt, ("fe", "re", "cre", "vce", "robust", "level", "noconstant")
        )
        if "cre" in requested:
            o = options(opt, ("cre", "robust", "vce", "level"))
            if "robust" in o and "vce" in o:
                raise StataError("Choose robust or vce()")
            if not self.panel:
                raise StataError("Declare panel with xtset first")
            head, q = qualifiers(args)
            vs = head.split()
            if not vs:
                raise StataError("Specify outcome and predictors")
            frame = self.df.loc[self.mask(q)].copy()
            y = self.model_response(vs[0], frame)
            x = self.regressors(vs[1:], frame)
            x.insert(0, "_cons", 1.0)
            cov = str(o.get("vce", "robust" if "robust" in o else "ols"))
            valid = y.notna() & x.notna().all(axis=1) & frame[self.panel[0]].notna()
            for factor in re.findall(r"(?:^|[# ])(?:i|c|ib-?\d+)\.(\w+)", head):
                valid &= frame[factor].notna()
            if cov.startswith("cluster "):
                names = self.varlist(cov[8:])
                if len(names) != 1:
                    raise StataError("CRE supports one cluster variable")
                valid &= frame[names[0]].notna()
            y = y.loc[valid]
            x = x.loc[valid]
            if (
                len(y) <= x.shape[1]
                or not np.isfinite(x).all().all()
                or not np.isfinite(y).all()
            ):
                raise StataError("Insufficient finite complete observations")
            level = float(o.get("level", self.level))
            if not 0 < level < 100:
                raise StataError("Invalid level()")
            temporary = Model(
                "xtreg",
                None,
                pd.Series(dtype=float),
                pd.DataFrame(),
                y.index,
                y,
                x,
                y,
                y,
                None,
                cov,
                level,
                revision=self.revision,
                metadata={"panel": self.panel},
            )
            model = self._cre(temporary)
            self.model = model
            self.report_model()
            self.notice(
                "CRE",
                "Mundlak correlated RE adds identified panel means of expanded time-varying regressors. Balanced complete-case panels only; Stata unbalanced-panel corrections and all CRE options are not implemented. Robust clusters by panel. Backend covariance corrections and RE variance components can differ.",
            )
        else:
            super().cmd_xtreg(args, opt)
            self.model.metadata = {"panel": self.panel}

    def _diagnostic(self, result, title):
        if not np.isfinite(result.stat) or not np.isfinite(result.pval):
            raise StataError("Diagnostic is undefined for this model: " + str(result))
        self.r = {
            "stat": float(result.stat),
            "df": result.df,
            "p": float(result.pval),
            "distribution": result.dist_name,
        }
        self.r["F" if result.dist_name.startswith("F") else "chi2"] = float(result.stat)
        if getattr(result, "df_denom", None) is not None:
            self.r["df_r"] = result.df_denom
        self.show_table(title, pd.DataFrame([self.r]))

    def cmd_estat(self, args, opt):
        key = args.strip()
        if key not in ("mundlak", "firststage", "endogenous", "overid"):
            return super().cmd_estat(args, opt)
        options(opt, ())
        m = self.require_model()
        if key == "mundlak":
            cre = m if (m.metadata or {}).get("cre_means") else self._cre(m)
            if cre.revision != self.revision:
                raise StataError("Data changed; refit before Mundlak")
            names = cre.metadata["cre_means"]
            b = cre.params[names].to_numpy()
            v = cre.cov.loc[names, names].to_numpy()
            if np.linalg.eigvalsh(v).min() <= 0:
                raise StataError("Singular or invalid covariance of panel means")
            chi = float(b @ np.linalg.solve(v, b))
            self.r = {
                "chi2": chi,
                "df": len(names),
                "p": float(stats.chi2.sf(chi, len(names))),
            }
            self.show_table(
                "Mundlak Wald test: all added panel-mean coefficients equal zero",
                pd.DataFrame([self.r]),
            )
            self.notice(
                "MUNDLAK",
                "Balanced-panel CRE Wald chi-square on identified panel means, with the selected covariance. Does not replace the active FE/RE fit. Cluster-robust inference is asymptotic; few clusters are a limitation. Non-rejection does not prove the RE restrictions.",
            )
            return
        if m.command != "ivregress":
            raise StataError("This diagnostic requires ivregress 2sls")
        result = m.result
        if key == "firststage":
            table = result.first_stage.diagnostics.copy()
            self.r = {"N": len(m.sample), "k": len(table)}
            self.show_table(
                "First-stage diagnostics (f.dist gives the actual reference distribution)",
                table,
            )
            self.notice(
                "IV_FIRSTSTAGE",
                "Unadjusted covariance uses F inference; robust/clustered covariance uses a Wald chi-square. Do not compare every f.stat to a universal F > 10 threshold. No Stock-Yogo critical values or weak-IV-robust intervals.",
            )
        elif key == "endogenous":
            conventional = m.covariance in ("ols", "unadjusted")
            test = result.wu_hausman() if conventional else result.wooldridge_regression
            self._diagnostic(
                test,
                (
                    "Exogeneity test: Wu-Hausman F"
                    if conventional
                    else "Exogeneity test: Wooldridge regression Wald with fitted covariance"
                ),
            )
            self.notice(
                "IV_ENDOGENOUS",
                "Tests all nominated endogenous regressors as exogenous under valid-instrument assumptions. Robust/clustered fits use Wooldridge regression, not the classical Wu-Hausman F. This is distinct from panel Hausman.",
            )
        else:
            if result.model.instruments.shape[1] <= result.model.endog.shape[1]:
                raise StataError(
                    "Overidentification requires more excluded instruments than endogenous regressors"
                )
            if m.covariance.startswith("cluster "):
                raise StataError(
                    "Cluster-robust overidentification is not implemented; no iid test substituted"
                )
            conventional = m.covariance in ("ols", "unadjusted")
            self._diagnostic(
                result.sargan if conventional else result.wooldridge_overid,
                (
                    "Sargan overidentification test"
                    if conventional
                    else "Wooldridge heteroskedasticity-robust overidentification score test"
                ),
            )
            self.notice(
                "IV_OVERID",
                "Joint instrument moment restrictions under the stated covariance assumptions. Rejection does not identify a particular invalid instrument; non-rejection does not prove validity. Robust score test is not a Hansen J test.",
            )

    def cmd_reghdfe(self, args, opt):
        o = options(opt, ("absorb", "vce", "robust", "level", "keepsingletons"))
        if "absorb" not in o:
            raise StataError("absorb() is required")
        if "robust" in o and "vce" in o:
            raise StataError("Choose robust or vce()")
        head, q = qualifiers(args)
        terms = head.split()
        if not terms:
            raise StataError("Specify outcome and predictors")
        absorbed = self.varlist(str(o["absorb"]))
        if not absorbed:
            raise StataError("At least one categorical absorbed variable required")
        frame = self.df.loc[self.mask(q)].copy()
        y = self.model_response(terms[0], frame)
        x = self.regressors(terms[1:], frame)
        if x.shape[1] == 0:
            raise StataError(
                "At least one slope is required; absorbed intercepts are not reported"
            )
        cov = str(o.get("vce", "robust" if "robust" in o else "ols"))
        clusters = []
        if cov.startswith("cluster "):
            clusters = self.varlist(cov[8:])
            if not 1 <= len(clusters) <= 2:
                raise StataError("One or two cluster variables supported")
        elif cov not in ("ols", "unadjusted", "robust"):
            raise StataError("Unsupported covariance")
        valid = (
            y.notna()
            & x.notna().all(axis=1)
            & frame[absorbed + clusters].notna().all(axis=1)
        )
        frame = frame.loc[valid]
        before = len(frame)
        if "keepsingletons" not in o:
            while len(frame):
                keep = np.ones(len(frame), dtype=bool)
                for c in absorbed:
                    keep &= frame[c].map(frame[c].value_counts()).gt(1).to_numpy()
                if keep.all():
                    break
                frame = frame.loc[keep]
        x = x.loc[frame.index]
        y = y.loc[frame.index]
        if (
            len(frame) <= x.shape[1]
            or not np.isfinite(x).all().all()
            or not np.isfinite(y).all()
        ):
            raise StataError("Insufficient finite observations after singleton removal")
        kw = {}
        covtype = "robust" if cov == "robust" else "unadjusted"
        if clusters:
            if any(frame[c].nunique() < 2 for c in clusters):
                raise StataError("At least two clusters in each dimension required")
            kw = {
                "clusters": np.column_stack(
                    [pd.factorize(frame[c])[0] for c in clusters]
                )
            }
            covtype = "clustered"
        level = float(o.get("level", self.level))
        if not 0 < level < 100:
            raise StataError("Invalid level()")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = AbsorbingLS(
                y, x, absorb=frame[absorbed].astype("category"), drop_absorbed=True
            ).fit(cov_type=covtype, debiased=True, **kw)
        if (
            result.df_resid <= 0
            or not np.isfinite(result.cov).all().all()
            or np.linalg.eigvalsh(result.cov).min() < -1e-10
            or np.any(np.diag(result.cov) <= 0)
        ):
            raise StataError(
                "Invalid residual df or covariance; reduce the specification"
            )
        df = (
            min(frame[c].nunique() - 1 for c in clusters)
            if clusters
            else result.df_resid
        )
        model = Model(
            "reghdfe",
            result,
            result.params,
            result.cov,
            y.index,
            y,
            x,
            result.fitted_values.iloc[:, 0],
            result.resids,
            df,
            cov,
            level,
            metadata={
                "absorbed": absorbed,
                "clusters": clusters,
                "singletons_dropped": before - len(frame),
            },
        )
        self.model = model
        self.report_model()
        self.emit_warnings(caught)
        self.notice(
            "HDFE",
            f"AbsorbingLS categorical effects (including intercept); no normalisation-dependent constant is reported. {before-len(frame)} singleton rows removed iteratively. Backend debiasing/absorbed degrees of freedom are not reghdfe-identical, including effects nested in clusters. Two-way cluster covariance uses inclusion-exclusion and t(min(G1,G2)-1); it can be indefinite. No weights, heterogeneous slopes or IV absorb syntax.",
        )

    def cmd_predict(self, args, opt):
        m = self.require_model()
        if m.command in ("reghdfe", "didregress", "xtdidregress"):
            o = options(opt, ("residuals",))
            if "residuals" not in o:
                raise StataError(
                    "Absorbed-model predict currently supports residuals only; xb with recovered effects is not implemented"
                )
            head, q = qualifiers(args)
            name = head.strip()
            self.newvar(name)
            if m.revision != self.revision:
                raise StataError("Data changed; refit before prediction")
            self.df[name] = m.residual.reindex(self.df.index).where(self.mask(q))
            self.dirty = True
            return
        return super().cmd_predict(args, opt)

    def _did(self, args, opt, panel):
        o = options(opt, ("group", "time", "vce", "level"))
        match = re.fullmatch(r"\(([^()]*)\)\s*\((\w+)\)", args.strip())
        if not match or "group" not in o or "time" not in o:
            raise StataError(
                "Syntax: didregress (y [controls]) (treated), group(groupvar) time(timevar)"
            )
        terms = match[1].split()
        treat = match[2]
        group = str(o["group"])
        time = str(o["time"])
        if not terms:
            raise StataError("Outcome required")
        self.varlist(f"{treat} {group} {time}")
        if panel and (not self.panel or not self.panel[1] or self.panel[1] != time):
            raise StataError(
                "xtdidregress requires xtset id time with the same time variable"
            )
        frame = self.df
        if frame[[group, time, treat]].isna().any().any():
            raise StataError("DiD identifiers and treatment must be complete")
        periods = sorted(frame[time].unique())
        if len(periods) != 2 or not frame[treat].isin([0, 1]).all():
            raise StataError(
                "This DiD implementation requires exactly two periods and binary treatment; staggered adoption is not supported"
            )
        if not frame.loc[frame[time] == periods[0], treat].eq(0).all():
            raise StataError("Treatment must begin only in the second period")
        cells = frame.groupby([group, time])[treat].agg(["min", "max"])
        if (
            not cells["min"].equals(cells["max"])
            or not frame.groupby(group)[time].nunique().eq(2).all()
        ):
            raise StataError(
                "Treatment must be constant within group-period and all groups present in both periods"
            )
        status = frame.loc[frame[time] == periods[1]].groupby(group)[treat].first()
        if status.nunique() != 2 or min(status.value_counts()) < 2:
            raise StataError(
                "Require at least two treated and two control groups for clustered inference"
            )
        if panel:
            idvar = self.panel[0]
            if (
                not frame.groupby(idvar)[time].nunique().eq(2).all()
                or not frame.groupby(idvar)[group].nunique().eq(1).all()
            ):
                raise StataError(
                    "Panel DiD requires a balanced panel with stable group membership"
                )
        # Restrict to complete data to avoid silently changing treatment cells or panel balance.
        y = self.model_response(terms[0], frame)
        x = self.regressors(terms[1:], frame)
        if y.isna().any() or x.isna().any().any():
            raise StataError(
                "DiD currently requires complete outcomes and controls; explicitly prepare the analysis sample"
            )
        vce = str(o.get("vce", "cluster " + group))
        if vce != "cluster " + group:
            raise StataError("DiD currently requires clustering on group()")
        absorb = f"{self.panel[0]} {time}" if panel else f"{group} {time}"
        self.cmd_reghdfe(
            " ".join(terms + [treat]),
            f'absorb({absorb}) vce({vce}) level({o.get("level",self.level)}) keepsingletons',
        )
        self.model.command = "xtdidregress" if panel else "didregress"
        self.model.metadata["did_treatment"] = treat
        self.report_model()
        self.notice(
            "DID",
            "Conventional two-period additive DiD with group/panel and period effects, clustered by treatment group. Treatment coefficient estimates a common conditional effect under parallel trends, no anticipation and no interference. Not a staggered/heterogeneous-treatment estimator. One pre-period cannot test parallel trends; no wild bootstrap or Stata-specific small-sample adjustment.",
        )

    def cmd_didregress(self, args, opt):
        self._did(args, opt, False)

    def cmd_xtdidregress(self, args, opt):
        self._did(args, opt, True)
