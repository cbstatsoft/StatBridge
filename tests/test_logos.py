# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""Logos grammar, state switching, failure isolation and command parity."""
import numpy as np
import pandas as pd
import pytest

from statbridge.engine import Engine
from statbridge.logos import translate_logos
from statbridge.syntax import StataError


@pytest.fixture
def data():
    rng = np.random.default_rng(123)
    x = np.linspace(-3, 3, 100)
    z = rng.normal(size=100)
    y = 2 + 3*x - .4*z + rng.normal(scale=.3, size=100)
    return pd.DataFrame({
        "x": x, "z": z, "y": y,
        "adult": (x >= 0).astype(int),
        "category": np.where(x > 0, "east", "west"),
    })


@pytest.mark.parametrize("source,expected", [
    ("show variables", "describe"),
    ("describe dataset", "describe"),
    ("count rows", "count"),
    ("how many observations where (adult = 1) ∧ (z ≤ 2)", "count if (adult == 1) & (z <= 2)"),
    ("keep rows where y ≥ 3 and z is not missing", "keep if y >= 3 & !missing(z)"),
    ("drop observations such that adult equals 0", "drop if adult == 0"),
    ("summarise y and x", "summarize y x"),
    ("summary of x, z where adult = 1", "summarize x z if adult == 1"),
    ("average of y", "mean y"),
    ("regress y on x and z where adult = 1", "regress y x z if adult == 1"),
    ("fit linear model y ~ x + z", "regress y x z"),
    ("fit logistic regression adult ~ x + z", "logit adult x z"),
    ("fit probit model adult ~ x", "probit adult x"),
    ("logistic regression adult on x and z", "logit adult x z"),
    ("create high as x ≥ 0", "generate high = x >= 0"),
    ("let high := x ≠ 1", "generate high = x != 1"),
    ("tabulate adult", "tabulate adult"),
    ("frequency of adult", "tabulate adult"),
    ("correlate x and z", "correlate x z"),
    ("plot histogram of x", "histogram x"),
    ("predict residuals as error", "predict error, residuals"),
    ("predict fitted values as predicted", "predict predicted, xb"),
    ("explain regress", "help regress"),
    ("list rows with x and z where adult = 1", "list x z if adult == 1"),
])
def test_translate_explicit_grammar(source, expected):
    assert translate_logos(source) == expected


def test_quoted_string_predicates_are_preserved():
    s = translate_logos('count rows where category equals "east and west"')
    assert s == 'count if category == "east and west"'
    s = translate_logos("count rows where x is not missing ∧ (z < 10)")
    assert s == "count if !missing(x) & (z < 10)"


@pytest.mark.parametrize("bad", [
    "delete all files", "automatically infer the best regression",
    "run bash rm -rf /", "regress y on x; drop rows where x=2",
    "fit nonlinear model y ~ x", "count rows where", "",
    "count rows where x > 0\nsyntax stata",
    "regress y on x and x", "create y as x;\nclear",
])
def test_unsupported_logos_does_not_translate(bad):
    with pytest.raises(StataError):
        translate_logos(bad)


def test_logos_mode_matches_stata_model_and_records_translation(data):
    english = Engine(syntax_mode="logos")
    regular = Engine()
    english.df = data.copy()
    regular.df = data.copy()
    command = "regress y on x and z where adult = 1"
    assert english.execute(command)
    assert regular.execute("regress y x z if adult == 1")
    np.testing.assert_allclose(english.model.params, regular.model.params)
    np.testing.assert_allclose(english.model.cov, regular.model.cov)
    assert english.ledger[-1]["command"] == command
    assert english.ledger[-1]["canonical"] == "regress"
    assert english.ledger[-1]["translated"] == "regress y x z if adult == 1"
    assert english.ledger[-1]["language"] == "logos"
    assert any(v["kind"] == "translation" and "Logos → regress" in v["text"] for v in english.events)
    pd.testing.assert_frame_equal(english.df, data)


