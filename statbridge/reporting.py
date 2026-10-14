# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Presentation only: numeric estimation results remain unchanged."""

from __future__ import annotations

from html import escape
import math


def number(value, digits=6):
    """Readable decimals, preserving the scale of tiny nonzero estimates."""
    value = float(value)
    if math.isnan(value):
        return "."
    if math.isinf(value):
        return "−∞" if value < 0 else "∞"
    if value != 0 and (abs(value) < 0.0001 or abs(value) >= 10_000_000):
        return f"{value:.{digits}e}"
    rounded = f"{value:.{digits}f}"
    return rounded.lstrip("-") if float(rounded) == 0 else rounded


def probability(value):
    value = float(value)
    if not math.isfinite(value):
        return "."
    return "<0.001" if value < 0.001 else f"{value:.3f}"


def model_summary(model, estimates):
    titles = {
        "regress": "Linear regression",
        "reghdfe": "Regression with absorbed effects",
        "didregress": "Two-period difference-in-differences",
        "xtdidregress": "Two-period panel difference-in-differences",
        "areg": "Linear regression with absorbed effects",
        "anova": "One-way ANOVA regression",
        "logit": "Logistic regression",
        "logistic": "Logistic regression",
        "probit": "Probit regression",
        "poisson": "Poisson regression",
        "nbreg": "Negative binomial regression",
        "glm": "Generalized linear model",
        "qreg": "Quantile regression",
        "ivregress": "Instrumental variables regression",
    }
    title = titles.get(model.command, model.command)
    covariance = model.covariance
    if covariance == "ols":
        covariance = "Conventional"
    elif model.command == "xtreg" and covariance == "robust":
        covariance = "Clustered by panel"
    pairs = [
        ("Dependent variable", str(model.y.name)),
        ("Observations", f"{estimates['N']:,.0f}"),
        ("Covariance", covariance),
        ("Confidence level", f"{model.level:g}%"),
    ]
    if model.weight_type:
        pairs.append(("Weight type", model.weight_type))
    if model.df is not None:
        pairs.append(("Inference df" if model.covariance.startswith("cluster ") else "Residual df", number(model.df, 0)))
    if model.command == "xtreg":
        result = model.result
        title = (
            "Fixed-effects (within) regression"
            if type(result.model).__name__ == "PanelOLS"
            else "Random-effects GLS regression"
        )
        if (model.metadata or {}).get("cre_means"):
            title = "Correlated random-effects (Mundlak) regression"
        info = result.entity_info
        pairs += [
            ("Panel variable", str(result.model.dependent.index.names[0])),
            ("Groups", f"{info['total']:,.0f}"),
            (
                "Obs per group (min / avg / max)",
                f"{info['min']:.0f} / {info['mean']:.2f} / {info['max']:.0f}",
            ),
            ("R-squared (within)", number(result.rsquared_within, 4)),
            ("R-squared (between)", number(result.rsquared_between, 4)),
            ("R-squared (overall)", number(result.rsquared_overall, 4)),
        ]
    labels = {
        "N_groups": "Absorbed groups",
        "df_absorb": "Absorbed df",
        "r2": "R-squared (model)" if model.command == "xtreg" else "R-squared",
        "r2_a": "Adjusted R-squared",
        "ll": "Log likelihood",
        "aic": "AIC",
        "bic": "BIC",
    }
    for key, value in estimates.items():
        if key not in ("N", "df_m", "df_r") and not (
            model.command == "xtreg" and key == "r2"
        ):
            pairs.append((labels.get(key, key), number(value, 0 if key in ("N_groups", "df_absorb") else 4)))
    return title, pairs


def model_report(model, table, estimates):
    """Return a log-friendly text report and Qt's supported HTML equivalent."""
    title, summary = model_summary(model, estimates)
    statistic = "t" if model.df is not None else "z"
    headers = [
        "Term",
        str(table.columns[0]),
        "Std. err.",
        statistic,
        f"P>|{statistic}|",
        "Lower",
        "Upper",
    ]
    rows = [
        [
            str(term),
            number(values[0]),
            number(values[1]),
            number(values[2], 2),
            probability(values[3]),
            number(values[4]),
            number(values[5]),
        ]
        for term, values in zip(table.index, table.to_numpy())
    ]
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows))
        for i in range(len(headers))
    ]

    def text_row(row):
        return "  ".join(
            value.ljust(widths[i]) if i == 0 else value.rjust(widths[i])
            for i, value in enumerate(row)
        )

    line = "-" * (sum(widths) + 2 * (len(widths) - 1))
    text = [title, f"Command: {model.command}", ""]
    label_width = max(len(label) for label, _ in summary)
    text += [f"  {label:<{label_width}} : {value}" for label, value in summary]
    text += [
        "",
        f"Coefficient estimates · {model.level:g}% confidence interval (Lower, Upper)",
        line,
        text_row(headers),
        line,
    ]
    text += [text_row(row) for row in rows]
    text += [line]
    notes = []
    if table.columns[0].startswith("Ratio"):
        notes.append(
            "Ratios use exponentiated coefficients and confidence limits; standard errors use the delta method."
        )
        if model.command == "nbreg":
            notes.append(
                "alpha is the untransformed dispersion parameter, not a ratio."
            )
        notes.append(
            f"{statistic} statistics and p-values test the original coefficient = 0 (ratio = 1)."
        )
    if model.command == "xtreg":
        notes.append(
            "Panel statistics and inference use linearmodels conventions. See the PANEL compatibility notice."
        )
    text += notes

    # Qt rich text supports table attributes reliably across the supported Qt6 versions.
    html = [
        f'<p style="font-size:13pt;color:#123f68"><b>{escape(title)}</b></p>',
        f'<p style="color:#607080">Command: {escape(model.command)}</p>',
        '<table cellspacing="0" cellpadding="4" style="font-size:10pt">',
    ]
    # Two label/value pairs per row leave room for the coefficient table below.
    for start in range(0, len(summary), 2):
        html.append("<tr>")
        for label, value in summary[start : start + 2]:
            html.append(
                f'<td style="color:#536577">{escape(label)}</td>'
                f'<td style="padding-right:24px"><b>{escape(value)}</b></td>'
            )
        html.append("</tr>")
    html += [
        "</table>",
        "<p><b>Coefficient estimates</b></p>",
        '<table cellspacing="0" cellpadding="7" style="font-size:11pt">',
        '<tr bgcolor="#dfeaf3">',
    ]
    for header in headers[:5]:
        html.append(
            f'<th rowspan="2" align="{"left" if header == "Term" else "right"}">{escape(header)}</th>'
        )
    html += [
        f'<th colspan="2" align="center">{model.level:g}% confidence interval</th></tr>',
        '<tr bgcolor="#dfeaf3"><th align="right">Lower</th><th align="right">Upper</th></tr>',
    ]
    for index, row in enumerate(rows):
        html.append(f'<tr bgcolor="{"#f0f5f9" if index % 2 else "#ffffff"}">')
        for i, value in enumerate(row):
            html.append(
                f'<td align="{"left" if i == 0 else "right"}">{escape(value)}</td>'
            )
        html.append("</tr>")
    html.append("</table>")
    html += [
        f'<p style="font-size:10pt;color:#536577">{escape(note)}</p>' for note in notes
    ]
    html.append("<p></p>")
    return "\n".join(text), "".join(html)
