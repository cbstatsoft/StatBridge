# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent numerical fixtures for bounded specialist roadmap additions."""
import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from statsmodels.stats.anova import AnovaRM
from statsmodels.tsa.api import VAR

from statbridge.engine import Engine
from statbridge.multiple_imputation import rubin_pool


def _engine(frame):
    engine = Engine()
    engine.df = frame.copy(deep=True)
    return engine


def test_mixed_random_intercept_matches_statsmodels_and_preserves_data():
    rng = np.random.default_rng(8301)
    n_groups, period = 22, 8
    group = np.repeat(np.arange(n_groups), period)
    x = rng.normal(size=len(group))
    u = rng.normal(scale=1.8, size=n_groups)
    y = 1.2 + 2.1*x + u[group] + rng.normal(scale=.55, size=len(group))
    frame = pd.DataFrame({"y": y, "x": x, "group": group})
    e = _engine(frame)
    assert e.execute("mixed y x, group(group)")
    pd.testing.assert_frame_equal(e.df, frame)
    m = e.model
    refx = pd.DataFrame({"_cons": 1., "x": x})
    ref = sm.MixedLM(y, refx, groups=group, exog_re=np.ones((len(y), 1))).fit(
        reml=True, method="lbfgs", maxiter=350, disp=False
    )
    np.testing.assert_allclose(m.params.to_numpy(), ref.fe_params.to_numpy(), rtol=1e-7)
    np.testing.assert_allclose(m.cov, ref.cov_params().loc[ref.fe_params.index, ref.fe_params.index], rtol=1e-7)
    assert m.fit_extra["N_groups"] == n_groups
    assert m.metadata["reml"] is True
    assert m.command == "mixed"


def test_mixed_rejects_inadequate_clusters_and_unsupported_options():
    rng = np.random.default_rng(11)
    frame = pd.DataFrame({"y": rng.normal(size=80), "x": rng.normal(size=80),
                          "g": np.repeat([0,1,2,3],20)})
    e = _engine(frame)
    assert not e.execute("mixed y x, group(g)")
    assert not e.execute("mixed y x, group(g) vce(robust)")
    assert e.model is None


def test_anovarm_matches_independent_statsmodels_fit_without_mutation():
    rng = np.random.default_rng(401)
    sid = np.repeat(np.arange(22), 3)
    period = np.tile(np.arange(3), 22)
    y = 2 + period*.35 + np.repeat(rng.normal(size=22), 3) + rng.normal(size=len(sid))
    frame = pd.DataFrame({"y": y, "person": sid, "period": period})
    e = _engine(frame)
    assert e.execute("anovarm y, subject(person) within(period)")
    ref = frame.copy()
    ref["person"] = ref.person.astype(str)
    ref["period"] = ref.period.astype(str)
    expected = AnovaRM(ref, "y", "person", within=["period"]).fit().anova_table
    np.testing.assert_allclose(e.results_table.to_numpy(), expected.to_numpy(), rtol=1e-9)
    pd.testing.assert_frame_equal(e.df, frame)
    assert e.r["subjects"] == 22


def test_anovarm_refuses_missing_subject_cells():
    rng = np.random.default_rng(404)
    frame = pd.DataFrame({"person": np.repeat(np.arange(6),3),
                          "period": np.tile(np.arange(3),6),
                          "y": rng.normal(size=18)}).iloc[:-1].copy()
    e = _engine(frame)
    assert not e.execute("anovarm y, subject(person) within(period)")


def test_var_coefficients_roots_and_forecasts_match_backend():
    rng = np.random.default_rng(202)
    data = np.zeros((140, 2))
    for i in range(1, len(data)):
        data[i] = np.array([[.65, .11], [.05, .48]]) @ data[i-1] + rng.normal(scale=.5,size=2)
    frame = pd.DataFrame({"t": np.arange(140), "a": data[:,0], "b": data[:,1]})
    e = _engine(frame)
    assert e.execute("tsset t")
    assert e.execute("var a b, lags(2)")
    ref = VAR(frame[["a", "b"]]).fit(2, trend="c")
    np.testing.assert_allclose(e.results_table.to_numpy(), ref.params.to_numpy(), rtol=1e-9)
    assert e.execute("varstable")
    assert e.r["stable"] == 1
    assert e.execute("varforecast, steps(4)")
    predicted = ref.forecast(data[-2:], 4)
    np.testing.assert_allclose(e.results_table[["a","b"]], predicted, atol=1e-9)
    np.testing.assert_allclose(e.results_table["t"], np.arange(140,144))
    pd.testing.assert_frame_equal(e.df, frame)


def test_var_refuses_gaps_missing_data_and_stale_model():
    rng = np.random.default_rng(12)
    frame = pd.DataFrame({"t": np.arange(85),
                          "a": rng.normal(size=85), "b": rng.normal(size=85)})
    e = _engine(frame)
    assert e.execute("tsset t")
    e.df.loc[7, "a"] = np.nan
    assert not e.execute("var a b, lags(1)")
    e.df.loc[7, "a"] = 1.
    assert e.execute("var a b, lags(1)")
    e.changed()
    assert not e.execute("varforecast, steps(2)")
    assert not e.execute("varstable")


def test_rubin_pool_against_explicit_between_and_within_covariance():
    coefs = [[1,2], [1.5,2.2], [2,2.4], [1.25,2.1], [1.75,2.3]]
    within = np.broadcast_to(np.diag([.16, .09]), (5,2,2)).copy()
    mu, total, degrees, r = rubin_pool(coefs, within)
    betas = np.asarray(coefs)
    assert mu == pytest.approx(betas.mean(0))
    expected = within.mean(0) + 1.2*np.cov(betas, rowvar=False, ddof=1)
    np.testing.assert_allclose(total, expected)
    assert np.all(degrees >= 4)
    assert np.all(r > 0)


def test_mi_uses_pmm_reproducibly_without_changing_original_dataset():
    rng = np.random.default_rng(5)
    x = rng.normal(size=100)
    z = rng.normal(size=100)
    y = 2 + 1.8*x - .5*z + rng.normal(scale=.7,size=100)
    frame = pd.DataFrame({"y": y, "x": x, "z": z})
    frame.loc[::6, "x"] = np.nan
    frame.loc[3::9, "z"] = np.nan
    one = _engine(frame)
    two = _engine(frame)
    cmd = "mi regress y x z, m(5) burnin(3) between(2) seed(123)"
    assert one.execute(cmd), [event["text"] for event in one.events if event["kind"]=="error"]
    assert two.execute(cmd)
    pd.testing.assert_frame_equal(one.results_table, two.results_table)
    pd.testing.assert_frame_equal(one.df, frame)
    assert one.model is None
    assert one.r["M"] == 5
    assert one.results_table["Std. err."].gt(0).all()
    assert one.results_table["df"].ge(4).all()


def test_mi_refuses_categorical_imputation_and_unsupported_syntax():
    rng = np.random.default_rng(3)
    frame = pd.DataFrame({"y": rng.normal(size=80),
                          "x": rng.normal(size=80),
                          "cat": np.repeat([0,1],40).astype(float)})
    frame.loc[5:12, "cat"] = np.nan
    e = _engine(frame)
    assert not e.execute("mi regress y cat, m(5) burnin(3)")
    assert not e.execute("mi estimate: regress y x")
    assert e.model is None
