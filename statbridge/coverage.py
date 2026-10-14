# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Auditable workflow scope, not a measured percentage of Stata usage."""

NEW_COMMANDS = {
    "mean": (
        "mean varlist [if/in] [, over(group) level(#)]",
        "NumPy/SciPy",
        "Unweighted complete-case means, joint IID covariance and t(N-1) intervals. Group df conventions may differ.",
    ),
    "total": (
        "total varlist [if/in] [, over(group) level(#)]",
        "NumPy/SciPy",
        "Unweighted sample totals and joint IID covariance. Use svy for population-weighted totals.",
    ),
    "proportion": (
        "proportion varlist [if/in] [, over(group) level(#)]",
        "NumPy/SciPy",
        "Categorical proportions, joint covariance, symmetric t intervals. Use ci proportions for exact/Wilson binary intervals.",
    ),
    "ci": (
        "ci means|proportions varlist [if/in] [, level(#) exact wilson]",
        "SciPy/statsmodels",
        "Variablewise Student-t mean intervals, exact Clopper-Pearson or Wilson binary proportion intervals.",
    ),
    "prtest": (
        "prtest binary = # | prtest binary, by(group) [level(#)]",
        "statsmodels",
        "Independent asymptotic proportion z test; pooled null variance for two groups.",
    ),
    "sdtest": (
        "sdtest x = y | sdtest outcome, by(group) [level(#)]",
        "SciPy",
        "Independent normal-population variance-ratio F test and SD-ratio interval; not paired or robust.",
    ),
    "kwallis": (
        "kwallis outcome [if/in], by(group)",
        "SciPy",
        "Tie-corrected Kruskal-Wallis H, asymptotic chi-square p-value.",
    ),
    "tab1": (
        "tab1 varlist [if/in] [, missing]",
        "pandas",
        "Separate one-way frequency tables.",
    ),
    "tab2": (
        "tab2 varlist [if/in] [, missing chi2 row col]",
        "pandas/SciPy",
        "Pairwise two-way tables, at most 20 variables.",
    ),
    "inspect": (
        "inspect [varlist]",
        "pandas",
        "Missingness, distinct counts and numeric sign counts.",
    ),
    "compare": (
        "compare x y",
        "pandas",
        "Counts of equal, different and missing observations.",
    ),
    "fillin": (
        "fillin varlist",
        "pandas",
        "Add absent combinations of observed categories; _fillin marks additions. Original duplicates retained, two-million-combination cap.",
    ),
    "ipolate": (
        "ipolate y x [if/in], generate(new) [epolate]",
        "NumPy",
        "Linear interpolation, repeated x uses mean observed y; explicit extrapolation. Supports bysort grouping.",
    ),
    "tsfill": (
        "tsfill [, full]",
        "pandas",
        "Fill declared time grid, with missing non-key values; full uses common panel range.",
    ),
    "xtdescribe": (
        "xtdescribe",
        "pandas",
        "Panel counts, min/mean/max observations per panel; no pattern diagrams.",
    ),
    "xtsum": (
        "xtsum [varlist] [if/in]",
        "pandas",
        "Overall, between and within spread; between SD uses unweighted panel means.",
    ),
    "newey": (
        "newey y predictors [if/in], lag(#) [noconstant level(#)]",
        "statsmodels HAC",
        "Bartlett HAC, N/(N-k) correction, t inference. Single regular complete time series only.",
    ),
    "mlogit": (
        "mlogit outcome predictors [if/in] [, baseoutcome(#) rrr level(#)]",
        "statsmodels MNLogit",
        "Unweighted ML, model-based covariance. Most frequent base category; no margins or robust VCE.",
    ),
    "ologit": (
        "ologit outcome predictors [if/in] [, level(#)]",
        "statsmodels OrderedModel",
        "Proportional-odds ML, latent-scale thresholds and transformed covariance; no robust VCE/margins.",
    ),
    "oprobit": (
        "oprobit outcome predictors [if/in] [, level(#)]",
        "statsmodels OrderedModel",
        "Ordered probit ML, transformed latent thresholds, model-based covariance only.",
    ),
    "stset": (
        "stset duration, failure(binary_or_expression) [id(subject) scale(#)] | stset, clear",
        "pandas",
        "Single-record right-censored origin-zero survival declaration. No delayed entry or time-varying records.",
    ),
    "stsum": (
        "stsum [, by(group)]",
        "statsmodels",
        "Counts, failures, risk-time and Kaplan-Meier median.",
    ),
    "sts": (
        "sts list|graph [, by(group)] | sts test group",
        "statsmodels/matplotlib",
        "Kaplan-Meier, Greenwood SEs, log-rank test. No confidence bands or censor marks.",
    ),
    "stcox": (
        "stcox predictors [if/in] [, ties(breslow|efron) strata(group) nohr level(#)]",
        "statsmodels PHReg",
        "Cox partial likelihood, model-based covariance, hazard ratios by default; no PH diagnostic or robust VCE.",
    ),
    "svyset": (
        "svyset [psu] [pw=weight] [, strata(group)] | svyset, clear",
        "NumPy/pandas",
        "One-stage with-replacement design. No FPC, multistage, replicate weights or singleton adjustment.",
    ),
    "svy": (
        "svy [, subpop(indicator)]: mean|total|proportion|regress varlist [, level(#)]",
        "NumPy/SciPy",
        "Taylor stratified-PSU covariance, PSU-minus-strata t df. Domains retain full design; no nonlinear survey estimators.",
    ),
    "coverage": (
        "coverage",
        "StatBridge",
        "Audited workflow scope and remaining gaps. Command count is not usage coverage.",
    ),
}
WORKFLOWS = [
    (
        "Files and reproducibility",
        "DTA/DO, SPSS, SAS import/XPORT export, R, Arrow/Parquet, Excel, text, SQLite; logs/macros/loops",
        "Bounded scripting and format variants; no full ado/program interpreter",
    ),
    (
        "Clean and reshape",
        "Generate/replace, egen, dates, merge/append, reshape/collapse, recode, missingness, interpolation",
        "Bounded functions and merge/reshape options",
    ),
    (
        "Describe and compare",
        "Tables, correlations, means/totals/proportions/CI, t/rank/proportion/variance tests, one-way ANOVA",
        "No full factorial/repeated ANOVA or multiple-comparison suite; mostly unweighted",
    ),
    (
        "Regression",
        "OLS/weighted OLS, binary/count/GLM/quantile, multinomial/ordered, predictions, Wald tests, tables",
        "Margins OLS/logit/probit only; new categorical models model-based VCE only",
    ),
    (
        "Panel and causal",
        "FE/RE/CRE, absorbed effects, IV2SLS, Hausman/Mundlak/IV diagnostics, two-period DiD",
        "No dynamic-panel GMM, staggered DiD, matching or general treatment-effects suite",
    ),
    (
        "Time series",
        "Time operators, tsfill, ARIMA, ADF, Newey-West",
        "No VAR/VECM, ARCH/GARCH, seasonal ARIMA or full forecasting",
    ),
    (
        "Survey",
        "One-stage stratified-PSU means/totals/proportions/linear regression and subpopulations",
        "No FPC/multistage/replicate/singleton designs or survey logit",
    ),
    (
        "Survival",
        "Right-censored stset, KM, log-rank, Cox with strata and tie handling",
        "No delayed entry, time-varying records, parametric survival, competing risks or PH diagnostic",
    ),
    (
        "Graphs and reporting",
        "Histogram, scatter/line/lfit, box/bar, layers, marginsplot, tables and export",
        "Bounded styling; no full graph editor or collect/putdocx",
    ),
    (
        "Specialist methods",
        "PCA and bounded bootstrap",
        "Mixed/multilevel, multiple imputation, SEM, Bayesian and general multivariate suite absent",
    ),
]
