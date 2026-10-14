# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Explicit weight semantics, without expanding frequency-weighted datasets."""

from __future__ import annotations
import re
from types import SimpleNamespace
import numpy as np
import pandas as pd
import statsmodels.api as sm
from .syntax import StataError, options, qualifiers


def extract_weight(text):
    """Remove a single, quote-aware [aw=expression] clause, retaining if/in."""
    quote = False
    start = None
    found = []
    depth = 0
    for i, c in enumerate(text):
        if c == '"':
            quote = not quote
        if quote:
            continue
        if c == "[":
            if depth == 0:
                start = i
            depth += 1
        elif c == "]":
            depth -= 1
            if depth < 0:
                raise StataError("Unbalanced brackets")
            if depth == 0 and start is not None:
                inner = text[start + 1 : i]
                m = re.fullmatch(
                    r"\s*(aw|aweight|fw|fweight|pw|pweight|iw|iweight|w|weight)\s*=\s*(.+)",
                    inner,
                    re.S,
                )
                if m:
                    found.append((start, i + 1, m[1], m[2]))
    if len(found) > 1:
        raise StataError("Specify only one weight expression")
    if not found:
        return text, None
    a, b, kind, expression = found[0]
    if kind in ("w", "weight"):
        raise StataError("Specify an explicit weight type: aw, fw or pw")
    return (text[:a] + " " + text[b:]).strip(), (kind[0] + "w", expression.strip())


def evaluate_weights(engine, spec, mask):
    kind, expression = spec
    value = engine.expr(expression)
    s = (
        value.reindex(engine.df.index)
        if isinstance(value, pd.Series)
        else pd.Series(value, index=engine.df.index)
    )
    if not pd.api.types.is_numeric_dtype(s):
        raise StataError("Weights must be numeric", 109)
    s = s.astype(float)
    chosen = s.loc[mask]
    if (chosen.dropna() < 0).any():
        raise StataError("Negative weights are not allowed")
    if np.isinf(chosen).any():
        raise StataError("Weights must be finite")
    if kind == "fw" and (chosen.dropna() % 1 != 0).any():
        raise StataError("Frequency weights must be integers")
    if kind == "fw" and chosen.sum() > 2**53:
        raise StataError("Frequency total exceeds exact float64 integer range")
    return s


def fit_weighted(engine, args, opt):
    from .models import Model

    args, spec = extract_weight(args)
    if spec is None:
        raise StataError("Expected a weight clause")
    kind, _ = spec
    if kind not in ("aw", "fw", "pw"):
        raise StataError("regress supports aw, fw and pw; iweights are not implemented")
    o = options(opt, ("vce", "robust", "noconstant", "level"))
    if "vce" in o and "robust" in o:
        raise StataError("Specify robust OR vce()")
    covariance = str(o.get("vce", "robust" if "robust" in o or kind == "pw" else "ols"))
    if kind == "pw" and covariance == "ols":
        raise StataError("Probability weights require robust or clustered covariance")
    if covariance not in ("ols", "robust") and not covariance.startswith("cluster "):
        raise StataError(
            "Weighted regress supports ols, robust or one-way cluster covariance"
        )
    level = float(o.get("level", engine.level))
    if not 0 < level < 100:
        raise StataError("level() must be between 0 and 100")
    head, q = qualifiers(args)
    terms = head.split()
    if not terms:
        raise StataError("Specify a dependent variable")
    mask = engine.mask(q)
    weights = evaluate_weights(engine, spec, mask)
    frame = engine.df.loc[mask & weights.gt(0) & weights.notna()]
    y = engine.model_response(terms[0], frame)
    x = engine.regressors(terms[1:], frame)
    if "noconstant" not in o:
        x.insert(0, "_cons", 1.0)
    valid = y.notna() & x.notna().all(axis=1)
    for name in re.findall(r"(?:^|[# ])(?:i|c|ib-?\d+)\.(\w+)", head):
        valid &= frame[name].notna()
    cluster = None
    if covariance.startswith("cluster "):
        names = engine.varlist(covariance[8:])
        if len(names) != 1:
            raise StataError("Exactly one cluster variable is supported")
        cluster = frame[names[0]]
        valid &= cluster.notna() & cluster.ne("")
    y, x = y.loc[valid], x.loc[valid]
    w = weights.loc[y.index].to_numpy()
    n = float(w.sum()) if kind == "fw" else float(len(y))
    k = x.shape[1]
    if k == 0 or len(y) < k or n <= k:
        raise StataError("Insufficient positive-weight complete observations", 2001)
    if not np.isfinite(x.to_numpy()).all() or not np.isfinite(y).all():
        raise StataError("Nonfinite model data")
    if kind != "fw":
        w = w * len(w) / w.sum()
    a = x.to_numpy()
    response = y.to_numpy()
    if np.linalg.matrix_rank(a * np.sqrt(w[:, None])) < k:
        raise StataError(
            "Collinear weighted design; redundant regressors must be removed"
        )
    fitted = sm.WLS(y, x, weights=w).fit()
    b = fitted.params
    residual = response - a @ b.to_numpy()
    bread = fitted.normalized_cov_params.to_numpy()
    df = n - k
    ss = float(np.dot(w, residual**2))
    if cluster is not None:
        cluster = cluster.loc[y.index]
        codes, levels = pd.factorize(cluster)
        if len(levels) < 2:
            raise StataError("At least two clusters are required")
        scores = np.zeros((len(levels), k))
        np.add.at(scores, codes, a * (w * residual)[:, None])
        cov = (
            bread
            @ (scores.T @ scores)
            @ bread
            * (len(levels) / (len(levels) - 1))
            * ((n - 1) / (n - k))
        )
        df = float(len(levels) - 1)
    elif covariance == "robust":
        factor = w if kind == "fw" else w**2
        meat = a.T @ (a * (factor * residual**2)[:, None])
        cov = bread @ meat @ bread * n / (n - k)
    else:
        cov = bread * ss / (n - k)
    center = float(np.average(response, weights=w)) if "_cons" in x else 0.0
    tss = float(np.dot(w, (response - center) ** 2))
    r2 = 1 - ss / tss if tss > 0 else np.nan
    # Avoid advertising WLS's row-count likelihood/IC for frequency weights.
    backend = SimpleNamespace(
        rsquared=r2, rsquared_adj=1 - (1 - r2) * (n - int("_cons" in x)) / (n - k)
    )
    pred = pd.Series(a @ b.to_numpy(), index=y.index)
    engine.model = Model(
        "regress",
        backend,
        b,
        pd.DataFrame(cov, index=x.columns, columns=x.columns),
        y.index,
        y,
        x,
        pred,
        pd.Series(residual, index=y.index),
        df,
        covariance,
        level,
        linear_prediction=pred,
        weight_type=kind,
        nobs=n,
    )
    engine.model.fit_extra = {
        "rmse": np.sqrt(ss / (n - k)),
        "sum_w": float(weights.loc[y.index].sum()),
        "N_rows": len(y),
    }
    engine.notice(
        "WEIGHTS",
        f"{kind}: statsmodels WLS coefficients with explicit weight-aware covariance/df. Zero and missing weights are excluded. Frequency weights use sum(weights) as N; analytic/probability weights use retained row count. No stratification, FPC or survey design is inferred.",
    )
    engine.report_model()


