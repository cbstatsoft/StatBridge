# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
import json
import numpy as np
import pandas as pd
import pytest
from scipy import stats
import pyreadstat
from statbridge.engine import Engine
from statbridge.syntax import StataError, logical_lines


@pytest.fixture
def e(tmp_path):
    return Engine(cwd=tmp_path)


def ok(e, source):
    assert e.run(source), "\n".join(v["text"] for v in e.events if v["kind"] == "error")


def sample(e):
    rng = np.random.default_rng(934)
    x = rng.normal(size=160)
    z = rng.normal(size=160)
    e.df = pd.DataFrame(
        {
            "y": 1.2 + 2.3 * x - 0.7 * z + rng.normal(size=160),
            "x": x,
            "z": z,
            "id": np.repeat(np.arange(40), 4),
            "t": np.tile(np.arange(4), 40),
        }
    )


def test_expressions_missing_precedence_and_restricted_evaluation(e):
    e.df = pd.DataFrame({"x": [1.0, np.nan, 7.0], "y": [3.0, 4.0, 5.0]})
    np.testing.assert_array_equal(e.expr("x > 5"), [False, True, True])
    np.testing.assert_array_equal(e.expr("x < . & x > 5"), [False, False, True])
    np.testing.assert_array_equal(e.expr("missing(x)"), [False, True, False])
    assert e.expr("-2^2") == -4
    assert e.expr("2^3^2") == 512
    np.testing.assert_allclose(e.expr("x[_n-1]"), [np.nan, 1, np.nan], equal_nan=True)
    np.testing.assert_allclose(e.expr("cond(missing(x), 0, x*2)"), [2, 0, 14])
    for text in ['__import__("os")', "x.__class__", 'open("secret")']:
        with pytest.raises(StataError):
            e.expr(text)


def test_do_comments_loops_macros_and_capture(e):
    source = """* Comment
clear
set obs 5
local prefix "v"
forvalues i = 1/3 {
    generate `prefix'`i' = _n * `i' ///
        + 1
}
/* across
lines */
foreach x of varlist v1-v3 {
    replace `x' = `x' + 1 if _n > 2
}
local mean = 5+2
generate x = `mean'
capture nonsense
assert _rc == 199
summarize x, meanonly
assert r(mean) == 7
"""
    ok(e, source)
    np.testing.assert_allclose(e.df.v2, [3, 5, 8, 10, 12])
    assert not e.run("generate before = 1\nunknowncommand\ngenerate after = 1")
    assert "before" in e.df and "after" not in e.df


def test_unknown_options_are_errors_and_no_mutation(e):
    sample(e)
    before = e.df.copy()
    assert not e.execute("drop x, nonsense")
    pd.testing.assert_frame_equal(e.df, before)
    assert not e.execute("regress y x [pw=z]")
    assert not e.execute("regress y x, vce(hc5)")


def test_ols_against_closed_form_and_hc1(e):
    sample(e)
    e.df.loc[0, "z"] = np.nan
    ok(e, "regress y x z")
    df = e.df.dropna()
    x = np.column_stack([np.ones(len(df)), df.x, df.z])
    y = df.y.to_numpy()
    b = np.linalg.solve(x.T @ x, x.T @ y)
    resid = y - x @ b
    cov = np.linalg.inv(x.T @ x) * (resid @ resid) / (len(y) - 3)
    np.testing.assert_allclose(e.model.params, b, rtol=1e-12)
    np.testing.assert_allclose(e.model.cov, cov, rtol=1e-12)
    ok(e, "regress y x z, robust")
    bread = np.linalg.inv(x.T @ x)
    expected = bread @ (x.T @ (x * resid[:, None] ** 2)) @ bread * len(y) / (len(y) - 3)
    np.testing.assert_allclose(e.model.cov, expected, rtol=1e-12)
    ok(e, "test x z\nlincom x - z\npredict fitted\npredict residual, residuals")
    np.testing.assert_allclose(
        e.df.fitted.iloc[1:] + e.df.residual.iloc[1:], e.df.y.iloc[1:]
    )
    assert np.isnan(e.df.fitted.iloc[0])


