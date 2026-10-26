# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prevent eager exponentiation of unrelated regression coefficients."""
import warnings

import numpy as np
import pandas as pd
import pytest

from statbridge.engine import Engine


def test_large_ols_coefficients_do_not_trigger_exponent_overflow():
    rng = np.random.default_rng(125)
    x = np.linspace(-2.0, 2.0, 120)
    y = 1200.0 + 850.0 * x + rng.normal(scale=0.4, size=x.size)
    engine = Engine()
    engine.df = pd.DataFrame({"y": y, "x": x})

    # Old np.where evaluated exp(1200) even when exponentiate=False.
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        assert engine.execute("regress y x"), [
            e["text"] for e in engine.events if e["kind"] == "error"
        ]
    table = engine.results_table
    assert table.loc["_cons", "Coef."] == pytest.approx(1200.0, abs=0.3)
    assert table.loc["x", "Coef."] == pytest.approx(850.0, abs=0.3)
    assert "Ratio" not in table
    assert not any(n["code"] == "EXP_COEFFICIENT_RANGE" for n in engine.notices)


def test_poisson_irr_still_exponentiates_only_requested_coefficients():
    rng = np.random.default_rng(456)
    x = rng.normal(size=200)
    y = rng.poisson(np.exp(0.25 + 0.4 * x))
    engine = Engine()
    engine.df = pd.DataFrame({"y": y, "x": x})

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        assert engine.execute("poisson y x, irr"), [
            e["text"] for e in engine.events if e["kind"] == "error"
        ]
    m = engine.model
    b = m.params.to_numpy()
    se = np.sqrt(np.diag(m.cov))
    crit = 1.959963984540054
    table = engine.results_table
    np.testing.assert_allclose(table["Ratio"].to_numpy(), np.exp(b), rtol=1e-10)
    np.testing.assert_allclose(table["Std. err."].to_numpy(), np.exp(b) * se, rtol=1e-10)
    np.testing.assert_allclose(table["CI lower"].to_numpy(), np.exp(b - crit * se), rtol=1e-10)
    np.testing.assert_allclose(table["CI upper"].to_numpy(), np.exp(b + crit * se), rtol=1e-10)


def test_true_ratio_scale_overflow_is_reported_without_raw_numpy_warning():
    rng = np.random.default_rng(759)
    x = rng.normal(size=130)
    y = rng.poisson(np.exp(0.5 + 0.2 * x))
    engine = Engine()
    engine.df = pd.DataFrame({"y": y, "x": x})
    assert engine.execute("poisson y x, irr")

    # Construct a report-only extreme log-rate; no optimiser is being tested.
    engine.model.params = engine.model.params.copy()
    engine.model.params.iloc[0] = 1000.0
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        engine.report_model(exponentiate=True)
    assert np.isinf(engine.results_table.loc["_cons", "Ratio"])
    assert any(n["code"] == "EXP_COEFFICIENT_RANGE" for n in engine.notices)
