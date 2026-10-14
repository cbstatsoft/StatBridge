# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
import numpy as np
import pandas as pd
import pytest
from scipy import stats
from statbridge.engine import Engine


def ok(e, source):
    assert e.run(source), "\n".join(
        ev["text"] for ev in e.events if ev["kind"] == "error"
    )


@pytest.fixture
def e(tmp_path):
    e = Engine(cwd=tmp_path)
    yield e
    e.close()


def test_recode_first_match_ranges_missing_and_labels(e):
    e.df = pd.DataFrame(
        {"x": [1.0, 2.0, 3.0, 4.0, 5.0, np.nan], "z": [3.0, 4.0, 5.0, 6.0, 7.0, np.nan]}
    )
    ok(e, 'recode x (min/3=1 "Low") (3/5=2 "High") (missing=9 "Unknown"), gen(band)')
    assert e.df.band.tolist() == [1, 1, 1, 2, 2, 9]
    assert e.value_labels["band"] == {1.0: "Low", 2.0: "High", 9.0: "Unknown"}
    ok(e, "recode x z (min/max=0) if _n <= 3, prefix(r_)")
    assert e.df.r_x.iloc[:3].tolist() == [0, 0, 0]
    assert e.df.r_x.iloc[3:].isna().all()
    ok(e, "recode x (1=10) if _n == 1, gen(copy) copyrest")
    np.testing.assert_allclose(e.df["copy"], [10, 2, 3, 4, 5, np.nan], equal_nan=True)


@pytest.mark.parametrize(
    "command",
    [
        "recode x (else=1) (2=0), gen(a)",
        "recode x (5/1=1), gen(a)",
        'recode x (1=2 "two"), gen(x)',
        "recode x (.a=1), gen(a)",
        "recode x (1=2), gen(a a)",
    ],
)
def test_invalid_recode_does_not_change_data(e, command):
    e.df = pd.DataFrame({"x": [1.0, 2.0, np.nan]})
    before = e.df.copy()
    assert not e.run(command)
    pd.testing.assert_frame_equal(e.df, before)


def test_clone_and_missing_code_roundtrip(e):
    e.df = pd.DataFrame({"x": [1.0, -99.0, np.nan], "text": ["a", "", "c"]})
    e.labels["x"] = "Response"
    e.value_labels["x"] = {1: "Yes"}
    e.formats["x"] = "%9.0g"
    ok(e, "clonevar backup = x\nmvdecode x, mv(-99)\nmvencode x, mv(-1)")
    assert e.df.x.tolist() == [1, -1, -1]
    assert e.labels["backup"] == "Response"
    assert e.value_labels["backup"] == {1: "Yes"}
    ok(e, "clonevar selected = text if _n == 1")
    assert e.df.selected.tolist() == ["a", "", ""]
    ok(e, "misstable summarize x text, all")
    assert e.r["N_complete"] == 2
    ok(e, "misstable patterns text")
    assert e.r["N_complete"] == 2
    assert not e.run("mvencode x, mv(-1)")


def test_tostring_precision_split_and_atomic_failure(e):
    e.df = pd.DataFrame(
        {"x": [1.25, 2.5, np.nan], "text": ["alpha,beta", "one,two", ""]}
    )
    assert not e.run("tostring x, gen(s) format(%3.0f)")
    assert "s" not in e.df
    ok(e, 'tostring x, gen(s) format(%8.2f)\nsplit text, parse(",") gen(part)')
    assert e.df.s.tolist() == ["1.25", "2.50", "."]
    assert e.df.part1.tolist() == ["alpha", "one", ""]
    assert e.df.part2.tolist() == ["beta", "two", ""]
    ok(e, 'split text, gen(num) parse(",") destring')
    assert e.df.num1.tolist() == ["alpha", "one", ""]
    before = e.df.copy()
    assert not e.run('split text, gen(num) parse(",")')
    pd.testing.assert_frame_equal(e.df, before)


