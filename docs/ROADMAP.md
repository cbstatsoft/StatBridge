# Roadmap implementation status: 0.4.0

6 October 2026. This release implements bounded workflows in each of the eight priority areas from the [research roadmap](ROADMAP_RESEARCH.md). It does not reproduce every Stata option. New command names are documented subsets, not complete Stata implementations.

| Area | Implemented | Remaining limits |
| --- | --- | --- |
| Margins | OLS/logit/logistic/probit predictions, factors/interactions, discrete factor changes, continuous derivatives, numeric `at()` grids, `over()`, fitted-covariance delta intervals, `marginsplot` | Unweighted estimation sample only; no unconditional VCE, post, time terms, general contrast syntax or all Stata prediction types |
| Tables | `etable`, bounded `esttab`, numeric `dtable`; shared structured results; CSV/HTML/LaTeX exports and GUI clipboard/export | No complete collect/estout system, Word export, categorical dtable frequencies or survey-weighted tables |
| Panel specification | `xtreg, cre` with identified means of time-varying expanded regressors; `estat mundlak` after FE/RE/CRE with selected covariance | Balanced complete-case panels on a common time grid only; no unbalanced-panel selection correction or classical Hausman sigmamore/sigmaless |
| IV diagnostics | First-stage diagnostics with correct distribution labels, conventional Wu-Hausman or robust/clustered Wooldridge regression exogeneity, Sargan or heteroskedasticity-robust Wooldridge score overidentification | Clustered overidentification refused; no weak-IV-robust intervals or Stock-Yogo tables; exactly identified models have no overidentification test |
| Excel and dates | `.xlsx` sheet/range import, explicit header and all-string options, workbook export, 18 date functions, numeric date preservation, standard `%td/%tm/%tq/%tc` display | No `.xls`, formula evaluation, sheet append/modify, locale inference, custom date pictures or leap-second clocks |
| Graphics | Layered scatter/line/lfit, residual-versus-fitted and normal Q-Q plots, existing PNG/PDF/SVG exports | Bounded graph grammar; no full Stata styling language; SciPy Q-Q positions differ |
| Absorbed effects | Categorical multi-effect absorption, iterative singleton removal, one/two-way clustering | No weights or heterogeneous slopes; backend df/finite-sample correction differs from reghdfe; normalisation-dependent constant not reported; invalid covariance refused |
| DiD | Complete two-period repeated-cross-section or balanced-panel additive DiD, group clustering, treatment/design checks | No staggered adoption, heterogeneous cohort/time effects, event-study estimator or wild-cluster bootstrap; one pre-period cannot test parallel trends |

The same engine is used in Qt, batch execution and the curses terminal. Learn has 24 runnable exercises and 13 reference guides, including new margins, Mundlak, IV diagnostics, DiD, dates and table workflows.

## Validation boundaries

The new checks compare margins with independent design/covariance calculations, nonlinear derivatives with finite differences, CRE slopes with FE, absorbed fits with explicit dummy-variable OLS, two-way covariance with manually accumulated cluster scores, and DiD with a difference of group means. Excel tests cover a 1904-epoch workbook, range selection, dates, literal formula-like strings and overwrite guards. There is no certified Stata numerical-parity claim and no native Windows/macOS validation from this Linux run.

## Still separate projects

Unbalanced CRE corrections, robust clustered overidentification, weak-IV-robust inference, staggered/heterogeneous DiD, full survey designs, multiple imputation, and native-platform validation remain open. The original roadmap's proposed survey/MI projects were not shallowly approximated with weights or single imputation.

See [the worked guide](ROADMAP_WORKFLOWS.md), [command syntax](COMMANDS.md) and [compatibility notes](COMPATIBILITY.md).
