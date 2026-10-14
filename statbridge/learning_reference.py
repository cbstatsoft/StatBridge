# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Offline interpretation notes. Rendering reads results; it never executes commands."""
from dataclasses import dataclass
from html import escape
import math
import re


@dataclass(frozen=True)
class TestGuide:
    key: str
    title: str
    null: str
    reject: str
    retain: str
    assumptions: str
    next_step: str
    syntax: str


TEST_GUIDES = [
    TestGuide("hausman", "Hausman: fixed versus random effects",
        "No systematic difference between the compared slopes, under the specification and efficiency assumptions. In the usual FE/RE comparison, RE requires regressors to be uncorrelated with the unobserved panel effect; FE allows that correlation.",
        "Evidence against the RE restrictions in this FE/RE comparison. FE or an appropriate correlated random-effects specification may be more defensible, provided its own assumptions hold.",
        "Insufficient evidence against the RE restrictions. This does not prove RE is valid or that the two models are equivalent. Limited power can hide important differences.",
        "Put the estimator consistent under both hypotheses first: hausman fixed random. FE still requires appropriate exogeneity of the idiosyncratic error. Classical covariance-difference inference is unsuitable with robust or clustered covariance. Compare the same outcome, observations and compatible specifications. A non-positive-definite covariance difference is an invalid test, not a vote for RE.",
        "Report the statistic, degrees of freedom, p-value, sample and assumptions. Do not choose solely by a threshold. If clustering is needed, consider a correctly specified robust Mundlak/CRE approach. StatBridge supports estat mundlak and xtreg, cre for balanced complete-case panels. Unbalanced CRE corrections and sigmamore/sigmaless are not implemented.",
        "xtreg y x, fe\nestimates store fixed\nxtreg y x, re\nestimates store random\nhausman fixed random"),
    TestGuide("wald", "Wald: joint restrictions and contrasts",
        "All specified coefficient restrictions hold simultaneously. test x z tests both slopes equal to zero; test x = z tests their equality. lincom tests the displayed linear combination equal to zero before exponentiation.",
        "Evidence that at least one restriction fails. A joint rejection does not identify which coefficient or restriction differs.",
        "Insufficient evidence against the restrictions. This is not proof that an effect is zero or practically negligible.",
        "Inference depends on the fitted model and its covariance, sample size and cluster count. Standard errors of contrasts require coefficient covariances. For lincom, eform, the null on the reported ratio scale is one.",
        "Report the contrast, its units and interval as well as its p-value. Choose hypotheses in advance; account for multiple testing when making many comparisons.",
        "test x = z\ntestparm i.group\nlincom x - z"),
    TestGuide("ttest", "t-test: means and paired differences",
        "The population mean equals the specified value, or the mean difference equals zero. A paired test concerns within-pair differences.",
        "Evidence against the specified equality of means under the sampling assumptions.",
        "Insufficient evidence of a difference. A wide interval may include both meaningful benefits and harms; non-rejection is not equivalence.",
        "Independent observations or independent pairs are needed. The pooled two-sample test assumes equal variances; unequal requests Welch inference. Pairing and cluster dependence cannot be ignored. Small samples require attention to the distribution of errors or differences.",
        "Read the confidence interval in outcome units. For by(), the difference is first sorted group minus second. Assess magnitude, design and uncertainty together.",
        "ttest score == 50\nttest after == before\nttest score, by(group) unequal"),
    TestGuide("hettest", "Breusch-Pagan: heteroskedasticity",
        "The error variance is constant against the variance relationship tested here, which uses fitted values.",
        "Evidence of nonconstant variance of the specified form. Conventional OLS uncertainty may be inappropriate.",
        "This test did not detect that variance pattern. Other forms of heteroskedasticity may remain.",
        "StatBridge uses the original normality-based Breusch-Pagan LM test with fitted values, not every Stata hettest variant. It requires an appropriate mean specification; residual plots remain useful.",
        "Consider robust covariance or clustering appropriate to the study design. Robust errors do not repair confounding, endogeneity or a misspecified mean.",
        "regress y x\nestat hettest"),
    TestGuide("ovtest", "RESET: functional form",
        "Coefficients on added powers of fitted values are jointly zero. StatBridge adds powers 2, 3 and 4.",
        "Evidence of a detectable specification problem. The test does not tell you which variable is missing or which transformation is correct.",
        "No detected departure of this form. The model is not thereby certified correct or causal.",
        "The implemented F test requires conventional unweighted OLS with an intercept. Its calibration depends on classical regression assumptions.",
        "Inspect residual patterns and use subject knowledge to consider nonlinearities or interactions. Do not keep changing specifications merely to obtain a large p-value.",
        "regress y x\nestat ovtest"),
    TestGuide("vif", "VIF: collinearity, not a hypothesis test",
        "There is no null hypothesis or p-value. For a nonconstant regressor, VIF = 1/(1 - R-squared) from regressing that regressor on the others with an intercept.",
        "A large VIF signals imprecise separation of correlated predictors, not a statistically significant finding.",
        "A small VIF does not demonstrate good identification or rule out omitted-variable bias.",
        "There is no universal cutoff. Interactions and polynomial terms can naturally be correlated. The intercept's VIF is usually not substantively useful.",
        "Inspect coefficient intervals and the estimand of interest. Do not delete a necessary confounder solely to reduce VIF; centring changes interpretation but does not add information.",
        "regress y x z\nestat vif"),
    TestGuide("dfuller", "ADF: unit roots and stationarity",
        "The series has a unit root, under the selected deterministic terms and lag specification.",
        "Evidence against a unit root in this specification. With a trend included, the alternative allows stationarity around a deterministic trend.",
        "Insufficient evidence against a unit root. This is not proof of a unit root; short samples, structural breaks and near-unit-root behaviour can reduce power.",
        "Choose intercept/trend terms and lag length deliberately. Too few lags can leave serial correlation; too many can reduce power. StatBridge fixes lags() and uses statsmodels MacKinnon approximations.",
        "Plot the series, inspect the study context and assess sensitivity to defensible specifications. Do not difference a series solely because one p-value exceeds 0.05.",
        "tsset time\ndfuller y, lags(1)"),
    TestGuide("oneway", "One-way ANOVA: group means",
        "All group population means are equal.",
        "Evidence that at least one group mean differs. The omnibus test does not identify which pair differs.",
        "Insufficient evidence of unequal means. This is not evidence that all groups are equivalent.",
        "The classical F test assumes independent errors, equal within-group variances and an appropriate error distribution for finite-sample calibration. This implementation does not provide Welch ANOVA.",
        "Inspect group summaries and effect sizes. Use planned contrasts and account for multiple comparisons when following up.",
        "oneway score group, tabulate"),
    TestGuide("iv", "IV: relevance, exclusion and endogeneity",
        "Different diagnostics ask different questions: an endogeneity test typically treats the nominated regressors as exogenous under its null; an overidentification test assesses joint moment restrictions under additional assumptions.",
        "An endogeneity-test rejection challenges OLS exogeneity if the instruments and test assumptions are valid. Overidentification rejection flags incompatible moment restrictions, not a named bad instrument.",
        "Non-rejection does not establish exogeneity or instrument validity. Weak instruments can make conventional inference unreliable.",
        "Instruments need relevance and a defensible exclusion/exogeneity argument. The familiar first-stage F > 10 rule is not a universal threshold, especially for multiple endogenous regressors or robust/clustered tests. IV Wu-Hausman and panel FE/RE Hausman are different tests.",
        "Report first-stage strength and the identification argument. Use estat firststage and estat endogenous; estat overid supports conventional or heteroskedasticity-robust fits but refuses clustered fits. Weak-IV-robust intervals are not implemented.",
        "ivregress 2sls y control (x = instrument)"),
]
TEST_GUIDES.extend([
    TestGuide("mundlak", "Mundlak: correlated random effects",
        "All identified panel-mean coefficients are jointly zero in the augmented RE model, assessing the additional RE restrictions.",
        "Evidence against these RE restrictions. Consider FE or a defensible CRE specification, subject to their own exogeneity assumptions.",
        "Insufficient evidence against the restrictions, not proof of random-effects validity. Power and the chosen set of means matter.",
        "This implementation requires balanced complete-case panels with a common time grid. It tests identified means of expanded time-varying regressors. The selected covariance is used; robust clusters by panel. The Wald chi-square is asymptotic and can be unreliable with few clusters.",
        "Report the mean terms, statistic, degrees of freedom, p-value and covariance. Do not remove required clustering to get a classical Hausman result. estat mundlak does not replace the active model.",
        "xtreg y x, cre vce(cluster id)\nestat mundlak"),
    TestGuide("firststage", "IV first stage: relevance and strength",
        "For each endogenous regressor, excluded-instrument coefficients are jointly zero in its first stage, conditional on included exogenous regressors.",
        "Evidence of relevance does not by itself establish sufficient strength for reliable conventional IV inference.",
        "Weak evidence of relevance raises concern about identification, but the p-value alone is not a complete weak-instrument diagnostic.",
        "Read f.dist. Unadjusted covariance uses F; robust/clustered covariance uses a Wald chi-square. The f.stat column name does not change that distribution. A universal F > 10 rule is not appropriate for every design.",
        "Report partial R-squared, the statistic and distribution. Substantiate exclusion separately. Stock-Yogo cutoffs and weak-IV-robust confidence sets are not supplied.",
        "ivregress 2sls y control (x = instrument)\nestat firststage"),
    TestGuide("endogenous", "IV exogeneity test",
        "All regressors nominated as endogenous can be treated as exogenous, assuming the instruments and maintained model are valid.",
        "Evidence against exogeneity under those assumptions. This is not an independent demonstration that the instruments are valid.",
        "Insufficient evidence against exogeneity. Weak instruments or limited power can hide endogeneity.",
        "Conventional 2SLS uses Wu-Hausman F. Robust or clustered fits use Wooldridge regression Wald with the fitted covariance. This is distinct from the panel FE/RE Hausman comparison.",
        "Report which test was used, its assumptions and instrument-strength evidence. Preserve the study's required covariance structure.",
        "estat endogenous"),
    TestGuide("overid", "IV overidentifying restrictions",
        "The tested instrument moment restrictions hold jointly under the maintained model and covariance assumptions.",
        "Some joint restrictions or maintained assumptions are incompatible with the data. The test does not identify which instrument is invalid.",
        "Insufficient evidence against the restrictions, not proof that instruments satisfy exclusion or exogeneity.",
        "There must be more excluded instruments than endogenous regressors. Conventional fits use Sargan; heteroskedasticity-robust fits use Wooldridge score, not Hansen J. Clustered overidentification is not implemented and is refused.",
        "Use design knowledge to assess exclusion and sensitivity to instrument choices. Do not select instruments solely to obtain a non-significant test.",
        "estat overid"),
])
GUIDES = {g.key: g for g in TEST_GUIDES}


