# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cohort time DiD: independently calculated 2x2 change scores and guards."""
import numpy as np
import pandas as pd
import pytest

from statbridge.engine import Engine


def cohort_panel():
    rng = np.random.default_rng(606)
    unit_cohort = np.repeat([0, 4, 5], 18)
    unit = np.repeat(np.arange(len(unit_cohort)), 7)
    time = np.tile(np.arange(1, 8), len(unit_cohort))
    cohort = unit_cohort[unit]
    effect = (cohort == 4) * (time >= 4) * 2.0 + (cohort == 5) * (time >= 5) * 3.0
    unit_shift = np.repeat(rng.normal(size=len(unit_cohort)), 7)
    outcome = 2 + .3*time + unit_shift + effect + rng.normal(scale=.3,size=len(unit))
    return pd.DataFrame({"id": unit, "time": time, "cohort": cohort, "y": outcome})


def test_cohort_att_matches_independent_last_pre_period_differences():
    frame = cohort_panel()
    e = Engine()
    e.df = frame.copy()
    assert e.execute("xtset id time")
    assert e.execute("attgt y, cohort(cohort) level(95)"), [v["text"] for v in e.events if v["kind"] == "error"]
    table = e.results_table
    assert e.model is None
    assert set(table["Cohort"]) == {4., 5.}
    assert "pre-placebo" in table["Period"].to_numpy()
    for g,t in [(4.,6.), (5.,7.), (4.,2.)]:
        base = g - 1
        treated = frame.loc[frame.cohort == g].pivot(index="id", columns="time", values="y")
        never = frame.loc[frame.cohort == 0].pivot(index="id", columns="time", values="y")
        a = (treated[t] - treated[base]).to_numpy()
        b = (never[t] - never[base]).to_numpy()
        row = table[(table["Cohort"] == g) & (table["Time"] == t)].iloc[0]
        assert row["ATT"] == pytest.approx(a.mean()-b.mean())
        assert row["SE"]**2 == pytest.approx(a.var(ddof=1)/len(a)+b.var(ddof=1)/len(b))
    assert table[(table["Cohort"]==4.) & (table["Time"]==6.)].iloc[0]["ATT"] == pytest.approx(2.,abs=.3)
    assert table[(table["Cohort"]==5.) & (table["Time"]==7.)].iloc[0]["ATT"] == pytest.approx(3.,abs=.3)
    pd.testing.assert_frame_equal(e.df, frame)


def test_attgt_rejects_unbalanced_and_inconsistent_cohorts():
    frame = cohort_panel()
    for damaged in [
        frame.iloc[:-1],
        frame.assign(cohort=frame.cohort.mask((frame.id == 18) & (frame.time == 2), 5)),
    ]:
        e = Engine()
        e.df = damaged.copy()
        assert e.execute("xtset id time")
        assert not e.execute("attgt y, cohort(cohort)")
        assert e.model is None


def test_attgt_requires_declared_panel_and_never_controls():
    frame = cohort_panel()
    e = Engine()
    e.df = frame
    assert not e.execute("attgt y, cohort(cohort)")
    assert e.execute("xtset id time")
    e.df = frame.loc[frame.cohort != 0].copy()
    assert not e.execute("attgt y, cohort(cohort)")
