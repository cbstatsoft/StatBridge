# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
from pathlib import Path
import os
import pandas as pd
import pytest
from statbridge.engine import Engine
from statbridge.completion import Suggestions
from statbridge.syntax import words


def output(e):
    return "\n".join(x["text"] for x in e.events if x["kind"] == "output")


@pytest.fixture
def session(tmp_path):
    e = Engine(cwd=tmp_path)
    (tmp_path / "Test Pack").mkdir()
    (tmp_path / "Test Pack" / "test_analysis.do").write_text('display "found script"')
    (tmp_path / "student_panel.dta").write_bytes(b"not a real DTA")
    (tmp_path / "other.txt").write_text("hello")
    (tmp_path / ".hidden").write_text("hidden")
    return e


@pytest.mark.parametrize("command", ["ls", "dir", "ls -lh", 'ls "."'])
def test_listing_aliases_names_sizes_and_no_data_changes(session, command):
    e = session
    e.df = pd.DataFrame({"x": [1.0, 2.0]})
    before = e.df.copy()
    revision = e.revision
    cwd = Path.cwd()
    assert e.execute(command)
    text = output(e)
    assert "Test Pack/" in text and "student_panel.dta" in text and "5 B" in text
    assert ".hidden" not in text
    assert e.r["N"] == 3
    pd.testing.assert_frame_equal(e.df, before)
    assert e.revision == revision and Path.cwd() == cwd


@pytest.mark.parametrize("command", ["ls -a", "ls -lah", "ls, all"])
def test_hidden_entries(session, command):
    assert session.execute(command)
    assert ".hidden" in output(session)


def test_globs_and_quoted_folders(session):
    e = session
    assert e.execute('ls "*.dta"')
    assert e.r["N"] == 1
    assert e.execute('ls "Test Pack/*.do"')
    assert "test_analysis.do" in output(e)
    assert e.execute('ls "Test Pack"')
    assert e.r["N"] == 1
    assert e.execute('ls "*.missing"')
    assert e.r["N"] == 0
    assert not e.execute("ls -z")


def test_cd_parent_previous_and_home(session):
    e = session
    root = e.cwd
    assert e.execute('cd "Test Pack"')
    assert e.cwd == root / "Test Pack"
    assert e.execute("pwd")
    assert e.execute("cd ..")
    assert e.cwd == root
    assert e.execute("cd -")
    assert e.cwd == root / "Test Pack"
    assert e.execute("chdir ~")
    assert e.cwd == Path.home().resolve()
    old = e.cwd
    assert not e.execute('cd "not-a-real-directory-203894029"')
    assert e.cwd == old
    assert e.execute("cd")


def test_nested_file_discovery_then_run(session):
    e = session
    assert e.execute('findfile "test_analysis.do"')
    assert e.r["N"] == 1 and e.r["fn"].endswith("test_analysis.do")
    assert "Test Pack" in output(e) and 'cd "' in output(e)
    assert e.execute('cd "Test Pack"')
    assert e.execute('do "test_analysis.do"')
    assert "found script" in output(e)


def test_missing_do_and_dataset_have_navigation_hint(session):
    e = session
    for command in ['do "test_analysis.do"', 'use "absent.dta", clear']:
        assert not e.execute(command)
        assert e.scalars["_rc"] == 601
        assert (
            "findfile" in e.events[-1]["text"]
            and "Working directory:" in e.events[-1]["text"]
        )


def test_find_limits_and_ambiguous_matches(session):
    e = session
    assert not e.execute('findfile "test_analysis.do", depth(0)')
    assert e.r["N"] == 0
    assert e.execute('findfile "*.do", depth(1)')
    (e.cwd / "test_analysis.do").write_text("display 2")
    assert e.execute('findfile "*.do"')
    assert e.r["N"] == 2 and "fn" not in e.r
    assert not e.execute('findfile "*.do", depth(50)')


def test_mkdir_and_existing_folder(session):
    e = session
    assert e.execute('mkdir "new folder"')
    assert (e.cwd / "new folder").is_dir()
    assert not e.execute('mkdir "new folder"')
    assert e.scalars["_rc"] == 602
    assert e.execute('mkdir "nested/inside", parents')
    assert (e.cwd / "nested/inside").is_dir()


def test_no_recursive_symlink_traversal(session):
    e = session
    try:
        (e.cwd / "Test Pack" / "loop").symlink_to(e.cwd, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation not available")
    assert e.execute('findfile "test_analysis.do", depth(12)')
    assert e.r["N"] == 1


def test_scan_cap_reports_truncation(session, monkeypatch):
    import statbridge.filesystem as fs

    monkeypatch.setattr(fs, "SCAN_LIMIT", 1)
    assert session.execute("ls")
    assert session.r["truncated"] == 1
    assert "limited" in output(session)


def test_path_completion_directories_file_types_and_suffix(session):
    c = Suggestions()
    c.sync(session)
    result = c.complete("cd Te")[0]
    assert result.text == 'cd "Test Pack/"'
    assert result.cursor == len(result.text) - 1
    assert c.candidates('do "Test Pack/te') == ['do "Test Pack/test_analysis.do"']
    assert c.candidates("use stu") == ['use "student_panel.dta"']
    assert not c.candidates("do stu")
    assert not c.candidates("cd stu")
    text = 'use "studXXX", clear'
    result = c.complete(text, len('use "stud'))[0]
    assert result.text == 'use "student_panel.dta", clear'
    assert c.candidates("ls -lh stu") == ['ls -lh "student_panel.dta"']
    assert 'save "student_panel.dta", replace' in c.candidates(
        'save "student_panel.dta", re'
    )


def test_completion_refreshes_after_cd(session):
    c = Suggestions()
    c.sync(session)
    assert c.candidates("do test") == []
    assert session.execute('cd "Test Pack"')
    c.sync(session)
    assert c.candidates("do test") == ['do "test_analysis.do"']


def test_windows_backslashes_are_literal():
    path = '"C:\\Users\\connor.baird\\Downloads\\Test Pack"'
    assert words(path) == [path]


@pytest.mark.skipif(os.name != "nt", reason="Native Windows path resolution")
def test_native_windows_path_resolution(session):
    path = str(session.cwd / "Test Pack")
    assert session.execute('cd "' + path + '"')
    assert session.execute("ls")
    assert "test_analysis.do" in output(session)
