# 0.7.1 public beta validation

**415 tests passed, 1 native-Windows test skipped, 24 upstream Qt/matplotlib deprecation warnings.** Installed-wheel checks passed for all 30 Learn lessons and three example do-files (demo, everyday coverage, and file formats). The wheel was loaded from outside the source tree. Dependency consistency, offline licence display and installation diagnostics passed. The installed GUI licence viewer was rendered and inspected using Qt offscreen. Both the ZIP and source-distribution file manifests verified.

The definitive automated test summary is in docs/test-results.txt and RELEASE.json in the built archive. Python 3.12 on Linux is the locally validated environment. GUI tests run with Qt offscreen, which does not validate a native window manager, high DPI, packaging on Windows/macOS or platform-specific installers.

New checks cover licence availability, author/version consistency, diagnostic privacy and missing-dependency handling, batch path/error behaviour, installer refusal for unsupported Python, and detection of altered release files. The release build validates wheel metadata and compares every packaged Python source file against the source tree.

No licensed Stata application was used for parity testing. Numerical tests establish specified Python calculations and documented conventions, not complete Stata equivalence. A CI matrix is supplied for Windows/macOS/Linux and Python 3.11 to 3.13, but those remote jobs have not been executed as part of this delivery. No public repository release or PyPI upload has been performed.

## Earlier validation records

# Release 0.7.0 validation

14 October 2026. Linux, Python 3.12.14.

- **403 passed, 1 Windows-only skipped** in the combined suite. Existing I/O, scripting, statistics, Qt and terminal tests retained.
- Independent references for descriptive covariance and exact binomial limits; explicit Bartlett HAC sandwich; stratified PSU survey variance and subpopulation scores; weighted linear sandwich; ordered cutpoint numerical Jacobian; multinomial probabilities; known Kaplan-Meier risk sets and Greenwood SEs; direct Cox risk-set score and observed information.
- Unsupported options, survey singleton strata, irregular HAC samples, declaration resets, preserve/restore, sample-only predictions, grouped interpolation and logical 0/1 arithmetic tested.
- All 30 Learn setups/solutions and non-mutating checks validated. Unattempted exercises fail checks.
- Seven new Qt analysis forms generate executable syntax. Dark survey and light Cox forms visually inspected offscreen. Context completion covers survey prefixes, variables, options and fitted outcome categories.
- Self-contained everyday_coverage.do completed through the batch CLI with a compatibility audit.
- Version launch checks rerun after the version bump. Wheel installed in a separate target outside the source tree; all 30 lessons, the new workflow and a Parquet round trip validated there.
- Windows/macOS were not executed. No licensed Stata comparison was performed. These checks validate the specified Python calculations and workflows, not full Stata parity or a measured percentage of users covered.

Earlier release records follow and describe those releases only.

# Release 0.6.0 validation

- Linux / Python 3.12: **358 passed, 1 Windows-only skipped**. Qt controls tested offscreen; dark/light import and export previews inspected.
- New format tests cover SPSS SAV/ZSAV/POR, Stata, XPORT, RData/RDS, Parquet, Feather, Arrow, CSV/TSV, JSON/JSONL, SQLite, ODS and numeric MAT/HDF5 round trips.
- Native upstream SAS fixture verifies strings, dates including year 1583, times and missing values; an XPORT round trip checks date conversion.
- Additional checks: metadata, nullable integers beyond 2^53, missing-value conversion, rejected nested data, ambiguous R/SQLite sources, duplicate names, atomic writer failure, import/preview state preservation, compression, variable subsets, completion and GUI preview.
- Built wheel installed into a separate target and imported outside the source directory; version, Parquet round trip and all 26 bundled lessons verified.
- `examples/file_formats.do` completed in a separate working directory and produced all 15 example exports.
- Legacy Minitab numeric portable import tested with a descriptor fixture. Excel XLS/XLSX/ODS tested; XLSB/XLSM dispatch uses Calamine but was not validated against independent native fixtures in this environment.
- Windows/macOS launchers are included but were not executed on those operating systems. No live proprietary Stata/SPSS/SAS/R application comparison was performed. Round-trip tests use Python backends and the independent native SAS input fixture.

The historical validation notes below describe earlier releases; their older totals do not replace the 0.6.0 results above.

# Validation record

Date: 13 October 2026. Performance timings were collected on 30 September 2026.

Environment: Linux, Python 3.12.14. GUI tests used Qt’s offscreen platform.

