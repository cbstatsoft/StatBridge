# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Offline, optional student lessons and transparent, non-mutating self-checks."""

from __future__ import annotations
from dataclasses import dataclass, replace
from html import escape
import numpy as np


@dataclass(frozen=True)
class Lesson:
    key: str
    title: str
    objective: str
    explanation: str
    setup: str
    task: str
    hint: str
    solution: str
    compatibility: str
    reflection: str = "What does this result tell you, and what does it leave unanswered?"
    answer: str = "Describe the result in its original units, state the assumptions, and distinguish evidence from proof."
    category: str = "Foundations"

    @property
    def script(self):
        return (
            "* "
            + self.title
            + "\n* Synthetic teaching data. This replaces data in memory.\n"
            + 'clear all\nlabel data "StatBridge lesson: '
            + self.key
            + '"\n'
            + self.setup.rstrip()
            + "\n\n* YOUR TURN: "
            + self.task
            + "\n"
        )


LESSONS = [
    Lesson(
        "summaries",
        "1. Data and summary statistics",
        "Read observations, variables, means and standard deviations.",
        "Each row is an observation and each column a variable. summarize reports the number of nonmissing observations, mean, sample standard deviation and range. The standard deviation describes spread, not the uncertainty of the mean.",
        'set obs 8\ngenerate score = 40 + 5*_n\nlabel variable score "Synthetic assessment score"\nlist score in 1/3',
        "Summarize score, then check your result.",
        "The command starts with summarize, followed by the variable name.",
        "summarize score",
        "The unweighted sample SD and ordinary percentile conventions are targeted. Storage precision can differ from Stata.",
    ),
    Lesson(
        "filters",
        "2. Conditions and subsets",
        "Use an if qualifier without deleting observations.",
        "count if score >= 60 counts only rows meeting the condition. A qualifier applies to one command; it does not remove other rows. Use == for an equality comparison and & to combine conditions.",
        "set obs 8\ngenerate score = 40 + 5*_n\nlist score",
        "Count observations with score at least 60.",
        "Use count with an if qualifier. There are five qualifying observations.",
        "count if score >= 60",
        "An if block makes a control-flow decision. An if qualifier filters rows for one command. They are different constructs.",
    ),
    Lesson(
        "missing",
        "3. The missing-value trap",
        "Exclude numeric missing values intentionally.",
        "In Stata, ordinary numeric missing (.) is larger than every finite number. Consequently x > 4 also includes missing x. Add x < . or !missing(x) when you intend to count observed values only.",
        "set obs 6\ngenerate x = _n\nreplace x = . in 3\nlist x\ncount if x > 4",
        "Count nonmissing x values greater than 4.",
        "Combine x > 4 with x < . using &.",
        "count if x > 4 & x < .",
        "StatBridge implements ordinary missing ordering. Extended tags .a through .z are not retained on import.",
    ),
    Lesson(
        "scripts",
        "4. Repeatable do-files",
        "Use a macro and a loop to create related variables.",
        "A do-file records the analysis so it can be rerun and reviewed. Local macros use a backtick and an apostrophe. Inside a forvalues loop, the macro changes at each iteration. Save the do-file as well as your results.",
        "set obs 5\ngenerate x = _n",
        "Create power1, power2 and power3 containing x, x squared and x cubed, using a loop.",
        "Use forvalues p = 1/3 {, then generate power`p' = x^`p', then close the brace.",
        "forvalues p = 1/3 {\n    generate power`p' = x^`p'\n}",
        "Simple local macros, nested loops, if/else and CR/semicolon delimiters are supported. The complete Stata programming language is not.",
    ),
    Lesson(
        "ols",
        "5. Interpret a regression",
        "Fit a slope and distinguish association from causation.",
        "regress outcome predictor fits a linear relationship and includes an intercept by default. A slope describes the fitted change in outcome for a one-unit increase in the predictor. A fitted association is not, by itself, a causal effect.",
        "set obs 30\ngenerate hours = _n/3\ngenerate score = 40 + 3*hours + 2*sin(_n)\nscatter score hours",
        "Regress score on hours.",
        "The outcome goes first, followed by predictors.",
        "regress score hours",
        "OLS coefficients are checked against direct least squares, but collinearity omissions and all Stata reporting details are not replicated.",
    ),
    Lesson(
        "robust",
        "6. Coefficients versus uncertainty",
        "Understand what robust standard errors change.",
        "Robust covariance changes estimated uncertainty when error variance is not constant. It does not fix omitted-variable bias, reverse causality or a poor design. For this OLS specification, adding robust should leave the coefficients unchanged.",
        "set seed 123\nset obs 120\ngenerate x = 1 + 4*runiform()\ngenerate y = 2 + 1.5*x + x*rnormal()\nregress y x\nestimates store ordinary",
        "Fit the same regression with robust standard errors.",
        "Add , vce(robust) to regress y x.",
        "regress y x, vce(robust)",
        "OLS robust uses HC1 and residual-degree-of-freedom t inference. Robust covariance is not a universal remedy for model misspecification.",
    ),
    Lesson(
        "weights",
        "7. Choose the right weight",
        "Distinguish repeated observations from survey weights.",
        "A frequency weight represents a count of identical observations. Analytic weights instead describe relative precision, while probability weights describe inverse selection probabilities. These meanings are not interchangeable. Frequency-weighted N equals the sum of the retained counts.",
        "set obs 12\ngenerate x = _n\ngenerate y = 2 + .7*x + sin(x)\ngenerate frequency = 1 + mod(_n,3)\nlist x y frequency",
        "Regress y on x using frequency as a frequency weight.",
        "Place [fw=frequency] after the variable list.",
        "regress y x [fw=frequency]",
        "Frequency covariance and sample size are checked against explicitly replicated rows. Probability weights alone do not specify strata, clusters or a finite-population correction.",
    ),
    Lesson(
        "panel",
        "8. Panel fixed effects",
        "Estimate within-panel associations and cluster uncertainty.",
        "xtset declares the panel identifier and time variable. Fixed effects use variation within each panel, removing time-invariant panel intercepts. Year indicators account for common period differences. Clustering by panel permits within-panel error correlation, but inference can be unreliable with few clusters.",
        "set seed 871\nset obs 240\ngenerate id = ceil(_n/6)\ngenerate year = 2010 + mod(_n-1,6)\nbysort id: generate effect = rnormal() if _n == 1\nbysort id: replace effect = effect[1]\ngenerate x = 3 + effect + rnormal()\ngenerate y = 1 + .8*x + effect + .2*(year-2010) + rnormal()",
        "Declare id and year, then fit fixed effects with x, year indicators and clustering by id.",
        "Use xtset id year, followed by xtreg y x i.year, fe vce(cluster id).",
        "xtset id year\nxtreg y x i.year, fe vce(cluster id)",
        "linearmodels FE covariance, residual degrees of freedom and R-squared reporting can differ from Stata xtreg. Read the compatibility notice before comparing outputs.",
    ),
]