def test_guide_html(guide):
    sections = [("Null or question", guide.null), ("If the null is rejected", guide.reject),
                ("If the null is not rejected", guide.retain), ("Assumptions and limits", guide.assumptions),
                ("What to do next", guide.next_step)]
    if guide.key == "vif":
        sections[1] = ("Larger values", guide.reject)
        sections[2] = ("Smaller values", guide.retain)
    return (f"<h2>{escape(guide.title)}</h2>" + "".join(
        f"<h3>{escape(title)}</h3><p>{escape(body)}</p>" for title, body in sections)
        + f"<h3>Syntax example</h3><pre>{escape(guide.syntax)}</pre>"
        + "<p>Examples require suitable variables and data. This reference does not execute commands. Choose a significance level in advance; a threshold is not a measure of practical importance.</p>")


def command_guide_key(record):
    cmd = record.get("canonical", "")
    if cmd in ("test", "testparm", "lincom"):
        return "wald"
    if cmd == "ivregress":
        return "iv"
    if cmd == "estat":
        match = re.match(r"\s*estat\s+(\w+)", record.get("command", ""), re.I)
        key = match.group(1).lower() if match else ""
        return key if key in ("vif", "hettest", "ovtest", "mundlak", "firststage", "endogenous", "overid") else None
    return cmd if cmd in GUIDES else None


