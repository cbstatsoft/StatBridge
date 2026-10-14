# Curses terminal workspace

From the installed environment:

```sh
python -m statbridge --terminal
python -m statbridge --terminal --cwd /path/to/project --audit session-audit.json
```

`--tui` is an alias. The terminal interface uses the same statistics engine, DTA I/O, do-file interpreter, command catalog, contextual completion and discrepancy reporting as the Qt application. It does not import Qt or require a graphical display. The normal distribution still installs the desktop dependencies.

On Windows, install the optional curses backend first, from the extracted project directory:

```sh
python -m pip install -e ".[terminal]"
python -m statbridge --terminal
```

Alternatively install `windows-curses` into the same environment. Linux/macOS Python builds usually include curses; some minimal distributions require their curses/terminfo packages. A real interactive terminal is required. For redirected output, use `--batch analysis.do`.

## Workspace and keys

Results retain aligned plain-text tables in a 10,000-line scrollback. The header shows dataset size, unsaved-data state and working folder. Backend messages, warnings and errors stay visible. Terminal colours follow the terminal palette; colour is supplemented by textual warning/error labels.

| Key | Action |
| --- | --- |
| Enter | Execute the current command |
| Tab | Extend common prefix, then accept/cycle contextual completions |
| Right at end | Accept an inline suggestion |
| Up / Down | Recall history, then return to the draft |
| Left / Right, Home / End | Edit within the command |
| Ctrl+U | Clear the command |
| Page Up / Page Down | Scroll results |
| F7 / F8 | Pan wide result tables horizontally |
| F1 | Show terminal help |
| F2 | List variables |
| F3 | Start a quoted `do ""` command |
| Ctrl+C | Request stop while running; clear the command while idle |
| F10, Ctrl+Q or `:quit` | Close; ask before discarding unsaved data |

When idle, a bare `exit` also closes the terminal. Within a do-file, Stata `exit` retains its existing meaning of ending that do-file. Commands cannot be submitted while another is executing. Stop is cooperative and takes effect between commands or supported resampling iterations, not inside a running backend call.

At least 45 columns by 10 rows are needed; around 100 by 28 is more comfortable. The workspace responds to terminal resizing. Very narrow terminals may require horizontal panning. Unicode width is estimated from combining and East Asian character properties; complex emoji/grapheme shaping can differ across terminals. Multi-line scripts should be run with `do`, rather than pasted directly into the single-line command field.

## Files, graphs and reproducibility

```stata
pwd
ls
cd "project"
use "student_panel.dta", clear
do "test_analysis.do"
log using "analysis.log", text
regress wage education experience, robust
histogram wage
graph export "wage.png", replace
save "analysed.dta", replace
log close
```

Graphs use a non-GUI matplotlib backend and can be exported as PNG/PDF/SVG. They are not rendered as terminal graphics. The Qt data editor and interactive teaching panels remain desktop features. All supported statistical commands remain available. Use `help command` and compatibility messages for guidance. `--audit` writes the session audit on exit; ordinary logs retain output beyond scrollback.

## Remembered state

Terminal history and working-folder preferences are separate from Qt preferences. Up to 1,000 submitted commands and the last working folder are remembered by default. The dataset itself is never persisted automatically.

- `:history off` removes saved history, keeping current-session recall.
- `:history on` enables saving again.
- `:history clear` clears current recall, suggestions and saved history.
- `:cwd off` removes the saved folder. The next terminal session starts in the launching shell's directory.
- `:cwd on` remembers the current folder on completion/exit.
- `:clear` clears visible output; it does not clear the dataset or audit.

You can also start with `--no-history` and/or `--no-remember-cwd`. These update the persisted preference. An explicit `--cwd` overrides a remembered folder.

Settings use an atomic JSON replacement under `%LOCALAPPDATA%/StatBridge/terminal.json` on Windows, `~/Library/Application Support/StatBridge/terminal.json` on macOS, and `$XDG_CONFIG_HOME/StatBridge/terminal.json` (default `~/.config`) on Linux. A failed settings write produces a visible warning. Corrupt settings are ignored.

## Validation and sources

The terminal was exercised in a real Linux pseudo-terminal, including do-file execution, variable-aware Tab completion, resizing, paging, DTA save, clean exit and audit export. Automated tests cover engine execution, failed-command recovery, history preferences, completion within a command and control-character sanitisation. Windows/macOS terminal operation has not been executed here.

Implementation references, accessed 2 October 2026: [Python curses HOWTO](https://docs.python.org/3.12/howto/curses.html), [Python curses reference](https://docs.python.org/3.12/library/curses.html), and [windows-curses](https://pypi.org/project/windows-curses/).
