# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent companion-recursion and variance-share reference tests."""
import numpy as np
import pandas as pd
import pytest
from statbridge.engine import Engine


def _fitted(stable=True):
    rng = np.random.default_rng(904)
    data = np.zeros((160, 2))
    coefficient = np.array([[.55, .12], [.08, .35]])
    for t in range(1, len(data)):
        data[t] = coefficient @ data[t-1] + rng.normal(size=2) @ np.array([[.8, .0],[.2, .55]])
    if not stable:
        data *= np.linspace(1, 1.5, len(data))[:, None]
    frame = pd.DataFrame({"t": np.arange(1, len(data)+1),
                          "a": data[:,0], "b": data[:,1]})
    e = Engine()
    e.df = frame
    assert e.execute("tsset t")
    assert e.execute("var a b, lags(2)")
    return e


def _independent_ma(coefs, steps):
    p,k,_ = coefs.shape
    phi = [np.eye(k)]
    for h in range(1, steps + 1):
        phi.append(sum((coefs[j-1] @ phi[h-j] for j in range(1, min(p,h)+1)),
                       np.zeros((k,k))))
    return np.stack(phi)


def test_irf_cholesky_matches_independent_ma_and_does_not_refit():
    e = _fitted()
    state = e._specialist_var
    fit = state["fit"]
    x = e.df.copy(deep=True)
    raw = _independent_ma(np.asarray(fit.coefs), 8)
    response = raw @ np.linalg.cholesky(np.asarray(fit.sigma_u))
    assert e.execute("varirf, steps(8)")
    table = e.results_table
    assert len(table) == 9 * 4
    assert set(table["Horizon"]) == set(range(9))
    for h in range(9):
        for i, name in enumerate(["a","b"]):
            for j, shock in enumerate(["a","b"]):
                v = table.query("Horizon == @h and Response == @name and Shock == @shock").iloc[0]
                assert v["Orthogonal IRF"] == pytest.approx(response[h,i,j],rel=1e-10,abs=1e-11)
    assert e._specialist_var is state
    pd.testing.assert_frame_equal(e.df, x)


def test_fevd_matches_cumulative_squared_irf_and_shares_sum_to_one():
    e = _fitted()
    fit = e._specialist_var["fit"]
    irfs = _independent_ma(np.asarray(fit.coefs), 7) @ np.linalg.cholesky(np.asarray(fit.sigma_u))
    square = irfs[:7] ** 2
    accum = np.cumsum(square, axis=0)
    expected = accum / accum.sum(axis=2, keepdims=True)
    assert e.execute("varfevd, steps(7)")
    table = e.results_table
    assert len(table) == 7 * 4
    for h in range(1,8):
        for i, name in enumerate(["a", "b"]):
            rows = table[(table["Horizon"] == h) & (table["Response"] == name)]
            assert rows["Variance share"].sum() == pytest.approx(1, abs=1e-12)
            for j, shock in enumerate(["a","b"]):
                cell = rows[rows["Shock"] == shock]["Variance share"].iloc[0]
                assert cell == pytest.approx(expected[h-1,i,j],rel=1e-10,abs=1e-11)
    assert e.r["horizon"] == 7


@pytest.mark.parametrize("command", [
    "varirf", "varfevd, steps(0)", "varirf, steps(25)", "varfevd, unsupported",
])
def test_invalid_var_postestimation_refuses_without_mutation(command):
    e = _fitted()
    before = e.df.copy(deep=True)
    state = e._specialist_var
    if command == "varirf":
        e.changed()
    assert not e.execute(command)
    assert e._specialist_var is state
    pd.testing.assert_frame_equal(e.df, before)


def test_restrict_var_postestimation_without_fitted_var():
    e = Engine()
    assert not e.execute("varirf, steps(5)")
    assert not e.execute("varfevd, steps(5)")