from .learning_extra import extra_lessons, check_extra
from .learning_roadmap import roadmap_lessons, check_roadmap
from .learning_reference import interpretation_html

LESSONS = [replace(lesson, category="Models and interpretation") if lesson.key in ("ols", "robust", "weights", "panel") else lesson for lesson in LESSONS]
LESSONS.extend(extra_lessons(Lesson))
LESSONS.extend(roadmap_lessons(Lesson))


from pathlib import Path
_databank_samples = Path(__file__).resolve().parent / "sample_data"
LESSONS.append(Lesson(
    "databank", "25. Merge World Bank indicator files",
    "Identify unmatched indicators and declare a country-year panel.",
    "The setup uses dtabnk to reshape and merge two synthetic indicator files. An outer merge keeps every country-year key. Missing indicator values stay missing; they are not zero. Numeric panel IDs encode countries, not a ranking.",
    f'dtabnk "{(_databank_samples / "gdp.csv").as_posix()}" "{(_databank_samples / "life_expectancy.csv").as_posix()}", merge clear\nlabel data "StatBridge lesson: databank"',
    "Encode Country into country_id and declare the panel with Year as the time variable. Inspect which countries lack each indicator.",
    "Use encode Country, generate(country_id), then xtset country_id Year. Inspect list to see unmatched indicators.",
    "encode Country, generate(country_id)\nxtset country_id Year\nlist",
    "Synthetic data, not actual World Bank observations. dtabnk is a StatBridge extension using Polars and validated one-to-one joins. Duplicate source keys are rejected unless averaging is explicit. No remote downloads occur.",
    reflection="Would replacing unmatched indicators with zero fix missing data?",
    answer="No. An unmatched or unavailable observation is not an observed zero. Investigate source coverage, units, definitions, country identifiers and time periods before analysis.",
    category="Data preparation",
))


