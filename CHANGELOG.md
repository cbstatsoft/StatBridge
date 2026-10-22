# Unreleased: next statistical roadmap phase

- Phase B (in progress): add `estat influence [, top(#)]` for conventional unweighted OLS, with Cook’s distance, leverage and internally studentised residuals and explicit heuristic cutoffs.
- Add independent mathematical tests for the influence output and refusal of robust or stale-model diagnostics.
- Restore the prior fitted model, results and return objects when an ANOVA command fails after temporarily fitting a model.
- Address Windows CI issues in SQLite atomic export (explicitly close database before rename), Unicode batch output, and locale-safe UTF-8 result assertions; preserve case-insensitive Windows path-completion semantics.
- Update two-way clustered covariance reference tests for the absorbed-model residual degrees-of-freedom correction.

- Replace the application SVG with a scalable, font-independent Σ logo, used for Linux shortcuts and the Qt window.
- Extend `anova` from one-way to bounded two-factor classical fixed-effects ANOVA, with optional interactions and explicitly identified partial or sequential SS.
- Extend `oneway` with Bonferroni, Šidák and Scheffé pooled-variance pairwise contrasts, adjusted p-values and simultaneous intervals.
- Add `pwmean` with unequal-size Tukey-Kramer, Bonferroni, Šidák and Scheffé adjustments.
- Add command documentation and synthetic regression tests. Tests for this unreleased phase have not yet been executed in the validated build environment.
- Remaining work includes Stata partial-SS numerical validation, repeated-measures/factorial extensions, and advanced survey, mixed-model, multiple-imputation and staggered-DiD inference.

# 0.7.1 - Public beta preparation (14 October 2026)

- Identify Connor Baird as author/copyright holder and retain GNU GPL version 3 or later.
- Add packaged offline licence/third-party notices, Help-menu access, terminal notices and a license command.
- Clarify independent Stata compatibility branding, provenance and redistribution policy.
- Add local-only --doctor/--json diagnostics and a copyable Help dialog.
- Harden Python-version selection, installation failures and Windows launcher exit codes.
- Handle invalid batch directories, missing do-files, audit-write errors and input/audit collisions.
- Package full source, wheel and sdist with licence metadata, verified versions and file hashes.
- Add build/verification tools, contributor/security guidance, bug template and updated roadmap.
- Keep existing statistical features, optional Learn, history/current-folder persistence and both themes.

# 0.7.0

- Added 26 command families and a workflow coverage report.
- Descriptive estimation/CI, tests, panel preparation, categorical models, Newey-West, one-stage survey and right-censored survival.
- Seven new analysis forms, variable-aware completion and four optional Learn exercises (30 total).
- Fixed numeric 0/1 arithmetic for logical expressions.
- Independent covariance, probability, cutpoint, risk-set and likelihood checks.
- Explicit supported subsets and gaps in docs/EVERYDAY_COVERAGE.md.

# 0.6.0 - 13 October 2026

- Shared format detection, workspace import, asynchronous preview, atomic export, variable selection and compression controls.
- Matching SPSS/R/Parquet imports and wider formats; detailed compatibility matrix in docs/FILE_FORMATS.md.
- Metadata-preserving StatBridge Arrow/Feather/Parquet round trips and explicit dates, missing-value and precision notices.
- Contextual file/format/variable/option completion and a format-fidelity Learn exercise.
- R I/O installed by default; existing launchers identify the bundled 0.6.0 release.

# Changes

## 0.5.0

- Integrated updated dtabnk panel conversion and multi-file merging from upstream commit a1af2b0: four layouts, CSV/XLSX/XLS, outer/inner/left joins, key validation and collision-safe column names.
- Added an asynchronous import-preview dialog, column/merge/memory controls, command completion and shared do-file/terminal support.
- Added atomic DTA, SAV, Parquet and optional RData output. RData uses pyreadr; no runtime dependency installation.
- Duplicate observations require explicit averaging. Missing IDs and invalid annual years fail; numeric coercions are counted. Indicator labels follow renamed merge columns.
- Added a synthetic test pack and the 25th Learn exercise.
- 313 tests passed on Linux, with one Windows-only test skipped. Native Windows/macOS validation remains outstanding.
- Checked launchers now identify the bundled release as 0.5.0.

