# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
import pandas as pd
import pytest
from statbridge.completion import Suggestions
from statbridge.engine import Engine


@pytest.fixture
def c():
    s = Suggestions()
    s.variables = ["income", "income_tax", "age", "region", "region_name", "weight"]
    s.variable_types = {
        v: "string" if v == "region_name" else "numeric" for v in s.variables
    }
    s.coefficients = ["_cons", "age", "income", "1.region"]
    s.estimates = ["fixed", "random"]
    s.local_names = ["controls"]
    s.global_names = ["data_root"]
    s.scalar_names = ["threshold"]
    s.result_names = {"r": ["N", "mean"], "e": ["N", "r2"]}
    return s


@pytest.mark.parametrize(
    "source, expected",
    [
        ("regress income a", "regress income age"),
        ("reg income a", "reg income age"),
        ("summarize inc", "summarize income"),
        ("summarize ", "summarize income"),
        ("encode reg", "encode region_name"),
        ("list reg", "list region_name"),
        ("generate log_income = ln(inc", "generate log_income = ln(income"),
        ("generate flag = inrange(age, inc", "generate flag = inrange(age, income"),
        ("replace inc", "replace income"),
        ("replace income = income + a", "replace income = income + age"),
        ("count if reg", "count if region_name"),
        ("quietly regress income a", "quietly regress income age"),
        ("cap qui regress income a", "cap qui regress income age"),
        ("bysort reg", "bysort region_name"),
        ("bysort region: summarize inc", "bysort region: summarize income"),
        ("regress income i.reg", "regress income i.region"),
        ("regress income i.region##c.a", "regress income i.region##c.age"),
        ("regress income L2.inc", "regress income L2.income"),
        ("generate change = D2.inc", "generate change = D2.income"),
        ("regress income age [aw=wei", "regress income age [aw=weight"),
        ("regress income age, vce(", "regress income age, vce(robust)"),
        ("regress income age, vce(cl", "regress income age, vce(cluster "),
        (
            "regress income age, vce(cluster reg",
            "regress income age, vce(cluster region)",
        ),
        ("ttest income, by(reg", "ttest income, by(region"),
        ("poisson income age, exposure(wei", "poisson income age, exposure(weight"),
        ("sum income, d", "sum income, detail"),
        ("glm income age, family(po", "glm income age, family(poisson)"),
        (
            "glm income age, family(binomial) link(pro",
            "glm income age, family(binomial) link(probit)",
        ),
        ("egen average = me", "egen average = mean("),
        ("egen average = mean(inc", "egen average = mean(income"),
        ("egen code = group(reg", "egen code = group(region_name"),
        ("collapse (me", "collapse (mean)"),
        ("collapse (mean) avg=inc", "collapse (mean) avg=income"),
        ("merge 1:", "merge 1:1"),
        ("merge m:1 reg", "merge m:1 region_name"),
        ("duplicates dr", "duplicates drop"),
        ("duplicates drop reg", "duplicates drop region_name"),
        ("rename inc", "rename income"),
        ("predict fitted, re", "predict fitted, residuals"),
        ("test a", "test age"),
        ("lincom inc", "lincom income"),
        ("display _b[1.reg", "display _b[1.region]"),
        ("display _se[a", "display _se[age]"),
        ("display r(me", "display r(mean)"),
        ("display e(sa", "display e(sample)"),
        ("regress income `con", "regress income `controls'"),
        ('use "${data', 'use "${data_root}'),
        ("set databackend po", "set databackend polars"),
        ("estimates restore fi", "estimates restore fixed"),
        ("hausman fixed ra", "hausman fixed random"),
    ],
)
def test_contexts_offer_relevant_completion(c, source, expected):
    assert expected in c.candidates(source)


@pytest.mark.parametrize(
    "source",
    [
        "generate inc",
        "predict inc",
        "rename age inc",
        "regress income age, level(",
        'histogram income, title("inc',
        "histogram income, bin(",
        "encode region_name, generate(inc",
        'save "data,inc',
        "use ",
        "merge m:1 region using ",
        'label variable income "if age',
        "set seed ",
        "regress income age // inc",
        "regress income age // $data",
        "* summarize inc",
    ],
)
def test_no_variable_suggestions_in_literal_or_new_name_positions(c, source):
    assert c.candidates(source) == []