LESSONS.append(Lesson(
    "file_formats", "26. Check what survives a file conversion",
    "Distinguish numeric data from labels and date display formats.",
    "A file can open successfully while losing labels, date units or missing-value distinctions. Parquet stores StatBridge metadata in its schema; other applications may discard it. A preview does not replace the active dataset. This exercise writes a small file in the working directory; choose a new name if it already exists.",
    'set obs 4\ngenerate id = _n\ngenerate day = 21915 + id\nformat day %td\nlabel variable day "Visit date"',
    "Export the data to lesson-formats.parquet, then import it back and confirm that Visit date and %td survive.",
    'Use export parquet using "lesson-formats.parquet", then import parquet "lesson-formats.parquet", clear. Read the compatibility notice.',
    'export parquet using "lesson-formats.parquet"\nimport parquet "lesson-formats.parquet", clear\ndescribe',
    "StatBridge metadata survives this round trip; this does not guarantee that other Parquet tools preserve it. R export writes daily/clock dates as ISO strings; text exports lose date-format metadata.",
    reflection="Does a successful import prove that the analysis will be identical?",
    answer="No. Check observation counts, identifiers, types, dates, labels, units and missing values. Model defaults and algorithms can still differ between applications.",
    category="Data preparation",
))


from .learning_coverage import coverage_lessons, check_coverage
LESSONS.extend(coverage_lessons(Lesson))

def lesson_html(lesson, reveal=False):
    h = lambda s: escape(s).replace("\n", "<br>")
    text = f"<h2>{h(lesson.title)}</h2><p><b>Goal:</b> {h(lesson.objective)}</p><p>{h(lesson.explanation)}</p><h3>Try it</h3><p>{h(lesson.task)}</p><p><b>Hint:</b> {h(lesson.hint)}</p>"
    text += f"<h3>Think it through</h3><p>{h(lesson.reflection)}</p>"
    if reveal:
        text += f"<h3>Suggested solution</h3><pre>{escape(lesson.solution)}</pre><p>Try changing one part and predict what will happen before running it.</p>"
        text += f"<h3>Interpretation notes</h3><p>{h(lesson.answer)}</p>"
    text += f"<h3>Compatibility</h3><p>{h(lesson.compatibility)}</p><hr><p>Examples are synthetic. Opening an example only fills the do-file editor. Running its setup replaces data in memory, so save your current dataset first.</p>"
    return text


def check_lesson(engine, lesson):
    if engine.file_label != "StatBridge lesson: " + lesson.key:
        return (
            False,
            "Open this example in the editor and run its setup first. Your current dataset has not been changed.",
        )
    k = lesson.key
    df = engine.df
    m = engine.model
    required = {
        "summaries": {"score"},
        "filters": {"score"},
        "missing": {"x"},
        "scripts": {"x"},
        "ols": {"score", "hours"},
        "robust": {"x", "y"},
        "weights": {"x", "y", "frequency"},
        "panel": {"id", "year", "x", "y"},
    }.get(k, set())
    if not required.issubset(df.columns):
        return (
            False,
            "The exercise variables have changed. Reopen and run its setup, then try the task again.",
        )
    if k == "summaries":
        passed = engine.r.get("N") == 8 and np.isclose(
            engine.r.get("mean", np.nan), 62.5
        )
    elif k == "filters":
        passed = engine.r.get("N") == 5
    elif k == "missing":
        passed = engine.r.get("N") == 2
    elif k == "scripts":
        passed = all(
            f"power{p}" in df and np.allclose(df[f"power{p}"], df.x**p)
            for p in (1, 2, 3)
        )
    elif k == "ols":
        passed = (
            m is not None
            and m.command == "regress"
            and list(m.x.columns) == ["_cons", "hours"]
            and len(m.sample) == 30
        )
    elif k == "robust":
        passed = (
            m is not None
            and m.command == "regress"
            and m.covariance == "robust"
            and list(m.x.columns) == ["_cons", "x"]
            and len(m.sample) == 120
        )
    elif k == "weights":
        passed = (
            m is not None
            and m.weight_type == "fw"
            and m.nobs == df.frequency.sum()
            and list(m.x.columns) == ["_cons", "x"]
        )
    elif k == "file_formats":
        passed = len(df) == 4 and engine.labels.get("day") == "Visit date" and engine.formats.get("day") == "%td" and any(r["canonical"] == "import" and r["status"] == "ok" and "lesson-formats.parquet" in r["command"] for r in engine.ledger)
    elif k == "databank":
        passed = (engine.panel == ("country_id", "Year") and len(df) == 9
                  and {"Country", "GDP", "Life_expectancy", "country_id"}.issubset(df.columns)
                  and df.GDP.isna().sum() == 3 and df.Life_expectancy.isna().sum() == 3)
    elif k == "panel":
        passed = (
            m is not None
            and m.command == "xtreg"
            and bool(getattr(m.result.model, "entity_effects", False))
            and m.covariance == "cluster id"
            and "2011.year" in m.params
        )
    else:
        passed = check_extra(engine, k) or check_roadmap(engine, k) or check_coverage(engine,k)
    return bool(passed), (
        "Your current result matches the exercise check. Explain what the result means in your own words before moving on."
        if passed
        else "The current result does not yet match this check. Review the task and hint, run your command, then check again. This checks the result, not whether you understand the reasoning."
    )


