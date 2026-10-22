# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unadjusted balanced-panel cohort-by-time DiD against never-treated units.

One 2x2 difference-in-differences per treated cohort and period, using each
cohort's last untreated period as baseline. No already-treated controls.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .syntax import StataError, options, qualifiers


class CohortDID:
    def cmd_attgt(self, args, opt):
        o = options(opt, ("cohort", "level"))
        if not self.panel or self.panel[1] is None:
            raise StataError("attgt requires xtset id time with a numeric time variable")
        if "cohort" not in o:
            raise StataError("Syntax: attgt outcome, cohort(first_treatment_period) [level(95)]")
        head, q = qualifiers(args)
        if q:
            raise StataError("attgt refuses if/in; prepare a balanced analysis dataset explicitly")
        outcome = self.varlist(head, numeric=True)
        cohort_col = self.varlist(str(o["cohort"]), numeric=True)
        if len(outcome) != 1 or len(cohort_col) != 1:
            raise StataError("attgt requires one outcome and one numeric cohort variable")
        unit, time = self.panel
        y, cohort = outcome[0], cohort_col[0]
        if len(set((unit, time, y, cohort))) < 4:
            raise StataError("Unit, time, cohort and outcome must be distinct variables")
        level = float(o.get("level", self.level))
        if not np.isfinite(level) or not 0 < level < 100:
            raise StataError("Invalid confidence level")
        frame = self.df.loc[:, [unit, time, cohort, y]].copy()
        if (frame.isna().any().any() or frame.shape[0] > 500000
                or frame.duplicated([unit, time]).any()):
            raise StataError("attgt requires unique complete unit-time observations, <=500000 rows")
        t_values = np.sort(frame[time].unique())
        t_numeric = t_values.astype(float)
        if (not np.isfinite(frame[y].to_numpy(dtype=float)).all()
                or not np.isfinite(t_numeric).all()
                or len(t_values) < 4 or len(t_values) > 40
                or not np.allclose(np.diff(t_numeric), self.time_delta, rtol=0, atol=1e-8)):
            raise StataError("attgt requires finite outcome and 4-40 gapless numeric time periods")
        cohort_numeric = frame[cohort].to_numpy(dtype=float)
        if (not np.isfinite(cohort_numeric).all()
                or not np.all(cohort_numeric == np.floor(cohort_numeric))
                or (cohort_numeric < 0).any()
                or 0 in t_numeric):
            raise StataError("Cohorts must be integer first-treatment periods, 0 for never; time cannot include 0")
        nuniq = frame.groupby(unit, sort=False)[cohort].nunique()
        if (nuniq != 1).any():
            raise StataError("First-treatment cohort must be constant within each unit")
        unit_cohort = frame.groupby(unit, sort=False)[cohort].first()
        treated_cohorts = sorted(float(v) for v in unit_cohort.unique() if v != 0)
        if len(treated_cohorts) < 2:
            raise StataError("attgt requires at least two staggered treated cohorts")
        if any(g not in t_numeric[1:] for g in treated_cohorts):
            raise StataError("Every cohort must start after the first observed period and within the panel")
        if int((unit_cohort == 0).sum()) < 5:
            raise StataError("attgt requires at least five never-treated control units")
        if any(int((unit_cohort == g).sum()) < 5 for g in treated_cohorts):
            raise StataError("Each treatment cohort needs at least five units")
        n_units = len(unit_cohort)
        if len(frame) != n_units * len(t_values):
            raise StataError("attgt requires a fully balanced unit-time panel")
        values = frame.pivot(index=unit, columns=time, values=y)
        if values.isna().any().any():
            raise StataError("attgt panel cells must be complete")
        unit_cohort = unit_cohort.reindex(values.index)
        controls = values.loc[unit_cohort == 0]
        rows = []
        for g in treated_cohorts:
            baseline = float(t_numeric[np.searchsorted(t_numeric, g) - 1])
            treated = values.loc[unit_cohort == g]
            for t in t_values:
                if float(t) == baseline:
                    continue
                dt = treated[t].to_numpy(dtype=float) - treated[baseline].to_numpy(dtype=float)
                dc = controls[t].to_numpy(dtype=float) - controls[baseline].to_numpy(dtype=float)
                effect = float(dt.mean() - dc.mean())
                variance_t = float(np.var(dt, ddof=1) / len(dt))
                variance_c = float(np.var(dc, ddof=1) / len(dc))
                v = variance_t + variance_c
                if not np.isfinite(v) or v <= 0:
                    raise StataError("ATT standard error undefined; each group needs variation in changes")
                df = float(v*v / (
                    variance_t**2 / (len(dt) - 1) + variance_c**2 / (len(dc) - 1)
                ))
                se = float(np.sqrt(v))
                critical = float(stats.t.ppf((1 + level/100)/2, df))
                rows.append({
                    "Cohort": g, "Time": float(t), "Event time": float(t-g),
                    "Period": "post" if float(t) >= g else "pre-placebo",
                    "N treated": len(dt), "N controls": len(dc),
                    "ATT": effect, "SE": se, "df": df,
                    "p": float(2 * stats.t.sf(abs(effect / se), df)),
                    "CI lower": effect - critical * se,
                    "CI upper": effect + critical * se,
                })
        table = pd.DataFrame(rows)
        if table.empty or not (table["Period"] == "post").any():
            raise StataError("No estimable post-treatment cohort-period comparisons")
        self.model = None
        self.e = {"N": len(frame), "N_units": n_units, "N_never": len(controls),
                  "N_cohorts": len(treated_cohorts)}
        self.r = {"N": len(frame), "N_cohorts": len(treated_cohorts),
                  "N_comparisons": len(table)}
        self.results_table = table
        self.results_table_title = "Unadjusted cohort-period DiD against never-treated controls"
        self.out(self.results_table_title + "\n" + table.to_string(index=False, float_format=lambda v: f"{v:.6g}"))
        self.notice(
            "ATTGT_SCOPE",
            "StatBridge extension, not a full Callaway-Sant'Anna estimator. Balanced panel, "
            "never-treated controls only, common g-1 baseline, no covariates, treatment must "
            "be absorbing and correctly coded by the first-treated cohort. Each cell is a "
            "2x2 DiD based on unit-level change scores; Welch between-unit SE and pointwise "
            "t intervals assume independent units. Pre-placebo differences are descriptive "
            "and do not prove parallel trends. No not-yet-treated controls, anticipatory "
            "effects, cohort aggregation/joint variance, clustered cross-unit shocks, "
            "bootstrap/simultaneous bands or conditional/doubly robust identification. "
            "Causal interpretation requires substantive parallel trends, no anticipation "
            "and no interference.",
        )
