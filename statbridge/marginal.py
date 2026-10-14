# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Average predictions and effects with frozen factor coding and delta covariance."""

import itertools
import re
import numpy as np
import pandas as pd
from scipy import stats, special
from .syntax import StataError, options


def numlist(text):
    text = text.strip()
    if re.fullmatch(r"[-+.\d]+\([-+.\d]+\)[-+.\d]+", text):
        a, step, b = map(float, re.split(r"[()]", text))
        if step == 0 or (b - a) / step < 0 or abs((b - a) / step) > 500:
            raise StataError("Invalid or excessive numeric grid")
        values = np.arange(a, b + step * 1e-8, step).tolist()
    else:
        try:
            values = [float(x) for x in text.split()]
        except ValueError:
            raise StataError("Numeric grid values required") from None
    if not values or len(values) > 500 or not np.isfinite(values).all():
        raise StataError("Require 1 to 500 finite grid values")
    return values


class MarginalCommands:
    def cmd_margins(self, args, opt):
        o = options(opt, ("dydx", "at", "over", "level"))
        m = self.require_model()
        if m.command not in ("regress", "logit", "logistic", "probit") or m.weight_type:
            raise StataError(
                "margins supports unweighted OLS, logit/logistic and probit"
            )
        if m.revision != self.revision or not m.sample.isin(self.df.index).all():
            raise StataError("Data changed since estimation; refit before margins")
        if m.prediction_terms is None:
            raise StataError("Fitted predictor metadata is unavailable")
        frame = self.df.loc[m.sample].copy()
        factors = {}
        for term in m.prediction_terms:
            for atom in term.split("#"):
                match = re.fullmatch(r"ib(-?\d+)\.(\w+)", atom)
                if match:
                    factors[match[2]] = (
                        float(match[1]),
                        sorted(frame[match[2]].dropna().unique()),
                    )
        variables = []
        atoms = {}
        for name in m.params.index:
            if name == "_cons":
                continue
            parts = []
            for atom in name.split("#"):
                match = re.fullmatch(r"(\d+)\.(\w+)", atom)
                var = match[2] if match else atom
                if var not in frame or not pd.api.types.is_numeric_dtype(frame[var]):
                    raise StataError(
                        "margins does not support time operators or this fitted term"
                    )
                parts.append((var, float(match[1]) if match else None))
                if var not in variables:
                    variables.append(var)
            atoms[name] = parts

        def design(data, derivative=None):
            columns = []
            for name in m.params.index:
                if name == "_cons":
                    columns.append(np.full(len(data), 0.0 if derivative else 1.0))
                    continue
                parts = atoms[name]
                vals = [
                    (
                        data[v].to_numpy(float)
                        if level is None
                        else (data[v].to_numpy() == level).astype(float)
                    )
                    for v, level in parts
                ]
                if derivative is None:
                    col = np.prod(vals, axis=0)
                else:
                    col = np.zeros(len(data))
                    for j, (var, level) in enumerate(parts):
                        if var == derivative and level is None:
                            col += (
                                np.prod(
                                    [val for i, val in enumerate(vals) if i != j],
                                    axis=0,
                                )
                                if len(vals) > 1
                                else 1.0
                            )
                columns.append(col)
            return np.column_stack(columns)

        if not np.allclose(design(frame), m.x.loc[:, m.params.index], equal_nan=True):
            raise StataError("Fitted predictors changed; refit before margins")
        beta = m.params.to_numpy()

        def prediction(data):
            x = design(data)
            eta = x @ beta
            if m.command == "regress":
                return eta, np.ones(len(data)), np.zeros(len(data)), x
            if m.command == "probit":
                g = stats.norm.cdf(eta)
                first = stats.norm.pdf(eta)
                return g, first, -eta * first, x
            g = special.expit(eta)
            first = g * (1 - g)
            return g, first, first * (1 - 2 * g), x

        def average(data):
            g, first, _, x = prediction(data)
            return g.mean(), (first[:, None] * x).mean(axis=0)

        grids = {}
        if "at" in o:
            spec = str(o["at"])
            pattern = r"(\w+)\s*=\s*(?:\(((?:[^()]|\([^()]*\))*)\)|([^\s()]+))"
            matches = list(re.finditer(pattern, spec))
            if re.sub(pattern, "", spec).strip() or not matches:
                raise StataError(
                    "Use at(x=(0 1 2) z=3); repeated at() and atmeans are not implemented"
                )
            for match in matches:
                var = match[1]
                if var in grids or var not in variables:
                    raise StataError("at() requires unique fitted predictor names")
                grids[var] = numlist(match[2] if match[2] is not None else match[3])
        if args.strip():
            if "dydx" in o:
                raise StataError("Specify factor margins OR dydx(), not both")
            for var in args.strip().split("#"):
                if var not in factors or var in grids:
                    raise StataError(
                        "Positional margins require fitted factor names, separated by #"
                    )
                grids[var] = factors[var][1]
        for var, values in grids.items():
            if var in factors and not set(values).issubset(factors[var][1]):
                raise StataError(f"Unestimated factor level in at({var}=...)")
        if np.prod([len(v) for v in grids.values()]) > 500:
            raise StataError("At most 500 counterfactual grid cells are supported")
        combinations = list(itertools.product(*grids.values())) if grids else [()]
        groups = [("All", frame)]
        if "over" in o:
            cols = self.varlist(str(o["over"]))
            if len(cols) != 1:
                raise StataError("over() requires one group variable")
            groups = list(frame.groupby(cols[0], dropna=True, sort=True))
        requested = []
        if "dydx" in o:
            requested = variables if o["dydx"] == "*" else str(o["dydx"]).split()
            if not requested or any(v not in variables for v in requested):
                raise StataError("dydx() requires fitted variable names or *")
        level = float(o.get("level", m.level))
        if not 0 < level < 100:
            raise StataError("Invalid confidence level")
        dist = stats.t(m.df) if m.df is not None else stats.norm
        crit = dist.ppf((1 + level / 100) / 2)
        rows, jacobians = [], []
        for group, sample in groups:
            for values in combinations:
                data = sample.copy()
                setting = dict(zip(grids, values))
                for var, value in setting.items():
                    data[var] = value
                effects = []
                if not requested:
                    effects = [("Prediction", *average(data))]
                for var in requested:
                    if var in factors:
                        base, levels = factors[var]
                        low = data.copy()
                        low[var] = base
                        lo, gl = average(low)
                        for value in levels:
                            if value == base:
                                continue
                            high = data.copy()
                            high[var] = value
                            hi, gh = average(high)
                            effects.append(
                                (f"{value:g}.{var} vs {base:g}", hi - lo, gh - gl)
                            )
                    else:
                        _, first, second, x = prediction(data)
                        dx = design(data, var)
                        slope = dx @ beta
                        effects.append(
                            (
                                f"dy/d{var}",
                                np.mean(first * slope),
                                np.mean(
                                    second[:, None] * slope[:, None] * x
                                    + first[:, None] * dx,
                                    axis=0,
                                ),
                            )
                        )
                for effect, estimate, gradient in effects:
                    variance = float(gradient @ m.cov.to_numpy() @ gradient)
                    if variance < -1e-10 or not np.isfinite(variance):
                        raise StataError("Invalid marginal-effect variance")
                    se = np.sqrt(max(variance, 0))
                    p = float(2 * dist.sf(abs(estimate / se))) if se else np.nan
                    rows.append(
                        {
                            "Group": group,
                            **setting,
                            "Effect": effect,
                            "N": len(data),
                            "Estimate": estimate,
                            "SE": se,
                            "p": p,
                            "Lower": estimate - crit * se,
                            "Upper": estimate + crit * se,
                        }
                    )
                    jacobians.append(gradient)
        if not rows:
            raise StataError("No eligible margins observations")
        table = pd.DataFrame(rows)
        jac = np.asarray(jacobians)
        self.margins_result = {
            "table": table.copy(),
            "covariance": jac @ m.cov.to_numpy() @ jac.T,
            "level": level,
            "command": self._command,
        }
        self.r = {"N": len(frame), "k": len(table)}
        self.show_table(f"Margins: {level:g}% delta-method intervals", table)
        self.notice(
            "MARGINS",
            "Averages use the estimation sample, empirical covariates treated as fixed, and the fitted covariance. Factors give discrete changes from their fitted base; numeric predictors give derivatives, including numeric 0/1 predictors. No weights, unconditional VCE, post, contrasts syntax or time-operator margins. General Stata parity is not certified.",
        )

    def cmd_marginsplot(self, args, opt):
        if args.strip():
            raise StataError("marginsplot takes comma options only")
        o = options(opt, ("title",))
        result = getattr(self, "margins_result", None)
        if result is None:
            raise StataError("Run margins successfully first")
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        table = result["table"]
        fig = Figure(figsize=(9, 5))
        FigureCanvasAgg(fig)
        ax = fig.subplots()
        y = table.Estimate.to_numpy()
        x = np.arange(len(table))
        ax.errorbar(
            x, y, yerr=np.vstack((y - table.Lower, table.Upper - y)), fmt="o", capsize=4
        )
        labels = []
        for _, row in table.iterrows():
            labels.append(
                ", ".join(
                    f"{k}={v}"
                    for k, v in row.items()
                    if k not in ("N", "Estimate", "SE", "p", "Lower", "Upper")
                    and not (k == "Group" and v == "All")
                )
            )
        ax.set_xticks(x, labels, rotation=30, ha="right")
        ax.set_ylabel("Estimate")
        ax.set_title(
            str(o.get("title", f'Margins with {result["level"]:g}% intervals'))
        )
        ax.grid(alpha=0.2)
        fig.tight_layout()
        self.figure = fig
        self.emit("graph", "Margins graph ready", fig)
