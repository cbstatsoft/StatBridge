# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic, independent checks for the post-beta ANOVA expansion."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from statbridge.engine import Engine


@pytest.fixture
def one_way():
    rng = np.random.default_rng(108)
    n_per_group = [12, 9, 14]
    group = np.concatenate([np.full(n, idx) for idx, n in enumerate(n_per_group)])
    y = np.concatenate([
        rng.normal(loc=mu, scale=1.0, size=n)
        for n, mu in zip(n_per_group, (0.0, 0.8, 2.3))
    ])
    e = Engine()
    e.df = pd.DataFrame({"y": y, "g": group})
    return e


@pytest.mark.parametrize("adjustment", ["bonferroni", "sidak", "scheffe"])
def test_pairwise_adjustments_against_independent_formulas(one_way, adjustment):
    e = one_way
    groups = [sub["y"].to_numpy() for _, sub in e.df.groupby("g")]
    reference = stats.f_oneway(*groups)
    assert e.execute(f"oneway y g, tabulate {adjustment}")
    assert e.r["F"] == pytest.approx(reference.statistic, rel=1e-11)
    assert e.r["p"] == pytest.approx(reference.pvalue, rel=1e-11)
    assert e.r["comparisons"] == 3
    assert e.r["mcompare"] == adjustment
    table = e.results_table
    assert len(table) == 3
    assert all(table["CI lower"] <= table["Mean diff."])
    assert all(table["CI upper"] >= table["Mean diff."])
    a, b = groups[:2]
    mse = sum(((g - g.mean()) ** 2).sum() for g in groups) / (len(e.df) - 3)
    se = np.sqrt(mse * (1 / len(a) + 1 / len(b)))
    statistic = abs(a.mean() - b.mean()) / se
    p_raw = 2 * stats.t.sf(statistic, len(e.df) - 3)
    expected = {
        "bonferroni": min(1, 3 * p_raw),
        "sidak": 1 - (1 - p_raw) ** 3,
        "scheffe": stats.f.sf(statistic**2 / 2, 2, len(e.df) - 3),
    }[adjustment]
    assert table.iloc[0]["Adj. p"] == pytest.approx(expected, abs=1e-12)
    assert table.iloc[0]["Mean diff."] == pytest.approx(a.mean() - b.mean())


def test_pwmean_tukey_kramer(one_way):
    e = one_way
    assert e.execute("pwmean y, over(g) mcompare(tukey) level(95)")
    table = e.results_table
    assert len(table) == 3
    assert e.r["mcompare"] == "tukey"
    assert e.r["N"] == len(e.df)
    groups = [sub.y.to_numpy() for _, sub in e.df.groupby("g")]
    a, b = groups[0], groups[1]
    df_r = len(e.df) - len(groups)
    mse = sum(((v - v.mean()) ** 2).sum() for v in groups) / df_r
    se = np.sqrt(mse * (1 / len(a) + 1 / len(b)))
    q = abs(a.mean() - b.mean()) / (se / np.sqrt(2))
    expected_p = stats.studentized_range.sf(q, len(groups), df_r)
    assert table.iloc[0]["Adj. p"] == pytest.approx(expected_p, rel=1e-10)
    simultaneous = stats.studentized_range.ppf(.95, len(groups), df_r) / np.sqrt(2) * se
    assert table.iloc[0]["CI upper"] == pytest.approx(a.mean() - b.mean() + simultaneous)


def test_pwmean_rejects_invalid_design(one_way):
    assert not one_way.execute("pwmean y, over(g) mcompare(unknown)")
    assert not one_way.execute("pwmean y, mcompare(tukey)")


def test_oneway_rejects_incompatible_adjustments(one_way):
    assert not one_way.execute("oneway y g, bonferroni scheffe")
    assert not one_way.execute("oneway y g, tukey")


@pytest.fixture
def factorial():
    rng = np.random.default_rng(45)
    # Unbalanced but full-rank 2 x 2 design with interaction.
    a = np.repeat([0, 0, 1, 1], [8, 13, 10, 17])
    b = np.repeat([0, 1, 0, 1], [8, 13, 10, 17])
    y = 2.0 + 1.4 * a + 2.1 * b + 1.0 * a * b + rng.normal(0, 0.8, len(a))
    e = Engine()
    e.df = pd.DataFrame({"y": y, "a": a, "b": b})
    return e