| Dependency | Tested version |
| --- | --- |
| numpy | 2.5.4 |
| pandas | 2.3.3 |
| polars | 1.44.2 |
| pyarrow | 25.0.1 |
| scipy | 1.18.1 |
| statsmodels | 0.15.0 |
| linearmodels | 7.0 |
| pyreadstat | 1.3.6 |
| PySide6 | 6.12.0 |
| matplotlib | 3.11.2 |
| openpyxl | 3.1.5 |
| jinja2 | 3.1.6 |
| pytest | 9.1.1 |

| psutil | 7.2.2 |
| xlrd | 2.0.2 |
| pyreadr (optional) | 0.5.7 |

## Checks

- The 0.5.0 wheel was installed into a separate target outside the source tree. Its packaged dtabnk lesson and outcome check passed from an unrelated working directory, and SAV/Parquet/RData exports succeeded. Both import-dialog themes were rendered and inspected.

- Version 0.5.0: 30 dtabnk integration tests, including four source layouts, XLS/XLSX, sparse outer/inner/left merges, duplicate and missing key refusals, raw/sanitised column collisions, leading-zero IDs, non-destructive previews, failed-import state preservation, memory refusals, atomic output and DTA/SAV/Parquet/RData round trips. The 25th Learn exercise passes setup/solution and pre-attempt checks. GUI previews run asynchronously. Source baseline is updated dtabnk commit `a1af2b0`.

- Version 0.4.0 wheel installed into an isolated target outside the source tree: all six new lesson workflows and `examples/roadmap_workflows.do` executed successfully. Light/dark workspace screenshots were regenerated and visually checked.

- Version 0.4.0: 24 lesson setups/solutions, 13 interpretation guides, independent margins/FE/HDFE/DiD and two-way cluster covariance checks, Excel/date round trips and literal-string exports, actual GUI import/clipboard controls, and new command/path completion. The full synthetic roadmap do-file executes successfully.

- Version 0.3.2: all 18 lesson setups/solutions execute; the ten new lessons do not pass before attempting the task. Read-only checks preserve data, revision, random state and ledger. Hausman explanations cover rejection, non-rejection, invalid results and generic comparisons. Search/topic filters and empty/busy UI states are checked.

- Wheel built, installed into a separate target directory and smoke-tested with a weighted regression, lesson result check, explicit Polars sort and full-window Tab completion. The 0.2.2 installed wheel also passed live-variable type filtering and completion inside an existing command.
- 313 automated tests passed; one native-Windows path test skipped on Linux. Raw output: `test-results.txt`.
- OLS coefficients and classical/HC1 covariance compared with independent matrix calculations.
- One-way cluster covariance compared with manually accumulated cluster scores and finite-sample correction.
- Fixed-effects slopes compared with manual within-group demeaning and least squares.
- Stata-style ordinary missing ordering, expression safety, percentiles, factor missingness, and exposure-adjusted predictions.
- Logit, logistic, probit, Poisson, NB2, GLM, quantile, IV, ADF and ARIMA backend execution.
- Classical Hausman matrix calculation plus robust-covariance rejection.
- DTA variable/value labels, Unicode text, numeric dates and extended-missing warning/normalisation.
- Merge, reshape, append, encode/decode, collapse, preserve/restore and log workflows.
- Macro expansion, loops, nested do-file local scope, capture and uncaptured-error stops.
- Deterministic PCG64 sampling/bootstrap, graph export and compatibility JSON.
- Qt window construction, worker execution, data edits, graph canvas, completion and history keys.
- Visual inspection of the populated Results, Graphs and optional Learn workspace screenshots.
- The three original example do-files and the new weighted/time example run through the batch entry point. All twenty-five lesson setups and suggested solutions execute in automated tests.
- Frequency-weighted classical/HC1/cluster covariance checked against explicit row replication; analytic-weight covariance and rescaling against independent formulas.
- First/second/seasonal differences, composed time operators, panel gaps and declared delta.
- Quote-aware comment parsing, semicolon delimiters, nested conditional blocks, preflight structural errors and nested exit.
- All twenty-five optional lesson outcomes checked without modifying data, random state, revision or audit. Opening a lesson and toggling Learn tested in Qt.

- Polars/pandas parity checks for sorting, duplicate detection/removal, grouped and ungrouped summaries, grouped egen, missing keys/values, empty inputs, qualifiers, metadata preservation and unsupported-type handling.
- Conversion-inclusive timing of one-million-row synthetic workloads; see PERFORMANCE.md.

- Tab completion exercised in the full Qt window, including focus retention, common-prefix extension, popup acceptance and unmatched input.

