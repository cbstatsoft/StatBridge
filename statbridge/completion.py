# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Context-sensitive, side-effect-free completion for incomplete Stata commands.

This recognises the syntax implemented by StatBridge. It deliberately leaves
free-text, filename and new-name positions alone rather than guessing variables.
"""

from dataclasses import dataclass
import re
from .catalog import COMMANDS, ALIASES

MODEL_COMMANDS = set(
    "regress logit logistic probit poisson nbreg qreg glm xtreg ivregress areg anova reghdfe".split()
)
NUMERIC_COMMANDS = MODEL_COMMANDS | set(
    "summarize correlate pwcorr ttest ranksum signrank swilk pca dfuller arima histogram scatter line tsset decode recode tostring mvencode mvdecode tabstat _pctile oneway spearman dtable lfit qnorm".split()
)
VARLIST_COMMANDS = NUMERIC_COMMANDS | set(
    "describe codebook list drop keep order sort gsort isid tabulate xtset destring ds levelsof contract".split()
)
EXPRESSION_COMMANDS = {"display", "assert", "if"}
PREFIXES = {"quietly", "noisily", "capture"}
FUNCTIONS = [
    name + "("
    for name in "ln log log10 exp sqrt abs floor ceil int sin cos normal invnormal logit invlogit runiform rnormal missing cond inrange inlist min max mod sum lower upper trim strlen real string substr round".split()
]
EGEN_FUNCTIONS = [
    name + "("
    for name in "mean sum total sd min max median count rowmean rowtotal group rowmiss rownonmiss rowmin rowmax rowsd std tag rank pctile concat".split()
]
OPTIONS = {
    "ls": ["all"],
    "mkdir": ["parents"],
    "findfile": ["depth("],
    "summarize": ["detail", "meanonly"],
    "use": ["clear"],
    "save": ["replace", "version("],
    "import": ["clear", "delimiter(", "encoding("],
    "export": ["replace", "delimiter("],
    "egen": ["by("],
    "duplicates": ["force"],
    "merge": ["nogen"],
    "collapse": ["by("],
    "reshape": ["i(", "j("],
    "encode": ["generate("],
    "decode": ["generate("],
    "destring": ["replace", "ignore(", "force"],
    "pwcorr": ["sig", "obs"],
    "tabulate": ["missing", "chi2", "row", "col"],
    "ttest": ["by(", "unequal", "level("],
    "ranksum": ["by("],
    "tsset": ["delta("],
    "xtset": ["delta("],
    "predict": ["xb", "residuals", "pr", "stdp", "stdf", "hat", "rstandard", "cooksd"],
    "margins": ["dydx("],
    "pca": ["components(", "covariance"],
    "dfuller": ["lags(", "trend", "noconstant"],
    "arima": ["arima(", "noconstant"],
    "histogram": ["bin(", "frequency", "percent", "density", "title("],
    "scatter": ["title("],
    "line": ["sort", "title("],
    "graph": ["replace"],
    "sample": ["count"],
    "log": ["text", "replace"],
    "lincom": [],
}
for _cmd in MODEL_COMMANDS:
    OPTIONS[_cmd] = ["vce(", "robust", "noconstant", "level("]
OPTIONS.update(
    {
        "areg": ["absorb(", "vce(", "robust", "level("],
        "anova": [],
        "recode": ["generate(", "prefix(", "copyrest"],
        "clonevar": [],
        "tostring": ["generate(", "replace", "format(", "force"],
        "split": ["parse(", "generate(", "limit(", "destring", "notrim"],
        "mvencode": ["mv(", "override"],
        "mvdecode": ["mv("],
        "misstable": ["all"],
        "ds": ["has(", "not"],
        "levelsof": ["local(", "missing", "clean", "separate("],
        "xtile": ["nquantiles(", "nq(", "altdef", "cutpoints("],
        "pctile": ["nquantiles(", "nq(", "altdef", "genp("],
        "_pctile": ["percentiles(", "p(", "nquantiles(", "altdef"],
        "expand": ["generate("],
        "contract": ["freq(", "percent(", "nomiss"],
        "tabstat": ["statistics(", "stat(", "by(", "missing", "columns("],
        "oneway": ["tabulate"],
        "spearman": ["pw", "stats("],
        "testparm": [],
        "lincom": ["level(", "eform"],
        "merge": ["nogen", "generate(", "keep(", "assert(", "keepusing("],
        "duplicates": ["force", "generate("],
        "egen": ["by(", "p(", "missing", "mean(", "std(", "punct("],
    }
)
OPTIONS["xtreg"] += ["fe", "re", "cre"]
OPTIONS["qreg"] += ["quantile("]
for _cmd in ("poisson", "nbreg"):
    OPTIONS[_cmd] += ["exposure(", "offset(", "irr"]
OPTIONS["glm"] += ["family(", "link(", "exposure(", "offset("]

OPTIONS.update(
    {
        "margins": ["dydx(", "at(", "over(", "level("],
        "marginsplot": ["title("],
        "qnorm": ["title("],
        "lfit": ["title("],
        "rvfplot": ["title("],
        "twoway": ["title("],
        "etable": ["estimates(", "level(", "export("],
        "esttab": ["se", "level(", "replace"],
        "dtable": ["by(", "export("],
        "reghdfe": ["absorb(", "vce(", "robust", "level(", "keepsingletons"],
        "didregress": ["group(", "time(", "vce(", "level("],
        "xtdidregress": ["group(", "time(", "level("],
    }
)
OPTIONS["dtabnk"] = [
    "clear",
    "preview",
    "merge",
    "on(",
    "join(",
    "conflicts(",
    "layout(",
    "id(",
    "yearcol(",
    "valuecol(",
    "seriescol(",
    "sheet(",
    "headerrow(",
    "delimiter(",
    "long",
    "aggregate(",
    "safe",
    "minfree(",
    "lazy(",
    "parquet(",
    "rows(",
    "saving(",
    "version(",
    "noload",
    "replace",
]
OPTIONS["import"] += ["sheet(", "cellrange(", "firstrow", "allstring"]
OPTIONS["export"] += ["sheet(", "cell(", "firstrow("]
FUNCTIONS += [
    name + "("
    for name in "date daily monthly quarterly clock mdy ym yq year month day dow dofm mofd dofq qofd dofc cofd".split()
]

MODEL_COMMANDS.update("mlogit ologit oprobit newey stcox".split())
NUMERIC_COMMANDS.update(
    MODEL_COMMANDS | set("mean total kwallis sdtest prtest ipolate xtsum stset".split())
)
VARLIST_COMMANDS.update(
    NUMERIC_COMMANDS | set("proportion tab1 tab2 inspect compare fillin svyset".split())
)
OPTIONS.update(
    {
        "mean": ["over(", "level("],
        "total": ["over(", "level("],
        "proportion": ["over(", "level("],
        "ci": ["level(", "exact", "wilson"],
        "prtest": ["by(", "level("],
        "sdtest": ["by(", "level("],
        "kwallis": ["by("],
        "tab1": ["missing"],
        "tab2": ["missing", "chi2", "row", "col"],
        "ipolate": ["generate(", "epolate"],
        "tsfill": ["full"],
        "newey": ["lag(", "level(", "noconstant"],
        "mlogit": ["baseoutcome(", "rrr", "level("],
        "ologit": ["level("],
        "oprobit": ["level("],
        "stset": ["failure(", "id(", "scale(", "clear"],
        "stsum": ["by("],
        "sts": ["by(", "title("],
        "stcox": ["ties(", "strata(", "nohr", "level("],
        "svyset": ["strata(", "clear"],
        "svy": ["subpop("],
    }
)
OPTIONS["predict"] += ["outcome(", "hr"]


@dataclass(frozen=True)
class Completion:
    text: str
    cursor: int


def structure(text):
    """Return top-level commas/colons and unmatched delimiters of partial input."""
    commas, colons, stack = [], [], []
    quote = False
    for i, char in enumerate(text):
        if char == '"':
            quote = not quote
        elif not quote:
            if text[i : i + 2] in ("//", "/*"):
                return commas, colons, stack, quote, True
            if char in "([":
                match = re.search(r"([A-Za-z_]\w*)$", text[:i])
                stack.append((char, i, match[1] if match else ""))
            elif char in ")]":
                if stack:
                    stack.pop()
            elif not stack and char == ",":
                commas.append(i)
            elif not stack and char == ":":
                colons.append(i)
    return commas, colons, stack, quote, False


class Suggestions:
    def __init__(self):
        self.cwd = None
        self.syntax_mode = "stata"
        self.history = []
        self.variables = []
        self.variable_types = {}  # numeric/string; missing metadata is permissive
        self.coefficients = []
        self.estimates = []
        self.local_names = []
        self.global_names = []
        self.scalar_names = []
        self.result_names = {"r": [], "e": []}
        self.label_names = []
        self.outcomes = []

    def sync(self, engine):
        """Refresh metadata after loading, editing, renaming or fitting data."""
        self.cwd = engine.cwd
        self.syntax_mode = getattr(engine, "syntax_mode", "stata")
        self.variables = list(engine.df.columns)
        numeric = set(engine.df.select_dtypes(include=["number", "bool"]).columns)
        self.variable_types = {
            v: "numeric" if v in numeric else "string" for v in self.variables
        }
        self.coefficients = list(engine.model.params.index) if engine.model else []
        self.estimates = list(engine.stored)
        self.local_names = list(engine.locals)
        self.global_names = list(engine.globals)
        self.scalar_names = list(engine.scalars)
        self.result_names = {"r": list(engine.r), "e": list(engine.e)}
        self.label_names = list(engine.label_sets)
        self.outcomes = (
            [f"{x:g}" for x in (engine.model.metadata or {}).get("categories", [])]
            if engine.model
            else []
        )

    def vars(self, kind=None):
        return [
            v
            for v in self.variables
            if kind is None or self.variable_types.get(v, kind) == kind
        ]

    def candidates(self, text, cursor=None):
        return [c.text for c in self.complete(text, cursor)]

    def complete(self, text, cursor=None):
        cursor = len(text) if cursor is None else max(0, min(cursor, len(text)))
        from .path_completion import path_completions

        paths = path_completions(text, cursor, self.cwd)
        if paths is not None:
            return [Completion(value, position) for value, position in paths]
        left, right = text[:cursor], text[cursor:]
        if not left.strip():
            return []
        stems = self._candidates(left, include_history=cursor == len(text))
        # Replace the rest of the current identifier when editing inside a token.
        tail = (
            re.sub(r"^[\w.]+", "", right)
            if left and re.search(r"[\w.]$", left)
            else right
        )
        out = []
        for value in stems:
            suffix = tail
            if value.endswith((")", "]", "}", "'")) and suffix.startswith(value[-1]):
                suffix = suffix[1:]
            out.append(Completion(value + suffix, len(value)))
        return out

    def _logos_candidates(self, text):
        """Complete only documented Logos statements; never invent free text."""
        phrases = [
            "show variables", "describe dataset", "summarise ",
            "summary of ", "average of ", "count rows",
            "count rows where ", "keep rows where ", "drop rows where ",
            "list rows with ", "regress ", "fit linear model ",
            "fit logistic model ", "fit probit model ",
            "create ", "let ", "tabulate ", "correlate ",
            "histogram of ", "every row satisfies ", "there exists a row where ",
            "∀ rows: ", "∃ row: ", "predict fitted values as ",
            "predict residuals as ", "explain ", "syntax stata",
            "stata: ", "logos: ",
        ]
        prefix = text.lstrip()
        roots = [x for x in phrases if x.lower().startswith(prefix.lower()) and x != prefix]
        if roots:
            return [text[:len(text)-len(prefix)] + x for x in roots]
        match = re.match(
            r"^(regress\s+|regress\s+\w+\s+on\s+|summari[sz]e\s+|"
            r"summary\s+of\s+|average\s+of\s+|"
            r"tabulate\s+|correlate\s+)([A-Za-z_]\w*)$",
            prefix, flags=re.I
        )
        if match:
            return [
                text[:len(text) - len(match[2])] + var
                for var in self.variables
                if var.lower().startswith(match[2].lower()) and var != match[2]
            ]
        return []

    def _candidates(self, text, include_history=True):
        if text.lstrip().startswith("*"):
            return []
        if self.syntax_mode == "logos" and not text.lstrip().startswith("stata:"):
            return self._logos_candidates(text)
        survey = re.match(r"^(\s*svy(?:\s*,[^:]*)?\s*:\s*)(.*)$", text)
        if survey:
            prefix, tail = survey.groups()
            if not re.search(r"\S+\s", tail):
                return [
                    prefix + x
                    for x in ("mean", "total", "proportion", "regress")
                    if x.startswith(tail) and x != tail
                ]
            return [prefix + x for x in self._candidates(tail, include_history=False)]
        commas, colons, stack, quoted, comment = structure(text)
        if comment:
            return []
        # Macros may occur inside quoted strings and filenames.
        macro = re.search(r"(`|\$\{?)([A-Za-z_]\w*|)$", text)
        if macro and macro[1]:
            names = self.local_names if macro[1] == "`" else self.global_names
            end = "'" if macro[1] == "`" else "}" if macro[1] == "${" else ""
            return [
                text[: macro.start(2)] + name + end
                for name in names
                if name.startswith(macro[2])
            ]
        if quoted:
            return []
        coefficient = re.search(r"_(b|se)\[([^\]]*)$", text)
        if coefficient:
            return [
                text[: coefficient.start(2)] + name + "]"
                for name in self.coefficients
                if name.startswith(coefficient[2])
            ]
        result = re.search(r"\b([re])\((\w*)$", text)
        if result:
            names = self.result_names[result[1]] + (
                ["sample"] if result[1] == "e" and self.coefficients else []
            )
            return [
                text[: result.start(2)] + name + ")"
                for name in dict.fromkeys(names)
                if name.startswith(result[2])
            ]

        # Peel off command prefixes without confusing merge 1:1 with by's colon.
        start = len(text) - len(text.lstrip())
        while True:
            first = re.match(r"(\S+)(\s+)", text[start:])
            if not first:
                break
            canonical = ALIASES.get(first[1], first[1])
            if canonical in PREFIXES:
                start += first.end()
            elif canonical in ("by", "bysort", "bootstrap"):
                colon = next((i for i in colons if i >= start), None)
                if colon is not None:
                    start = colon + 1
                    start += len(text[start:]) - len(text[start:].lstrip())
                elif canonical in ("by", "bysort"):
                    return self._tokens(
                        text, self.vars(), exclude=text[start + first.end() :]
                    )
                else:
                    return []
            else:
                break
        active = text[start:]
        match = re.match(r"([^\s,]+)([\s,])", active)
        if not match:
            pool = (
                list(COMMANDS)
                + list(ALIASES)
                + ["quietly", "noisily", "capture", "by", "bysort"]
            )
            options = [
                text[:start] + name
                for name in sorted(set(pool))
                if name.startswith(active) and name != active
            ]
            history = [
                h
                for h in reversed(self.history)
                if include_history and h.startswith(text) and h != text
            ]
            return list(dict.fromkeys(history + options))
        cmd = ALIASES.get(match[1], match[1])
        arg_start = start + len(match[1])
        comma = next((i for i in commas if i >= arg_start), None)
        if comma is not None:
            return self._options(text, cmd, comma, stack)
        args = text[arg_start:].lstrip()
        # Weight expressions and if qualifiers use expressions, not varlists.
        if re.search(r"\[(?:aw|fw|pw|aweight|fweight|pweight)\s*=[^\]]*$", args):
            return self._expression(text, numeric=True)
        if re.search(r"\bif\s+", args):
            return self._expression(text)
        if re.search(r"\bin\s+", args):
            return self._tokens(text, ["f", "l"])
        if cmd in ("generate", "scalar", "local", "global", "egen"):
            if "=" not in args:
                return []  # a new variable/macro name is not an existing variable
            if cmd == "egen" and "(" not in args.split("=", 1)[1]:
                return self._tokens(text, EGEN_FUNCTIONS)
            if cmd == "egen":
                fn = re.search(r"=\s*(\w+)\(([^)]*)$", args)
                if fn:
                    kind = (
                        None
                        if fn[1]
                        in ("group", "count", "tag", "concat", "rowmiss", "rownonmiss")
                        else "numeric"
                    )
                    return self._tokens(text, self.vars(kind), exclude=fn[2])
                return []
            return self._expression(text)
        if cmd == "replace":
            return (
                self._expression(text)
                if "=" in args
                else self._tokens(text, self.vars())
            )
        if cmd in EXPRESSION_COMMANDS:
            return self._expression(text)
        if cmd in ("test", "testparm", "lincom"):
            return self._tokens(
                text,
                self.coefficients,
                exclude=args if cmd == "test" else "",
                token_pattern=r"[\w.]*$",
            )
        if cmd in ("clonevar", "xtile", "pctile"):
            return self._expression(text) if "=" in args else []
        if cmd == "split":
            return self._tokens(text, self.vars("string"))
        if cmd == "misstable":
            if not re.match(r"^(summarize|patterns)\s", args):
                return self._tokens(text, ["summarize", "patterns"])
            return self._tokens(text, self.vars())
        if cmd == "predict":
            return []
        if cmd == "rename":
            return (
                self._tokens(text, self.vars())
                if len(args.split()) < 2 and not (args.strip() and args.endswith(" "))
                else []
            )
        if cmd == "encode":
            return self._tokens(text, self.vars("string"))
        if cmd in ("help",):
            return self._tokens(text, list(COMMANDS))
        if cmd == "set":
            return self._subcommand(
                text,
                args,
                ["obs", "seed", "level", "more", "databackend"],
                {"more": ["on", "off"], "databackend": ["auto", "polars", "pandas"]},
            )
        if cmd == "estimates":
            return self._subcommand(
                text,
                args,
                ["store", "restore", "dir", "table"],
                {"restore": self.estimates, "table": self.estimates},
            )
        if cmd == "esttab":
            return self._tokens(text, self.estimates + ["using"], exclude=args)
        if cmd == "margins":
            return self._tokens(text, self.vars("numeric"), exclude=args)
        if cmd == "hausman":
            return self._tokens(text, self.estimates, exclude=args)
        if cmd == "estat":
            return self._tokens(
                text,
                [
                    "vif",
                    "hettest",
                    "ic",
                    "ovtest",
                    "mundlak",
                    "firststage",
                    "endogenous",
                    "overid",
                ],
            )
        if cmd in ("return", "ereturn"):
            return self._tokens(text, ["list"])
        if cmd == "clear":
            return self._tokens(text, ["all"])
        if cmd == "label":
            return self._label(text, args)
        if cmd == "duplicates":
            if not re.match(r"(report|list|drop|tag)\s+", args):
                return self._tokens(text, ["report", "list", "drop", "tag"])
            return self._tokens(text, self.vars(), exclude=args)
        if cmd == "merge":
            if not re.match(r"(1:1|1:m|m:1)\s+", args):
                return self._tokens(
                    text, ["1:1", "1:m", "m:1"], token_pattern=r"[^\s]*$"
                )
            if re.search(r"\busing\s+", args):
                return []
            return self._tokens(text, self.vars() + ["using"], exclude=args)
        if cmd == "ivregress" and not re.match(r"2sls\s+", args):
            return self._tokens(text, ["2sls"])
        if cmd == "collapse":
            if stack and stack[-1][0] == "(":
                return self._tokens(
                    text,
                    [
                        x + ")"
                        for x in [
                            "mean",
                            "sum",
                            "count",
                            "sd",
                            "min",
                            "max",
                            "median",
                            "first",
                            "last",
                        ]
                    ],
                )
            return self._tokens(text, self.vars("numeric"), exclude=args)
        if cmd == "reshape":
            return self._subcommand(text, args, ["long", "wide"], {})
        if cmd in ("import", "export"):
            from .format_io import EXTENSIONS, ALIASES as IO_ALIASES

            formats = ["excel"] + list(EXTENSIONS) + list(IO_ALIASES)
            formats += ["results"] if cmd == "export" else ["auto"]
            if (
                cmd == "export"
                and re.match(r"\S+\s+", args)
                and not re.search(r"\busing\b", args)
            ):
                return self._tokens(
                    text,
                    self.vars() + ["using"],
                    exclude=(
                        args.split(None, 1)[1] if len(args.split(None, 1)) > 1 else ""
                    ),
                )
            return self._subcommand(text, args, formats, {})
        if cmd == "append":
            return self._subcommand(text, args, ["using"], {})
        if cmd == "graph":
            if re.match(r"(?:box|bar)\s+", args):
                return self._tokens(text, self.vars("numeric"), exclude=args)
            return self._subcommand(text, args, ["export", "box", "bar"], {})
        if cmd == "ci":
            if re.match(r"(?:means|proportions)\s+", args):
                return self._tokens(text, self.vars("numeric"), exclude=args)
            return self._subcommand(text, args, ["means", "proportions"], {})
        if cmd == "sts":
            return self._subcommand(
                text, args, ["list", "graph", "test"], {"test": self.vars()}
            )
        if cmd == "log":
            return self._subcommand(text, args, ["using", "close"], {})
        if cmd == "compatibility":
            return self._subcommand(text, args, ["export"], {})
        if cmd == "count":
            return self._tokens(text, ["if", "in"])
        if cmd in VARLIST_COMMANDS:
            numeric = cmd in NUMERIC_COMMANDS
            decoration = re.search(r"((?:i|c|ib\d+|(?:[LFDSlfds]\d*)+)\.)(\w*)$", text)
            if decoration:
                return [
                    text[: decoration.start(2)] + v
                    for v in self.vars("numeric")
                    if v.startswith(decoration[2])
                ]
            pool = self.vars("numeric" if numeric else None)
            finished = (
                args.split()[:-1]
                if args and not args.endswith((" ", "\t"))
                else args.split()
            )
            limit = {
                "tsset": 1,
                "xtset": 2,
                "decode": 1,
                "histogram": 1,
                "arima": 1,
                "dfuller": 1,
                "ranksum": 1,
                "scatter": 2,
                "line": 2,
                "tabulate": 2,
            }.get(cmd)
            if limit is not None and len(finished) >= limit:
                pool = []
            if cmd in ("ttest", "signrank") and finished:
                operator = "==" if cmd == "ttest" else "="
                if "=" not in args:
                    return self._tokens(text, [operator, "if", "in"])
            if (
                cmd
                in {
                    "list",
                    "summarize",
                    "drop",
                    "keep",
                    "correlate",
                    "pwcorr",
                    "tabulate",
                    "ttest",
                    "ranksum",
                    "signrank",
                    "swilk",
                    "pca",
                    "dfuller",
                    "arima",
                    "histogram",
                    "scatter",
                    "line",
                }
                | MODEL_COMMANDS
            ):
                if args.strip():
                    pool = pool + ["if", "in"]
            return self._tokens(text, pool, exclude=args)
        return []

    def _tokens(self, text, pool, exclude="", token_pattern=r"[A-Za-z_][\w.]*$|$"):
        match = re.search(token_pattern, text)
        stem, prefix = text[: match.start()], match[0]
        # Do not offer identifier suffixes after a numeric literal.
        if not prefix and text and (text[-1].isdigit() or text[-1] in "\"'"):
            return []
        used = set(exclude[: len(exclude) - len(prefix)].split()) if exclude else set()
        return [
            stem + name
            for name in sorted(set(pool))
            if name.startswith(prefix) and name not in used and stem + name != text
        ]

    def _expression(self, text, numeric=False):
        decoration = re.search(r"((?:[LFDSlfds]\d*)+)\.(\w*)$", text)
        if decoration:
            return [
                text[: decoration.start(2)] + name
                for name in self.vars("numeric")
                if name.startswith(decoration[2])
            ]
        return self._tokens(
            text,
            self.vars("numeric" if numeric else None)
            + self.scalar_names
            + FUNCTIONS
            + ["_n", "_N", "_b[", "_se["],
        )

    def _subcommand(self, text, args, names, values):
        bits = args.split()
        if len(bits) <= 1 and not (args.strip() and args.endswith((" ", "\t"))):
            return self._tokens(text, names)
        return (
            self._tokens(text, values.get(bits[0], []))
            if bits
            else self._tokens(text, names)
        )

    def _label(self, text, args):
        bits = args.split()
        if len(bits) <= 1 and not (args.strip() and args.endswith((" ", "\t"))):
            return self._tokens(text, ["variable", "values", "define", "data"])
        if bits and bits[0] in ("variable", "values"):
            if len(bits) == 1 or (len(bits) == 2 and not args.endswith((" ", "\t"))):
                return self._tokens(text, self.vars())
            if bits[0] == "values":
                return self._tokens(text, self.label_names)
        return []

    def _options(self, text, cmd, comma, stack):
        # Option arguments are typed: vce values are not variable names until cluster.
        opened = [entry for entry in stack if entry[1] > comma and entry[0] == "("]
        if opened:
            _, pos, name = opened[-1]
            arg = text[pos + 1 :]
            if name == "vce":
                if re.match(r"cluster\s+", arg):
                    if cmd == "reghdfe":
                        return self._tokens(text, self.vars(), exclude=arg)
                    return self._tokens(text, [v + ")" for v in self.vars()])
                choices = ["robust)", "cluster "]
                if cmd == "regress" and not re.search(
                    r"\[(?:aw|fw|pw|aweight|fweight|pweight)\s*=", text[:comma]
                ):
                    choices += ["hc2)", "hc3)"]
                return self._tokens(text, choices)
            if cmd == "dtabnk":
                choices = {
                    "layout": [
                        "auto",
                        "wide",
                        "wide_header_series",
                        "long",
                        "year_rows",
                    ],
                    "join": ["outer", "inner", "left"],
                    "conflicts": ["suffix", "error"],
                    "aggregate": ["error", "mean"],
                }
                if name in choices:
                    return self._tokens(text, [x + ")" for x in choices[name]])
                if name == "on":
                    return self._tokens(
                        text, ["Country", "Year", "Series", "Series_Code"], exclude=arg
                    )
                if name in ("id", "yearcol", "valuecol", "seriescol", "sheet"):
                    return []  # Source columns are not the active dataset's columns.
            if name == "estimates":
                return self._tokens(text, self.estimates, exclude=arg)
            if name == "at" and (not arg or re.search(r"(?:^|\s)[A-Za-z_]\w*$", arg)):
                return self._tokens(text, [v + "=" for v in self.vars("numeric")])
            if name in (
                "by",
                "i",
                "j",
                "over",
                "group",
                "time",
                "absorb",
                "strata",
                "id",
            ):
                return self._tokens(text, self.vars())
            if name in (
                "exposure",
                "offset",
                "absorb",
                "cutpoints",
                "failure",
                "subpop",
            ):
                return self._tokens(text, self.vars("numeric"))
            if cmd == "merge" and name in ("keep", "assert"):
                return self._tokens(text, ["master", "using", "match"], exclude=arg)
            if cmd == "tabstat" and name in ("statistics", "stat"):
                return self._tokens(
                    text,
                    "n mean sd min max median p25 p75 sum var semean iqr".split(),
                    exclude=arg,
                )
            if cmd == "tabstat" and name == "columns":
                return self._tokens(text, ["variables)", "statistics)"])
            if cmd == "spearman" and name == "stats":
                return self._tokens(text, ["rho", "p", "obs"], exclude=arg)
            if cmd == "ds" and name == "has":
                return (
                    self._tokens(text, ["numeric)", "string)"])
                    if arg.startswith("type ")
                    else self._tokens(text, ["type "])
                )
            if name == "outcome":
                return self._tokens(
                    text,
                    [v + ")" for v in self.outcomes],
                    token_pattern=r"-?\d*(?:\.\d*)?$",
                )
            if name == "ties":
                return self._tokens(text, ["breslow)", "efron)"])
            if name == "family":
                return self._tokens(
                    text,
                    [v + ")" for v in ["gaussian", "binomial", "poisson", "gamma"]],
                )
            if name == "link":
                family = re.search(r"\bfamily\((\w+)\)", text[comma:])
                links = {
                    "gaussian": ["identity", "log", "inverse"],
                    "binomial": ["logit", "probit", "log", "identity"],
                    "poisson": ["log", "identity"],
                    "gamma": ["inverse", "log", "identity"],
                }
                return self._tokens(
                    text,
                    [
                        v + ")"
                        for v in links.get(family[1] if family else "gaussian", [])
                    ],
                )
            if cmd in ("import", "export") and name == "compression":
                from .format_io import ALIASES as IO_ALIASES

                kind = text.split()[1]
                kind = IO_ALIASES.get(kind, kind)
                choices = {
                    "parquet": ["none", "snappy", "gzip", "brotli", "lz4", "zstd"],
                    "arrow": ["none", "lz4", "zstd"],
                    "feather": ["none", "lz4", "zstd"],
                    "sav": ["none", "row", "zlib"],
                    "rdata": ["none", "gzip"],
                    "rds": ["none", "gzip"],
                }.get(kind, [])
                return self._tokens(text, [x + ")" for x in choices])
            if (
                cmd == "export"
                and name == "version"
                and re.match(r"export\s+(?:xport|sasxport)\b", text)
            ):
                return self._tokens(text, ["5)", "8)"], token_pattern=r"\d*$")
            if name == "version":
                return self._tokens(text, ["13)", "14)", "15)"], token_pattern=r"\d*$")
            if name == "dydx":
                return self._tokens(text, ["*)"] + self.vars("numeric"), exclude=arg)
            # Numeric settings, free text and new variable names have no variable completion.
            return []
        raw = text[comma + 1 :]
        current = re.search(r"[A-Za-z_]\w*$|$", raw)
        before = raw[: current.start()]
        used = set(re.findall(r"(\w+)\s*(?:\([^)]*\))?(?:\s+|$)", before))
        pool = [opt for opt in OPTIONS.get(cmd, []) if opt.rstrip("(") not in used]
        if cmd == "graph":
            pool = [
                x
                for x in (
                    ["over(", "title("]
                    if re.search(r"\b(?:box|bar)\s", text[:comma])
                    else ["replace"]
                )
                if x.rstrip("(") not in used
            ]
        if cmd == "sts":
            pool = [
                x
                for x in (
                    []
                    if re.search(r"\btest\s", text[:comma])
                    else (
                        ["by(", "title("]
                        if re.search(r"\bgraph\b", text[:comma])
                        else ["by("]
                    )
                )
                if x.rstrip("(") not in used
            ]
        if cmd in ("import", "export"):
            from .format_io import ALIASES as IO_ALIASES, ARROW

            parts = text[:comma].split()
            kind = IO_ALIASES.get(parts[1], parts[1]) if len(parts) > 1 else ""
            if kind == "excel":
                choices = (
                    ["clear", "sheet(", "cellrange(", "firstrow", "allstring"]
                    if cmd == "import"
                    else ["replace", "sheet(", "cell(", "firstrow("]
                )
            elif kind == "results":
                choices = ["replace"]
            else:
                choices = (
                    ["clear", "preview", "rows(", "rename"]
                    if cmd == "import"
                    else ["replace"]
                )
                if kind == "delimited":
                    choices += ["delimiter(", "encoding("]
                if kind == "rdata":
                    choices += ["object("]
                if kind == "sqlite":
                    choices += ["table("]
                if kind == "workbook":
                    choices += ["sheet("]
                if kind == "hdf5" and cmd == "import":
                    choices += ["group("]
                if cmd == "export" and (
                    kind in ARROW or kind in ("sav", "rdata", "rds")
                ):
                    choices += ["compression("]
                if cmd == "export" and kind in ("stata", "xport"):
                    choices += ["version("]
            pool = [x for x in choices if x.rstrip("(") not in used]
        if "robust" in used:
            pool = [v for v in pool if v != "vce("]
        if "vce" in used:
            pool = [v for v in pool if v != "robust"]
        if {"fe", "re", "cre"} & used:
            pool = [v for v in pool if v not in ("fe", "re", "cre")]
        return self._tokens(text, pool)
