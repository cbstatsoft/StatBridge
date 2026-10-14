# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from statbridge.engine import Engine
from statbridge.syntax import logical_lines, options


@pytest.fixture
def e(tmp_path):
    return Engine(cwd=tmp_path)


def ok(e, text):
    assert e.run(text), "\n".join(x["text"] for x in e.events if x["kind"] == "error")


def fixture(e):
    rng = np.random.default_rng(127)
    x = rng.normal(size=35)
    z = rng.normal(size=35)
    e.df = pd.DataFrame(
        {
            "y": 2 + 1.7 * x + 0.3 * z + rng.normal(size=35),
            "x": x,
            "z": z,
            "w": rng.integers(1, 6, 35),
            "g": np.repeat(np.arange(7), 5),
        }
    )


@pytest.mark.parametrize("option", ["", "robust", "vce(cluster g)"])
def test_frequency_weights_match_expanded_ols(e, option):
    fixture(e)
    expanded = e.df.loc[e.df.index.repeat(e.df.w)].reset_index(drop=True)
    x = sm.add_constant(expanded[["x", "z"]])
    kw = {}
    if option == "robust":
        kw = {"cov_type": "HC1"}
    elif option:
        kw = {
            "cov_type": "cluster",
            "cov_kwds": {"groups": expanded.g, "use_correction": True},
        }
    reference = sm.OLS(expanded.y, x).fit(**kw)
    ok(e, "regress y x z [fw=w]" + (", " + option if option else ""))
    np.testing.assert_allclose(e.model.params, reference.params, rtol=1e-12)
    np.testing.assert_allclose(e.model.cov, reference.cov_params(), rtol=1e-12)
    assert e.e["N"] == len(expanded)
    assert e.e["N_rows"] == 35
    ok(
        e,
        "predict fit\nscalar slope = _b[x]\nscalar error = _se[x]\ntest x z\nlincom x-z",
    )
    np.testing.assert_allclose(e.df.fit, e.model.x @ e.model.params)


@pytest.mark.parametrize("option", ["", "robust", "vce(cluster g)"])
def test_analytic_weight_normalisation_and_covariance(e, option):
    fixture(e)
    e.df.w = e.df.w / 3 + 0.2
    x = np.column_stack([np.ones(len(e.df)), e.df.x, e.df.z])
    w = e.df.w.to_numpy()
    y = e.df.y.to_numpy()
    b = np.linalg.solve(x.T @ (w[:, None] * x), x.T @ (w * y))
    residual = y - x @ b
    bread = np.linalg.inv(x.T @ (w[:, None] * x))
    if option == "robust":
        cov = bread @ (x.T @ ((w * residual)[:, None] ** 2 * x)) @ bread * 35 / 32
    elif option:
        scores = np.asarray(
            [
                x[e.df.g == g].T @ (w[e.df.g == g] * residual[e.df.g == g])
                for g in range(7)
            ]
        )
        cov = bread @ (scores.T @ scores) @ bread * (7 / 6) * (34 / 32)
    else:
        cov = bread * np.sum(w * residual**2) / 32
    command = "regress y x z [aw=w]" + (", " + option if option else "")
    ok(e, command)
    np.testing.assert_allclose(e.model.params, b, rtol=1e-12)
    np.testing.assert_allclose(e.model.cov, cov, rtol=1e-12)
    first = e.model.cov.copy()
    e.df.w *= 1000
    ok(e, command)
    np.testing.assert_allclose(e.model.cov, first, rtol=1e-11)


def test_probability_weights_default_to_sandwich(e):
    fixture(e)
    ok(e, "regress y x z [pw=w]")
    first = e.model.cov.copy()
    ok(e, "regress y x z [aw=w], robust")
    np.testing.assert_allclose(e.model.cov, first)
    assert not e.execute("regress y x [pw=w], vce(ols)")


def test_weight_validation_and_sample_selection(e):
    fixture(e)
    e.df.loc[0, "w"] = 0
    e.df.loc[1, "w"] = np.nan
    e.df.loc[2, "x"] = np.nan
    ok(e, "regress y x z if g < 5 [fw=w]")
    assert not set([0, 1, 2]) & set(e.model.sample)
    ok(e, "generate fitted_sample = e(sample)")
    assert e.df.fitted_sample.sum() == 22
    assert not e.execute("display e(sample)")  # generation invalidates prior sample
    e.df.loc[10, "w"] = -1
    assert not e.execute("regress y x [aw=w]")
    e.df.loc[10, "w"] = 1.5
    assert not e.execute("regress y x [fw=w]")
    assert not e.execute("logit y x [aw=w]")
    assert not e.execute("bootstrap _b[x], reps(4): regress y x [fw=w]")


def test_frequency_summary_detail_matches_replication(e):
    e.df = pd.DataFrame({"x": [1.0, 2.0, 9.0, 11.0], "w": [2.0, 1.0, 4.0, 1.0]})
    expanded = np.repeat(e.df.x, e.df.w.astype(int))
    ok(e, "summarize x [fw=w], detail")
    assert e.r["N"] == len(expanded)
    assert e.r["mean"] == pytest.approx(np.mean(expanded))
    assert e.r["Var"] == pytest.approx(np.var(expanded, ddof=1))
    for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
        assert e.r[f"p{p}"] == np.percentile(
            expanded, p, method="averaged_inverted_cdf"
        )
    ok(e, "summarize x [aw=w]")
    assert e.r["Var"] == pytest.approx(
        np.average((e.df.x - np.average(e.df.x, weights=e.df.w)) ** 2, weights=e.df.w)
        * 4
        / 3
    )
    assert not e.execute("summarize x [aw=w], detail")