def test_ds_and_levelsof_macros_drive_loops(e):
    e.df = pd.DataFrame({"x": [1, 2, 1], "g": ["A", "B", "A"], "z": [2, 4, 6]})
    ok(
        e,
        "ds, has(type numeric)\nlocal vars `r(varlist)'\nforeach v of varlist `vars' {\n summarize `v'\n}",
    )
    assert e.locals["vars"] == "x z"
    ok(
        e,
        "levelsof g, local(groups)\nforeach group in `groups' {\n count if g == \"`group'\"\n}",
    )
    assert e.r["N"] == 1
    ok(e, "ds x, not")
    assert e.r["varlist"] == "g z"


def test_percentile_definitions_ties_qualifiers_and_macro_results(e):
    e.df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, np.nan]})
    ok(e, "_pctile x, p(25 50 75)")
    assert [e.r[f"r{i}"] for i in (1, 2, 3)] == [1.5, 2.5, 3.5]
    ok(e, "pctile cut = x, nq(4) genp(percent)\nxtile bin = x, nq(4)")
    np.testing.assert_allclose(
        e.df.cut, [1.5, 2.5, 3.5, np.nan, np.nan], equal_nan=True
    )
    assert e.df.bin.iloc[:4].tolist() == [1, 2, 3, 4]
    ok(e, "xtile custom = x, cutpoints(cut)")
    pd.testing.assert_series_equal(e.df["bin"], e.df.custom, check_names=False)
    e.df = pd.DataFrame({"x": [1.0, 1.0, 2.0, 2.0, 3.0, 3.0]})
    ok(e, "xtile band = x, nq(3)")
    assert e.df.band.tolist() == [1, 1, 2, 2, 3, 3]
    ok(e, "_pctile x, p(20) altdef")
    assert e.r["r1"] == pytest.approx(np.quantile(e.df.x, 0.2, method="weibull"))


def test_expand_originals_and_contract_counts(e):
    e.df = pd.DataFrame({"g": ["a", "b", "b", "c"], "n": [3.0, 0.0, np.nan, 1.6]})
    ok(e, "expand n, gen(copy)")
    assert e.df.g.tolist() == ["a", "b", "b", "c", "a", "a", "c"]
    assert e.df["copy"].tolist() == [0, 0, 0, 0, 1, 1, 1]
    ok(e, "contract g, freq(n) percent(p)")
    assert e.df.n.tolist() == [3, 2, 2]
    np.testing.assert_allclose(e.df.p, [300 / 7, 200 / 7, 200 / 7])


def test_egen_missing_rank_standardisation_tag_and_group(e):
    e.df = pd.DataFrame(
        {
            "x": [1.0, 2.0, np.nan, 4.0],
            "z": [2.0, np.nan, np.nan, 8.0],
            "g": ["a", "a", "", "b"],
        }
    )
    ok(
        e,
        'egen missing_n = rowmiss(x z)\negen observed = rownonmiss(x z)\negen first = tag(g)\negen gid = group(g), missing\negen zx = std(x)\negen rankx = rank(x)\negen medianx = pctile(x), p(50)\negen name = concat(g x), punct(":")',
    )
    assert e.df.missing_n.tolist() == [0, 1, 2, 0]
    assert e.df.observed.tolist() == [2, 1, 0, 2]
    assert e.df["first"].tolist() == [1, 0, 0, 1]
    assert e.df.gid.notna().all()
    assert e.df.zx.mean() == pytest.approx(0, abs=1e-14)
    assert e.df.zx.std() == pytest.approx(1)
    np.testing.assert_allclose(e.df.rankx, [1, 2, np.nan, 3], equal_nan=True)
    assert e.df.medianx.tolist() == [2, 2, 2, 2]
    assert e.df["name"].tolist() == ["a:1", "a:2", ":.", "b:4"]


def test_bysort_within_order_and_duplicate_tag(e):
    e.df = pd.DataFrame(
        {"id": [2, 1, 1, 2], "t": [2, 2, 1, 1], "x": [4.0, 2.0, 1.0, 3.0]}
    )
    ok(
        e,
        "bysort id (t): gen sequence = _n\nbys id: egen n = count(x)\nduplicates tag id, gen(dup)",
    )
    assert e.df.x.tolist() == [1, 2, 3, 4]
    assert e.df.sequence.tolist() == [1, 2, 1, 2]
    assert e.df.n.tolist() == [2, 2, 2, 2]
    assert e.df.dup.tolist() == [1, 1, 1, 1]


