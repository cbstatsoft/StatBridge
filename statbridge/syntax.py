# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Quote-aware command parsing and a non-eval, vectorised expression evaluator."""

from __future__ import annotations
import re
import numpy as np
import pandas as pd
from scipy import special


class StataError(Exception):
    def __init__(self, message, code=198):
        super().__init__(message)
        self.code = code


def split_top(text, delimiter=","):
    parts, start, depth, quote = [], 0, 0, False
    for i, c in enumerate(text):
        if c == '"':
            quote = not quote
        if quote:
            continue
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif c == delimiter and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    if quote or depth:
        raise StataError("Unbalanced quotes or parentheses")
    parts.append(text[start:].strip())
    return parts


def words(text):
    # Backslashes in Windows paths are literal, not shell escape characters.
    return re.findall(r'"[^"]*"|[^\s]+', text)


def unquote(text):
    text = text.strip()
    return (
        text[1:-1]
        if len(text) >= 2 and text[0] == text[-1] == '"' and text.count('"') == 2
        else text
    )


def options(text, allowed=()):
    result = {}
    pattern = re.compile(r"([A-Za-z_][\w]*)")
    at = 0
    while at < len(text):
        if text[at].isspace():
            at += 1
            continue
        m = pattern.match(text, at)
        if not m:
            raise StataError(f"Invalid option near: {text[at:]}")
        k = m[1].lower()
        at = m.end()
        v = None
        if at < len(text) and text[at] == "(":
            start = at + 1
            depth = 1
            quoted = False
            at += 1
            while at < len(text) and depth:
                c = text[at]
                if c == '"':
                    quoted = not quoted
                elif not quoted:
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1
                at += 1
            if depth or quoted:
                raise StataError(f"Unbalanced argument for option {k}")
            v = text[start : at - 1]
        if k == "gen" and "generate" in allowed:
            k = "generate"
        if k not in allowed:
            raise StataError(
                f"Option {k} is not supported here; no option was silently ignored"
            )
        if k in result:
            raise StataError(f"Duplicate option: {k}")
        valued = {
            "object",
            "compression",
            "table",
            "layout",
            "id",
            "yearcol",
            "valuecol",
            "seriescol",
            "headerrow",
            "minfree",
            "lazy",
            "parquet",
            "aggregate",
            "rows",
            "saving",
            "on",
            "join",
            "conflicts",
            "estimates",
            "export",
            "at",
            "over",
            "sheet",
            "cellrange",
            "firstrow",
            "cell",
            "group",
            "time",
            "xlabel",
            "ylabel",
            "stats",
            "prefix",
            "format",
            "parse",
            "limit",
            "mv",
            "has",
            "local",
            "separate",
            "nquantiles",
            "nq",
            "cutpoints",
            "genp",
            "freq",
            "percent",
            "statistics",
            "stat",
            "columns",
            "mean",
            "std",
            "p",
            "percentiles",
            "punct",
            "absorb",
            "keep",
            "assert",
            "keepusing",
            "depth",
            "version",
            "delimiter",
            "encoding",
            "level",
            "top",
            "mcompare",
            "by",
            "generate",
            "ignore",
            "i",
            "j",
            "vce",
            "quantile",
            "exposure",
            "offset",
            "family",
            "link",
            "components",
            "lags",
            "arima",
            "bin",
            "title",
            "reps",
            "seed",
            "dydx",
            "delta",
            "baseoutcome",
            "outcome",
            "failure",
            "scale",
            "ties",
            "strata",
            "fpc",
            "subpop",
            "lag",
            "subject",
            "cohort",
            "within",
            "slope",
            "steps",
            "burnin",
            "between",
            "m",
        }
        if k in valued and (
            (v is None and k != "firstrow") or (v is not None and not v.strip())
        ):
            raise StataError(f"Option {k} requires a nonempty argument in parentheses")
        if k not in valued and v is not None:
            raise StataError(f"Option {k} does not accept an argument")
        result[k] = (
            True if v is None else v.strip() if k == "parse" else unquote(v.strip())
        )
    return result


def qualifiers(text):
    """Extract top-level if/in, leaving expressions in strings untouched."""
    quote, depth, positions = False, 0, []
    for m in re.finditer(r'"|[()]|\bif\b|\bin\b', text):
        t = m.group()
        if t == '"':
            quote = not quote
        elif not quote:
            if t == "(":
                depth += 1
            elif t == ")":
                depth -= 1
            elif depth == 0:
                positions.append((m.start(), m.end(), t))
    head = text[: positions[0][0]].strip() if positions else text.strip()
    q = {}
    for i, (a, b, k) in enumerate(positions):
        if k in q:
            raise StataError(f"Duplicate {k} qualifier")
        q[k] = text[
            b : positions[i + 1][0] if i + 1 < len(positions) else len(text)
        ].strip()
    return head, q


