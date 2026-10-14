# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Runnable teaching workflows for the 0.4 command additions."""

import numpy as np


def roadmap_lessons(Lesson):
    return [
        Lesson(
            "margins",
            "19. Predictions with interactions",
            "Interpret adjusted predictions for each group.",
            "A group interaction changes the slope. margins rebuilds the fitted design at each requested value and averages over other observed covariates. Its intervals describe fitted means, not the spread of individual outcomes.",
            "set seed 91\nset obs 160\ngenerate group = mod(_n,2)\ngenerate x = 4*runiform()\ngenerate y = 2 + x + 3*group + 2*x*group + rnormal()\nregress y c.x##i.group",
            "Estimate group predictions at x = 1 and x = 3, then graph their intervals.",
            "Use margins group, at(x=(1 3)), then marginsplot.",
            "margins group, at(x=(1 3))\nmarginsplot",
            "Unweighted OLS/logit/probit only. Delta-method covariance conditions on the empirical covariates; these are not individual prediction intervals.",
            reflection="Does evaluating everyone at x = 3 establish an intervention effect?",
            answer="No. It is a model-based counterfactual prediction; a causal interpretation additionally needs identification assumptions.",
            category="Models and interpretation",
        ),
        Lesson(
            "mundlak",
            "20. Mundlak with clustered uncertainty",
            "Assess RE restrictions while retaining panel clustering.",
            "Correlated RE adds panel means of time-varying regressors. A joint test of these means assesses the additional RE restrictions. This differs from forcing classical Hausman to accept clustered covariance.",
            "set seed 871\nset obs 600\ngenerate id = ceil(_n/6)\ngenerate time = 1+mod(_n-1,6)\nbysort id: generate effect = rnormal() if _n == 1\nbysort id: replace effect = effect[1]\ngenerate x = .5*effect+rnormal()\ngenerate y = 1+.8*x+effect+rnormal()\nxtset id time",
            "Fit correlated RE with clustering by id, then test the panel means.",
            "Use xtreg y x, cre vce(cluster id), then estat mundlak.",
            "xtreg y x, cre vce(cluster id)\nestat mundlak",
            "Balanced complete-case panel subset. Stata unbalanced-panel corrections are not implemented. Clustered Wald chi-square is asymptotic; few clusters remain problematic.",
            reflection="Does non-rejection prove the random-effects assumptions?",
            answer="No. State the tested restrictions and power limitations. The test also cannot establish exogeneity of the remaining idiosyncratic error.",
            category="Tests and diagnostics",
        ),
        Lesson(
            "ivdiagnostics",
            "21. Diagnose a 2SLS model",
            "Read instrument strength, exogeneity and overidentification separately.",
            "A first-stage Wald statistic with robust covariance has a chi-square reference distribution here. Do not treat its label as a classical F statistic. Overidentification and endogeneity tests address different null hypotheses and do not prove instrument validity.",
            "set seed 92\nset obs 500\ngenerate instrument1 = rnormal()\ngenerate instrument2 = rnormal()\ngenerate control = rnormal()\ngenerate error = rnormal()\ngenerate x = instrument1+.7*instrument2+.5*control+error+rnormal()\ngenerate y = 1+2*x+control+error\nivregress 2sls y control (x = instrument1 instrument2), vce(robust)",
            "Inspect first-stage strength, test exogeneity, then test overidentifying restrictions.",
            "Use estat firststage, estat endogenous, and estat overid, in that order.",
            "estat firststage\nestat endogenous\nestat overid",
            "Robust overidentification uses Wooldridge score, not Hansen J. Clustered overidentification is refused. Exactly identified models have no overidentification test.",
            reflection="Could strong instruments still violate exclusion?",
            answer="Yes. Relevance and exclusion are different requirements. A high first-stage statistic cannot validate the exclusion argument.",
            category="Tests and diagnostics",
        ),
        Lesson(
            "did",
            "22. Two-period difference-in-differences",
            "Interpret a treatment-by-post change under parallel trends.",
            "The DiD coefficient compares the change in treated groups with the change in control groups. Group and time effects alone do not establish parallel trends, no anticipation or absence of spillovers.",
            "set seed 93\nset obs 160\ngenerate id = ceil(_n/2)\ngenerate time = mod(_n-1,2)\ngenerate treated = (id>40) & (time==1)\ngenerate y = id/10 + 2*time + 4*treated + rnormal()\nxtset id time",
            "Estimate panel DiD using id as the treatment-group identifier and time as the period.",
            "Use xtdidregress (y) (treated), group(id) time(time).",
            "xtdidregress (y) (treated), group(id) time(time)",
            "Complete balanced two-period panels only. No staggered adoption, heterogeneous event-study estimator or wild-cluster bootstrap. AbsorbingLS corrections can differ from Stata.",
            reflection="Can this example test whether trends were parallel before treatment?",
            answer="No. There is only one pre-treatment period. More pre-periods can inform design assessment but still cannot prove the identifying counterfactual.",
            category="Models and interpretation",
        ),
        Lesson(
            "dates",
            "23. Numeric dates and display formats",
            "Keep numeric date units separate from calendar display.",
            "Stata daily dates count days since 1 January 1960. Monthly dates count months from January 1960. format changes the display, not the underlying numbers or units.",
            'set obs 4\ngenerate raw = "2020-02-29"\nreplace raw = "1960-01-01" in 1\nreplace raw = "1959-12-31" in 2\nreplace raw = "2021-02-29" in 4',
            'Create daydate with daily(raw,"YMD") and give it %td format.',
            "Invalid calendar dates become missing; the first two values should be 0 and -1.",
            'generate daydate = daily(raw,"YMD")\nformat daydate %td',
            "Explicit documented masks only, four-digit years and ordinary missing. Custom Stata date display pictures and leap-second clocks are not implemented.",
            reflection="Does format daydate %tm convert days into months?",
            answer="No. Use mofd(daydate) to convert the units, then apply %tm to the new monthly variable.",
            category="Data preparation",
        ),
        Lesson(
            "tables",
            "24. Compare and export models",
            "Build a structured comparison without confusing samples or covariance.",
            "A comparison table should identify the outcome, sample and uncertainty method for each model. A coefficient change can reflect controls or a different sample. Robust covariance changes uncertainty, not the OLS coefficient for an unchanged specification.",
            "set seed 94\nset obs 120\ngenerate x = rnormal()\ngenerate z = .4*x+rnormal()\ngenerate y = 1+2*x+z+rnormal()\nregress y x\nestimates store short\nregress y x z, vce(robust)\nestimates store adjusted",
            "Compare short and adjusted with etable. Use the Results menu to copy or export if desired.",
            "Use etable, estimates(short adjusted). Export is optional and not needed for the check.",
            "etable, estimates(short adjusted)",
            "The table reports coefficients on the fitted scale. CSV/HTML/LaTeX export is a bounded subset, not the complete Stata collect/estout system.",
            reflection="Must the larger model have the more credible causal coefficient?",
            answer="No. Control selection depends on the causal question and design; additional controls can themselves introduce bias.",
            category="Models and interpretation",
        ),
    ]


