# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent numerical and state-preservation tests for OLS influence."""
import numpy as np
import pandas as pd
import pytest

from statbridge.engine import Engine


@pytest.fixture
def fitted():
    rng = np.random.default_rng(510)
    x = np.linspace(-3, 3, 65)
    y = 4 + 1.8 * x + rng.normal(scale=.6, size=len(x))
    y[15] += 5.0
    e = Engine()
    e.df = pd.DataFrame({"y": y, "x": x}, index=np.arange(100, 165))
    assert e.execute("regress y x")
    return e


def test_influence_against_projection_matrix_and_independent_cooks_formula(fitted):
    e = fitted
    before = e.df.copy(deep=True)
    model = e.model
    assert e.execute("estat influence, top(7)")
    assert e.model is model
    pd.testing.assert_frame_equal(e.df, before)

    x = model.x.to_numpy()
    y = model.y.to_numpy()
    n, k = x.shape
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = y - x @ beta
    mse = np.sum(residual**2) / (n-k)
    h = np.einsum("ij,jk,ik->i", x, np.linalg.inv(x.T @ x), x)
    internal = residual / np.sqrt(mse * (1 - h))
    cooks = internal**2 / k * h / (1-h)

    table = e.results_table
    assert len(table) == 7
    assert table.index.tolist() == model.sample[np.argsort(-cooks, kind="stable")[:7]].tolist()
    assert table.iloc[0]["Cook's D"] == pytest.approx(max(cooks), rel=1e-10)
    for label, row in table.iterrows():
        position = model.sample.get_loc(label)
        assert row["Leverage"] == pytest.approx(h[position], rel=1e-10)
        assert row["Studentized resid."] == pytest.approx(internal[position], rel=1e-10)
        assert row["Cook's D"] == pytest.approx(cooks[position], rel=1e-10)
    assert e.r["N"] == n
    assert e.r["k"] == k
    assert e.r["N_large_cook"] == sum(cooks > 4/n)
    assert e.r["N_high_leverage"] == sum(h > 2*k/n)
    assert e.r["max_cook"] == pytest.approx(max(cooks))


@pytest.mark.parametrize("arg", ["top(0)", "top(-1)", "top(2.4)", "top(101)", "foo"])
def test_influence_refuses_invalid_options_without_changing_fitted_model(fitted, arg):
    e = fitted
    model = e.model
    assert not e.execute("estat influence, " + arg)
    assert e.model is model


def test_influence_refuses_robust_or_changed_data(fitted):
    e = fitted
    assert e.execute("regress y x, vce(robust)")
    model = e.model
    assert not e.execute("estat influence")
    assert e.model is model
    assert e.execute("regress y x")
    e.revision += 1
    assert not e.execute("estat influence")


def test_influence_missing_rows_keep_dataset_index():
    rng = np.random.default_rng(11)
    e = Engine()
    e.df = pd.DataFrame({
        "y": 1 + np.arange(34)*.7 + rng.normal(size=34),
        "x": np.arange(34, dtype=float),
    }, index=np.arange(200, 234))
    e.df.loc[205, "y"] = np.nan
    assert e.execute("regress y x")
    assert e.execute("estat influence, top(99)")
    assert len(e.results_table) == 33
    assert 205 not in e.results_table.index
    assert set(e.results_table.index) == set(e.model.sample)


def test_influence_requires_existing_model():
    e = Engine()
    assert not e.execute("estat influence")
