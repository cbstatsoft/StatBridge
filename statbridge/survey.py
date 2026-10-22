# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""One-stage with-replacement Taylor linearization for common survey estimates."""

from types import SimpleNamespace
import numpy as np
import pandas as pd
import statsmodels.api as sm
from .syntax import StataError, options, split_top, qualifiers
from .weights import extract_weight
from .models import Model
from .everyday import level_option


def survey_covariance(scores, psu, strata, fpc=None):
    data = pd.DataFrame(scores).copy()
    data["_psu"] = np.asarray(psu)
    data["_stratum"] = np.asarray(strata)
    if fpc is not None:
        data["_fpc"] = np.asarray(fpc, dtype=float)
    grouped = data.drop(columns=["_fpc"], errors="ignore").groupby(["_stratum", "_psu"], sort=False, dropna=False).sum()
    cov = np.zeros((scores.shape[1], scores.shape[1]))
    npsu = nstrata = 0
    for _, group in grouped.groupby(level=0, sort=False):
        n = len(group)
        if n < 2:
            raise StataError(
                "A stratum has only one PSU; singleton adjustments not implemented"
            )
        z = group.to_numpy()
        z = z - z.mean(axis=0)
        fraction = 0.0
        if fpc is not None:
            in_stratum = data.loc[data["_stratum"].eq(group.index.get_level_values(0)[0]), "_fpc"]
            if not np.isfinite(in_stratum).all() or in_stratum.nunique() != 1:
                raise StataError("fpc() must be finite and constant within each stratum")
            value = float(in_stratum.iloc[0])
            if value <= 0:
                raise StataError("fpc() must be a positive population count or sampling fraction")
            fraction = value if value <= 1 else n / value
            if fraction > 1 or (value > 1 and value < n):
                raise StataError("fpc population PSU count must be >= sampled PSUs")
        cov += (1 - fraction) * n / (n - 1) * (z.T @ z)
        npsu += n
        nstrata += 1
    return cov, npsu, nstrata


