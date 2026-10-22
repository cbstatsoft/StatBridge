# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
"""One-stage FPC must scale PSU Taylor covariance, without sample changes."""
import numpy as np
import pandas as pd
import pytest

from statbridge.engine import Engine
from statbridge.survey import survey_covariance


def test_one_stratum_known_psu_scores_fpc_fraction_and_population_size():
    scores = np.array([[1., 0.], [3., 2.], [-2., 1.], [4., 6.]])
    psu = np.arange(4)
    strata = np.ones(4)
    baseline, npsu, ns = survey_covariance(scores, psu, strata)
    corrected, _, _ = survey_covariance(scores, psu, strata, np.full(4, .25))
    equivalent, _, _ = survey_covariance(scores, psu, strata, np.full(4, 16.))
    assert (npsu, ns) == (4, 1)
    np.testing.assert_allclose(corrected, baseline * .75)
    np.testing.assert_allclose(equivalent, corrected)


def test_fpc_different_strata_and_invalid_population_count():
    scores = np.arange(10, dtype=float).reshape(10, 1)
    psu = np.arange(10)
    strata = np.repeat([1, 2], 5)
    values = np.repeat([.3, .6], 5)
    v, n, h = survey_covariance(scores, psu, strata, values)
    manual = 0.0
    for s, f in [(1, .3), (2, .6)]:
        x = scores[strata == s]
        centered = x - x.mean(axis=0)
        manual += (1 - f) * len(x) / (len(x)-1) * (centered.T @ centered).item()
    assert v[0, 0] == pytest.approx(manual)
    assert (n, h) == (10, 2)
    with pytest.raises(Exception):
        survey_covariance(scores, psu, strata, np.repeat([2., 3.], 5))
    with pytest.raises(Exception):
        survey_covariance(scores, psu, strata, np.array([.3]*4+[.2]+[.6]*5))


def test_svyset_fpc_integration_and_unchanged_point_estimate():
    rng = np.random.default_rng(5)
    n = 45
    e = Engine()
    e.df = pd.DataFrame({
        "id": np.arange(n),
        "stratum": np.repeat([1, 2, 3], 15),
        "fpc": np.repeat([.2, .4, .5], 15),
        "w": rng.uniform(1, 2, n),
        "y": rng.normal(size=n),
    })
    assert e.execute("svyset id [pw=w], strata(stratum)")
    assert e.execute("svy: mean y")
    estimate = float(e.model.params["y"])
    ordinary = float(e.model.cov.loc["y", "y"])
    assert e.execute("svyset id [pw=w], strata(stratum) fpc(fpc)")
    assert e.execute("svy: mean y")
    assert float(e.model.params["y"]) == pytest.approx(estimate)
    corrected = float(e.model.cov.loc["y", "y"])
    assert 0 < corrected < ordinary
