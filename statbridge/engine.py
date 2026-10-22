# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
from __future__ import annotations
import copy
import fnmatch
import importlib.metadata
import json
import re
import threading
from pathlib import Path
import numpy as np
import pandas as pd
from .syntax import StataError, Expression, split_top, words, unquote
from .catalog import COMMANDS, ALIASES
from .data import DataCommands
from .common_data import CommonDataCommands
from .models import ModelCommands
from .common_models import CommonModelCommands
from .model_diagnostics import ModelDiagnostics
from .anova_extensions import AnovaExtensions
from .filesystem import FileCommands
from .result_tables import ResultTables
from .marginal import MarginalCommands
from .panel_extensions import PanelExtensions
from .excel_io import ExcelCommands
from .graphics_extra import GraphicsCommands
from .databank import DatabankCommands
from .format_io import FormatIOCommands
from .everyday import EverydayCommands
from .extended_models import ExtendedModelCommands
from .survey import SurveyCommands


class Engine(
    ModelDiagnostics,
    AnovaExtensions,
    EverydayCommands,
    ExtendedModelCommands,
    SurveyCommands,
    FormatIOCommands,
    DatabankCommands,
    GraphicsCommands,
    ExcelCommands,
    PanelExtensions,
    MarginalCommands,
    ResultTables,
    CommonDataCommands,
    DataCommands,
    CommonModelCommands,
    ModelCommands,
    FileCommands,
):
    def __init__(self, emit=None, cwd=None):
        self.df = pd.DataFrame()
        from .data_backend import DataBackend

        self.data_backend = "auto"
        self.data_ops = DataBackend(self)
        self.labels = {}
        self.value_labels = {}
        self.label_sets = {}
        self.formats = {}
        self.file_label = ""
        self.cwd = Path(cwd or Path.cwd()).resolve()
        self.previous_cwd = None
        self.filename = None
        self.dirty = False
        self.locals = {}
        self.globals = {}
        self.scalars = {}
        self.r = {}
        self.e = {}
        self.rng = np.random.default_rng()
        self.panel = None
        self.tsvar = None
        self.time_delta = 1.0
        self.survey_design = None
        self.survival_set = False
        self.model = None
        self.stored = {}
        self.preserved = None
        self.revision = 0
        self.level = 95.0
        self.events = []
        self.emit_callback = emit
        self.history = []
        self.ledger = []
        self.notices = []
        self.stop = threading.Event()
        self.quiet = False
        self.logfile = None
        self.figure = None
        self._command = ""
        self._command_notices = set()
        self._depth = 0
        self.versions = {
            p: importlib.metadata.version(p)
            for p in [
                "numpy",
                "pandas",
                "polars",
                "pyarrow",
                "scipy",
                "statsmodels",
                "linearmodels",
                "pyreadstat",
                "matplotlib",
            ]
        }

    def emit(self, kind, text="", payload=None):
        event = {"kind": kind, "text": str(text), "payload": payload}
        self.events.append(event)
        if len(self.events) > 5000:
            self.events = self.events[-2500:]
        if self.logfile and kind in (
            "command",
            "output",
            "warning",
            "error",
            "translation",
        ):
            self.logfile.write(str(text) + "\n")
            self.logfile.flush()
        if self.emit_callback and (
            not self.quiet or kind in ("warning", "error", "graph")
        ):
            self.emit_callback(event)

    def out(self, text):
        if not self.quiet:
            self.emit("output", text)

    def notice(self, code, message):
        if code in self._command_notices:
            return
        self._command_notices.add(code)
        record = {"command": self._command, "code": code, "message": message}
        self.notices.append(record)
        self.emit("warning", f"[{code}] {message}")

    def path(self, text, extension=None):
        p = Path(unquote(text)).expanduser()
        if not p.is_absolute():
            p = self.cwd / p
        if extension and not p.suffix:
            p = p.with_suffix(extension)
        return p.resolve()

    def expr(self, text, frame=None):
        return Expression(self, frame).evaluate(text)

    def varlist(self, text, default=False, numeric=False):
        cols = list(self.df.columns)
        result = []
        for token in words(text):
            if token == "_all":
                found = cols
            elif token in cols:
                found = [token]
            elif "-" in token:
                a, b = token.split("-", 1)
                if a not in cols or b not in cols:
                    raise StataError(f"Invalid variable range: {token}", 111)
                ia, ib = cols.index(a), cols.index(b)
                if ia > ib:
                    raise StataError("Variable range is reversed")
                found = cols[ia : ib + 1]
            elif "*" in token or "?" in token:
                found = [c for c in cols if fnmatch.fnmatchcase(c, token)]
            else:
                found = [c for c in cols if c.startswith(token)]
                if len(found) > 1:
                    raise StataError(f"Ambiguous variable abbreviation: {token}", 111)
            if not found:
                raise StataError(f"Variable {token} not found", 111)
            result.extend(c for c in found if c not in result)
        if not result and default:
            result = cols
        if numeric:
            bad = [c for c in result if not pd.api.types.is_numeric_dtype(self.df[c])]
            if bad:
                raise StataError("Numeric variables required: " + ", ".join(bad), 109)
        return result

    def mask(self, q):
        mask = pd.Series(True, index=self.df.index)
        if "if" in q:
            mask &= Expression(self).truth(self.expr(q["if"]))
        if "in" in q:
            n = len(self.df)

            def idx(s):
                if s in ("l", "L"):
                    return n
                if s in ("f", "F"):
                    return 1
                v = int(s)
                return n + v + 1 if v < 0 else v

            parts = q["in"].split("/")
            a = idx(parts[0])
            b = idx(parts[-1])
            if not 1 <= a <= b <= n:
                raise StataError("Invalid observation range")
            mask &= pd.Series(
                (np.arange(n) >= a - 1) & (np.arange(n) < b), index=self.df.index
            )
        return mask

    def newvar(self, name):
        if not re.fullmatch(r"[A-Za-z_]\w{0,31}", name):
            raise StataError(f"Invalid variable name: {name}")
        if name in self.df:
            raise StataError(f"Variable {name} already defined", 110)

    def changed(self):
        self.df = self.df.reset_index(drop=True)
        self.dirty = True
        self.revision += 1
        self.labels = {k: v for k, v in self.labels.items() if k in self.df}
        self.value_labels = {k: v for k, v in self.value_labels.items() if k in self.df}
        self.formats = {k: v for k, v in self.formats.items() if k in self.df}
        self.model = None
        self.e = {}
        if self.tsvar and self.tsvar not in self.df:
            self.tsvar = None
        if self.panel and any(x not in self.df for x in self.panel if x):
            self.panel = None

    def snapshot(self):
        return copy.deepcopy(
            (
                self.df,
                self.labels,
                self.value_labels,
                self.formats,
                self.file_label,
                self.panel,
                self.filename,
                self.dirty,
                self.label_sets,
                self.tsvar,
                self.time_delta,
                self.survey_design,
                self.survival_set,
            )
        )

    def load_snapshot(self, state):
        (
            self.df,
            self.labels,
            self.value_labels,
            self.formats,
            self.file_label,
            self.panel,
            self.filename,
            self.dirty,
            self.label_sets,
            self.tsvar,
            self.time_delta,
            self.survey_design,
            self.survival_set,
        ) = copy.deepcopy(state)
        self.model = None
        self.e = {}
        self.revision += 1

    def expand(self, text):
        for _ in range(20):
            before = text
            text = re.sub(
                r"`([re])\((\w+)\)'",
                lambda m: str((self.r if m[1] == "r" else self.e).get(m[2], "")),
                text,
            )
            text = re.sub(
                r"`([A-Za-z_]\w*)\'", lambda m: self.locals.get(m[1], ""), text
            )
            text = re.sub(
                r"\$\{([A-Za-z_]\w*)\}|\$([A-Za-z_]\w*)",
                lambda m: self.globals.get(m[1] or m[2], ""),
                text,
            )
            if text == before:
                return text
        raise StataError("Macro expansion limit reached")

    def execute(self, text, line=None):
        """One logical command, returning success. Do-files use this same entry point."""
        text = self.expand(text.strip())
        if not text:
            return True
        if self.stop.is_set():
            raise StataError("Execution interrupted", 1)
        self._command = text
        self._command_notices = set()
        self.history.append(text)
        previous_quiet = self.quiet
        capture = False
        while True:
            parts = text.split(None, 1)
            first = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            first = ALIASES.get(first, first)
            if first in ("capture", "quietly", "noisily"):
                if first == "capture":
                    capture = True
                else:
                    self.quiet = first == "quietly"
                text = rest.strip()
            else:
                break
        if not self.quiet:
            self.emit("command", ". " + text)
        firstword = text.split(None, 1)[0].split(",")[0]
        canonical = ALIASES.get(firstword, firstword)
        if canonical in ("svy:", "svy,"):
            canonical = "svy"
        record = {
            "command": text,
            "canonical": canonical,
            "backend": COMMANDS.get(canonical, ("", "interpreter"))[1],
            "status": "running",
        }
        self.ledger.append(record)
        try:
            self.dispatch(text)
            record["status"] = "ok"
            self.scalars["_rc"] = 0
            return True
        except Exception as exc:
            code = exc.code if isinstance(exc, StataError) else 498
            record["status"] = "captured-error" if capture else "error"
            record["error"] = str(exc)
            self.scalars["_rc"] = code
            self.emit(
                "error",
                f"{'line ' + str(line) + ': ' if line else ''}{exc}\nr({code});"
                + (" [captured]" if capture else ""),
            )
            return capture
        finally:
            record["notices"] = sorted(self._command_notices)
            self.quiet = previous_quiet

    def dispatch(self, text):
        if re.match(r"^svy(?:\s|,|:)", text):
            return self.survey_command(text)
        text = re.sub(r"^bys\s", "bysort ", text)
        if re.match(r"^(by|bysort)\s", text):
            return self.by_command(text)
        if re.match(r"^bootstrap\s", text):
            return self.bootstrap(text)
        parts = text.split(None, 1)
        cmd = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        cmd = ALIASES.get(cmd, cmd)
        # Commands may be followed directly by a comma, e.g. summarize, detail.
        if "," in cmd:
            cmd, tail = cmd.split(",", 1)
            cmd = ALIASES.get(cmd, cmd)
            rest = "," + tail + " " + rest
        pieces = split_top(rest)
        if len(pieces) > 2:
            raise StataError("Unexpected top-level comma")
        args = pieces[0]
        opt = pieces[1] if len(pieces) == 2 else ""
        from .weights import extract_weight

        _, weight = extract_weight(args)
        if weight is not None and cmd not in ("regress", "summarize", "svyset"):
            raise StataError(
                f"Weights are not implemented for {cmd}; no unweighted substitute was run"
            )
        handler = getattr(self, "cmd_" + cmd, None)
        if handler is None:
            raise StataError(
                f"Command {cmd!r} is unsupported. Use help to see implemented syntax.",
                199,
            )
        if cmd in COMMANDS:
            self.emit("translation", f"↳ {COMMANDS[cmd][1]}")
        return handler(args, opt)

    def run(self, source, echo=True):
        from .scripting import compile_script, run_nodes, DoExit

        if self._depth >= 20:
            raise StataError("Nested do-file depth limit reached")
        self._depth += 1
        try:
            nodes = compile_script(source)
            return run_nodes(self, nodes, echo)
        except DoExit:
            return True
        except StataError as exc:
            self.scalars["_rc"] = exc.code
            self.emit("error", f"{exc}\nr({exc.code});")
            return False
        finally:
            self._depth -= 1

    def loop_values(self, text):
        m = re.fullmatch(r"foreach\s+(\w+)\s+(in|of varlist|of numlist)\s+(.+)", text)
        if m:
            name, kind, items = m.groups()
            vals = self.varlist(items) if kind == "of varlist" else words(items)
            if kind == "of numlist":
                vals = [v for part in vals for v in self.number_range(part)]
            return name, [unquote(v) if isinstance(v, str) else v for v in vals]
        m = re.fullmatch(r"forvalues\s+(\w+)\s*=\s*(.+)", text)
        if m:
            return m[1], self.number_range(m[2])
        raise StataError("Unsupported loop syntax")

    @staticmethod
    def number_range(text):
        if re.fullmatch(r"-?\d+", text):
            return [int(text)]
        m = re.fullmatch(r"(-?\d+)(?:/|\((-?\d+)\))(-?\d+)", text)
        if not m:
            raise StataError("Expected integer a/b or a(step)b")
        a, step, b = int(m[1]), int(m[2] or 1), int(m[3])
        if not step or (b - a) * step < 0:
            raise StataError("Invalid loop step")
        if abs((b - a) // step) > 100000:
            raise StataError("Loop exceeds 100,000 iterations")
        return range(a, b + (1 if step > 0 else -1), step)

    def by_command(self, text):
        pieces = split_top(text, ":")
        if len(pieces) != 2:
            raise StataError("Expected by variables: command")
        prefix, command = pieces
        kind, keys = prefix.split(None, 1)
        match = re.fullmatch(r"(.+?)(?:\s*\(([^()]*)\))?", keys)
        if not match:
            raise StataError("Expected by groups (within_group_sort): command")
        cols = self.varlist(match[1])
        within = self.varlist(match[2]) if match[2] else []
        if not cols:
            raise StataError("Specify grouping variables")
        sortcols = cols + [c for c in within if c not in cols]
        first = ALIASES.get(command.split()[0], command.split()[0])
        if first not in (
            "summarize",
            "count",
            "tabulate",
            "correlate",
            "generate",
            "replace",
            "egen",
            "tabstat",
            "recode",
            "xtile",
            "clonevar",
            "ipolate",
        ):
            raise StataError(
                "by is supported for summarize/count/tabulate/correlate/generate/replace/egen"
            )
        original = self.df
        if kind == "bysort":
            original = original.sort_values(sortcols, kind="stable").reset_index(
                drop=True
            )
        elif not original[sortcols].equals(
            original.sort_values(sortcols, kind="stable")[sortcols]
        ):
            raise StataError("not sorted; use bysort", 5)
        pieces = []
        try:
            for key, group in original.groupby(cols, sort=False, dropna=False):
                self.df = group.copy().reset_index(drop=True)
                self.out(f"-> {keys} = {key}")
                self.dispatch(command)
                pieces.append(self.df)
            self.df = pd.concat(pieces, ignore_index=True) if pieces else original
            if first in (
                "generate",
                "replace",
                "egen",
                "recode",
                "xtile",
                "clonevar",
                "ipolate",
            ):
                self.changed()
        except Exception:
            self.df = original
            raise

    def cmd_version(self, args, opt):
        if opt or not re.fullmatch(r"\d+(?:\.\d+)?", args):
            raise StataError("Syntax: version number")
        self.notice(
            "VERSION",
            f"Stata version {args} requested. StatBridge cannot emulate historical Stata version semantics; current Python backends remain in use.",
        )

    def cmd_help(self, args, opt):
        if opt:
            raise StataError("help does not accept options")
        key = ALIASES.get(args, args)
        if not key:
            self.out("\n".join(f"{k:14} {v[0]}" for k, v in COMMANDS.items()))
        elif key in COMMANDS:
            syntax, backend, detail = COMMANDS[key]
            self.out(f"{syntax}\nBackend: {backend}\n{detail}")
        else:
            raise StataError(f"No implemented command {key}")

    def cmd_about(self, args, opt):
        if args or opt:
            raise StataError("Syntax: about")
        from . import __version__
        from .legal import NOTICE

        self.out(
            f"StatBridge Qt {__version__} (public beta)\n{NOTICE}\nApplication folder: {Path(__file__).resolve().parent.parent}\nIndependent software, not affiliated with StataCorp.\nDocumented subset only; see compatibility.\n"
            + json.dumps(self.versions, indent=2)
        )

    def cmd_license(self, args, opt):
        if args or opt:
            raise StataError("Syntax: license")
        from .legal import license_text
        self.out(license_text())

    def cmd_compatibility(self, args, opt):
        if opt:
            raise StataError("No compatibility options")
        if args.startswith("export "):
            path = self.path(args[7:])
            self.write_guard(path, False)
            path.write_text(
                json.dumps(
                    {
                        "versions": self.versions,
                        "notices": self.notices,
                        "commands": self.ledger,
                    },
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
            self.out(f"Saved {path}")
        elif not args:
            self.out(
                "Results are Python-backend results, not certified Stata equivalents.\nUnknown commands/options fail. RNG uses PCG64. Numeric storage uses float64.\nExtended missing tags are normalised with a warning on import.\nDates remain Stata numeric values. Arbitrary ado/Mata/Python/shell execution is unavailable.\n"
                + (
                    "\n".join(f"[{n['code']}] {n['message']}" for n in self.notices)
                    or "No command-specific notices yet."
                )
            )
        else:
            raise StataError('Syntax: compatibility [export "file.json"]')

    def cmd_local(self, args, opt):
        self.macro(args, opt, self.locals)

    def cmd_global(self, args, opt):
        self.macro(args, opt, self.globals)

    def macro(self, args, opt, bank):
        if opt:
            raise StataError("Commas in macro text must be quoted")
        name, _, value = args.partition(" ")
        if not re.fullmatch(r"[A-Za-z_]\w*", name):
            raise StataError("Invalid macro name")
        if value.startswith("="):
            val = self.expr(value[1:])
            if isinstance(val, pd.Series):
                raise StataError("Macro expression must be scalar")
            value = format(val, "g") if isinstance(val, (float, int)) else str(val)
        bank[name] = unquote(value)

    def cmd_scalar(self, args, opt):
        if opt or "=" not in args:
            raise StataError("Syntax: scalar name = expression")
        name, value = map(str.strip, args.split("=", 1))
        if not re.fullmatch(r"[A-Za-z_]\w*", name):
            raise StataError("Invalid scalar name")
        val = self.expr(value)
        if isinstance(val, pd.Series):
            raise StataError("Scalar expression required")
        self.scalars[name] = val

    def cmd_display(self, args, opt):
        if opt:
            raise StataError("Unsupported display option")
        self.out(self.expr(args))

    def cmd_return(self, args, opt):
        if args != "list" or opt:
            raise StataError("Syntax: return list")
        self.out("\n".join(f"r({k}) = {v}" for k, v in self.r.items()))

    def cmd_ereturn(self, args, opt):
        if args != "list" or opt:
            raise StataError("Syntax: ereturn list")
        self.out("\n".join(f"e({k}) = {v}" for k, v in self.e.items()))

    def cmd_do(self, args, opt):
        self.do_file(args, opt, True)

    def cmd_run(self, args, opt):
        self.do_file(args, opt, False)

    def do_file(self, args, opt, echo):
        if opt:
            raise StataError("No do-file options")
        p = self.path(args, ".do")
        if not p.is_file():
            raise self.missing_file(p)
        old = self.locals
        self.locals = {}
        try:
            if not self.run(p.read_text(encoding="utf-8-sig"), echo):
                raise StataError(f"Do-file stopped: {p.name}")
        finally:
            self.locals = old

    def cmd_log(self, args, opt):
        from .syntax import options

        o = options(opt, ("replace", "append", "text"))
        if args == "close":
            if self.logfile:
                self.logfile.close()
                self.logfile = None
            return
        if not args.startswith("using "):
            raise StataError('Syntax: log using "file.log", text [replace|append]')
        if self.logfile:
            raise StataError("A log is already open")
        if "replace" in o and "append" in o:
            raise StataError("Choose replace or append")
        p = self.path(args[6:])
        self.write_guard(p, "replace" in o or "append" in o)
        self.logfile = p.open("a" if "append" in o else "w", encoding="utf-8")
        self.notice("LOG", "Logs are plain UTF-8 text; SMCL is not implemented.")

    def close(self):
        if self.logfile:
            self.logfile.close()
            self.logfile = None
