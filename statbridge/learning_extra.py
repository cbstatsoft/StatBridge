# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Additional runnable exercises and read-only outcome checks."""
import numpy as np


def extra_lessons(Lesson):
    return [
        Lesson("recode", "9. Clean special missing codes", "Preserve raw values and treat missing codes explicitly.",
            "A value such as 99 is an ordinary number until you explicitly convert it. Keep an original copy and check the coding rules before calculating summaries.",
            "set obs 8\ngenerate score = 10*_n\nreplace score = 99 in 3\nclonevar raw_score = score",
            "Convert 99 in score to missing, then create band: 1 for 0 to 40 and 2 for 41 to 100, retaining missing.",
            "Use mvdecode score, mv(99), then recode with gen(band).",
            "mvdecode score, mv(99)\nrecode score (0/40=1) (41/100=2), gen(band)",
            "Ordinary missing is supported; extended Stata missing tags are not preserved.",
            reflection="Why would including 99 change the mean? Is 99 always a missing code?",
            answer="It would be counted as an observed score and increase the mean here. Only the data dictionary can justify treating it as missing.", category="Data preparation"),
        Lesson("reshape", "10. Reshape repeated measurements", "Turn wide repeated measures into a long panel.",
            "Wide data store measurement occasions in column names; long data store them in rows. Declare the observation key and check that each panel-time pair is unique before estimation.",
            "set obs 4\ngenerate id = _n\ngenerate score1 = 40 + id\ngenerate score2 = 45 + id",
            "Reshape score1 and score2 into score with occasion in wave, then declare id and wave.",
            "The stub is score. Use reshape long with i(id) j(wave), then xtset.",
            "reshape long score, i(id) j(wave)\nxtset id wave",
            "This exercise covers a numeric-suffix reshape subset. Reshaping does not create independent observations.",
            reflection="Why are the resulting eight rows not necessarily eight independent people?",
            answer="There are four people observed twice. Repeated observations from a person may be dependent.", category="Data preparation"),
        Lesson("interactions", "11. Interpret an interaction", "Compute the slope for a specified group using coefficient covariance.",
            "With a group-by-x interaction, the x coefficient is the slope in the reference group. For group 1, add the interaction coefficient. The uncertainty of that sum depends on their covariance.",
            "set seed 31\nset obs 160\ngenerate group = mod(_n,2)\ngenerate x = 4*runiform()\ngenerate y = 2 + x + 3*group + 2*x*group + rnormal()\nregress y c.x##i.group",
            "Use lincom to estimate the x slope for group 1.",
            "Read the coefficient names in the fitted table and combine x with x#1.group.",
            "lincom x + x#1.group",
            "This uses implemented factor expansion and linear contrasts. Unweighted OLS/logit/probit margins with factors and interactions is also available.",
            reflection="Does the x coefficient alone describe the slope in both groups?",
            answer="No. It is the reference-group slope; group 1's slope adds the interaction. Neither association is automatically causal.", category="Models and interpretation"),
        Lesson("joint", "12. Test several restrictions", "Distinguish a joint test from separate coefficient tests.",
            "A joint Wald test uses the covariance among estimates. Rejecting a set of zero restrictions means at least one fails; it does not mean every coefficient differs from zero.",
            "set seed 32\nset obs 120\ngenerate x = rnormal()\ngenerate z = rnormal()\ngenerate y = 1 + x + .2*z + rnormal()\nregress y x z, vce(robust)",
            "Test jointly that the x and z slopes are zero.", "Use test followed by both coefficient names.",
            "test x z", "Wald inference uses the fitted covariance and backend degrees of freedom; this is not a likelihood-ratio test.",
            reflection="If this test rejects, must the z slope be significant separately?",
            answer="No. Rejection concerns the restrictions jointly, not each coefficient individually.", category="Tests and diagnostics"),
        Lesson("prediction", "13. Fitted values and residuals", "Separate a prediction from its error and from uncertainty.",
            "A residual equals the observed outcome minus its fitted value. Fitted values describe the estimated conditional mean; they are not prediction intervals for individual outcomes.",
            "set obs 30\ngenerate x = _n/3\ngenerate y = 2 + .7*x + sin(_n)\nregress y x",
            "Create fitted containing fitted values and error containing residuals.",
            "Use predict fitted, xb and predict error, residuals.",
            "predict fitted, xb\npredict error, residuals",
            "Eligible unweighted OLS can predict outside its estimation sample; other paths retain estimation-sample and data-revision restrictions.",
            reflection="Would a small residual on training data establish good prediction on new data?",
            answer="No. Assess predictions on suitable held-out data and consider whether the new population differs.", category="Models and interpretation"),
        Lesson("logit", "14. Odds versus probabilities", "Read binary-outcome results on the correct scale.",
            "Logit coefficients change log odds. An odds ratio is a multiplicative change in odds, not in probability. An average marginal effect averages probability-scale changes over observations; for a continuous predictor it is an average derivative.",
            "set seed 33\nset obs 240\ngenerate x = rnormal()\ngenerate probability = 1/(1+exp(-(.2+.8*x)))\ngenerate outcome = runiform() < probability",
            "Fit logit outcome x, then request average marginal effects.",
            "Use margins, dydx(*) after fitting the logit model.",
            "logit outcome x\nmargins, dydx(*)",
            "margins supports unweighted OLS/logit/logistic/probit, factors, interactions and marginsplot. Numeric 0/1 predictors give derivatives; use factor notation for discrete changes.",
            reflection="If a probability-scale effect is 0.10, is that a 10% relative increase?",
            answer="It is 10 percentage points for a unit change (locally for a continuous derivative). Relative percent change needs a baseline probability.", category="Models and interpretation"),
        Lesson("hausman", "15. Interpret a Hausman comparison", "Compare FE and RE while stating the assumptions and limits.",
            "The usual panel Hausman test asks whether common FE and RE slopes differ systematically. RE requires no correlation between regressors and the panel effect. FE allows that correlation but still needs appropriate exogeneity of the idiosyncratic error. A p-value cannot choose a model on its own.",
            "set seed 871\nset obs 600\ngenerate id = ceil(_n/6)\ngenerate year = 1 + mod(_n-1,6)\nbysort id: generate effect = rnormal() if _n == 1\nbysort id: replace effect = effect[1]\ngenerate x = .2*effect + rnormal()\ngenerate y = 1 + .8*x + effect + rnormal()\nxtset id year",
            "Store conventional FE as fixed and RE as random, then run hausman fixed random. Read Explain my command.",
            "Estimate xtreg y x, fe and store fixed; estimate with re and store random. Put fixed first in hausman.",
            "xtreg y x, fe\nestimates store fixed\nxtreg y x, re\nestimates store random\nhausman fixed random",
            "This deliberately illustrates classical covariance assumptions. Robust/clustered, weighted, unequal-sample and non-positive-definite comparisons are refused. No sigmamore/sigmaless adjustment. Cluster-robust estat mundlak is available for balanced complete-case panels. NumPy's random stream differs from Stata's for the same seed.",
            reflection="What would p = 0.30 establish? What if the covariance difference is invalid?",
            answer="At a prechosen 5% level, 0.30 means insufficient evidence against the RE restrictions, not proof of validity. An invalid covariance difference gives no valid decision. Do not remove needed clustering to force a test to run.", category="Tests and diagnostics"),
        Lesson("diagnostics", "16. Diagnose functional form", "Use RESET as evidence, not a specification recipe.",
            "A fitted straight line may miss a curved relationship. RESET adds powers of fitted values and tests them jointly. Rejection does not identify a particular omitted variable, and non-rejection does not validate a causal model.",
            "set seed 34\nset obs 150\ngenerate x = 4*runiform()\ngenerate y = 1 + x + x^2 + rnormal()\nregress y x",
            "Run the implemented RESET test and explain what it can and cannot establish.",
            "Use estat ovtest after conventional OLS.", "estat ovtest",
            "Uses fitted-value powers 2 through 4 and conventional unweighted OLS. Rank tolerances may differ from Stata.",
            reflection="If RESET rejects, does that prove x squared is the right correction in real data?",
            answer="No. We know the synthetic generating formula here, but in real data several specification problems can yield rejection. Use theory and residual patterns.", category="Tests and diagnostics"),
        Lesson("ttest", "17. Compare means with uncertainty", "Read a mean-difference interval in outcome units.",
            "Welch's independent two-sample t-test allows unequal group variances. Statistical significance is distinct from the size and practical importance of the difference. Group membership alone does not imply random assignment.",
            "set seed 35\nset obs 120\ngenerate group = mod(_n,2)\ngenerate score = 50 + 4*group + (3+3*group)*rnormal()",
            "Compare score across group using unequal-variance inference.",
            "Use ttest score, by(group) unequal.", "ttest score, by(group) unequal",
            "SciPy supplies Welch degrees of freedom and a two-sided confidence interval. The reported difference is group 0 minus group 1.",
            reflection="Can a negative difference be consistent with higher scores in group 1?",
            answer="Yes. This ordering subtracts group 1's mean from group 0's. State the ordering and score units explicitly.", category="Tests and diagnostics"),
        Lesson("iv", "18. Instruments and identification", "Distinguish a fitted 2SLS model from a credible instrument.",
            "An instrument must predict the endogenous regressor and satisfy a defensible exclusion/exogeneity argument. A successful 2SLS fit alone establishes neither condition. Here the synthetic design makes instrument independent of the outcome disturbance, while x shares part of that disturbance.",
            "set seed 36\nset obs 500\ngenerate instrument = rnormal()\ngenerate control = rnormal()\ngenerate disturbance = rnormal()\ngenerate x = instrument + .5*control + disturbance + rnormal()\ngenerate y = 1 + 2*x + control + disturbance",
            "Fit 2SLS for y on control, instrumenting x with instrument.",
            "Use ivregress 2sls y control (x = instrument).", "ivregress 2sls y control (x = instrument)",
            "linearmodels supplies 2SLS. First-stage, endogeneity and selected overidentification diagnostics are available; weak-IV-robust intervals and clustered overidentification are not implemented. Panel Hausman is not the IV Wu-Hausman test.",
            reflection="Can a strong first-stage relationship prove exclusion?",
            answer="No. Relevance is different from exclusion. The latter needs a credible design and substantive argument; statistical diagnostics do not prove it.", category="Models and interpretation"),
    ]