def interpretation_html(engine, record):
    """Only attach a numeric decision to commands that actually return r(p)."""
    key = command_guide_key(record)
    if key is None:
        return ""
    guide = GUIDES[key]
    text = ""
    if record.get("status") != "ok":
        text += "<p><b>No valid result to interpret from this command.</b> Earlier stored results must not be used as its p-value.</p>"
    elif key not in ("vif", "iv", "firststage"):
        p = engine.r.get("p")
        if isinstance(p, (int, float)) and math.isfinite(p) and 0 <= p <= 1:
            formatted = "&lt; 0.0001" if p < .0001 else f"= {p:.6g}"
            decision = "reject" if p < .05 else "do not reject"
            details = []
            for field, label in (("chi2", "Chi-square"), ("F", "F"), ("t", "t"), ("Zt", "ADF statistic"),
                                 ("df", "df"), ("df_m", "numerator df"), ("df_r", "denominator df"), ("df_t", "df")):
                value = engine.r.get(field)
                if isinstance(value, (int, float)) and math.isfinite(value):
                    details.append(f"{label} = {value:.6g}")
            if key == "wald" and record.get("canonical") == "lincom":
                value = engine.r.get("estimate")
                if isinstance(value, (int, float)) and math.isfinite(value):
                    details.append(f"Reported estimate = {value:.6g}")
            if key in ("wald", "ttest") and {"lb", "ub"}.issubset(engine.r):
                low, high = engine.r["lb"], engine.r["ub"]
                if all(isinstance(x, (int, float)) and math.isfinite(x) for x in (low, high)):
                    details.append(f"Reported confidence interval = [{low:.6g}, {high:.6g}]")
            text += "<p>" + escape("; ".join(details)) + "</p>" if details else ""
            text += (f"<h3>Your test result</h3><p><b>p {formatted}.</b> Using 5% as an illustrative significance level, {decision} the stated null. "
                     "The comparison uses the unrounded p-value. A p-value is not the probability that the null is true. Choose your threshold before examining results.</p>")
            if key == "hausman":
                # Hausman can compare other estimators: never label them FE/RE by name alone.
                names = record.get("command", "").split()[1:3]
                fits = [engine.stored.get(name) for name in names]
                panel_pair = (len(fits) == 2 and all(m is not None and m.command == "xtreg" for m in fits)
                              and getattr(fits[0].result.model, "entity_effects", False)
                              and type(fits[1].result.model).__name__ == "RandomEffects" and not (fits[1].metadata or {}).get("cre_means"))
                if panel_pair:
                    text += f"<p>{escape(guide.reject if p < .05 else guide.retain)}</p>"
                else:
                    text += "<p>This is a general Hausman comparison. Its null requires no systematic difference and the second estimator to be efficient under that null. The FE/RE interpretation below applies only when the stored models are actually FE followed by RE; model names alone do not establish this.</p>"
            else:
                text += f"<p>{escape(guide.reject if p < .05 else guide.retain)}</p>"
    return text + test_guide_html(guide)