## 0.4.0

- 281 tests passed on Linux; one Windows-only test skipped.

- Implemented bounded workflows across all eight roadmap areas: factor-aware margins and marginsplot, structured tables/exports, balanced CRE/Mundlak, IV diagnostics, Excel/date support, diagnostic/layered graphics, absorbed effects with two-way clustering, and conventional two-period DiD.
- Added Excel import controls and Results copy/export actions, command/option/path completion and six more Learn exercises.
- Numeric binary predictors in margins now use derivatives; factor notation requests discrete changes. This replaces the earlier numeric-binary shortcut.
- Explicitly documented remaining unsupported designs and backend covariance differences. Absorbed-model intercepts are not reported; invalid covariance is refused.
- Learn now has 24 exercises and 13 interpretation guides. Catalog contains 125 bounded entries and 23 aliases.
- Preserved checked launchers; release identifiers updated to 0.4.0.

## 0.3.2

- 251 tests passed on Linux; one Windows-only test skipped.

- Expanded optional Learn from 8 to 18 executable exercises, with topic/search filters, reflection questions and answer notes.
- Added nine offline interpretation guides for Hausman, Wald/contrasts, t-tests, heteroskedasticity, RESET, VIF, ADF, ANOVA and IV assumptions.
- Added result-aware p-value explanations and explicit invalid-test handling, without rerunning models or changing data. Generic Hausman comparisons are distinguished from FE/RE comparisons.
- Corrected teaching descriptions of OLS prediction scope and nonzero linear restrictions.
- Added a sourced, prioritised functionality roadmap. Proposed commands are not represented as implemented.
- Retained checked launchers and bumped all release identifiers to 0.3.2.

## 0.3.1

- 223 tests passed on Linux; one Windows-only test skipped.

- All archive launchers explicitly run the bundled application through a checked bootstrap. Missing files or a version mismatch fail visibly instead of falling back to a different installation.
- Added --version and retained the version in the window title after dataset refresh. The about command now shows the application folder.
- Added regression checks using a deliberately older package on PYTHONPATH with safe-path mode, plus an incomplete-extraction check.

## 0.3.0

- Added a curses terminal workspace (`--terminal` / `--tui`) using the same engine, with history, contextual Tab completion, inline suggestions, scrollback, table panning, do-files, DTA I/O, cooperative stop and optional audit export. Added separate persistent terminal history/folder preferences and Windows curses extra/launcher.
- Replaced incomplete Statistics command prefills with real analysis dialogs for five common workflows. Dialogs provide numeric variable selectors, validation, syntax previews, execution and do-file insertion.
- Added themed toolbar icons, grouped actions, clear button states, shared editor/menu actions, accessible names, F6 pane navigation and correct Stop availability. Included a sourced UI design review.

- Added 20 commands: clonevar, recode, tostring, split, mvdecode, mvencode, misstable, ds, levelsof, xtile, pctile, _pctile, expand, contract, tabstat, oneway, anova, areg, testparm and spearman. The catalog contains 114 entries with explicitly bounded syntax.
- Added ten egen functions, group missing handling, parenthesised within-group sorting, duplicates tag and textual returned-result macro expansion.
- Added merge keep/assert/keepusing and custom indicators. Failed assertions do not modify the current dataset.
- Extended test to linear equalities and lincom to constants, coefficient expressions and eform. Added conventional OLS Ramsey RESET.
- Added eligible out-of-sample unweighted OLS predictions, prediction standard errors and selected conventional-OLS influence diagnostics. Retained factor bases and rejected unknown levels.
- Extended context completion and help for these workflows. Added a synthetic runnable do-file and a task-oriented guide with backend and compatibility limits.
- Retained theme/history/folder preferences, optional teaching and existing Polars acceleration.
- 221 automated tests passed on Linux; one Windows-only test skipped. No certified Stata parity or measured 95% usage-coverage claim.

