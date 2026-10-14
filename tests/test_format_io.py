# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
import datetime as dt
import json
import sqlite3
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pyreadstat
import pytest
from statbridge.engine import Engine
from statbridge.format_io import META_KEY


def run(e, text):
    assert e.execute(text), "\n".join(x["text"] for x in e.events[-5:])
    return e.df


def sample(tmp_path):
    e = Engine(cwd=tmp_path)
    e.df = pd.DataFrame(
        {
            "id": [1.0, 2.0, 3.0],
            "score": [5.25, np.nan, 8.125],
            "name": ["Ann", "Béa", ""],
        }
    )
    e.labels = {"score": "Test score", "id": "Student ID"}
    e.value_labels = {"id": {1.0: "First", 2.0: "Second"}}
    e.file_label = "Students"
    e.changed()
    return e


@pytest.mark.parametrize(
    "kind,ext",
    [
        ("sav", "sav"),
        ("sav", "zsav"),
        ("por", "por"),
        ("xport", "xpt"),
        ("stata", "dta"),
        ("parquet", "parquet"),
        ("feather", "feather"),
        ("arrow", "arrow"),
        ("rdata", "RData"),
        ("rds", "rds"),
        ("delimited", "csv"),
        ("delimited", "tsv"),
        ("json", "json"),
        ("jsonl", "jsonl"),
        ("sqlite", "sqlite"),
        ("workbook", "ods"),
    ],
)
def test_roundtrip(kind, ext, tmp_path):
    e = sample(tmp_path)
    # POR character conversion is limited by the underlying portable format.
    if kind == "por":
        e.df["name"] = ["Ann", "Bea", ""]
    original = e.df.copy()
    run(e, f'export {kind} using "data.{ext}"')
    assert e.df.equals(original)
    e2 = Engine(cwd=tmp_path)
    run(e2, f'import auto "data.{ext}"')
    if kind == "por":
        e2.df.columns = e2.df.columns.str.lower()
    assert list(e2.df) == list(original)
    np.testing.assert_allclose(
        e2.df.score.astype(float), original.score, equal_nan=True
    )
    assert e2.df.name.tolist() == original.name.tolist()
    if kind in ("sav", "stata", "parquet", "feather", "arrow"):
        assert e2.labels["score"] == "Test score"
        assert e2.value_labels["id"][1.0] == "First"


@pytest.mark.parametrize("kind", ["mat", "hdf5"])
def test_numeric_vectors_roundtrip(kind, tmp_path):
    e = sample(tmp_path)
    ext = "mat" if kind == "mat" else "h5"
    run(e, f'export {kind} id score using "data.{ext}"')
    run(e, f'use "data.{ext}", clear')
    assert list(e.df) == ["id", "score"]
    assert np.isnan(e.df.score.iloc[1])
    assert e.df.score.iloc[2] == 8.125


@pytest.mark.parametrize("kind", ["parquet", "feather", "arrow"])
def test_arrow_wide_nullable_integers_metadata_and_dates(kind, tmp_path):
    e = sample(tmp_path)
    e.df["big"] = pd.Series([2**60 + 1, None, 3], dtype="Int64")
    e.df["day"] = [0.0, 1.0, np.nan]
    e.formats["day"] = "%td"
    run(e, f'export {kind} using "data.{kind}", compression(zstd)')
    run(e, f'import {kind} "data.{kind}", clear')
    assert e.df.big.iloc[0] == 2**60 + 1 and pd.isna(e.df.big.iloc[1])
    assert e.formats["day"] == "%td"
    assert e.file_label == "Students"
    run(e, "summarize big")


@pytest.mark.parametrize(
    "kind,ext", [("sav", "sav"), ("xport", "xpt"), ("stata", "dta")]
)
def test_dates_convert_calendar_units(kind, ext, tmp_path):
    e = sample(tmp_path)
    e.df["day"] = [0.0, 21915.0, np.nan]
    e.df["clock"] = [1.0, 123456789.0, np.nan]
    e.formats.update(day="%td", clock="%tc")
    run(e, f'export {kind} using "dates.{ext}"')
    run(e, f'import auto "dates.{ext}", clear')
    np.testing.assert_allclose(e.df.day, [0.0, 21915.0, np.nan], equal_nan=True)
    np.testing.assert_allclose(
        e.df.clock, [1.0, 123456789.0, np.nan], equal_nan=True, atol=0.001
    )
    assert e.formats["day"] == "%td"


def test_external_parquet_temporal_and_factor(tmp_path):
    frame = pd.DataFrame(
        {
            "when": pd.to_datetime(["2020-01-01", None], utc=True),
            "group": pd.Categorical(["a", "b"], categories=["a", "b", "c"]),
        }
    )
    frame.to_parquet(tmp_path / "foreign.parquet", index=False)
    e = Engine(cwd=tmp_path)
    run(e, 'use "foreign.parquet"')
    assert e.formats["when"] == "%tc"
    assert e.df.group.tolist() == ["a", "b"]
    assert (
        e.df.when.iloc[0]
        == (pd.Timestamp("2020-01-01") - pd.Timestamp("1960-01-01")).total_seconds()
        * 1000
    )


