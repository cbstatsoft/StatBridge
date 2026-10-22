# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Postestimation diagnostics that leave the fitted model and dataset intact.

Influence measures apply only to conventional, unweighted ordinary least
squares. Their heuristic flags are diagnostic prompts, not hypothesis tests.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .syntax import StataError, options


class ModelDiagnostics:
    def cmd_estat(self, args, opt):
        if args.strip() != "influence":
            return super().cmd_estat(args, opt)

        o = options(opt, ("top",))
        raw = str(o.get("top", "10"))
        if not re.fullmatch(r"[1-9][0-9]*", raw):
            raise StataError("estat influence: top() must be a positive integer")
        limit = int(raw)
        if limit > 100:
            raise StataError("estat influence: top() may not exceed 100")

        m = self.require_model()
        if (
            m.command != "regress"
            or m.weight_type is not None
            or m.covariance != "ols"
        ):
            raise StataError(
                "estat influence requires conventional unweighted regress; "
                "robust, clustered, weighted and other estimators are not supported"
            )
        if m.revision != self.revision:
            raise StataError("Data changed since estimation; refit before estat influence")
        n, k = m.x.shape
        if n <= k + 1:
            raise StataError(
                "estat influence requires at least two residual degrees of freedom"
            )
        try:
            influence = m.result.get_influence()
            leverage = np.asarray(influence.hat_matrix_diag, dtype=float)
            residual = np.asarray(influence.resid_studentized_internal, dtype=float)
            cooks = np.asarray(influence.cooks_distance[0], dtype=float)
        except (AttributeError, ValueError, np.linalg.LinAlgError, ZeroDivisionError) as exc:
            raise StataError(f"Could not compute OLS influence diagnostics: {exc}") from exc
        if (
            any(len(values) != n for values in (leverage, residual, cooks))
            or not all(np.isfinite(values).all() for values in (leverage, residual, cooks))
            or np.any(leverage < -1e-9)
            or np.any(leverage >= 1)
            or np.any(cooks < -1e-9)
        ):
            raise StataError(
                "OLS influence measures are undefined or nonfinite; "
                "check residual variance, leverage and the estimation sample"
            )

        cutoff_leverage = 2 * k / n
        cutoff_cook = 4 / n
        summary = pd.DataFrame(
            {
                "Leverage": leverage,
                "Studentized resid.": residual,
                "Cook's D": cooks,
                "Leverage > 2k/N": leverage > cutoff_leverage,
                "Cook's D > 4/N": cooks > cutoff_cook,
            },
            index=m.sample,
        )
        summary.index.name = "Data index"
        # Sorting by Cook's D gives a predictable, readable table even if the
        # estimation sample differs from the original DataFrame's row order.
        shown = summary.sort_values("Cook's D", ascending=False, kind="stable").head(limit)
        values = {
            "N": n,
            "k": k,
            "N_high_leverage": int((leverage > cutoff_leverage).sum()),
            "N_large_cook": int((cooks > cutoff_cook).sum()),
            "max_cook": float(cooks.max()),
            "max_leverage": float(leverage.max()),
            "leverage_cutoff": float(cutoff_leverage),
            "cook_cutoff": float(cutoff_cook),
        }
        self.r = values
        self.results_table = shown.copy()
        self.results_table_title = "OLS influence diagnostics (largest Cook's D)"
        self.out(
            f"OLS influence diagnostics, top {len(shown)} of {n} fitted observations "
            f"(k={k} parameters)\n"
            f"Heuristic leverage threshold 2k/N={cutoff_leverage:.6g}; "
            f"Cook's D threshold 4/N={cutoff_cook:.6g}\n"
            + shown.to_string(float_format=lambda v: f"{v:.6g}")
        )
        self.notice(
            "OLS_INFLUENCE",
            "Influence is computed on the estimation sample with the ordinary OLS "
            "variance, not robust or cluster-adjusted inference. The displayed "
            "row labels are DataFrame index values, not necessarily Stata row "
            "numbers. Thresholds 2k/N and 4/N are exploratory heuristics, not "
            "significance tests. No observations are removed.",
        )