def test_cluster_covariance_against_independent_formula(e):
    sample(e)
    ok(e, "regress y x z, vce(cluster id)")
    x = e.model.x.to_numpy()
    resid = e.model.residual.to_numpy()
    bread = np.linalg.inv(x.T @ x)
    meat = np.zeros((3, 3))
    for group in e.df.id.unique():
        idx = e.df.id == group
        score = x[idx].T @ resid[idx]
        meat += np.outer(score, score)
    n, k = x.shape
    g = e.df.id.nunique()
    expected = bread @ meat @ bread * (g / (g - 1)) * ((n - 1) / (n - k))
    np.testing.assert_allclose(e.model.cov, expected, rtol=1e-12)
    assert e.model.df == g - 1


def test_fe_against_demeaned_least_squares(e):
    sample(e)
    ok(e, "xtset id t\nxtreg y x z, fe")
    df = e.df[["y", "x", "z"]]
    dm = df - e.df.groupby("id")[["y", "x", "z"]].transform("mean")
    b = np.linalg.lstsq(dm[["x", "z"]].to_numpy(), dm.y.to_numpy(), rcond=None)[0]
    np.testing.assert_allclose(e.model.params[["x", "z"]], b, rtol=1e-10)
    ok(
        e,
        "estimates store fixed\nxtreg y x z, re\nestimates store random\nestimates table fixed random",
    )
    assert any(n["code"] == "PANEL" for n in e.notices)


def test_lag_respects_gaps_and_entities(e):
    e.df = pd.DataFrame(
        {
            "id": [1, 1, 1, 2, 2],
            "t": [1, 2, 4, 1, 2],
            "x": [10.0, 20.0, 40.0, 100.0, 200.0],
        }
    )
    ok(e, "xtset id t")
    x = e.regressors(["L.x"], e.df)
    np.testing.assert_allclose(
        x["L.x"], [np.nan, 10, np.nan, np.nan, 100], equal_nan=True
    )


def test_factor_interactions(e):
    sample(e)
    e.df["g"] = np.tile([0.0, 1.0], 80)
    ok(e, "regress y c.x##i.g z")
    assert list(e.model.params.index) == ["_cons", "x", "1.g", "x#1.g", "z"]
    expected = np.column_stack([np.ones(160), e.df.x, e.df.g, e.df.x * e.df.g, e.df.z])
    np.testing.assert_allclose(e.model.x, expected)


def test_dta_roundtrip_labels_numeric_dates_and_unicode(e, tmp_path):
    e.df = pd.DataFrame(
        {
            "x": [1.0, 2.0, np.nan],
            "name": ["Café", "東京", ""],
            "day": [0.0, 1.0, 20000.0],
        }
    )
    e.labels = {"x": "Measurement", "name": "Place"}
    e.value_labels = {"x": {1: "one", 2: "two"}}
    e.formats = {"day": "%td"}
    ok(e, 'save "with space.dta"\nclear\nuse "with space.dta"')
    assert e.labels["x"] == "Measurement"
    assert e.value_labels["x"][1] == "one"
    assert e.df.name.iloc[1] == "東京"
    np.testing.assert_allclose(e.df.day, [0, 1, 20000])
    assert e.formats["day"] == "%td"
    assert not e.execute('save "with space.dta"')


def test_extended_missing_warns(e, tmp_path):
    path = tmp_path / "missing.dta"
    pyreadstat.write_dta(
        pd.DataFrame({"x": [1.0, "a", 2.0]}), path, missing_user_values={"x": ["a"]}
    )
    ok(e, 'use "missing.dta"')
    assert e.df.x.isna().sum() == 1
    assert any(n["code"] == "DTA_MISSING" for n in e.notices)


def test_merge_append_reshape_and_preserve(e, tmp_path):
    e.df = pd.DataFrame({"id": [1.0, 2.0], "x": [10.0, 20.0]})
    ok(e, 'save "using.dta"')
    e.df = pd.DataFrame({"id": [2.0, 3.0], "y": [8.0, 9.0]})
    ok(e, 'merge 1:1 id using "using.dta"')
    assert dict(zip(e.df.id, e.df._merge)) == {1: 2, 2: 3, 3: 1}
    ok(e, "preserve\nkeep if _merge == 3\nrestore")
    assert len(e.df) == 3
    e.df = pd.DataFrame({"id": [1.0, 2.0], "x1": [1.0, 2.0], "x2": [3.0, 4.0]})
    ok(e, "reshape long x, i(id) j(t)")
    assert len(e.df) == 4
    ok(e, "reshape wide x, i(id) j(t)")
    assert list(e.df.columns) == ["id", "x1", "x2"]


