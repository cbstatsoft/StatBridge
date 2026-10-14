# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Structured tables shared by desktop, terminal and atomic file export."""

from html import escape
import os
import tempfile
import re
import numpy as np
import pandas as pd
from scipy import stats
from .syntax import StataError, options, split_top, qualifiers, unquote


def atomic_write(engine, path, replace, writer):
    engine.write_guard(path, replace)
    fd, tmp = tempfile.mkstemp(suffix=path.suffix, dir=path.parent)
    os.close(fd)
    try:
        writer(tmp)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class ResultTables:
    def cmd_clear(self, args, opt):
        super().cmd_clear(args, opt)
        if args == "all":
            self.results_table = None
            self.margins_result = None

    def show_table(self, title, frame):
        self.results_table = frame.copy(deep=True)
        self.results_table_title = title
        html = (
            "<h3>"
            + escape(title)
            + "</h3>"
            + frame.to_html(
                escape=True, na_rep=".", border=0, float_format=lambda x: f"{x:.6g}"
            ).replace('<table class="dataframe">', '<table cellspacing="0" cellpadding="6">')
        )
        if not self.quiet:
            self.emit(
                "output",
                title
                + "\n"
                + frame.to_string(na_rep=".", float_format=lambda x: f"{x:.6g}"),
                {"html": html},
            )

    def export_table(self, specification, replace=False):
        pieces = split_top(specification)
        if len(pieces) > 2:
            raise StataError('export("file.csv|html|tex" [, replace])')
        if len(pieces) == 2:
            replace = "replace" in options(pieces[1], ("replace",))
        path = self.path(unquote(pieces[0]))
        table = getattr(self, "results_table", None)
        if table is None:
            raise StataError("No structured results table is available")
        suffix = path.suffix.lower()
        if suffix not in (".csv", ".html", ".htm", ".tex"):
            raise StataError("Results exports support .csv, .html and .tex")

        def writer(tmp):
            if suffix == ".csv":
                table.to_csv(tmp)
            elif suffix == ".tex":
                table.to_latex(tmp, escape=True, na_rep=".")
            else:
                from pathlib import Path

                Path(tmp).write_text(
                    '<!doctype html><meta charset="utf-8"><title>'
                    + escape(self.results_table_title)
                    + "</title>"
                    + "<style>body{font:15px sans-serif;margin:32px}table{border-collapse:collapse}th,td{padding:8px 12px;border-bottom:1px solid #ccc;text-align:right}th{text-align:left}</style>"
                    + "<h1>"
                    + escape(self.results_table_title)
                    + "</h1>"
                    + table.to_html(escape=True, na_rep="."),
                    encoding="utf-8",
                )

        atomic_write(self, path, replace, writer)
        self.out(f"Saved {path}")

    def cmd_etable(self, args, opt):
        if args.strip():
            raise StataError(
                'Syntax: etable [, estimates(names) level(#) export("file", replace)]'
            )
        o = options(opt, ("estimates", "level", "export", "replace"))
        names = str(o.get("estimates", "")).split()
        if names:
            if len(set(names)) != len(names) or any(
                n not in self.stored for n in names
            ):
                raise StataError("Specify unique stored estimate names")
            models = [(n, self.stored[n]) for n in names]
        else:
            models = [("Active model", self.require_model())]
        data = {}
        for name, model in models:
            level = float(o.get("level", model.level))
            if not 0 < level < 100:
                raise StataError("level() must be between 0 and 100")
            se = np.sqrt(np.diag(model.cov))
            dist = stats.t(model.df) if model.df is not None else stats.norm
            crit = dist.ppf((1 + level / 100) / 2)
            column = {}
            for term, b, s in zip(model.params.index, model.params, se):
                column.update(
                    {
                        term: b,
                        f"  SE: {term}": s,
                        f"  p: {term}": 2 * dist.sf(abs(b / s)),
                        f"  lower ({level:g}%): {term}": b - crit * s,
                        f"  upper ({level:g}%): {term}": b + crit * s,
                    }
                )
            column["N"] = model.nobs if model.nobs is not None else len(model.sample)
            column["R-squared"] = getattr(model.result, "rsquared", np.nan)
            data[name] = column
        self.show_table(
            "Estimation comparison (coefficients on fitted scale)", pd.DataFrame(data)
        )
        for name, model in models:
            self.out(
                f"{name}: {model.command}; covariance {model.covariance}; outcome {model.y.name}; df {model.df}"
            )
        if "export" in o:
            self.export_table(str(o["export"]), "replace" in o)
        elif "replace" in o:
            raise StataError("replace requires export()")

    def cmd_esttab(self, args, opt):
        o = options(opt, ("replace", "se", "level"))
        match = re.fullmatch(r"(.*?)\s+using\s+(.+)", " " + args)
        names, filename = (
            (match[1].strip(), match[2]) if match else (args.strip(), None)
        )
        options_text = (f"estimates({names}) " if names else "") + (
            f'level({o["level"]})' if "level" in o else ""
        )
        self.cmd_etable("", options_text)
        self.notice(
            "ESTTAB_SUBSET",
            "Bounded community esttab-style wrapper: coefficient, SE, p and interval rows. Full estout formatting syntax is not implemented.",
        )
        if filename:
            self.export_table(filename, "replace" in o)
        elif "replace" in o:
            raise StataError("replace requires using filename")

    def cmd_dtable(self, args, opt):
        o = options(opt, ("by", "export", "replace"))
        head, q = qualifiers(args)
        cols = self.varlist(head, default=True, numeric=True)
        frame = self.df.loc[self.mask(q)]
        groups = [(None, frame)]
        if "by" in o:
            by = self.varlist(str(o["by"]))
            if len(by) != 1:
                raise StataError("by() requires one group variable")
            groups = list(frame.groupby(by[0], dropna=True, sort=True))
        rows = []
        for group, part in groups:
            for c in cols:
                x = part[c].dropna()
                rows.append(
                    {
                        "Group": "All" if group is None else group,
                        "Variable": c,
                        "N": len(x),
                        "Mean": x.mean(),
                        "SD": x.std(ddof=1),
                        "Min": x.min(),
                        "Max": x.max(),
                    }
                )
        table = pd.DataFrame(rows)
        if table.empty:
            raise StataError("No observations for descriptive table", 2000)
        self.show_table(
            "Descriptive statistics (unweighted, available observations)",
            table.set_index(["Group", "Variable"]),
        )
        if "export" in o:
            self.export_table(str(o["export"]), "replace" in o)
        elif "replace" in o:
            raise StataError("replace requires export()")
