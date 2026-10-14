# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
import numpy as np
import pandas as pd
import pytest
from statbridge.engine import Engine
from statbridge.data_backend import AUTO_MIN_ROWS


def run(frame, command, mode, tmp_path):
    e = Engine(cwd=tmp_path)
    e.df = frame.copy(deep=True)
    e.labels = {"x": "Original label"}
    assert e.execute("set databackend " + mode)
    assert e.execute(command), [x["text"] for x in e.events if x["kind"] == "error"]
    return e


@pytest.fixture
def frame():
    return pd.DataFrame(
        {
            "g": [2.0, 1.0, 1.0, np.nan, 2.0, 1.0, np.nan, 3.0],
            "s": ["b", "a", "a", None, "b", "a", None, ""],
            "x": [4.0, 1.0, np.nan, 3.0, 4.0, 1.0, np.nan, np.nan],
            "untouched": pd.Categorical(["a", "b", "c", "a", "b", "c", "a", "b"]),
        }
    )


@pytest.mark.parametrize(
    "command",
    [
        "sort g x",
        "gsort -g +x",
        "sort s x",
        "duplicates drop g x, force",
        "duplicates report s x",
        "collapse (mean) avg=x (sum) total=x (count) n=x (sd) sd=x (median) med=x (min) lo=x (max) hi=x (first) f=x (last) l=x, by(g)",
        "collapse (mean) avg=x (sum) total=x (count) n=x (sd) sd=x (first) f=x (last) l=x",
        "collapse (sum) total=x (first) f=x, by(s)",
        "egen avg = mean(x), by(g)",
        "egen sd = sd(x), by(g)",
        "egen n = count(x) if g < 3, by(g)",
        "egen total = total(x), by(s)",
    ],
)
def test_polars_matches_pandas_on_missing_groups_order_and_qualifiers(
    frame, command, tmp_path
):
    pd_result = run(frame, command, "pandas", tmp_path)
    pl_result = run(frame, command, "polars", tmp_path)
    pd.testing.assert_frame_equal(
        pd_result.df, pl_result.df, check_dtype=False, rtol=1e-12
    )
    assert pd_result.labels == pl_result.labels
    assert pl_result.ledger[-1]["data_backends"][0]["backend"] == "polars"
    if command.startswith("duplicates report"):
        assert [x["text"] for x in pd_result.events if x["kind"] == "output"][-1] == [
            x["text"] for x in pl_result.events if x["kind"] == "output"
        ][-1]
    if command.startswith(("sort", "gsort", "duplicates drop")):
        assert pl_result.df.untouched.dtype == frame.untouched.dtype


def test_backend_auto_threshold_and_explicit_modes(tmp_path):
    frame = pd.DataFrame({"x": np.arange(AUTO_MIN_ROWS, dtype=float)[::-1]})
    e = run(frame, "sort x", "auto", tmp_path)
    assert e.ledger[-1]["data_backends"][0]["backend"] == "polars"
    e = run(frame.iloc[:12], "sort x", "auto", tmp_path)
    assert e.ledger[-1]["data_backends"][0]["backend"] == "pandas"
    assert not e.execute("set databackend unknown")
    assert e.data_backend == "auto"


def test_unsupported_types_fallback_or_fail_without_mutation(tmp_path):
    e = Engine(cwd=tmp_path)
    e.df = pd.DataFrame({"x": pd.Categorical(["a"] * AUTO_MIN_ROWS)})
    assert e.execute("sort x")
    assert e.ledger[-1]["data_backends"][0]["backend"] == "pandas"
    assert "dtype" in e.ledger[-1]["data_backends"][0]["reason"]
    before = e.df.copy(deep=True)
    assert e.execute("set databackend polars")
    assert not e.execute("sort x")
    pd.testing.assert_frame_equal(e.df, before)


@pytest.mark.parametrize(
    "command",
    [
        "collapse (mean) avg=x (sum) s=x (count) n=x, by(g)",
        "collapse (mean) avg=x (sum) s=x (count) n=x",
        "egen avg=mean(x), by(g)",
        "sort g",
        "duplicates report g",
    ],
)
def test_empty_frames(frame, command, tmp_path):
    a = run(frame.iloc[:0], command, "pandas", tmp_path)
    b = run(frame.iloc[:0], command, "polars", tmp_path)
    pd.testing.assert_frame_equal(a.df, b.df, check_dtype=False)
