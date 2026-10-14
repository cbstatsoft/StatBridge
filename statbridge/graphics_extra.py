# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Bounded layered and diagnostic graphics using the existing graph channel."""

import re
import numpy as np
from scipy import stats
from .syntax import StataError, options, qualifiers, split_top


class GraphicsCommands:
    def _figure(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        fig = Figure(figsize=(8, 5), dpi=120)
        FigureCanvasAgg(fig)
        return fig, fig.subplots()

    def _graph_ready(self, fig, ax, title):
        ax.set_title(str(title))
        ax.grid(alpha=0.18)
        fig.tight_layout()
        self.figure = fig
        self.emit("graph", "Graph ready", fig)

    def cmd_lfit(self, args, opt):
        return self.cmd_twoway("lfit " + args, opt)

    def cmd_twoway(self, args, opt):
        o = options(opt, ("title",))
        args = args.strip()
        if args.startswith("("):
            layers = []
            depth = 0
            start = 0
            quoted = False
            for i, c in enumerate(args):
                if c == '"':
                    quoted = not quoted
                if quoted:
                    continue
                if c == "(":
                    if depth == 0:
                        start = i + 1
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        layers.append(args[start:i])
                elif depth == 0 and not c.isspace():
                    raise StataError("Use parenthesised twoway layers")
            if depth or quoted:
                raise StataError("Unbalanced graph layers")
        else:
            layers = args.split("||")
        prepared = []
        for layer in layers:
            parts = split_top(layer)
            head = parts[0].strip()
            kind, _, text = head.partition(" ")
            if kind not in ("scatter", "line", "lfit"):
                raise StataError("twoway supports scatter, line and lfit layers")
            lo = options(
                parts[1] if len(parts) == 2 else "", ("sort",) if kind == "line" else ()
            )
            if len(parts) > 2:
                raise StataError("Invalid layer options")
            head, q = qualifiers(text)
            cols = self.varlist(head, numeric=True)
            if len(cols) != 2:
                raise StataError("Each layer requires y and x")
            frame = self.df.loc[self.mask(q), cols].dropna()
            if len(frame) < 2 or not np.isfinite(frame).all().all():
                raise StataError("Each layer needs at least two finite observations")
            if kind == "lfit" and frame[cols[1]].nunique() < 2:
                raise StataError("lfit requires variation in x")
            prepared.append((kind, cols, frame, lo))
        if not prepared:
            raise StataError("At least one graph layer required")
        fig, ax = self._figure()
        for kind, cols, frame, lo in prepared:
            if kind == "lfit":
                x = frame[cols[1]].to_numpy()
                y = frame[cols[0]].to_numpy()
                coef = np.linalg.lstsq(
                    np.column_stack([np.ones(len(x)), x]), y, rcond=None
                )[0]
                xs = np.array([x.min(), x.max()])
                ax.plot(xs, coef[0] + coef[1] * xs, label=f"Linear fit: {cols[0]}")
            elif kind == "scatter":
                ax.scatter(
                    frame[cols[1]], frame[cols[0]], s=18, alpha=0.7, label=cols[0]
                )
            else:
                if "sort" in lo:
                    frame = frame.sort_values(cols[1])
                ax.plot(frame[cols[1]], frame[cols[0]], label=cols[0])
        ax.set(xlabel=prepared[0][1][1], ylabel=prepared[0][1][0])
        ax.legend()
        self._graph_ready(fig, ax, o.get("title", ""))

    def cmd_rvfplot(self, args, opt):
        if args.strip():
            raise StataError("rvfplot takes comma options only")
        o = options(opt, ("title",))
        m = self.require_model()
        if m.command not in (
            "regress",
            "areg",
            "xtreg",
            "reghdfe",
            "didregress",
            "xtdidregress",
        ):
            raise StataError("rvfplot currently supports linear regression models")
        fig, ax = self._figure()
        ax.scatter(m.predicted, m.residual, s=18, alpha=0.7)
        ax.axhline(0, color="gray", linestyle="--")
        ax.set(xlabel="Fitted values", ylabel="Residuals")
        self._graph_ready(fig, ax, o.get("title", "Residuals versus fitted"))
        self.notice(
            "RVFPLOT",
            "Displays the stored estimation-sample fitted values and residuals. Panel FE residuals remove absorbed effects while the reported fitted component may exclude them; use the estimator-specific interpretation.",
        )

    def cmd_qnorm(self, args, opt):
        o = options(opt, ("title",))
        head, q = qualifiers(args)
        cols = self.varlist(head, numeric=True)
        if len(cols) != 1:
            raise StataError("qnorm requires one numeric variable")
        x = self.df.loc[self.mask(q), cols[0]].dropna()
        if len(x) < 3 or not np.isfinite(x).all():
            raise StataError("qnorm requires at least three finite observations")
        fig, ax = self._figure()
        stats.probplot(x, dist="norm", plot=ax)
        ax.set_ylabel(cols[0])
        self._graph_ready(fig, ax, o.get("title", "Normal Q-Q plot"))
        self.notice(
            "QNORM",
            "SciPy probability-plot plotting positions and fitted reference line can differ from Stata qnorm. Visual departures are not a formal normality test.",
        )
