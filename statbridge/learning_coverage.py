# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Optional, runnable interpretation exercises for everyday analysis."""

import numpy as np


def coverage_lessons(Lesson):
    return [
        Lesson(
            "confidence",
            "27. Confidence intervals are about a procedure",
            "Separate uncertainty in a mean from the spread of observations.",
            "A 95% confidence procedure covers the population mean in 95% of repeated samples under its assumptions. It does not contain 95% of individual scores. Sampling design and missingness matter.",
            "set seed 712\nset obs 100\ngenerate score = 60+12*rnormal()",
            "Compute a 95% interval for the mean score.",
            "Use ci means score.",
            "ci means score",
            "Unweighted independent observations, Student-t interval; no survey adjustment.",
            reflection="Would a narrow interval rule out selection bias?",
            answer="No. Precision concerns sampling uncertainty under assumptions. A precise estimate can still be biased.",
            category="Tests and diagnostics",
        ),
        Lesson(
            "survey",
            "28. A survey domain keeps the full design",
            "Estimate a domain mean without dropping other sampled PSUs.",
            "Weights affect the point estimate. Clusters and strata affect uncertainty. Domain variance retains all sampled PSUs, even those without domain members. Dropping other rows changes the design.",
            "set seed 713\nset obs 120\ngenerate psu = ceil(_n/5)\ngenerate stratum = ceil(psu/6)\ngenerate weight = 1+mod(psu,3)\ngenerate adult = mod(_n,3)>0\ngenerate income = 20+5*rnormal()",
            "Declare psu, weight and stratum, then estimate mean income for adults using subpop().",
            "Use svyset, then svy, subpop(adult): mean income.",
            "svyset psu [pw=weight], strata(stratum)\nsvy, subpop(adult): mean income",
            "One-stage with-replacement Taylor variance only, PSU-minus-strata df. No FPC or singleton adjustments.",
            reflection="Are probability weights enough to describe every survey design?",
            answer="No. Weights alone do not encode strata, clustering or stages. Coefficients may agree while standard errors differ.",
            category="Models and interpretation",
        ),
        Lesson(
            "survival",
            "29. A hazard ratio is not a risk ratio",
            "Distinguish survival probability from instantaneous relative hazard.",
            "Censored subjects contribute time at risk without an observed failure. Kaplan-Meier estimates survival. Cox models relative hazards assuming proportional hazards and independent censoring. A hazard ratio of two is not twice the failure probability by a fixed date.",
            "set seed 714\nset obs 300\ngenerate x = rnormal()\ngenerate eventtime = -ln(runiform())/exp(.5*x)\ngenerate censortime = -3*ln(runiform())\ngenerate duration = min(eventtime,censortime)\ngenerate failure = eventtime<=censortime",
            "Declare survival data, inspect Kaplan-Meier survival, then fit Cox with x.",
            "Use stset duration, failure(failure), then sts list and stcox x.",
            "stset duration, failure(failure)\nsts list\nstcox x",
            "One record per subject, origin zero, model-based covariance. No PH diagnostic or delayed entry.",
            reflection="Does a significant coefficient verify proportional hazards?",
            answer="No. That test concerns a coefficient, not whether the hazard ratio is constant over time. Assess the assumption using suitable diagnostics.",
            category="Models and interpretation",
        ),
        Lesson(
            "ordered",
            "30. Ordered categories and predicted probabilities",
            "Interpret an ordered slope without treating it as a probability difference.",
            "Ordered logit has common slopes across cumulative category odds. Cutpoints separate positions on a latent scale; their spacing need not equal the category codes. A positive slope shifts probability toward higher categories, with category-specific changes.",
            "set seed 715\nset obs 300\ngenerate x = rnormal()\ngenerate u = runiform()\ngenerate latent = .7*x+ln(u/(1-u))\ngenerate rating = (latent>-.5)+(latent>.7)",
            "Fit ordered logit and generate category 2 probability as p_high.",
            "Use ologit rating x, then predict p_high, pr outcome(2).",
            "ologit rating x\npredict p_high, pr outcome(2)",
            "Unweighted model-based covariance, latent-scale cutpoints, sample-only predictions. No margins or proportional-odds diagnostic.",
            reflection="Does a slope of .7 mean a 70-percentage-point increase?",
            answer="No. It is on the log-odds scale. Probability changes depend on covariates and category.",
            category="Models and interpretation",
        ),
    ]


def check_coverage(engine, key):
    m = engine.model
    df = engine.df
    if key == "confidence":
        return (
            "score" in df
            and engine.r.get("N") == 100
            and np.isclose(engine.r.get("mean", np.nan), df.score.mean())
            and engine.r.get("lb", np.inf)
            < df.score.mean()
            < engine.r.get("ub", -np.inf)
        )
    if key == "survey":
        return (
            m is not None
            and m.command == "svy: mean"
            and "income" in m.params
            and "adult" in df
            and len(m.sample) == int(df.adult.sum())
            and m.df == 20
            and engine.survey_design
            == {"psu": "psu", "weight": "weight", "strata": "stratum"}
        )
    if key == "survival":
        return (
            m is not None
            and m.command == "stcox"
            and list(m.params.index) == ["x"]
            and len(m.sample) == 300
            and engine.survival_set
        )
    if key == "ordered":
        return (
            m is not None
            and m.command == "ologit"
            and {"p_high", "rating", "x"}.issubset(df.columns)
            and np.allclose(df.p_high, m.metadata["probabilities"][:, 2])
        )
    return False