def test_grouped_generate_and_egen(e):
    e.df = pd.DataFrame({"id": [2, 1, 1, 2], "x": [8.0, 2.0, 4.0, 6.0]})
    ok(e, "bysort id: generate n = _n\negen average = mean(x), by(id)")
    assert list(e.df.n) == [1, 2, 1, 2]
    assert list(e.df.average) == [3, 3, 7, 7]


def test_summary_percentiles_match_stata_definition(e):
    e.df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
    ok(e, "summarize x, detail")
    assert e.r["p25"] == 1.5
    assert e.r["p50"] == 2.5
    assert e.r["sd"] == pytest.approx(np.sqrt(5 / 3))
    ok(e, "ttest x == 0")
    assert e.r["t"] == pytest.approx(stats.ttest_1samp(e.df.x, 0).statistic)


def test_binary_count_iv_quantile_and_glm_smoke(e):
    sample(e)
    rng = np.random.default_rng(124)
    e.df["binary"] = rng.binomial(1, 1 / (1 + np.exp(-e.df.x)))
    e.df["count"] = rng.poisson(np.exp(0.2 + 0.3 * e.df.x))
    for cmd in [
        "logit binary x z",
        "logistic binary x z",
        "probit binary x z",
        "poisson count x z",
        "nbreg count x z",
        "qreg y x z",
        "glm binary x z, family(binomial) link(logit)",
        "ivregress 2sls y z (x = t)",
    ]:
        ok(e, cmd)
        assert np.isfinite(e.model.params).all()


def test_bootstrap_is_reproducible_restores_data(e):
    sample(e)
    original = e.df.copy()
    ok(e, "bootstrap _b[x], reps(20) seed(121): regress y x z")
    result = e.r.copy()
    pd.testing.assert_frame_equal(original, e.df)
    ok(e, "bootstrap _b[x], reps(20) seed(121): regress y x z")
    assert e.r == result
    assert e.r["reps"] == 20
    assert e.r["se"] > 0


def test_export_graph_and_audit(e, tmp_path):
    sample(e)
    ok(
        e,
        'scatter y x, title("Example")\ngraph export "plot.png"\ncompatibility export "audit.json"',
    )
    assert (tmp_path / "plot.png").stat().st_size > 1000
    report = json.loads((tmp_path / "audit.json").read_text())
    assert report["versions"]["statsmodels"]


def test_completion():
    from statbridge.completion import Suggestions

    c = Suggestions()
    c.variables = ["income", "industry"]
    c.history = ["regress income industry, robust"]
    assert c.candidates("reg")[0] == "regress income industry, robust"
    assert "summarize income" in c.candidates("summarize inc")


def test_malformed_flag_and_valued_options_rejected(e):
    sample(e)
    for cmd in [
        "regress y x, robust(foo)",
        "regress y x, level",
        "regress y x, level(0)",
        "regress y x, noconstant(1)",
        "xtreg y x, fe(no)",
    ]:
        assert not e.execute(cmd), cmd


def test_saved_model_prediction_rejected_after_regressor_changes(e):
    sample(e)
    ok(
        e,
        "regress y x z\nestimates store saved\nreplace x = x*10\nestimates restore saved",
    )
    assert not e.execute("predict stale")
    assert "stale" not in e.df


def test_boolean_generate_keeps_numeric_storage(e):
    ok(e, "set obs 10\ngenerate treated = _n > 5")
    assert pd.api.types.is_numeric_dtype(e.df.treated)
    assert e.df.treated.sum() == 5


def test_time_series_arima_and_unit_lags(e):
    rng = np.random.default_rng(351)
    n = 150
    e.df = pd.DataFrame({"t": np.arange(n), "y": rng.normal(size=n).cumsum()})
    ok(e, "tsset t\ndfuller y, lags(1)\narima y, arima(1,1,0)")
    assert e.model.command == "arima"
    assert np.isfinite(e.model.params).all()
    lag = e.regressors(["L.y"], e.df)["L.y"]
    np.testing.assert_allclose(lag.iloc[1:], e.df.y.iloc[:-1])
    assert not e.execute("predict broken, xb")


def test_constant_factor_still_excludes_missing_observations(e):
    sample(e)
    e.df["group"] = 1.0
    e.df.loc[:4, "group"] = np.nan
    ok(e, "regress y x i.group")
    assert len(e.model.sample) == 155


