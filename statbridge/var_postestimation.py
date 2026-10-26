# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Point impulse responses and forecast error variance shares for stable VAR.

Orthogonal shocks use the lower-triangular Cholesky of the fitted innovations
covariance. This is ordering-dependent descriptive VAR analysis, not a
structurally identified model or an inference procedure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .syntax import StataError, options
from .specialist_models import _positive_integer


class VarPostEstimation:
    def _var_dynamics(self, args, opt, command):
        if args.strip():
            raise StataError(f"Syntax: {command}, steps(8)")
        o = options(opt, ("steps",))
        steps = _positive_integer(o.get("steps", 8), "steps", 1, 24)
        state = self._require_var()
        fit = state["fit"]
        if not fit.is_stable():
            raise StataError(f"{command} requires a stable VAR; inspect varstable")
        try:
            covariance = np.asarray(fit.sigma_u, dtype=float)
            cholesky = np.linalg.cholesky(covariance)
            ma = np.asarray(fit.ma_rep(maxn=steps), dtype=float)
            response = ma @ cholesky
        except (ValueError, np.linalg.LinAlgError, ZeroDivisionError) as exc:
            raise StataError(
                f"{command}: innovations covariance must be positive definite: {exc}"
            ) from exc
        k = len(state["names"])
        if (ma.shape != (steps + 1, k, k)
                or not np.isfinite(response).all()
                or not np.isfinite(covariance).all()):
            raise StataError(f"{command}: undefined VAR response")
        return state["names"], steps, response

    def cmd_varirf(self, args, opt):
        names, steps, response = self._var_dynamics(args, opt, "varirf")
        rows = [
            {"Horizon": h, "Response": names[i], "Shock": names[j],
             "Orthogonal IRF": float(response[h, i, j])}
            for h in range(steps + 1)
            for i in range(len(names)) for j in range(len(names))
        ]
        self.r = {"horizon": steps, "equations": len(names)}
        self.results_table = pd.DataFrame(rows)
        self.results_table_title = "Cholesky-orthogonalized VAR impulse responses"
        self.out(
            self.results_table_title + "\n"
            + self.results_table.to_string(index=False, float_format=lambda x: f"{x:.6g}")
        )
        self.notice(
            "VAR_IRF_SCOPE",
            "Descriptive Cholesky orthogonalized impulse responses, shocks ordered exactly "
            "as the fitted VAR variables. Orthogonal shocks are one innovation SD in the "
            "recursive ordering; the representation depends on variable order and is not "
            "structural causal identification. No intervals, bootstrap, generalized IRFs "
            "or parameter/identification uncertainty. Data and fitted coefficients unchanged.",
        )

    def cmd_varfevd(self, args, opt):
        names, steps, response = self._var_dynamics(args, opt, "varfevd")
        sq = response[:steps] ** 2
        cum = np.cumsum(sq, axis=0)
        denominators = cum.sum(axis=2, keepdims=True)
        if (np.any(denominators <= 0) or not np.isfinite(denominators).all()):
            raise StataError("varfevd: nonpositive forecast-error variance")
        shares = cum / denominators
        rows = [
            {"Horizon": h + 1, "Response": names[i], "Shock": names[j],
             "Variance share": float(shares[h, i, j])}
            for h in range(steps)
            for i in range(len(names)) for j in range(len(names))
        ]
        self.r = {"horizon": steps, "equations": len(names)}
        self.results_table = pd.DataFrame(rows)
        self.results_table_title = "Orthogonalized VAR forecast-error variance shares"
        self.out(
            self.results_table_title + "\n"
            + self.results_table.to_string(index=False, float_format=lambda x: f"{x:.6g}")
        )
        self.notice(
            "VAR_FEVD_SCOPE",
            "Forecast error shares sum to one for each response and horizon. They use "
            "the Cholesky ordering and fitted point coefficients only. Not causal variance "
            "decomposition, no confidence intervals, no generalized or structural shocks.",
        )