def test_time_operators_differences_seasonal_composition_and_gaps(e):
    e.df = pd.DataFrame(
        {
            "id": [1] * 5 + [2] * 4,
            "t": [0, 2, 4, 6, 10, 0, 2, 4, 6],
            "x": [0.0, 1.0, 4.0, 9.0, 25.0, 100.0, 101.0, 104.0, 109.0],
        }
    )
    ok(
        e,
        "xtset id t, delta(2)\ngenerate d2 = D2.x\ngenerate seasonal = S2.x\ngenerate lead = f.x\ngenerate combined = LD.x",
    )
    np.testing.assert_allclose(
        e.df.d2, [np.nan, np.nan, 2, 2, np.nan, np.nan, np.nan, 2, 2], equal_nan=True
    )
    np.testing.assert_allclose(
        e.df.seasonal, [np.nan, np.nan, 4, 8, 16, np.nan, np.nan, 4, 8], equal_nan=True
    )
    np.testing.assert_allclose(
        e.df.combined,
        [np.nan, np.nan, 1, 3, np.nan, np.nan, np.nan, 1, 3],
        equal_nan=True,
    )
    np.testing.assert_allclose(e.expr("LF.x"), e.df.x)
    assert np.isnan(e.df.lead.iloc[3])


def test_transformed_response_predictions_and_hc2_hc3(e):
    fixture(e)
    e.df["t"] = np.arange(len(e.df))
    ok(
        e,
        "tsset t\nregress D.y L.x z, vce(hc2)\npredict expected\npredict residual, residuals",
    )
    np.testing.assert_allclose(
        e.df.expected.iloc[1:] + e.df.residual.iloc[1:], np.diff(e.df.y)
    )
    ref = sm.OLS(
        np.diff(e.df.y),
        np.column_stack([np.ones(34), e.df.x.iloc[:-1], e.df.z.iloc[1:]]),
    ).fit(cov_type="HC2")
    np.testing.assert_allclose(e.model.cov, ref.cov_params())
    ok(e, "regress y x z, vce(hc3)")
    ref = sm.OLS(e.df.y, sm.add_constant(e.df[["x", "z"]])).fit(cov_type="HC3")
    np.testing.assert_allclose(e.model.cov, ref.cov_params())


def test_invalidated_time_index_is_rejected(e):
    e.df = pd.DataFrame({"t": [1.0, 2.0, 3.0], "x": [1.0, 4.0, 9.0]})
    ok(e, "tsset t\nreplace t = 1 in 2")
    assert not e.execute("generate bad = L.x")
    assert "bad" not in e.df


def test_semicolon_and_block_comments_preserve_strings_and_lines(e):
    source = """#delimit ;
clear; set obs 4;
generate x =
 _n /* inline block
 nested /* block */ end */ * 2;
local url "https://example.org/a;b";
#delimit cr
assert x[4] == 8
"""
    ok(e, source)
    assert e.locals["url"] == "https://example.org/a;b"
    lines = list(logical_lines("display 1 /* across\nline */ + 2"))
    assert len(lines) == 1 and lines[0][0] == 1
    assert lines[0][1].split() == ["display", "1", "+", "2"]


def test_nested_if_else_macro_loops_and_exit(e):
    ok(
        e,
        """set obs 3
local branch 2
forvalues i = 1/2 {
 if `branch' == 1 {
  generate wrong`i' = 1
 } else if `branch' == 2 {
  generate correct`i' = `i'
 } else {
  unsupported_should_not_execute
 }
}
if 0 {
 nonexistent
} else {
 scalar success = 1
}
forvalues j = 1/3 {
 if `j' == 2 {
  exit
 }
 generate first = `j'
}
generate unreachable = 1
""",
    )
    assert set(e.df) == {"correct1", "correct2", "first"}
    assert e.scalars["success"] == 1


def test_block_errors_preflight_no_partial_mutation(e):
    e.df = pd.DataFrame({"safe": [1.0]})
    assert not e.run("clear\nif 1 {\nset obs 10")
    assert "safe" in e.df
    assert not e.run("clear\n#delimit ;\ngenerate unfinished = 1")
    assert "safe" in e.df


def test_quotes_in_star_comments_and_scalar_coefficient_access(e):
    fixture(e)
    ok(
        e,
        '* unmatched " in a comment\nregress y x z\nscalar b = _b[x]\nscalar se = _se[x]',
    )
    assert e.scalars["b"] == e.model.params.x
    assert e.scalars["se"] == pytest.approx(np.sqrt(e.model.cov.loc["x", "x"]))


def test_tab_delimited_commands_and_quoted_options(e):
    ok(e, "set\tobs 5\ngenerate\tx = _n\nquietly\tsummarize x")
    assert e.r["mean"] == 3
    assert (
        options('title("Effect (adjusted)")', ("title",))["title"]
        == "Effect (adjusted)"
    )
    ok(e, 'histogram x, title("Effect (adjusted)")')


def test_nonfinite_intermediates_propagate_as_missing(e):
    assert np.isnan(e.expr("1 / (1/0)"))
    assert e.expr("(-1/0) > 100")
    assert not e.expr("(-1/0) < 0")
    assert e.expr("exp(10000) == .")


def test_completion_time_factor_coefficients_and_options():
    from statbridge.completion import Suggestions

    c = Suggestions()
    c.variables = ["income", "industry", "region"]
    c.coefficients = ["_cons", "income", "1.region"]
    assert "generate change = D2.income" in c.candidates("generate change = D2.inc")
    assert "regress income i.region" in c.candidates("regress income i.reg")
    assert "display _b[income]" in c.candidates("display _b[inc")
    assert not any("robust" in x for x in c.candidates('save "data.dta", '))
