# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
from html import escape
import numpy as np
import pandas as pd
import pytest
from statbridge.engine import Engine
from statbridge.reporting import model_report, number, probability
from statbridge.themes import DARK, report_html


@pytest.fixture
def fitted(tmp_path):
    e = Engine(cwd=tmp_path)
    rng = np.random.default_rng(88)
    x = rng.normal(size=120)
    e.df = pd.DataFrame(
        {
            "y": 2 + 3 * x + rng.normal(size=120),
            "x": x,
            "id": np.repeat(np.arange(30), 4),
            "year": np.tile(np.arange(4), 30),
        }
    )
    yield e
    e.close()


def report(e):
    return next(
        event
        for event in reversed(e.events)
        if event["kind"] == "output"
        and isinstance(event["payload"], dict)
        and "html" in event["payload"]
    )


def test_number_format_preserves_scale_and_small_probabilities():
    assert number(1.23456789) == "1.234568"
    assert number(-1e-10) == "-1.000000e-10"
    assert number(1e12) == "1.000000e+12"
    assert number(float("nan")) == "."
    assert number(-0.0) == "0.000000"
    assert probability(1e-100) == "<0.001"
    assert probability(0.001) == "0.001"
    assert probability(0.45112) == "0.451"
    assert probability(float("nan")) == "."


@pytest.mark.parametrize("kind", ["fe", "re"])
def test_panel_report_uses_fitted_sample_and_retains_full_precision(fitted, kind):
    e = fitted
    e.df.loc[0, "y"] = np.nan
    assert e.run(
        f"xtset id year\nxtreg y x, {kind} vce(cluster id)\nestimates store panel"
    )
    result = e.model.result
    output = report(e)
    assert (
        "Fixed-effects (within)" if kind == "fe" else "Random-effects GLS"
    ) in output["text"]
    assert "119" in output["text"]
    assert "3 / 3.97 / 4" in output["text"]
    for name in ["within", "between", "overall"]:
        assert f"R-squared ({name})" in output["text"]
        assert number(getattr(result, "rsquared_" + name), 4) in output["text"]
    table = [ev["payload"]["table"] for ev in e.events if ev["kind"] == "model"][-1]
    np.testing.assert_array_equal(table["Coef."], e.model.params)
    assert "P>|t|" in output["text"]
    assert "&lt;0.001" in output["payload"]["html"]
    # Restoring a model must not depend on the current panel or current data.
    assert e.run("clear\nestimates restore panel")
    assert report(e)["text"] == output["text"]


def test_text_logs_are_aligned_and_quiet_regression_stays_quiet(fitted, tmp_path):
    e = fitted
    assert e.run('log using "report.log", replace\nregress y x, robust\nlog close')
    output = report(e)
    logged = (tmp_path / "report.log").read_text()
    assert output["text"] in logged
    assert "<table" not in logged
    assert "<0.001" in logged
    lines = output["text"].splitlines()
    coef_rows = [line for line in lines if line.startswith(("_cons ", "x "))]
    assert len(coef_rows) == 2
    assert len(coef_rows[0]) == len(coef_rows[1])
    before = len(e.events)
    assert e.run("quietly regress y x")
    assert not any(ev["kind"] == "output" for ev in e.events[before:])


def test_html_escapes_labels_in_both_themes(fitted):
    e = fitted
    assert e.run("regress y x")
    table = [ev["payload"]["table"] for ev in e.events if ev["kind"] == "model"][
        -1
    ].copy()
    label = '<img src="https://example.invalid/a"> & #ffffff'
    table.index = ["_cons", label]
    plain, html = model_report(e.model, table, e.e)
    assert label in plain
    assert escape(label) in html
    assert "<img" not in html
    dark = report_html(html, DARK)
    assert escape(label) in dark
    assert 'bgcolor="#1e1e1e"' in dark
    assert 'bgcolor="#ffffff"' not in dark
