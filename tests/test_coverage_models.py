# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Independent references for added estimator and survival calculations."""

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from scipy.special import expit, softmax
from statbridge.engine import Engine


def run(e, text):
    assert e.execute(text), "\n".join(x["text"] for x in e.events[-6:])


def test_newey_independent_hac_reference():
    rng = np.random.default_rng(38)
    n = 150
    x = rng.normal(size=n)
    u = rng.normal(size=n)
    for i in range(1, n):
        u[i] += 0.6 * u[i - 1]
    e = Engine()
    e.df = pd.DataFrame({"t": np.arange(n), "x": x, "y": 1 + 2 * x + u})
    run(e, "tsset t")
    run(e, "newey y x, lag(3)")
    X = np.column_stack([np.ones(n), x])
    b = np.linalg.lstsq(X, e.df.y, rcond=None)[0]
    scores = X * (e.df.y - X @ b).to_numpy()[:, None]
    meat = scores.T @ scores
    for lag in range(1, 4):
        cross = scores[lag:].T @ scores[:-lag]
        meat += (1 - lag / 4) * (cross + cross.T)
    bread = np.linalg.inv(X.T @ X)
    np.testing.assert_allclose(e.model.params, b)
    np.testing.assert_allclose(e.model.cov, bread @ meat @ bread * n / (n - 2))
    run(e, "predict double error, resid")
    np.testing.assert_allclose(e.df.error, e.df.y - X @ b)
    old = e.model
    assert not e.execute("newey y x if t!=5, lag(3)")
    assert e.model is old
    assert not e.execute("newey y x, lag(3) force")


def categorical_data():
    rng = np.random.default_rng(437)
    n = 700
    x = rng.normal(size=n)
    p = softmax(np.column_stack([np.zeros(n), 0.2 + 0.7 * x, -0.3 - 0.4 * x]), axis=1)
    e = Engine()
    e.df = pd.DataFrame({"x": x, "y": [rng.choice([2, 5, 9], p=row) for row in p]})
    return e


def test_multinomial_probability_and_base():
    e = categorical_data()
    run(e, "mlogit y x, baseoutcome(5) rrr")
    m = e.model
    assert m.metadata["categories"] == [5, 2, 9]
    assert m.params.index.tolist() == ["2:_cons", "2:x", "9:_cons", "9:x"]
    logits = np.column_stack(
        [
            np.zeros(len(e.df)),
            m.x @ np.array(m.params[:2]),
            m.x @ np.array(m.params[2:]),
        ]
    )
    np.testing.assert_allclose(m.metadata["probabilities"], softmax(logits, axis=1))
    for cat in [2, 5, 9]:
        run(e, f"predict p{cat}, pr outcome({cat})")
    np.testing.assert_allclose(e.df[["p2", "p5", "p9"]].sum(axis=1), 1)
    assert (np.linalg.eigvalsh(m.cov) > 0).all()
    run(e, "estimates store m")
    run(e, "estimates restore m")
    assert not e.execute("mlogit y x, vce(robust)")
    assert not e.execute("predict bad, outcome(7)")


@pytest.mark.parametrize("kind", ["ologit", "oprobit"])
def test_ordered_cutpoints_covariance(kind):
    e = categorical_data()
    run(e, f"{kind} y x")
    m = e.model
    cut = m.params.filter(like="/cut")
    assert np.all(np.diff(cut) > 0)
    cdf = expit if kind == "ologit" else stats.norm.cdf
    c1 = cdf(cut.iloc[0] - m.x.to_numpy() @ m.params.iloc[:1])
    c2 = cdf(cut.iloc[1] - m.x.to_numpy() @ m.params.iloc[:1])
    expected = np.column_stack([c1, c2 - c1, 1 - c2])
    np.testing.assert_allclose(m.metadata["probabilities"], expected)
    raw = np.asarray(m.result.params)
    jac = np.empty((len(raw), len(raw)))
    eps = 1e-5

    def transform(v):
        return np.r_[v[:1], m.result.model.transform_threshold_params(v)[1:-1]]

    for j in range(len(raw)):
        delta = np.zeros(len(raw))
        delta[j] = eps
        jac[:, j] = (transform(raw + delta) - transform(raw - delta)) / (2 * eps)
    np.testing.assert_allclose(
        m.cov, jac @ np.asarray(m.result.cov_params()) @ jac.T, rtol=1e-7, atol=1e-9
    )
    run(e, "predict p2, pr outcome(2)")
    np.testing.assert_allclose(e.df.p2, expected[:, 0])
    assert not e.execute("predict bad, xb")


def test_kaplan_meier_risk_sets_and_state():
    e = Engine()
    e.df = pd.DataFrame(
        {
            "t": [1, 2, 2, 3, 4, 5],
            "d": [1, 1, 0, 1, 0, 1],
            "id": range(6),
            "g": [0, 0, 1, 1, 0, 1],
        }
    )
    run(e, "stset t, failure(d) id(id)")
    run(e, "sts list")
    table = e.results_table
    np.testing.assert_allclose(table.Time, [1, 2, 3, 5])
    np.testing.assert_allclose(table["At risk"], [6, 5, 3, 1])
    np.testing.assert_allclose(table.Survival, [5 / 6, 2 / 3, 4 / 9, 0])
    np.testing.assert_allclose(
        table["Std. err."].iloc[:3],
        np.array([5 / 6, 2 / 3, 4 / 9]) * np.sqrt(np.cumsum([1 / 30, 1 / 20, 1 / 6])),
    )
    run(e, "stsum")
    assert e.r["N_fail"] == 4
    run(e, "sts graph, by(g)")
    assert e.figure is not None
    run(e, "sts test g")
    assert 0 <= e.r["p"] <= 1
    assert not e.execute("sts test g, by(id)")
    run(e, "preserve")
    run(e, "clear")
    assert not e.survival_set
    run(e, "restore")
    assert e.survival_set
    run(e, "sts list")