- Context completion checked across typed variable lists, options, expressions with commas, prefixes, factors/lags, weights, macros, model coefficients and stored estimates. Tests cover names removed or changed in the live dataset, new-name/literal positions, and preserving command text and cursor location during mid-line completion.

- Navigation tests cover ls/dir, glob patterns, quoted folders, cd history, mkdir, bounded findfile, symlink recursion avoidance, path completion and the Qt folder actions.
- Reproduced the nested ZIP test-pack layout: the initial relative do-file fails with r(601), then ls/findfile/cd locate the inner folder and the entire supplied test analysis succeeds with 960 rows and final regression N=920.

- Installed 0.2.3 wheel smoke-tested separately for ls, findfile with depth, cd, glob listing and directory completion.

- Release 0.2.4 adds checks for fitted-sample FE/RE summaries, HTML escaping, tiny-number/p-value formatting, quiet output, aligned logs, Qt table cells, theme persistence, recolouring existing results and unchanged numeric model state.
- The separately installed 0.2.4 wheel completed the full supplied test_analysis.do with 960 rows and final regression N=920. Its light/dark xtreg screenshots were visually inspected at a 1400 by 950 window size with no horizontal scrolling in the results pane.

- Release 0.2.5 tests clearing history without old commands reappearing, enabled/disabled history persistence across new windows, working-folder opt-out and restoration, and the icon-only theme control's activation and accessible target labels.

- Separately installed 0.2.5 wheel opened and rendered the panel-regression workspace with the new Review controls and theme icon; the dark view was visually inspected.

## Release 0.3.0 checks

- Twenty added command entries; final catalog count 114, plus 23 explicit aliases. Function/option additions are documented separately and are not counted as complete Stata commands.
- Recode first-match rules, invalid-rule atomicity, labels and qualifiers; cloning metadata; ordinary missing-code round trips; string conversion; splitting; variable-list and level macros; quantile definitions and tied bins; observation expansion and contraction; grouped helpers and tabstat.
- Merge keep/assert/keepusing, cardinality and unchanged data on assertion failure; secondary group sorting and duplicate tags.
- One-factor ANOVA compared with SciPy. Absorbed OLS slopes compared with within demeaning; coefficients and transformed covariance compared with explicit indicator OLS for conventional, robust and clustered cases.
- Linear equalities and combinations compared with independent covariance calculations. OLS out-of-sample predictions/standard errors checked with matrix formulas; retained factor bases, unknown-level rejection and stale-model guards exercised. Influence values checked with the hat matrix and RESET against an independent augmented fit.
- All five analysis dialogs execute through the real engine. Invalid selections, condition validation, cancellation without data/random-state changes, busy toolbar state and pane-focus shortcuts tested.
- Terminal execution, error recovery, DTA save, do-files, mid-line variable completion, history persistence/opt-out, audit export, Unicode cell slicing and control-character handling tested. A subprocess verifies terminal startup without importing Qt.
- Real Linux pseudo-terminal smoke: startup, do-file, contextual Tab completion, paging, resize, DTA save, exit and audit export.
- The synthetic examples/core_workflows.do completes, as does the original 960-observation test pack with final regression N=920. The separately installed 0.3.0 wheel is used for the final batch and interface smoke checks.
- Updated dark/light workspace and analysis-dialog screenshots inspected; absorbed-effect regression table has no horizontal scrollbar at 1400 by 950.

## Release 0.3.1 launch verification

- Retrieved the saved 0.3.0 archive and verified it matched the locally delivered ZIP byte-for-byte. Both its source and bundled wheel identify as 0.3.0 and contain dark-mode code. The user's screenshot showed 0.2.0; the cause of that mismatch could not be established from the screenshot alone.
- The new checked launcher was tested with a deliberately older 0.2.0 package on PYTHONPATH, safe-path mode enabled and a different working directory. It loaded the bundled 0.3.1. Incomplete extraction fails explicitly.
- All archive launchers now invoke launch.py. The command-line --version path requires no GUI or statistical backend import. The window title retains its version after refresh; about reports the application folder.
- 223 tests passed; one Windows-only test skipped. A fresh wheel installation verified version 0.3.1, the persistent version title, the dark-mode icon/toggle and application-path output.

## Boundaries

No Stata executable was available. These checks do not establish complete parity with Stata, especially estimator-specific degrees of freedom, complex survey analyses, weighted estimator edge cases, factor-cell conventions and optimisation edge cases. Windows/macOS were not executed here. The CI matrix is supplied for follow-up validation on those systems.

The archive includes Python source, tests, a platform-independent wheel and installation scripts. It does not include prebuilt standalone operating-system executables.