def check_roadmap(engine, key):
    record = engine.ledger[-1] if engine.ledger else {}
    if record.get("status") != "ok":
        return False
    if key == "margins":
        r = getattr(engine, "margins_result", None)
        return (
            r is not None
            and len(r["table"]) == 4
            and record["canonical"] == "marginsplot"
        )
    if key == "mundlak":
        return (
            record["canonical"] == "estat"
            and record["command"].strip() == "estat mundlak"
            and engine.r.get("df") == 1
        )
    if key == "ivdiagnostics":
        recent = [
            v.get("command", "").strip()
            for v in engine.ledger[-3:]
            if v.get("status") == "ok"
        ]
        return (
            recent == ["estat firststage", "estat endogenous", "estat overid"]
            and engine.r.get("df") == 1
        )
    if key == "did":
        return (
            engine.model is not None
            and engine.model.command == "xtdidregress"
            and "treated" in engine.model.params
        )
    if key == "dates":
        return (
            "daydate" in engine.df
            and np.allclose(engine.df.daydate[:2], [0, -1])
            and np.isnan(engine.df.daydate.iloc[3])
            and engine.formats.get("daydate") == "%td"
        )
    if key == "tables":
        table = getattr(engine, "results_table", None)
        return (
            table is not None
            and list(table.columns) == ["short", "adjusted"]
            and "x" in table.index
        )
    return False