def test_filter_types_used_variables_options_and_covariance_context(c):
    assert "regress income region_name" not in c.candidates("regress income reg")
    assert "summarize income income" not in c.candidates("summarize income ")
    assert "regress income age, vce(region)" not in c.candidates(
        "regress income age, vce("
    )
    assert c.candidates('save "file.dta", ro') == []
    assert "regress income age, robust vce(" not in c.candidates(
        "regress income age, robust "
    )
    assert "regress income age, vce(robust) robust" not in c.candidates(
        "regress income age, vce(robust) "
    )
    assert "regress income age [aw=weight], vce(hc2)" not in c.candidates(
        "regress income age [aw=weight], vce("
    )
    assert c.candidates("glm income age, family(poisson) link(pro") == []
    assert "egen average = mean(region_name" not in c.candidates(
        "egen average = mean(reg"
    )
    assert "scatter income age region" not in c.candidates("scatter income age reg")


def test_history_cannot_override_argument_context(c):
    c.history = [
        "regress removed oldvar, robust",
        "regress income region_name",
        'save "data.dta", robust',
    ]
    assert c.candidates("reg")[0] == c.history[1]
    assert "regress income region_name" not in c.candidates("regress income reg")
    assert c.candidates('save "data.dta", ro') == []


def test_cursor_replacement_preserves_remaining_command_and_closer(c):
    text = "regress inc age, vce(robust)"
    result = next(
        x
        for x in c.complete(text, len("regress inc"))
        if x.text == "regress income age, vce(robust)"
    )
    assert result.cursor == len("regress income")
    text = "regress incXXX age"
    assert "regress income age" in c.candidates(text, len("regress inc"))
    text = "regress income age, vce(cluster reg)"
    assert "regress income age, vce(cluster region)" in c.candidates(
        text, len(text) - 1
    )
    assert not any("))" in x for x in c.candidates(text, len(text) - 1))


def test_metadata_tracks_renames_drops_models_and_types(tmp_path):
    e = Engine(cwd=tmp_path)
    e.df = pd.DataFrame(
        {
            "income": [1.0, 2.0, 3.0, 5.0],
            "age": [1.0, 3.0, 4.0, 5.0],
            "name": ["a", "b", "c", "d"],
        }
    )
    c = Suggestions()
    c.sync(e)
    assert "encode name" in c.candidates("encode na")
    assert c.candidates("regress income na") == []
    assert e.run("regress income age\nestimates store fitted")
    c.sync(e)
    assert "display _b[age]" in c.candidates("display _b[a")
    assert "estimates restore fitted" in c.candidates("estimates restore fi")
    assert e.run("rename age years\ndrop name")
    c.sync(e)
    assert not c.candidates("regress income ag")
    assert not c.candidates("encode na")
    assert not c.candidates("display _b[a")
    assert "regress income years" in c.candidates("regress income ye")


def test_numeric_factor_coefficient_and_mid_command_history(c):
    assert "test 1.region" in c.candidates("test 1.reg")
    c.history = ["regress income age, robust"]
    assert set(c.candidates("regXXX income age", 3)) == {"regress income age", "reghdfe income age"}


@pytest.mark.parametrize('source,expected',[
('mean inc','mean income'),('ci means inc','ci means income'),('mlogit region a','mlogit region age'),
('stset age, failure(reg','stset age, failure(region'),('stcox age, strata(reg','stcox age, strata(region'),
('svyset region [pw=wei','svyset region [pw=weight'),('svy, subpop(reg','svy, subpop(region'),
('svy: me','svy: mean'),('svy: mean inc','svy: mean income'),
('svy, subpop(region): regress income a','svy, subpop(region): regress income age'),
('graph box inc','graph box income'),('graph box income, ov','graph box income, over('),
('sts test reg','sts test region'),('newey income age, la','newey income age, lag('),
])
def test_new_workflow_completion(c,source,expected):
    assert expected in c.candidates(source)


def test_category_outcome_completion(c):
    c.outcomes=['2','5','9'];assert 'predict p, outcome(2)' in c.candidates('predict p, outcome(2');assert not c.candidates('sts test region, by')