def check_extra(engine, key):
    df, m = engine.df, engine.model
    last = engine.ledger[-1] if engine.ledger else {}
    cmd = last.get("canonical") if last.get("status") == "ok" else None
    if key == "recode":
        return (set(("score", "raw_score", "band")).issubset(df)
                and len(df) == 8 and df.raw_score.iloc[2] == 99
                and df.score.isna().sum() == 1 and np.isnan(df.score.iloc[2])
                and np.allclose(df.band, [1, 1, np.nan, 1, 2, 2, 2, 2], equal_nan=True))
    if key == "reshape":
        if not {"id", "wave", "score"}.issubset(df) or len(df) != 8:
            return False
        frame = df.sort_values(["id", "wave"])
        return (np.allclose(frame.id, np.repeat([1, 2, 3, 4], 2))
                and np.allclose(frame.wave, [1, 2]*4)
                and np.allclose(frame.score, [41, 46, 42, 47, 43, 48, 44, 49]) and cmd == "xtset")
    if key == "interactions":
        return (m is not None and {"x", "x#1.group"}.issubset(m.params.index)
                and cmd == "lincom" and np.isclose(engine.r.get("estimate", np.nan), m.params["x"] + m.params["x#1.group"]))
    if key == "joint":
        return cmd == "test" and engine.r.get("df") == 2 and m is not None and m.covariance == "robust"
    if key == "prediction":
        return (m is not None and {"y", "fitted", "error"}.issubset(df)
                and np.allclose(df.fitted, m.predicted)
                and np.allclose(df.error, df.y - df.fitted))
    if key == "logit":
        return cmd == "margins" and m is not None and m.command == "logit" and "x" in m.params
    if key == "hausman":
        return (cmd == "hausman" and last.get("command", "").strip() == "hausman fixed random"
                and {"fixed", "random"}.issubset(engine.stored)
                and engine.r.get("df") == 1 and np.isfinite(engine.r.get("p", np.nan)))
    if key == "diagnostics":
        return cmd == "estat" and last.get("command", "").strip() == "estat ovtest" and engine.r.get("df") == 3
    if key == "ttest":
        return cmd == "ttest" and "unequal" in last.get("command", "") and np.isfinite(engine.r.get("df_t", np.nan))
    if key == "iv":
        return m is not None and m.command == "ivregress" and "x" in m.params and "control" in m.params
    return False