def weighted_percentiles(x, w, percentiles):
    order = np.argsort(x, kind="stable")
    x = x[order]
    w = w[order]
    cumulative = np.cumsum(w)
    total = cumulative[-1]
    result = []
    for p in percentiles:
        rank = total * p / 100
        j = min(int(np.searchsorted(cumulative, rank, side="left")), len(x) - 1)
        if cumulative[j] == rank and j + 1 < len(x):
            result.append((x[j] + x[j + 1]) / 2)
        else:
            result.append(x[j])
    return np.asarray(result)


def summarize_weighted(engine, args, opt):
    args, spec = extract_weight(args)
    kind, _ = spec
    if kind not in ("aw", "fw"):
        raise StataError("Weighted summarize supports analytic and frequency weights")
    o = options(opt, ("detail", "meanonly"))
    if "detail" in o and "meanonly" in o:
        raise StataError("detail and meanonly cannot be combined")
    if kind == "aw" and "detail" in o:
        raise StataError(
            "Analytic-weight percentiles/detail are not implemented; use basic summarize or explicit frequency weights"
        )
    head, q = qualifiers(args)
    mask = engine.mask(q)
    weights = evaluate_weights(engine, spec, mask)
    rows = []
    engine.r = {}
    for name in engine.varlist(head, default=True):
        s = engine.df[name]
        if not pd.api.types.is_numeric_dtype(s):
            continue
        valid = mask & weights.gt(0) & weights.notna() & s.notna()
        x = s.loc[valid].to_numpy(dtype=float)
        w = weights.loc[valid].to_numpy()
        if not len(x):
            continue
        total = float(w.sum())
        n = int(total) if kind == "fw" else len(x)
        mean = float(np.average(x, weights=w))
        m2 = float(np.average((x - mean) ** 2, weights=w))
        variance = m2 * n / (n - 1) if n > 1 else np.nan
        engine.r = {
            "N": n,
            "sum_w": total,
            "mean": mean,
            "sum": mean * total,
            "min": x.min(),
            "max": x.max(),
            "Var": variance,
            "sd": np.sqrt(variance),
        }
        rows.append(
            {
                "Variable": name,
                "Obs": n,
                "Weight": total,
                "Mean": mean,
                "Std. dev.": np.sqrt(variance),
                "Min": x.min(),
                "Max": x.max(),
            }
        )
        if "detail" in o:
            ps = [1, 5, 10, 25, 50, 75, 90, 95, 99]
            vals = weighted_percentiles(x, w, ps)
            engine.r.update({f"p{p}": float(v) for p, v in zip(ps, vals)})
            engine.r["skewness"] = (
                float(np.average((x - mean) ** 3, weights=w) / m2**1.5)
                if m2
                else np.nan
            )
            engine.r["kurtosis"] = (
                float(np.average((x - mean) ** 4, weights=w) / m2**2) if m2 else np.nan
            )
            engine.out(name + "\n" + pd.Series(engine.r).to_string())
    engine.notice(
        "WEIGHT_SUMMARY",
        "Frequency summaries use conceptual row replication without expanding data. Analytic-weight variance uses the retained row count. Analytic detail and probability-weight summaries are rejected.",
    )
    if "meanonly" not in o:
        engine.out(pd.DataFrame(rows).to_string(index=False))