def test_cox_direct_risk_score_information():
    rng = np.random.default_rng(723)
    n = 500
    x = rng.normal(size=n)
    death = rng.exponential(size=n) / np.exp(0.65 * x)
    censor = rng.exponential(3, size=n)
    e = Engine()
    e.df = pd.DataFrame(
        {"x": x, "t": np.minimum(death, censor), "d": (death <= censor).astype(int)}
    )
    run(e, "stset t, failure(d)")
    run(e, "stcox x")
    m = e.model
    b = m.params.iloc[0]
    assert b == pytest.approx(0.65, abs=0.16)
    score = information = 0.0
    for i in np.flatnonzero(e.df.d):
        risk = x[e.df.t >= e.df.t[i]]
        w = np.exp(b * risk)
        mu = np.sum(w * risk) / w.sum()
        score += x[i] - mu
        information += np.sum(w * risk**2) / w.sum() - mu**2
    assert abs(score) < 1e-5
    assert m.cov.iloc[0, 0] == pytest.approx(1 / information, rel=1e-8)
    run(e, "predict hazard, hr")
    np.testing.assert_allclose(e.df.hazard, np.exp(b * x))
    run(e, "stcox x if x>-1, ties(efron) nohr")
    run(e, "predict linear, xb")
    assert e.df.loc[e.df.x <= -1, "linear"].isna().all()
    assert not e.execute("stcox x, vce(robust)")


def survey_data():
    e = Engine()
    e.df = pd.DataFrame(
        {
            "psu": [1, 1, 2, 2, 3, 3, 4, 4],
            "s": [1, 1, 1, 1, 2, 2, 2, 2],
            "w": [1.0, 2, 2, 1, 3, 1, 2, 2],
            "y": [1.0, 3, 4, 6, 8, 10, 11, 13],
            "x": [1.0, 3, 2, 5, 4, 8, 7, 9],
            "b": [0, 1, 1, 0, 1, 0, 0, 1],
            "domain": [1, 1, 0, 0, 1, 1, 0, 0],
        }
    )
    run(e, "svyset psu [pw=w], strata(s)")
    return e


def reference_covariance(scores, df):
    scores = np.asarray(scores)
    scores = scores[:, None] if scores.ndim == 1 else scores
    cov = np.zeros((scores.shape[1], scores.shape[1]))
    for stratum in [1, 2]:
        groups = [
            scores[(df.s == stratum) & (df.psu == p)].sum(axis=0)
            for p in df.loc[df.s == stratum, "psu"].unique()
        ]
        d = groups[0] - groups[1]
        cov += np.outer(d, d)
    return cov


def test_survey_mean_total_subpop():
    e = survey_data()
    df = e.df
    w = df.w
    y = df.y
    b = np.average(y, weights=w)
    run(e, "svy: mean y")
    assert e.model.params.y == pytest.approx(b)
    np.testing.assert_allclose(
        e.model.cov, reference_covariance(w * (y - b) / w.sum(), df)
    )
    assert e.model.df == 2
    assert e.e["N_psu"] == 4
    run(e, "svy: total y")
    assert e.model.params.y == pytest.approx((w * y).sum())
    np.testing.assert_allclose(e.model.cov, reference_covariance(w * y, df))
    d = df.domain.eq(1)
    b = np.average(y[d], weights=w[d])
    scores = np.where(d, w * (y - b) / w[d].sum(), 0)
    run(e, "svy, subpop(domain): mean y")
    assert e.model.params.y == pytest.approx(b)
    np.testing.assert_allclose(e.model.cov, reference_covariance(scores, df))
    assert e.e["N_psu"] == 4


def test_survey_regression_and_proportions():
    e = survey_data()
    df = e.df
    X = np.column_stack([np.ones(len(df)), df.x])
    w = df.w.to_numpy()
    y = df.y.to_numpy()
    bread = np.linalg.inv(X.T @ (w[:, None] * X))
    b = bread @ X.T @ (w * y)
    scores = (w * (y - X @ b))[:, None] * X @ bread
    run(e, "svy: regress y x")
    np.testing.assert_allclose(e.model.params, b)
    np.testing.assert_allclose(e.model.cov, reference_covariance(scores, df))
    assert "ll" not in e.e
    run(e, "predict fitted")
    np.testing.assert_allclose(e.df.fitted, X @ b)
    run(e, "svy: proportion b")
    assert e.model.params.sum() == pytest.approx(1)
    assert e.model.cov.iloc[0, 1] < 0
    assert not e.execute("predict bad")


def test_survey_failures_and_state(tmp_path):
    e = survey_data()
    e.cwd = tmp_path
    run(e, "svy: mean y")
    old = e.model
    for command in [
        "svy: logit b x",
        "svy: mean y if x>2",
        "svy: mean y, over(s)",
        "svy: mean y, level(95), bad",
        "svyset psu [aw=w]",
    ]:
        assert not e.execute(command)
        assert e.model is old
    run(e, "preserve")
    run(e, "clear")
    assert e.survey_design is None
    run(e, "restore")
    assert e.survey_design["psu"] == "psu"
    e.df["s"] = e.df.psu
    assert not e.execute("svy: mean y")
    run(e, 'export delimited using "copy.csv", replace')
    run(e, 'import delimited "copy.csv", clear')
    assert e.survey_design is None
    assert not e.survival_set