def test_merge_filters_selected_columns_assertion_is_atomic(e, tmp_path):
    import pyreadstat

    pyreadstat.write_dta(
        pd.DataFrame({"id": [2.0, 3.0], "z": [20.0, 30.0], "unused": [9.0, 9.0]}),
        str(tmp_path / "other.dta"),
    )
    e.df = pd.DataFrame({"id": [1.0, 2.0], "x": [1.0, 2.0]})
    original = e.df.copy()
    assert not e.run('merge 1:1 id using "other.dta", assert(match)')
    pd.testing.assert_frame_equal(e.df, original)
    ok(e, 'merge 1:1 id using "other.dta", keep(match master) keepusing(z) gen(status)')
    assert e.df.status.tolist() == [1, 3]
    assert e.df.id.tolist() == [1, 2]
    assert "unused" not in e.df
    assert e.r == {"N_1": 1, "N_2": 1, "N_3": 1}


def model_data(e):
    rng = np.random.default_rng(833)
    g = np.repeat(np.arange(5), 12)
    x = rng.normal(size=len(g))
    z = rng.normal(size=len(g))
    y = 2 + 3 * x - 0.5 * z + g + rng.normal(size=len(g))
    e.df = pd.DataFrame({"y": y, "x": x, "z": z, "g": g})


def test_oneway_anova_and_spearman(e):
    model_data(e)
    groups = [part.y.to_numpy() for _, part in e.df.groupby("g")]
    expected = stats.f_oneway(*groups)
    ok(e, "oneway y g, tabulate")
    assert e.r["F"] == pytest.approx(expected.statistic)
    assert e.r["p"] == pytest.approx(expected.pvalue)
    ok(e, "anova y g")
    assert e.model.command == "anova"
    assert e.model.result.fvalue == pytest.approx(expected.statistic)
    expectedcorr = stats.spearmanr(e.df.x, e.df.y)
    ok(e, "spearman x y, stats(rho p obs)")
    assert e.r["rho"] == pytest.approx(expectedcorr.statistic)
    assert e.r["p"] == pytest.approx(expectedcorr.pvalue)


@pytest.mark.parametrize("vce", ["", "robust", "vce(cluster g)"])
def test_areg_slopes_covariance_and_normalised_intercept(e, vce):
    model_data(e)
    ok(e, "regress y x z i.g" + (", " + vce if vce else ""))
    full = e.model
    expected_params = full.params[["x", "z"]].copy()
    expected_cov = full.cov.loc[["x", "z"], ["x", "z"]].copy()
    expected_cons = (
        e.df.y.mean()
        - expected_params.x * e.df.x.mean()
        - expected_params.z * e.df.z.mean()
    )
    transform = np.zeros((3, len(full.params)))
    transform[:, :3] = np.eye(3)
    transform[0, 3:] = full.x.iloc[:, 3:].mean().to_numpy()
    expected_all_cov = transform @ full.cov.to_numpy() @ transform.T
    expected_resid = full.residual.copy()
    ok(e, "areg y x z, absorb(g) " + vce)
    np.testing.assert_allclose(e.model.params[["x", "z"]], expected_params)
    np.testing.assert_allclose(e.model.cov.loc[["x", "z"], ["x", "z"]], expected_cov)
    assert e.model.params["_cons"] == pytest.approx(expected_cons)
    np.testing.assert_allclose(e.model.cov, expected_all_cov)
    np.testing.assert_allclose(e.model.residual, expected_resid)
    # Independent within transformation checks the main slopes.
    within = e.df[["y", "x", "z"]] - e.df.groupby("g")[["y", "x", "z"]].transform(
        "mean"
    )
    beta = np.linalg.lstsq(within[["x", "z"]], within.y, rcond=None)[0]
    np.testing.assert_allclose(e.model.params[["x", "z"]], beta)
    assert e.e["df_absorb"] == 4