def test_one_factor_anova_matches_scipy(one_way):
    e = one_way
    f_expected = stats.f_oneway(*(s.y.to_numpy() for _, s in e.df.groupby("g")))
    assert e.execute("anova y g")
    assert e.model.command == "anova"
    assert e.results_table.loc["g", "F"] == pytest.approx(f_expected.statistic, rel=1e-10)
    assert e.e["N"] == len(e.df)


def test_factorial_sequential_anova_matches_nested_least_squares(factorial):
    e = factorial
    assert e.execute("anova y a##b, sequential")
    output = e.results_table
    assert list(output.index) == ["a", "b", "a#b"]
    assert e.model.command == "anova"
    assert e.e["N"] == len(e.df)
    assert e.e["df_r"] == len(e.df) - 4
    y = e.df.y.to_numpy()
    x_intercept = np.ones((len(y), 1))
    x_a = np.column_stack((x_intercept, e.df.a))
    x_b = np.column_stack((x_a, e.df.b))
    x_full = np.column_stack((x_b, e.df.a * e.df.b))
    def rss(matrix):
        return float(np.square(y - matrix @ np.linalg.lstsq(matrix, y, rcond=None)[0]).sum())
    rss0, rss1, rss2, rss3 = (rss(x) for x in (x_intercept, x_a, x_b, x_full))
    mse = rss3 / (len(y) - 4)
    for term, ss in zip(output.index, (rss0 - rss1, rss1 - rss2, rss2 - rss3)):
        assert output.loc[term, "SS"] == pytest.approx(ss, rel=1e-9)
        assert output.loc[term, "F"] == pytest.approx(ss / mse, rel=1e-9)


def test_factorial_partial_main_effects_depend_on_reference_coding(factorial):
    e = factorial
    assert e.execute("anova y a b a#b, partial")
    output = e.results_table
    assert (output["df"] == 1).all()
    assert (output["P>F"] >= 0).all()
    assert (output["P>F"] <= 1).all()
    y = e.df.y.to_numpy()
    a, b = e.df.a.to_numpy(), e.df.b.to_numpy()
    full = np.column_stack((np.ones(len(y)), a, b, a * b))
    reduced = np.column_stack((np.ones(len(y)), b, a * b))
    def rss(x):
        residual = y - x @ np.linalg.lstsq(x, y, rcond=None)[0]
        return residual @ residual
    assert output.loc["a", "SS"] == pytest.approx(rss(reduced) - rss(full), rel=1e-9)


@pytest.mark.parametrize("syntax", [
    "anova y a#b",
    "anova y a##b, robust",
    "anova y a##b, partial sequential",
    "anova y a##b c",
    "anova y a|b",
])
def test_rejects_unsupported_factorial_specifications(factorial, syntax):
    assert not factorial.execute(syntax)


def test_large_factorial_preflight_rejects_before_fitting():
    e = Engine()
    e.df = pd.DataFrame({"y": np.arange(300.0), "a": np.arange(300)})
    assert not e.execute("anova y a")
    assert e.model is None


def test_failed_anova_restores_preceding_estimation():
    e = Engine()
    rng = np.random.default_rng(12)
    g = np.repeat([0, 1], 24)
    e.df = pd.DataFrame({
        "y": g.astype(float),
        "g": g,
        "x": rng.normal(size=len(g)),
    })
    assert e.execute("regress y x")
    original_model = e.model
    original_e = dict(e.e)
    previous_table = e.results_table.copy(deep=True)
    # Full-rank indicator regression fits each group exactly. Its zero
    # residual variance is invalid for the classical ANOVA F-test.
    assert not e.execute("anova y g")
    assert e.model is original_model
    assert e.e == original_e
    pd.testing.assert_frame_equal(e.results_table, previous_table)


def test_sigma_is_a_path_based_svg():
    from pathlib import Path
    svg = (Path(__file__).resolve().parents[1] /
           "statbridge" / "assets" / "statbridge.svg").read_text(encoding="utf-8")
    assert "Σ" in svg
    assert "<path " in svg
    assert "transform=" in svg
    assert "<text" not in svg