def test_spss_user_missing_is_not_an_observation(tmp_path):
    pyreadstat.write_sav(
        pd.DataFrame({"x": [1.0, 99.0, np.nan]}),
        str(tmp_path / "missing.sav"),
        missing_ranges={"x": [99.0]},
    )
    e = Engine(cwd=tmp_path)
    run(e, 'import spss "missing.sav"')
    assert e.df.x.isna().tolist() == [False, True, True]


def test_preview_and_failure_leave_dataset_and_model_untouched(tmp_path):
    e = sample(tmp_path)
    model = e.model = object()
    rev = e.revision
    original = e.df.copy()
    run(e, 'export parquet using "data.parquet"')
    run(e, 'import parquet "data.parquet", preview rows(2)')
    assert len(e.results_table) == 2
    assert e.df.equals(original) and e.model is model and e.revision == rev
    assert not e.execute('import parquet "data.parquet"')  # dirty guard
    (tmp_path / "bad.json").write_text('[{"x":{"nested":true}}]')
    assert not e.execute('import json "bad.json", clear')
    assert e.df.equals(original) and e.model is model and e.revision == rev
    assert not e.execute('import parquet "data.parquet", clear nonsense')


def test_rename_and_metadata_validation(tmp_path):
    frame = pd.DataFrame({"bad name": [1], "bad-name": [2], "3rd": [3]})
    frame.to_parquet(tmp_path / "headers.parquet")
    e = Engine(cwd=tmp_path)
    assert not e.execute('use "headers.parquet"')
    run(e, 'import auto "headers.parquet", rename')
    assert list(e.df) == ["bad_name", "bad_name_2", "v_3rd"]
    table = pa.Table.from_pandas(pd.DataFrame({"x": [1]}))
    pq.write_table(
        table.replace_schema_metadata({META_KEY: b"{broken"}), tmp_path / "bad.parquet"
    )
    original = e.df.copy()
    assert not e.execute('import parquet "bad.parquet", clear')
    assert e.df.equals(original)


def test_subset_and_atomic_failure(tmp_path, monkeypatch):
    e = sample(tmp_path)
    run(e, 'export parquet id score if id > 1 using "subset.parquet"')
    loaded = pd.read_parquet(tmp_path / "subset.parquet")
    assert list(loaded) == ["id", "score"] and len(loaded) == 2
    (tmp_path / "protected.sav").write_bytes(b"original")

    def fail(*args, **kwargs):
        raise RuntimeError("writer failed")

    monkeypatch.setattr(pyreadstat, "write_sav", fail)
    assert not e.execute('export sav using "protected.sav", replace')
    assert (tmp_path / "protected.sav").read_bytes() == b"original"
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "protected.sav",
        "subset.parquet",
    ]


def test_wide_integer_refused_by_double_formats(tmp_path):
    e = sample(tmp_path)
    e.df["id"] = [2**60 + 1, 2, 3]
    for kind, ext in [
        ("sav", "sav"),
        ("stata", "dta"),
        ("rdata", "RData"),
        ("xport", "xpt"),
    ]:
        assert not e.execute(f'export {kind} using "bad.{ext}"')
        assert not (tmp_path / f"bad.{ext}").exists()


def test_rdata_object_selection(tmp_path, monkeypatch):
    import pyreadr

    e = sample(tmp_path)
    run(e, 'export rdata using "x.RData", object(students) compression(gzip)')
    assert "students" in pyreadr.read_r(str(tmp_path / "x.RData"))
    run(e, 'import rdata "x.RData", object(students) clear')
    original = e.df.copy()
    monkeypatch.setattr(
        pyreadr, "read_r", lambda *a, **k: {"first": original, "second": original}
    )
    assert not e.execute('import rdata "x.RData", clear')
    assert e.df.equals(original)
    run(e, 'import rdata "x.RData", clear object(second)')


def test_sqlite_requires_table_and_does_not_modify_input(tmp_path):
    path = tmp_path / "multi.db"
    with sqlite3.connect(path) as con:
        pd.DataFrame({"x": [1]}).to_sql("first", con, index=False)
        pd.DataFrame({"y": [2]}).to_sql("second table", con, index=False)
    original = path.read_bytes()
    e = Engine(cwd=tmp_path)
    assert not e.execute('import sqlite "multi.db"')
    run(e, 'import sqlite "multi.db", table("second table")')
    assert list(e.df) == ["y"] and path.read_bytes() == original


@pytest.mark.parametrize("ext", ["xlsx", "xls", "ods"])
def test_workbook_auto_import(ext, tmp_path):
    frame = pd.DataFrame({"id": [1, 2], "name": ["A", "B"]})
    path = tmp_path / f"book.{ext}"
    if ext == "xls":
        import xlwt

        book = xlwt.Workbook()
        sheet = book.add_sheet("Students")
        for i, row in enumerate([list(frame), *frame.values.tolist()]):
            for j, value in enumerate(row):
                sheet.write(i, j, value)
        book.save(str(path))
    else:
        frame.to_excel(path, index=False, sheet_name="Students")
    e = Engine(cwd=tmp_path)
    run(e, f'import auto "book.{ext}", sheet(Students)')
    assert e.df.name.tolist() == ["A", "B"]