## 0.2.5

- Added Clear history and Remember history controls in the Review pane, its context menu and Window > Command history. Clearing also resets command recall and history suggestions. Disabling persistence immediately removes saved history while retaining current-session recall.
- Added File > Remember working folder between sessions. Disabling it removes the saved folder and starts future sessions at the home folder, without changing the current session's folder.
- Replaced the text theme toolbar button with a compact sun/moon icon showing the target theme, with a tooltip and accessible label. The Window menu keeps its text action.
- 186 tests passed on Linux; one Windows-only test skipped. Restart behaviour and icon activation are covered.

## 0.2.4

- 183 tests passed on Linux; one Windows-only test skipped. Separately installed wheel completed the full test pack; both result themes visually checked.

- Regression output uses native Qt rich tables with aligned numbers, shaded rows, grouped confidence limits and readable small p-values. Logs, batch output and Save results retain aligned plain text. Full-precision model values are unchanged.
- xtreg reports FE/RE titles, panel groups, observations per group and within/between/overall R-squared from the fitted model, including restored estimates.
- Added Material-inspired dark mode in the toolbar and Window menu. The choice persists between sessions and updates existing results, syntax highlighting, completion popups, data views and optional lessons.

## 0.2.3

- 177 tests passed on Linux; one Windows-only test skipped. The nested test-pack scenario was reproduced and the full analysis completed.

- Added ls/dir with directory/file patterns, sizes, dates and dotfile visibility; cd/chdir supports parent, home and previous directories. Added mkdir and bounded recursive findfile.
- Added local file/folder Tab completion, including quoted paths and context-specific extensions.
- Added Choose working folder, Use do-file folder and List working folder actions.
- Missing do-files and DTA inputs return r(601) with the current directory and navigation hints.

## 0.2.2

- Context-aware command completion uses live variable types, coefficients, stored estimates, macros and returned results.
- Recognises argument positions, aliases/prefixes, factors/lags, expressions, weight clauses and command-specific option arguments. Avoids variable suggestions in new-name, filename and free-text positions.
- Enter accepts an open suggestion without executing it; Enter with the popup closed runs the command.
- Tab supports editing inside a token and preserves the remaining command and cursor position. Stale suggestion popups close when input changes.
- 158 tests, including command-context and full-window live-dataset checks.

## 0.2.1

- Polars data-processing backend for sort/gsort, duplicates, numeric collapse and grouped numeric egen. Auto mode selects by input size and dtype; explicit pandas and Polars modes are available.
- Column projection before conversion and row-position selection preserve untouched payload dtypes and metadata.
- Backend choices and versions recorded in compatibility audits.
- Fixed Tab completion being intercepted by Qt focus traversal. Tab also extends common prefixes and accepts the selected popup suggestion without executing the command.
- 85 tests, including data-backend parity; conversion-inclusive benchmark script and measured timings.
- Ungrouped collapse first/last now consistently skips missing values.

## 0.2.0

- Optional Learn dock, off by default, with eight guided exercises, hints, solutions, nonmutating result checks and explanations of current commands. All analysis functionality remains available with teaching on or off.
- Analytic, frequency and probability weights for linear regression, with explicit sample-size and covariance corrections. Frequency weights also support detailed summaries; analytic weights support basic summaries. Unsupported combinations fail explicitly.
- HC2 and HC3 for unweighted OLS, plus `_b[]`, `_se[]` and `e(sample)` expressions.
- L/F/D/S operators in expressions and model terms, composed operators, panel-aware gaps and declared time delta. Corrected `D2.x` to a second difference; use `S2.x` for the two-period seasonal difference.
- Do-file `if`/`else if`/`else`, semicolon delimiters, quote-aware comments, structural preflight and nested exit handling.
- Completion for factor/time terms, coefficients and selected command-specific options.
- Expanded numerical, scripting and Qt validation to 62 tests.

## 0.1.0

Initial desktop, data editor, do-file engine, compatibility ledger, statistical commands, DTA support, graphs and batch interface.