def test_collapse_encoding_append_and_log(e, tmp_path):
    e.df = pd.DataFrame(
        {
            "group": [1.0, 1.0, 2.0, 2.0],
            "text": ["rural", "urban", "rural", ""],
            "x": [1.0, 3.0, 5.0, 7.0],
        }
    )
    ok(
        e,
        'encode text, generate(code)\ndecode code, generate(decoded)\nsave "part.dta"',
    )
    assert list(e.df.decoded) == list(e.df.text)
    ok(e, 'append using "part.dta"')
    assert len(e.df) == 8
    ok(
        e,
        'log using "analysis.log", text\ncollapse (mean) x (sum) total=x, by(group)\nlog close',
    )
    assert list(e.df.x) == [2, 6]
    assert list(e.df.total) == [8, 24]
    assert "collapse" in (tmp_path / "analysis.log").read_text()


def test_hausman_covariance_difference_and_rejection(e):
    from statbridge.models import Model
    import types

    ix = pd.Index(range(4))
    params = pd.Index(["_cons", "x", "z"])

    def model(b, cov):
        return Model(
            "xtreg",
            types.SimpleNamespace(),
            pd.Series(b, index=params),
            pd.DataFrame(cov, index=params, columns=params),
            ix,
            pd.Series([1.0, 2.0, 3.0, 4.0], name="y"),
            pd.DataFrame(),
            pd.Series(),
            pd.Series(),
            10,
            "ols",
            95,
        )

    e.stored["a"] = model([1.0, 2.0, 3.0], np.diag([2.0, 0.2, 0.3]))
    e.stored["b"] = model([1.0, 1.8, 2.7], np.diag([1.0, 0.1, 0.1]))
    ok(e, "hausman a b")
    assert e.r["chi2"] == pytest.approx(0.2**2 / 0.1 + 0.3**2 / 0.2)
    e.stored["b"].covariance = "robust"
    assert not e.execute("hausman a b")


def test_seed_sample_selection_reproducibility(e):
    e.df = pd.DataFrame({"x": np.arange(100.0)})
    source = e.df.copy()
    ok(e, "set seed 7\nsample 10, count")
    chosen = e.df.copy()
    e.df = source
    ok(e, "set seed 7\nsample 10, count")
    pd.testing.assert_frame_equal(chosen, e.df)
    assert e.df.x.is_unique


def test_stats_suite_and_pca(e):
    sample(e)
    e.df["g"] = (e.df.x > 0).astype(float)
    for cmd in [
        "correlate y x z",
        "pwcorr y x, sig obs",
        "tabulate g t, chi2 row col",
        "ttest y, by(g) unequal",
        "ranksum y, by(g)",
        "signrank y = x",
        "swilk y",
        "pca y x z, components(2)",
    ]:
        ok(e, cmd)


def test_literal_windows_paths_and_comment_markers(e):
    from statbridge.syntax import words, unquote

    path = '"C:\\Users\\Example User\\data.dta"'
    assert unquote(words(path)[0]) == "C:\\Users\\Example User\\data.dta"
    assert list(
        logical_lines('display "https://example.org/*literal*/" // real comment')
    ) == [(1, 'display "https://example.org/*literal*/"')]


def test_nested_do_file_errors_and_local_scope(e, tmp_path):
    (tmp_path / "inner.do").write_text('local name "inner"\ngenerate z = 1\n')
    ok(e, 'set obs 3\nlocal name "outer"\ndo "inner.do"')
    assert e.locals["name"] == "outer"
    assert "z" in e.df
    (tmp_path / "bad.do").write_text("bad_command\ngenerate should_not_exist = 1")
    assert not e.run('do "bad.do"\ngenerate should_not_exist2 = 1')
    assert "should_not_exist" not in e.df and "should_not_exist2" not in e.df


def test_poisson_exposure_prediction_and_nbreg_irr(e):
    sample(e)
    rng = np.random.default_rng(700)
    e.df["exposure"] = rng.uniform(1, 3, len(e.df))
    mean = e.df.exposure * np.exp(0.2 + 0.3 * e.df.x)
    e.df["count"] = rng.negative_binomial(2, 2 / (2 + mean))
    ok(e, "poisson count x, exposure(exposure)\npredict linear, xb\npredict mean_count")
    np.testing.assert_allclose(np.exp(e.df.linear), e.df.mean_count, rtol=1e-10)
    ok(e, "nbreg count x, irr")
    table = [ev["payload"]["table"] for ev in e.events if ev["kind"] == "model"][-1]
    assert table.loc["alpha", "Ratio / alpha"] == pytest.approx(e.model.params["alpha"])