def logical_lines(source):
    """Quote-aware CR/semicolon lexer, nested block comments and continuations."""
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    buffer = []
    first = 1
    line = 1
    i = 0
    quote = False
    block_depth = 0
    delimiter = "cr"
    physical_start = True
    has_text = False

    def emit():
        text = "".join(buffer).strip()
        if not text:
            return []
        # Stata permits a closing brace and else on the same line.
        m = re.fullmatch(r"}\s*(else(?:\s+if\s+.+)?\s*{)", text)
        return [(first, "}"), (first, m[1])] if m else [(first, text)]

    while i < len(source):
        c = source[i]
        if physical_start and not quote and not block_depth:
            end = source.find("\n", i)
            if end < 0:
                end = len(source)
            physical = source[i:end].strip()
            if physical.startswith("#delimit"):
                if has_text:
                    raise StataError(
                        f"line {line}: finish the current command before changing delimiter"
                    )
                m = re.fullmatch(r"#delimit\s+(;|cr)\s*;?", physical)
                if not m:
                    raise StataError(f"line {line}: use #delimit ; or #delimit cr")
                delimiter = m[1]
                i = end
                physical_start = False
                continue
            if physical.startswith("*"):
                i = end
                physical_start = False
                continue
            physical_start = False
        if block_depth:
            if source[i : i + 2] == "/*":
                block_depth += 1
                i += 2
                continue
            if source[i : i + 2] == "*/":
                block_depth -= 1
                physical_start = False
                i += 2
                buffer.append(" ")
                continue
            if c == "\n":
                line += 1
                physical_start = True
            else:
                physical_start = False
            i += 1
            continue
        if not quote and source[i : i + 2] == "/*":
            block_depth = 1
            buffer.append(" ")
            i += 2
            continue
        if not quote and source[i : i + 2] == "//":
            continued = source[i : i + 3] == "///"
            end = source.find("\n", i)
            if end < 0:
                end = len(source)
            if continued:
                buffer.append(" ")
                i = end
                if i < len(source):
                    line += 1
                    i += 1
                    physical_start = True
            else:
                i = end
            continue
        if c == '"':
            quote = not quote
        if c == "\n":
            if quote and delimiter == "cr":
                raise StataError(f"line {first}: unterminated quoted string")
            if delimiter == "cr" and not quote:
                yield from emit()
                buffer = []
                has_text = False
            else:
                buffer.append(" ")
            line += 1
            physical_start = True
            i += 1
            continue
        if c == ";" and not quote and delimiter == ";":
            yield from emit()
            buffer = []
            has_text = False
            i += 1
            continue
        if not has_text and not c.isspace():
            first = line
            has_text = True
        buffer.append(c)
        i += 1
    if quote:
        raise StataError(f"line {first}: unterminated quoted string")
    if block_depth:
        raise StataError("Unterminated block comment")
    if "".join(buffer).strip():
        if delimiter == ";":
            raise StataError(f"line {first}: missing final semicolon")
        yield from emit()


TOKEN = re.compile(
    r'\s*(?:(_(?:b|se)\[[^\[\]]+\])|((?:[LFDSlfds]\d*)+\.[A-Za-z_]\w*)|(\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)|("[^"]*")|([A-Za-z_]\w*)|(\.[a-z]?)(?!\w)|([!<>=~]=|\^|[+*/%(),\[\]<>!~&|=\-]))'
)