def test_language_is_opt_in_and_can_toggle_without_losing_results(data):
    e = Engine()
    e.df = data.copy()
    assert not e.execute("regress y on x and z")
    assert e.execute("syntax logos")
    assert e.syntax_mode == "logos"
    assert e.execute("regress y on x and z")
    model = e.model
    assert e.execute("syntax stata")
    assert e.model is model
    assert e.execute("regress y x z")
    assert e.execute("logos: count rows where x ≥ 0 ∧ z is not missing")
    assert e.r["N"] == 50
    assert e.execute("syntax logos")
    assert e.execute("stata: summarize x")
    assert e.r["N"] == len(data)
    assert e.execute("stata: help logos")
    assert any("grammar" in v["text"].lower() for v in e.events if v["kind"] == "output")


def test_logos_errors_cannot_mutate_data_or_silently_fallback(data):
    e = Engine(syntax_mode="logos")
    e.df = data.copy(deep=True)
    assert not e.execute("please delete all columns and rows")
    assert e.ledger[-1]["status"] == "error"
    assert e.ledger[-1]["canonical"] == "logos"
    assert not e.execute("regress y on x and x")
    assert e.ledger[-1]["canonical"] == "logos"
    pd.testing.assert_frame_equal(e.df, data)
    assert e.model is None
    assert e.execute("count rows where (adult = 1) ∧ (z ≤ 2)")
    assert e.r["N"] > 0


def test_logos_do_file_can_mix_explicit_stata_escapes(tmp_path):
    script = """syntax logos
stata: clear
stata: set obs 35
stata: generate x = _n
create y as 2 + 3*x + sin(x)
count rows where x ≥ 20 and y is not missing
regress y on x
predict residuals as u
syntax stata
count if x >= 20
"""
    e = Engine(cwd=tmp_path)
    assert e.run(script), [v["text"] for v in e.events if v["kind"] == "error"]
    assert e.syntax_mode == "stata"
    assert "u" in e.df
    assert e.r["N"] == 16
    assert e.ledger[-1]["canonical"] == "count"


def test_logos_invalid_mode_is_rejected(data):
    with pytest.raises(ValueError):
        Engine(syntax_mode="natural")
    e = Engine()
    e.df = data
    assert not e.execute("syntax gpt")
    assert e.syntax_mode == "stata"


def test_logos_example_and_cli_batch(tmp_path):
    from pathlib import Path
    import subprocess
    import sys

    script = Path(__file__).resolve().parents[1] / "examples" / "logos_workflow.do"
    e = Engine(cwd=tmp_path)
    assert e.run(script.read_text(encoding="utf-8")), [
        v["text"] for v in e.events if v["kind"] == "error"
    ][-5:]
    assert len(e.df) == 120
    assert "error" in e.df
    assert e.syntax_mode == "stata"
    assert any(record.get("language") == "logos" for record in e.ledger)

    result = subprocess.run([
        sys.executable, "-m", "statbridge", "--syntax", "stata",
        "--batch", str(script), "--cwd", str(tmp_path)
    ], cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, (result.stdout[-1200:], result.stderr)
    assert "Logos → regress income education experience" in result.stdout


def test_cli_logos_startup_without_mode_switch(tmp_path):
    import subprocess
    import sys

    script = tmp_path / "logos.do"
    script.write_text(
        "stata: clear\nstata: set obs 12\n"
        "stata: generate age = _n\ncount rows where age ≥ 10\n",
        encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, "-m", "statbridge", "--batch", str(script),
         "--syntax", "logos", "--cwd", str(tmp_path)],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "3" in result.stdout


@pytest.mark.parametrize("statement,canonical", [
    ("∀ rows: x ≥ -3", "assert x >= -3"),
    ("every row satisfies adult ≥ 0", "assert adult >= 0"),
    ("∃ row: x ≥ 2", "logosexists x >= 2"),
    ("there exists a row where x > 0", "logosexists x > 0"),
])
def test_quantified_predicates_translate(statement, canonical):
    assert translate_logos(statement) == canonical


def test_row_quantifiers_are_truthful_and_preserve_data(data):
    e = Engine(syntax_mode="logos")
    e.df = data.copy(deep=True)
    assert e.execute("∀ rows: x ≥ -3")
    assert not e.execute("∀ rows: x > 0")
    assert e.ledger[-1]["canonical"] == "assert"
    assert e.execute("∃ row: x > 2")
    assert e.r["exists"] == 1
    assert e.r["N_matches"] > 0
    assert e.execute("there exists a row where x > 200")
    assert e.r["exists"] == 0
    assert e.r["N_matches"] == 0
    pd.testing.assert_frame_equal(e.df, data)