def test_linear_restrictions_factor_joint_tests_and_lincom(e):
    model_data(e)
    ok(e, "regress y x z i.g, robust")
    m = e.model
    b = m.params
    cov = m.cov
    expected = ((b.x - 3) ** 2) / cov.loc["x", "x"]
    ok(e, "test x=3")
    assert e.r["F"] == pytest.approx(expected)
    ok(e, "test (x=3) (z=-.5)")
    contrast = np.array([b.x - 3, b.z + 0.5])
    expected = contrast @ np.linalg.solve(cov.loc[["x", "z"], ["x", "z"]], contrast) / 2
    assert e.r["F"] == pytest.approx(expected)
    ok(e, "testparm i.g")
    assert e.r["df"] == 4
    ok(e, "lincom 2*_b[x] - z + 1, level(90)")
    expected = 2 * b.x - b.z + 1
    se = np.sqrt(4 * cov.loc["x", "x"] + cov.loc["z", "z"] - 4 * cov.loc["x", "z"])
    assert e.r["estimate"] == pytest.approx(expected)
    assert e.r["se"] == pytest.approx(se)
    assert e.r["lb"] == pytest.approx(expected - stats.t.ppf(0.95, m.df) * se)
    assert not e.run("test x*x=1")
    assert not e.run('lincom __import__("os")')


def test_tabstat_qualified_group_output(e):
    e.df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "g": ["a", "a", "b", "b"]})
    ok(e, "tabstat x if x > 1, stat(n mean sd p25 median p75) by(g)")
    assert e.r["N"] == 3
    outputs = "\n".join(ev["text"] for ev in e.events if ev["kind"] == "output")
    assert "Total" in outputs
    assert "p25" in outputs


def test_ols_out_of_sample_prediction_and_standard_errors(e):
    model_data(e)
    ok(e, "regress y x z if _n <= 40, robust")
    m = e.model
    design = np.column_stack([np.ones(len(e.df)), e.df.x, e.df.z])
    expected = design @ m.params.to_numpy()
    expected_se = np.sqrt(np.einsum("ij,jk,ik->i", design, m.cov, design))
    ok(e, "predict double fitted, xb\npredict se, stdp\npredict err if _n > 40, resid")
    np.testing.assert_allclose(e.df.fitted, expected)
    np.testing.assert_allclose(e.df.se, expected_se)
    assert e.df.err.iloc[:40].isna().all()
    np.testing.assert_allclose(e.df.err.iloc[40:], e.df.y.iloc[40:] - expected[40:])
    assert not e.run("predict forecast_se, stdf")


def test_predict_preserves_fitted_factor_base_and_rejects_unseen_levels(e):
    model_data(e)
    ok(e, "regress y x i.g if g > 0")
    ok(e, "predict fitted if g > 0, xb")
    np.testing.assert_allclose(e.df.fitted.loc[e.model.sample], e.model.predicted)
    assert e.df.fitted.loc[e.df.g == 0].isna().all()
    assert not e.run("predict invalid, xb")
    assert "invalid" not in e.df


def test_ols_influence_and_reset_match_independent_calculation(e):
    model_data(e)
    ok(e, "regress y x z")
    model = e.model
    x = model.x.to_numpy()
    y = model.y.to_numpy()
    projection = x @ np.linalg.inv(x.T @ x) @ x.T
    ok(e, "predict leverage, hat\npredict forecast_se, stdf\nestat ovtest")
    np.testing.assert_allclose(e.df.leverage, np.diag(projection), rtol=1e-12)
    fitted = model.predicted.to_numpy()
    # Scaling powers improves conditioning without changing the tested column span.
    scaled = fitted / np.sqrt(np.mean(fitted**2))
    augmented = np.column_stack([x, scaled**2, scaled**3, scaled**4])
    residual = y - augmented @ np.linalg.lstsq(augmented, y, rcond=None)[0]
    sse = (residual**2).sum()
    n, k = augmented.shape
    expected = ((model.residual**2).sum() - sse) / 3 / (sse / (n - k))
    assert e.r["F"] == pytest.approx(expected, rel=1e-8)
    assert e.r["df"] == 3


def test_new_command_completion_uses_context(e):
    from statbridge.completion import Suggestions

    model_data(e)
    suggestions = Suggestions()
    suggestions.sync(e)
    assert "areg y x, absorb(g" in suggestions.candidates("areg y x, absorb(")
    assert "tabstat x, stat(mean" in suggestions.candidates("tabstat x, stat(me")
    assert "xtile new = x" in suggestions.candidates("xtile new = ")
    assert not suggestions.candidates("recode x (1=0), generate(new")
    assert "duplicates tag g" in suggestions.candidates("duplicates tag ")