def explain_current(engine):
    from .catalog import COMMANDS

    if not engine.ledger:
        return "<h3>This command</h3><p>Run a command to see a plain-language explanation here. Learning mode never changes an estimate.</p>"
    record = engine.ledger[-1]
    cmd = record["canonical"]
    h = escape
    text = f"<h3>This command</h3><pre>{h(record['command'])}</pre>"
    if record["status"] not in ("ok", "running"):
        text += f"<p><b>The command did not complete.</b> {h(record.get('error', ''))}</p><p>Check the variable names, command syntax and declared panel/time variables. The Help menu lists implemented syntax. Earlier successful commands remain in memory.</p>"
        return text + interpretation_html(engine, record)
    definitions = {
        "summarize": "N counts nonmissing values. The mean describes the centre; the standard deviation describes spread. Different variables may have different N because of missing values.",
        "count": "This counts observations meeting the if/in conditions. It does not delete observations or estimate a model.",
        "generate": "This creates a new variable. The expression is evaluated over observations; _n is the observation number. Keep the distinction between assignment (=) and comparison (==).",
        "replace": "This modifies values in an existing variable. Use a qualifier if you intend to change only selected rows.",
        "xtset": "This declares panel structure; it does not estimate a model. The panel-time pair must be unique.",
        "tsset": "This declares a time index. Lags use time values and the declared delta, not simply the previous displayed row.",
        "predict": "These values come from the active fitted model. Eligible unweighted OLS can predict outside the estimation sample; other paths retain sample and data-revision restrictions. A residual is an observed value minus its fitted value.",
        "ttest": "This test compares means under the selected one-sample, paired or independent-sample assumptions. A small p-value is not a measure of practical importance.",
        "test": "This Wald test evaluates the specified coefficient restrictions using the fitted covariance. Restrictions can include zero values, nonzero values or coefficient equalities. Non-rejection does not establish that they are true.",
        "lincom": "This combines estimated coefficients and their covariances. Subtracting two standard errors is not the standard error of the difference.",
    }
    text += f"<p>{h(definitions.get(cmd, COMMANDS.get(cmd, ('', '', 'See the command reference for supported syntax.'))[2]))}</p>"
    m = engine.model
    if m is not None and cmd in (
        "regress",
        "areg",
        "anova",
        "xtreg",
        "logit",
        "logistic",
        "probit",
        "poisson",
        "nbreg",
        "qreg",
        "glm",
        "ivregress",
        "arima",
        "estimates",
    ):
        n = engine.e.get("N", len(m.sample))
        text += f"<h3>Read the output</h3><p><b>N = {n:g}.</b> This is the estimation sample size after exclusions; frequency weights count represented observations.</p><ul><li><b>Coefficient:</b> direction and magnitude on this model’s scale.</li><li><b>Standard error:</b> estimated sampling uncertainty, under the selected covariance assumptions.</li><li><b>Confidence interval:</b> a range from a procedure with the stated long-run coverage under its assumptions.</li><li><b>P-value:</b> the probability, under the tested null and model assumptions, of a statistic at least as extreme. It is not the probability that the null is true.</li></ul>"
        if m.command in ("regress", "xtreg", "ivregress"):
            text += "<p>Linear slopes describe conditional associations in outcome units. Design and identifying assumptions, rather than statistical significance alone, determine whether a causal interpretation is justified.</p>"
        elif m.command in ("logit", "logistic"):
            text += "<p>Logit coefficients are on the log-odds scale; logistic displays odds ratios. Neither is directly a percentage-point change in probability.</p>"
        text += f"<p><b>Covariance:</b> {h(m.covariance)}. Robust or clustered covariance does not remove bias in the coefficients.</p>"
    text += interpretation_html(engine, record)
    codes = set(record.get("notices", []))
    if codes:
        text += "<h3>Compatibility to consider</h3>"
        seen = set()
        for note in reversed(engine.notices):
            if note["code"] in codes and note["code"] not in seen:
                text += "<p>" + h(note["message"]) + "</p>"
                seen.add(note["code"])
    return text
