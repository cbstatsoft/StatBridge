# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
import numpy as np
import pandas as pd
import pytest
from scipy import stats
from statbridge.engine import Engine


def run(e, text):
    assert e.execute(text), "\n".join(x["text"] for x in e.events[-6:])


@pytest.fixture
def data():
    e = Engine()
    e.df = pd.DataFrame(
        {
            "y": [1.0, 3, 4, 8, 9, 11],
            "z": [2.0, 5, 2, 6, 8, 10],
            "g": [1, 1, 1, 2, 2, 2],
            "b": [0, 1, 0, 1, 1, 1],
        }
    )
    return e


def test_descriptive_joint_covariance(data):
    e = data
    run(e, "mean y z")
    np.testing.assert_allclose(e.model.params, e.df[["y", "z"]].mean())
    np.testing.assert_allclose(e.model.cov, e.df[["y", "z"]].cov() / 6)
    run(e, "lincom y-z")
    assert e.r["estimate"] == pytest.approx((e.df.y - e.df.z).mean())
    assert not e.execute("predict bad")
    run(e, "total y z")
    np.testing.assert_allclose(e.model.params, e.df[["y", "z"]].sum())
    np.testing.assert_allclose(e.model.cov, e.df[["y", "z"]].cov() * 6)
    run(e, "proportion g")
    assert e.model.params.sum() == pytest.approx(1)
    assert e.model.cov.iloc[0, 1] < 0
    run(e, "mean y, over(g)")
    np.testing.assert_allclose(e.model.params, [8 / 3, 28 / 3])
    assert e.model.cov.iloc[0, 1] == 0


def test_intervals_tests_graphs(data):
    e = data
    run(e, "ci means y, level(90)")
    assert e.r["lb"] == pytest.approx(
        e.df.y.mean() - stats.t.ppf(0.95, 5) * e.df.y.sem()
    )
    run(e, "ci proportions b")
    assert e.r["lb"] == pytest.approx(stats.beta.ppf(0.025, 4, 3))
    assert e.r["ub"] == pytest.approx(stats.beta.ppf(0.975, 5, 2))
    run(e, "ci proportions b, wilson")
    assert 0 < e.r["lb"] < e.r["ub"] < 1
    run(e, "prtest b = .5")
    assert e.r["z"] == pytest.approx((4 / 6 - 0.5) / np.sqrt(0.25 / 6))
    run(e, "prtest b, by(g)")
    assert e.r["difference"] == pytest.approx(-2 / 3)
    run(e, "kwallis y, by(g)")
    assert e.r["chi2"] == pytest.approx(stats.kruskal(e.df.y[:3], e.df.y[3:]).statistic)
    run(e, "sdtest y = z")
    assert e.r["F"] == pytest.approx(e.df.y.var() / e.df.z.var())
    run(e, "inspect")
    assert e.results_table.iloc[0].Distinct == 6
    run(e, "compare y z")
    assert e.r["different"] == 6
    run(e, "tab1 g b")
    run(e, "tab2 g b, row chi2")
    run(e, "graph box y, over(g)")
    assert e.figure is not None
    run(e, "graph bar (mean) y, over(g)")
    assert [p.get_height() for p in e.figure.axes[0].patches] == pytest.approx(
        [8 / 3, 28 / 3]
    )


def test_panel_and_grouped_interpolation(data):
    e = data
    e.df = pd.DataFrame(
        {
            "id": [1, 1, 1, 2, 2, 2],
            "t": [1.0, 2, 3, 1, 2, 3],
            "y": [2.0, np.nan, 6, 20, np.nan, 60],
            "text": ["x"] * 6,
        }
    )
    run(e, "bysort id (t): ipolate y t, generate(filled)")
    assert e.df.filled.tolist() == [2, 4, 6, 20, 40, 60]
    run(e, "xtset id t")
    run(e, "xtdescribe")
    assert e.r["n"] == 2
    run(e, "xtsum")
    assert "text" not in e.results_table.Variable.tolist()
    assert set(e.results_table.Variation) == {"overall", "between", "within"}
    run(e, "drop if t==2 | (id==2 & t==1)")
    run(e, "tsfill, full")
    assert len(e.df) == 6
    assert e.df.y.isna().sum() == 3


def test_fillin_epolate_and_rejected_changes(data):
    e = data
    e.df = pd.DataFrame(
        {"a": [1, 1, 2], "b": [1, 2, 1], "_merge": [7, 7, 7], "x": [5.0, 6, 7]}
    )
    run(e, "fillin a b")
    assert len(e.df) == 4
    assert e.df._fillin.sum() == 1
    assert pd.isna(e.df.loc[e.df._fillin.eq(1), "x"].iloc[0])
    assert "_merge" in e.df
    e.df = pd.DataFrame({"x": [0.0, 1, 2, 3], "y": [np.nan, 3, 5, np.nan]})
    run(e, "ipolate y x, generate(z) epolate")
    assert e.df.z.tolist() == [1, 3, 5, 7]
    before = e.df.copy()
    for text in [
        "ci means y, wilson",
        "ipolate y x, generate(z)",
        "mean y, unsupported",
        "tsfill",
    ]:
        assert not e.execute(text)
        pd.testing.assert_frame_equal(e.df, before)


def test_logical_numeric_arithmetic(data):
    e = data
    run(e, "generate rating = (y>3)+(y>8)")
    assert e.df.rating.tolist() == [0, 0, 1, 1, 2, 2]
    run(e, "generate delta = (y>3)-(y>8)")
    assert e.df.delta.tolist() == [0, 0, 1, 1, 0, 0]
    run(e, "generate negative = -(y>3)")
    assert e.df.negative.tolist() == [0, 0, -1, -1, -1, -1]


def test_coverage_report(data):
    from statbridge.catalog import COMMANDS

    run(data, "coverage")
    assert len(COMMANDS) == 154
    assert len(data.results_table) == 10
    assert any("not a measured percentage" in x["text"] for x in data.events)