class SurveyCommands:
    def cmd_svyset(self, args, opt):
        o = options(opt, ("strata", "fpc", "clear"))
        if "clear" in o:
            if args or len(o) > 1:
                raise StataError("Use svyset, clear alone")
            self.survey_design = None
            self.out("Survey declaration cleared")
            return
        if not args and not opt:
            self.out(str(self.survey_design or "Survey design not set"))
            return
        text, spec = extract_weight(args)
        if spec is not None and spec[0] != "pw":
            raise StataError("svyset requires probability weights [pw=variable]")
        psus = self.varlist(text) if text else []
        weights = self.varlist(spec[1], numeric=True) if spec else []
        strata = self.varlist(o["strata"]) if "strata" in o else []
        fpc = self.varlist(o["fpc"], numeric=True) if "fpc" in o else []
        if len(psus) > 1 or len(weights) > 1 or len(strata) > 1 or len(fpc) > 1:
            raise StataError("One variable per design role supported")
        self.survey_design = {
            "psu": psus[0] if psus else None,
            "weight": weights[0] if weights else None,
            "strata": strata[0] if strata else None,
            "fpc": fpc[0] if fpc else None,
        }
        self.out(str(self.survey_design))
        self.notice(
            "SVY_DESIGN",
            "One-stage stratified Taylor variance, optionally with a finite population correction fpc() constant per stratum (sampling fraction or stratum population PSU count). No multistage, replicate weights, calibration or singleton adjustment. Omitted PSU treats observations as sampling units.",
        )

    def survey_command(self, text):
        parts = split_top(text, ":")
        if len(parts) != 2:
            raise StataError(
                "svy [, subpop(indicator)]: mean|total|proportion|regress ..."
            )
        prefix = split_top(parts[0][3:].strip())
        if len(prefix) > 2 or prefix[0]:
            raise StataError("Use svy: command or svy, subpop(indicator): command")
        po = options(prefix[1] if len(prefix) == 2 else "", ("subpop",))
        bits = parts[1].strip().split(None, 1)
        kind = bits[0] if bits else ""
        if kind not in ("mean", "total", "proportion", "regress"):
            raise StataError(
                "Survey supports mean/total/proportion/regress; no ordinary weighted substitute is run"
            )
        spec = split_top(bits[1] if len(bits) > 1 else "")
        if len(spec) > 2:
            raise StataError("Unexpected top-level comma")
        o = options(spec[1] if len(spec) > 1 else "", ("level",))
        level = level_option(self, o)
        head, q = qualifiers(spec[0])
        if q:
            raise StataError(
                "Use subpop(indicator); if/in survey restrictions are not supported"
            )
        design = self.survey_design
        if design is None:
            raise StataError("Declare svyset first")
        if any(c is not None and c not in self.df for c in design.values()):
            raise StataError("Design variable missing; declare svyset again")
        data = self.df
        psu = (
            data[design["psu"]]
            if design["psu"]
            else pd.Series(np.arange(len(data)), index=data.index)
        )
        strata = (
            data[design["strata"]]
            if design["strata"]
            else pd.Series(1, index=data.index)
        )
        weight = (
            data[design["weight"]].astype(float)
            if design["weight"]
            else pd.Series(1.0, index=data.index)
        )
        if (
            psu.isna().any()
            or strata.isna().any()
            or psu.eq("").any()
            or strata.eq("").any()
            or not np.isfinite(weight).all()
            or (weight <= 0).any()
        ):
            raise StataError(
                "Nonmissing design IDs and finite positive weights required"
            )
        domain = pd.Series(True, index=data.index)
        if "subpop" in po:
            names = self.varlist(po["subpop"], numeric=True)
            if len(names) != 1 or not data[names[0]].isin([0, 1]).all():
                raise StataError("subpop() requires a nonmissing 0/1 indicator")
            domain = data[names[0]].eq(1)
        if kind == "regress":
            terms = head.split()
            if not terms:
                raise StataError("Specify outcome and regressors")
            y = self.model_response(terms[0], data)
            x = self.regressors(terms[1:], data)
            x.insert(0, "_cons", 1.0)
            valid = domain & y.notna() & x.notna().all(axis=1)
            if valid.sum() <= x.shape[1]:
                raise StataError("Insufficient complete domain observations")
            xv = x.loc[valid].astype(float)
            yv = y.loc[valid].astype(float)
            w = weight.loc[valid]
            if (
                not np.isfinite(xv.to_numpy()).all()
                or not np.isfinite(yv).all()
                or np.linalg.matrix_rank(xv) < xv.shape[1]
            ):
                raise StataError("Collinear or nonfinite survey design")
            fit = sm.WLS(yv, xv, weights=w).fit()
            params = fit.params
            bread = np.linalg.inv(xv.T @ xv.mul(w, axis=0))
            u = np.zeros((len(data), xv.shape[1]))
            u[np.flatnonzero(valid)] = xv.mul(w * fit.resid, axis=0).to_numpy() @ bread
            predicted = pd.Series(fit.predict(), index=yv.index)
            residual = yv - predicted
        else:
            cols = self.varlist(head, numeric=kind != "proportion")
            if not cols:
                raise StataError("Specify variables")
            valid = domain & data[cols].notna().all(axis=1)
            if kind == "proportion":
                valid &= ~data[cols].eq("").any(axis=1)
            if valid.sum() < 2:
                raise StataError("At least two complete domain observations required")
            xv = pd.DataFrame(index=data.index[valid])
            yv = pd.Series(0.0, index=xv.index)
            predicted = yv.copy()
            residual = yv.copy()
            ys = {}
            for c in cols:
                if kind == "proportion":
                    for category in sorted(data.loc[valid, c].unique()):
                        ys[f"{category}.{c}"] = (
                            data.loc[valid, c].eq(category).astype(float)
                        )
                else:
                    ys[c] = data.loc[valid, c].astype(float)
            w = weight.loc[valid]
            estimates = {}
            scores = []
            for name, y in ys.items():
                if not np.isfinite(y).all():
                    raise StataError("Nonfinite survey outcome")
                b = float((w * y).sum() / (1 if kind == "total" else w.sum()))
                estimates[name] = b
                v = pd.Series(0.0, index=data.index)
                v.loc[valid] = w * y if kind == "total" else w * (y - b) / w.sum()
                scores.append(v.to_numpy())
            params = pd.Series(estimates)
            u = np.column_stack(scores)
        fpc = data[design["fpc"]] if design.get("fpc") else None
        cov, npsu, nstrata = survey_covariance(u, psu, strata, fpc)
        cov = pd.DataFrame(cov, index=params.index, columns=params.index)
        # Ordinary WLS likelihood and information criteria are not survey statistics.
        self.model = Model(
            "svy: " + kind,
            SimpleNamespace(),
            params,
            cov,
            data.index[valid],
            yv,
            xv,
            predicted,
            residual,
            npsu - nstrata,
            "linearized",
            level,
            weight_type="pw",
            fit_extra={
                "N_psu": npsu,
                "N_strata": nstrata,
                "N_pop": float(weight.loc[valid].sum()),
            },
            metadata={"survey": True, "summary": kind != "regress"},
        )
        self.report_model()
        self.notice(
            "SVY_LINEARIZED",
            "Stratified PSU-total Taylor covariance, optional stratum-level one-stage FPC, design df=PSUs minus strata, symmetric t intervals. All design PSUs retained with zero scores outside subpopulations. No multistage design effects, replicate weights or transformed proportion intervals.",
        )
