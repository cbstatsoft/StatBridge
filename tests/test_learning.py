# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
import copy
from html import unescape
import pandas as pd
import pytest
from statbridge.engine import Engine
from statbridge.learning import LESSONS, check_lesson, explain_current, lesson_html


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda x: x.key)
def test_lessons_and_solutions_execute_and_check_without_mutation(lesson, tmp_path):
    e = Engine(cwd=tmp_path)
    assert e.run(lesson.script), [
        (v["kind"], v["text"]) for v in e.events if v["kind"] == "error"
    ]
    assert e.run(lesson.solution), [v["text"] for v in e.events if v["kind"] == "error"]
    data = e.df.copy()
    revision = e.revision
    rng = copy.deepcopy(e.rng.bit_generator.state)
    ledger = copy.deepcopy(e.ledger)
    passed, message = check_lesson(e, lesson)
    assert passed, message
    pd.testing.assert_frame_equal(data, e.df)
    assert revision == e.revision
    assert rng == e.rng.bit_generator.state
    assert ledger == e.ledger
    assert "Compatibility" in lesson_html(lesson)
    assert lesson.solution.splitlines()[0] in unescape(lesson_html(lesson, True))
    assert "This command" in explain_current(e)


def test_learning_check_does_not_replace_personal_data(tmp_path):
    e = Engine(cwd=tmp_path)
    e.df = pd.DataFrame({"own_data": [12.0, 24.0]})
    original = e.df.copy()
    passed, _ = check_lesson(e, LESSONS[0])
    assert not passed
    pd.testing.assert_frame_equal(original, e.df)


def test_explanations_escape_user_input_and_distinguish_odds(tmp_path):
    e = Engine(cwd=tmp_path)
    e.ledger = [
        {
            "canonical": "bad",
            "command": "<script>alert(1)</script>",
            "status": "error",
            "error": "<b>not HTML</b>",
        }
    ]
    text = explain_current(e)
    assert "<script>" not in text and "&lt;script&gt;" in text


def test_learning_check_handles_removed_exercise_variables(tmp_path):
    e = Engine(cwd=tmp_path)
    lesson = LESSONS[3]
    assert e.run(lesson.script + lesson.solution + "\ndrop x")
    passed, message = check_lesson(e, lesson)
    assert not passed and "variables have changed" in message


@pytest.mark.parametrize("lesson", LESSONS[8:], ids=lambda x: x.key)
def test_new_exercises_do_not_pass_before_attempt(lesson, tmp_path):
    e = Engine(cwd=tmp_path)
    assert e.run(lesson.script)
    assert not check_lesson(e, lesson)[0]


def test_hausman_interpretation_and_invalid_comparison(tmp_path):
    e = Engine(cwd=tmp_path)
    lesson = next(x for x in LESSONS if x.key == "hausman")
    assert e.run(lesson.script + lesson.solution)
    before = copy.deepcopy((e.r, e.ledger, e.rng.bit_generator.state))
    text = explain_current(e)
    assert "Your test result" in text and "Evidence against the RE restrictions" in text
    assert (e.r, e.ledger, e.rng.bit_generator.state) == before
    e.r["p"] = .30
    text = explain_current(e)
    assert "do not reject" in text and "does not prove RE is valid" in text
    e.r["p"] = 0
    assert "p &lt; 0.0001" in explain_current(e)
    assert e.run("xtreg y x, fe vce(cluster id)\nestimates store fixed")
    assert not e.run("hausman fixed random")
    text = explain_current(e)
    assert "No valid result" in text and "Your test result" not in text
    assert "robust or clustered" in text


@pytest.mark.parametrize("p", [float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_pvalue_never_yields_decision(p, tmp_path):
    e = Engine(cwd=tmp_path)
    e.ledger = [{"canonical": "test", "command": "test x", "status": "ok"}]
    e.r = {"p": p}
    assert "Your test result" not in explain_current(e)


def test_reference_commands_cannot_use_stale_pvalue(tmp_path):
    e = Engine(cwd=tmp_path)
    e.r = {"p": .001}
    for cmd, raw in [("estat", "estat vif"), ("estat", "estat ic"), ("ivregress", "ivregress 2sls y (x = z)")]:
        e.ledger = [{"canonical": cmd, "command": raw, "status": "ok"}]
        assert "Your test result" not in explain_current(e)


def test_generic_hausman_does_not_assume_panel_models(tmp_path):
    e = Engine(cwd=tmp_path)
    e.ledger = [{"canonical": "hausman", "command": "hausman a b", "status": "ok"}]
    e.r = {"p": .01}
    assert "general Hausman comparison" in explain_current(e)

