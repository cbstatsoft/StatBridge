# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="StatBridge Qt: Stata syntax on Python statistical backends"
    )
    from . import __version__

    parser.add_argument(
        "--version", action="version", version=f"StatBridge Qt {__version__}"
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--doctor",
        action="store_true",
        help="Check installation metadata without loading Qt",
    )
    modes.add_argument(
        "--license",
        action="store_true",
        help="Show offline licence and attribution notices",
    )
    parser.add_argument(
        "--json", action="store_true", help="Machine-readable --doctor output"
    )
    modes.add_argument(
        "--terminal",
        "--tui",
        action="store_true",
        help="Open the curses terminal workspace",
    )
    modes.add_argument(
        "--batch", metavar="FILE.do", help="Run a do-file without the GUI"
    )
    parser.add_argument(
        "--audit",
        metavar="FILE.json",
        help="Write a compatibility/backend report in batch mode",
    )
    parser.add_argument(
        "--cwd", metavar="DIRECTORY", help="Initial session working directory"
    )
    parser.add_argument(
        "--syntax", choices=("stata", "logos"), default=None,
        help="Initial command language for batch, terminal or desktop session"
    )
    parser.add_argument(
        "--no-history", action="store_true", help="Disable saved terminal history"
    )
    parser.add_argument(
        "--no-remember-cwd",
        action="store_true",
        help="Disable saved terminal working folder",
    )
    args = parser.parse_args()
    if sys.platform == "win32":
        # Avoid legacy-code-page failures on Unicode command output.
        # Batch reports are UTF-8 whether redirected or shown in a terminal.
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
    if args.json and not args.doctor:
        parser.error("--json requires --doctor")
    if args.doctor or args.license:
        if args.cwd or args.audit or args.no_history or args.no_remember_cwd or args.syntax:
            parser.error(
                "Session options cannot be combined with --doctor or --license"
            )
        if args.license:
            from .legal import license_text

            print(license_text())
            return 0
        from .diagnostics import report, format_report

        data = report()
        print(json.dumps(data, indent=2) if args.json else format_report(data))
        return 0 if data["ok"] else 1
    if args.cwd and not Path(args.cwd).expanduser().is_dir():
        parser.error("--cwd must name an existing directory")
    if args.cwd:
        args.cwd = str(Path(args.cwd).expanduser().resolve())
    if (args.no_history or args.no_remember_cwd) and not args.terminal:
        parser.error("--no-history and --no-remember-cwd require --terminal")
    if args.terminal:
        from .terminal import main as terminal

        return terminal(
            cwd=args.cwd,
            audit=args.audit,
            no_history=args.no_history,
            no_cwd=args.no_remember_cwd,
            syntax=args.syntax or "stata",
        )
    if args.batch:
        # CLI paths are relative to invocation directory; --cwd affects commands.
        script = Path(args.batch).expanduser().resolve()
        if args.audit and Path(args.audit).expanduser().resolve() == script:
            parser.error("--audit must not overwrite the input do-file")
        try:
            source = script.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            print(f"Cannot read do-file: {exc}", file=sys.stderr)
            return 1
        from .engine import Engine

        def emit(event):
            if event["kind"] in (
                "command",
                "output",
                "warning",
                "error",
                "translation",
            ):
                print(event["text"], flush=True)

        engine = Engine(emit=emit, cwd=args.cwd, syntax_mode=args.syntax or "stata")
        try:
            success = engine.run(source)
        except (OSError, UnicodeError) as e:
            print(str(e), file=sys.stderr)
            success = False
        finally:
            engine.close()
        if args.audit:
            try:
                Path(args.audit).expanduser().write_text(
                    json.dumps(
                        {
                            "versions": engine.versions,
                            "notices": engine.notices,
                            "commands": engine.ledger,
                        },
                        indent=2,
                        default=str,
                    ),
                    encoding="utf-8",
                )
            except OSError as exc:
                print(f"Cannot write audit report: {exc}", file=sys.stderr)
                return 1
        return 0 if success else 1
    if args.audit or args.cwd:
        parser.error("--audit and --cwd require --batch or --terminal")
    from .ui import main as gui

    return gui(syntax=args.syntax)


if __name__ == "__main__":
    raise SystemExit(main())