class Expression:
    """Pratt parser. No eval, exec, attribute access or arbitrary function calls."""

    def __init__(self, engine, frame=None):
        self.engine = engine
        self.df = engine.df if frame is None else frame

    def evaluate(self, text):
        self.tokens = []
        pos = 0
        text = text.strip()
        while pos < len(text):
            m = TOKEN.match(text, pos)
            if not m:
                raise StataError(
                    f"Unsupported expression near {text[pos : pos + 35]!r}"
                )
            self.tokens.append(next(x for x in m.groups() if x is not None))
            pos = m.end()
        self.tokens.append("<end>")
        self.pos = 0
        with np.errstate(all="ignore"):
            v = self.parse(0)
        if self.peek() != "<end>":
            raise StataError(f"Unexpected token {self.peek()}")
        if isinstance(v, pd.Series) and pd.api.types.is_numeric_dtype(v):
            v = v.replace([np.inf, -np.inf], np.nan)
        elif isinstance(v, (float, np.floating)) and not np.isfinite(v):
            v = np.nan
        return v

    def peek(self):
        return self.tokens[self.pos]

    def take(self):
        v = self.peek()
        self.pos += 1
        return v

    def series(self, v):
        return v if isinstance(v, pd.Series) else pd.Series(v, index=self.df.index)

    def truth(self, v):
        # In Stata numeric missing is nonzero and therefore true.
        s = self.series(v)
        if not pd.api.types.is_numeric_dtype(s):
            raise StataError("Numeric expression required for condition", 109)
        return s.ne(0)

    def parse(self, minbp):
        t = self.take()
        if t in ("-", "+", "!", "~"):
            v = self.parse(65)
            if t in ("-", "+"):
                v = self.numeric_boolean(v)
            left = -v if t == "-" else v if t == "+" else ~self.truth(v)
        elif t == "(":
            left = self.parse(0)
            if self.take() != ")":
                raise StataError("Expected )")
        elif t.startswith('"'):
            left = t[1:-1]
        elif re.fullmatch(r"\.[a-z]?", t):
            if t != ".":
                raise StataError(
                    "Extended missing literals .a-.z are not supported; use . or missing()"
                )
            left = np.nan
        elif re.match(r"\d|\.\d", t):
            left = float(t)
        elif re.fullmatch(r"_(b|se)\[[^\[\]]+\]", t):
            m = self.engine.require_model()
            key = t[t.index("[") + 1 : -1].strip()
            if key not in m.params:
                raise StataError(f"Coefficient {key} not found")
            left = (
                float(m.params[key])
                if t.startswith("_b[")
                else float(np.sqrt(m.cov.loc[key, key]))
            )
        elif re.fullmatch(r"(?:[LFDSlfds]\d*)+\.[A-Za-z_]\w*", t):
            from .timeseries import time_values

            left = time_values(self.engine, t, self.df)
        elif re.fullmatch(r"[A-Za-z_]\w*", t):
            if self.peek() == "(":
                self.take()
                args = []
                # Stored scalar results accept bare names, not expressions.
                if t in ("r", "e"):
                    name = self.take()
                    if self.take() != ")":
                        raise StataError("Expected stored result name")
                    bank = self.engine.r if t == "r" else self.engine.e
                    if t == "e" and name == "sample":
                        left = self.engine.estimation_sample(self.df)
                    else:
                        if name not in bank:
                            raise StataError(f"{t}({name}) not available")
                        left = bank[name]
                else:
                    if self.peek() != ")":
                        while True:
                            args.append(self.parse(0))
                            if self.peek() != ",":
                                break
                            self.take()
                    if self.take() != ")":
                        raise StataError("Expected )")
                    left = self.finite(self.call(t, args))
            elif t == "_n":
                left = pd.Series(np.arange(1, len(self.df) + 1), index=self.df.index)
            elif t == "_N":
                left = float(len(self.df))
            elif t in self.df:
                left = self.df[t]
            elif t in self.engine.scalars:
                left = self.engine.scalars[t]
            else:
                raise StataError(f"Variable or scalar {t} not found", 111)
        else:
            raise StataError(f"Unexpected expression token: {t}")
        precedence = {
            "|": 10,
            "&": 20,
            "==": 30,
            "=": 30,
            "!=": 30,
            "~=": 30,
            "<": 30,
            ">": 30,
            "<=": 30,
            ">=": 30,
            "+": 40,
            "-": 40,
            "*": 50,
            "/": 50,
            "%": 50,
            "^": 70,
        }
        while True:
            op = self.peek()
            if op == "[" and 90 >= minbp:
                self.take()
                idx = self.parse(0)
                if self.take() != "]":
                    raise StataError("Expected ]")
                values = self.series(left)
                if isinstance(idx, pd.Series):
                    good = (
                        idx.notna()
                        & (idx >= 1)
                        & (idx <= len(values))
                        & (idx == np.floor(idx))
                    )
                    out = pd.Series(
                        np.nan,
                        index=self.df.index,
                        dtype=object if values.dtype == object else float,
                    )
                    out.loc[good] = values.iloc[
                        idx[good].astype(int).to_numpy() - 1
                    ].to_numpy()
                    left = out
                else:
                    left = (
                        values.iloc[int(idx) - 1]
                        if pd.notna(idx) and idx == int(idx) and 1 <= idx <= len(values)
                        else np.nan
                    )
                continue
            bp = precedence.get(op, -1)
            if bp < minbp:
                break
            self.take()
            right = self.parse(bp if op == "^" else bp + 1)
            left = self.finite(self.binary(op, left, right))
        return left

    @staticmethod
    def finite(value):
        if isinstance(value, pd.Series) and pd.api.types.is_numeric_dtype(value):
            return value.replace([np.inf, -np.inf], np.nan)
        if isinstance(value, (float, np.floating)) and not np.isfinite(value):
            return np.nan
        return value

    @staticmethod
    def numeric_boolean(value):
        if isinstance(value, pd.Series) and pd.api.types.is_bool_dtype(value):
            return value.astype(float)
        if isinstance(value, (bool, np.bool_)):
            return float(value)
        return value

    def binary(self, op, a, b):
        a, b = self.finite(a), self.finite(b)
        if op in ("&", "|"):
            return (
                self.truth(a) & self.truth(b)
                if op == "&"
                else self.truth(a) | self.truth(b)
            )
        if op in ("=", "==", "!=", "~=", "<", ">", "<=", ">="):
            # Stata's ordinary numeric missing sorts above all finite numbers.
            def comparable(v):
                if isinstance(v, pd.Series):
                    return (
                        v.fillna(np.inf)
                        if pd.api.types.is_numeric_dtype(v)
                        else v.fillna("")
                    )
                return (
                    np.inf
                    if v is None or (not isinstance(v, str) and pd.isna(v))
                    else v
                )

            a, b = comparable(a), comparable(b)
            return {
                "=": lambda: a == b,
                "==": lambda: a == b,
                "!=": lambda: a != b,
                "~=": lambda: a != b,
                "<": lambda: a < b,
                ">": lambda: a > b,
                "<=": lambda: a <= b,
                ">=": lambda: a >= b,
            }[op]()
        a, b = self.numeric_boolean(a), self.numeric_boolean(b)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return np.divide(a, b)
        if op == "%":
            return np.mod(a, b)
        if op == "^":
            return np.power(a, b)
        raise StataError(f"Unsupported operator {op}")

    def call(self, name, args):
        from .dates import DATE_FUNCTIONS, date_call

        if name in DATE_FUNCTIONS:
            return date_call(name, args, self.df.index)
        unary = {
            "ln": np.log,
            "log": np.log,
            "log10": np.log10,
            "exp": np.exp,
            "sqrt": np.sqrt,
            "abs": np.abs,
            "floor": np.floor,
            "ceil": np.ceil,
            "int": np.trunc,
            "sin": np.sin,
            "cos": np.cos,
            "normal": special.ndtr,
            "invnormal": special.ndtri,
            "logit": special.logit,
            "invlogit": special.expit,
        }
        if name in unary and len(args) == 1:
            return unary[name](args[0])
        if name in ("runiform", "rnormal"):
            if (name == "runiform" and len(args) not in (0, 2)) or (
                name == "rnormal" and len(args) not in (0, 2)
            ):
                raise StataError("Expected zero or two random-distribution arguments")
            self.engine.notice(
                "RNG",
                "NumPy PCG64 is used. Stata seeds, draws and sample selections will differ, even with the same seed.",
            )
            a, b = args if args else ((0, 1))
            result = (
                self.engine.rng.uniform(a, b, len(self.df))
                if name == "runiform"
                else self.engine.rng.normal(a, b, len(self.df))
            )
            return pd.Series(result, index=self.df.index)
        if name == "missing" and args:
            result = pd.Series(False, index=self.df.index)
            for a in args:
                result |= self.series(a).isna() | self.series(a).eq("")
            return result
        if name == "cond" and len(args) == 3:
            return pd.Series(
                np.where(self.truth(args[0]), args[1], args[2]), index=self.df.index
            )
        if name == "inrange" and len(args) == 3:
            return self.binary(">=", args[0], args[1]) & self.binary(
                "<=", args[0], args[2]
            )
        if name == "inlist" and len(args) > 1:
            out = pd.Series(False, index=self.df.index)
            for a in args[1:]:
                out |= self.series(self.binary("==", args[0], a))
            return out
        if name in ("min", "max") and args:
            return pd.concat([self.series(a) for a in args], axis=1).agg(name, axis=1)
        if name == "mod" and len(args) == 2:
            return np.mod(args[0], args[1])
        if name == "sum" and len(args) == 1:
            return self.series(args[0]).fillna(0).cumsum()
        if name in ("lower", "upper", "trim", "strlen") and len(args) == 1:
            s = self.series(args[0]).fillna("").astype(str).str
            return {
                "lower": s.lower,
                "upper": s.upper,
                "trim": s.strip,
                "strlen": s.len,
            }[name]()
        if name == "real" and len(args) == 1:
            return pd.to_numeric(self.series(args[0]), errors="coerce")
        if name == "string" and len(args) == 1:
            return self.series(args[0]).map(
                lambda x: "." if pd.isna(x) else format(x, "g")
            )
        if name == "substr" and len(args) == 3:
            a, b, c = args
            start = int(b) - 1 if b > 0 else int(b)
            return (
                self.series(a)
                .astype(str)
                .str.slice(start, None if c < 0 else start + int(c))
            )
        if name == "round" and len(args) in (1, 2):
            a = args[0]
            unit = args[1] if len(args) == 2 else 1
            if unit <= 0:
                raise StataError("round() unit must be positive")
            self.engine.notice(
                "ROUND",
                "Halfway rounding uses NumPy ties-to-even and can differ from Stata.",
            )
            return np.round(a / unit) * unit
        raise StataError(f"Function {name} with {len(args)} arguments is not supported")