def test_minitab_portable_numeric_columns(tmp_path):
    path = tmp_path / "legacy.mtp"
    path.write_text(
        "Minitab Portable Worksheet 1.1\n"
        + f'%{3:7d}{1:7d}{3:7d}{0:7d} {"score":8s}\n'
        + "1.234567890E+00 2.0 *\n"
        + f'%{3:7d}{2:7d}{3:7d}{0:7d} {"id":8s}\n'
        + "1 2 3\n"
    )
    e = Engine(cwd=tmp_path)
    run(e, 'use "legacy.mtp"')
    assert list(e.df) == ["score", "id"]
    assert e.df.score.iloc[0] == 1.23456789 and np.isnan(e.df.score.iloc[2])
    path.write_text(path.read_text().replace(f"%{3:7d}", f"%{4:7d}", 1))
    assert not e.execute('import mtp "legacy.mtp", clear')


def test_csv_duplicates_explicit_rename_and_json_wide_missing(tmp_path):
    e = Engine(cwd=tmp_path)
    (tmp_path / "duplicate.csv").write_text("id,id\n1,2\n")
    assert not e.execute('import delimited "duplicate.csv"')
    run(e, 'import delimited "duplicate.csv", rename')
    assert list(e.df) == ["id", "id_2"]
    (tmp_path / "large.json").write_text(json.dumps([{"id": 2**60 + 1}, {"id": None}]))
    run(e, 'import json "large.json", clear')
    assert int(e.df.id.iloc[0]) == 2**60 + 1 and pd.isna(e.df.id.iloc[1])


def test_hdf5_external_link_refused_and_foreign_group(tmp_path):
    import h5py

    with h5py.File(tmp_path / "vectors.h5", "w") as f:
        group = f.create_group("survey")
        group["id"] = np.array([1, 2])
        group["score"] = np.array([3.0, 4.0])
    e = Engine(cwd=tmp_path)
    run(e, 'import hdf5 "vectors.h5", group(survey)')
    assert list(e.df) == ["id", "score"]
    with h5py.File(tmp_path / "link.h5", "w") as f:
        f["other"] = h5py.ExternalLink("vectors.h5", "/survey/id")
    assert not e.execute('import hdf5 "link.h5", clear')


def test_r_date_text_has_fractional_seconds(tmp_path):
    e = Engine(cwd=tmp_path)
    e.df = pd.DataFrame({"clock": [1.0, 123456789.0]})
    e.formats = {"clock": "%tc"}
    run(e, 'export rds using "dates.rds"')
    run(e, 'import rds "dates.rds", clear')
    assert e.df.clock.tolist() == [
        "1960-01-01 00:00:00.001000",
        "1960-01-02 10:17:36.789000",
    ]
    assert not e.formats


def test_format_completion_and_paths(tmp_path):
    from statbridge.completion import Suggestions
    from statbridge.path_completion import path_completions

    c = Suggestions()
    c.variables = ["income", "age"]
    assert "import parquet" in c.candidates("import par")
    assert "export parquet income" in c.candidates("export parquet inc")
    assert 'export parquet using "x.parquet", compression(zstd)' in c.candidates(
        'export parquet using "x.parquet", compression(z'
    )
    assert 'import sav "x.sav", compression(' not in c.candidates(
        'import sav "x.sav", '
    )
    assert 'export xport using "x.xpt", version(8)' in c.candidates(
        'export xport using "x.xpt", version('
    )
    for name in ["dataset.parquet", "dataset.RData", "unrelated.do"]:
        (tmp_path / name).touch()
    result = path_completions('use "data', len('use "data'), tmp_path)
    assert {x[0] for x in result} == {'use "dataset.parquet"', 'use "dataset.RData"'}
    result = path_completions('import rdata "data', len('import rdata "data'), tmp_path)
    assert [x[0] for x in result] == ['import rdata "dataset.RData"']


def test_real_sas_fixture_including_pre1677_dates(tmp_path):
    from pathlib import Path

    path = Path(__file__).parent / "fixtures" / "readstat-sample.sas7bdat"
    e = Engine(cwd=tmp_path)
    run(e, f'import sas "{path.as_posix()}"')
    assert len(e.df) == 5
    assert e.df.mychar.tolist() == ["a", "b", "c", "d", "e"]
    assert e.formats["mydate"] == "%td"
    assert e.df.mydate.iloc[3] == (dt.date(1583, 1, 1) - dt.date(1960, 1, 1)).days
    assert e.df.mytime.iloc[0] == 36610000
    assert pd.isna(e.df.mydate.iloc[4])
    run(e, 'export xport using "sas-roundtrip.xpt"')
    original = e.df.copy()
    run(e, 'import xport "sas-roundtrip.xpt", clear')
    np.testing.assert_allclose(e.df.mydate, original.mydate, equal_nan=True)
