# StatBridge development roadmap

Updated 14 October 2026. The last validated public-beta release is **0.7.1**. This roadmap separates implemented code from validation still required. StatBridge is **not** a complete or numerically certified Stata replacement.

## Completed and available in the public beta

| Area | Implemented scope | Where to verify limits |
| --- | --- | --- |
| Data preparation | Imports/exports across Stata, SPSS, SAS, R, Excel, Parquet/Arrow, text and selected other tabular formats; cleaning, merging, reshaping, group summaries, dated variables | [File formats](FILE_FORMATS.md) |
| Regression | OLS and selected robust/cluster covariance, binary/count/GLM models, quantile and categorical models, predictions and selected diagnostics | [Commands](COMMANDS.md), [compatibility](COMPATIBILITY.md) |
| Applied econometrics | Fixed/random effects, guarded Hausman, CRE/Mundlak, selected IV diagnostics, absorbed regressions, two-period DiD, Newey-West | [Workflow guide](ROADMAP_WORKFLOWS.md) |
| Descriptives and graphics | Tests, one-way ANOVA, structured tables, scatter/line/diagnostic plots and exports | [Everyday coverage](EVERYDAY_COVERAGE.md) |
| Additional 0.7 workflows | Bounded survey, survival and panel preparation; 30 optional offline learning exercises | [Coverage](EVERYDAY_COVERAGE.md), [Learn](LEARNING.md) |
| User experience | Qt6 desktop, curses terminal, command/path completion, theme switching and Linux XDG desktop launcher | [UI](UI_DESIGN.md), [Linux shortcuts](LINUX_SHORTCUT.md) |

0.7.1 validation established 415 passing tests and one Windows-only skipped test on Linux/Python 3.12, plus wheel smoke checks. Those results **predate** the changes under development below. Native Windows/macOS and licensed Stata comparisons remain incomplete. See [validation](VALIDATION.md).

## Phase A: factorial models and group comparisons (implemented, awaiting validation)

The current unreleased branch contains:

- Two-factor `anova` with a bounded `#`/`##` grammar and explicit partial drop-term or sequential sums of squares.
- One-way Bonferroni, Šidák and Scheffé adjusted comparisons with simultaneous intervals.
- `pwmean` with Tukey-Kramer for unequal group sizes and three additional familywise methods.
- A consolidated [ANOVA guide](ANOVA.md), command help and synthetic tests.
- An outlined **Σ** application icon for the Linux desktop entry and Qt application window.

**Validation gate:** Run the full Linux test suite and the new `tests/test_anova_phase.py`; check wheel/sdist packaging, headless desktop launch and the refreshed launcher icon. Compare factorial SS (including unbalanced, reference-coded interaction models) against independent known-design calculations and state precisely where Stata differs. Do not publish this as a validated release until the gate passes.

## Phase B: estimation diagnostics and model consistency (in progress)

Implemented on the development branch pending CI validation: bounded conventional-OLS `estat influence` reporting, independent projection-matrix/Cook’s distance fixtures, rejection of unsupported/stale covariance conditions, and rollback of fitted model state after a rejected ANOVA. These additions do not establish numerical parity with Stata.

1. Build independent fixtures for new categorical models, inference choices, and regression/prediction interactions.
2. Add robust reference tests for finite-sample covariance, factor contrasts, invalid or nonestimable design restrictions, and stored-model/reporting consistency.
3. Improve model diagnostics and reporting, including adjusted confidence intervals for supported estimators without silently altering covariances.
4. Maintain realistic do-file workflow fixtures and track pass/fail by workflow rather than counting commands.

**Exit gate:** tests for all new families, explicit unsupported-option handling, updated help/completion/Learn, and distributable source/wheel integrity checks.

## Phase C: specialist estimators (partly implemented, specialist gaps remain)

The development branch adds four explicitly bounded workflows: Gaussian grouped mixed models (random intercept or correlated random slope), balanced repeated-measures ANOVA, predictive-mean-matching continuous chained imputation with Rubin-pooled OLS, and gapless VAR with stability/point forecasts. Independent tests and [specialist scope documentation](SPECIALIST_MODELS.md) accompany these additions. This does not finish the full Phase C requirements: complex surveys, generalized multiple imputation, cohort-specific staggered DiD, weak-IV robust inference, and specialist multivariate/SEM/time-series remain open. Do not treat the commands as release-validated until CI passes.


| Priority | Candidate | Correctness risk |
| --- | --- | --- |
| High | Factorial and repeated-measures ANOVA with correct error strata, postestimation contrasts, and marginal means | Independence/sphericity, contrasts, missing cells, SS conventions |
| High | Mixed/multilevel models | Random-effects design, optimiser convergence, covariance and df |
| High | Multiple imputation and pooled inference | Reproducible imputation, Rubin combination, missing-data assumptions |
| Medium | More complex survey designs | Multistage PSUs, FPCs, replicate weights, variance and subpopulation conventions |
| Medium | Staggered-adoption heterogeneous DiD and event studies | Cohort/time estimands, negative weighting, overlap and anticipation |
| Medium | Expanded IV identification and robust weak-instrument procedures | Identification, correct reference distributions and confidence sets |
| Lower | More time-series and multivariate specialist methods | Unit roots, lag selection, stability, diagnostics and conventions |

None of these are claimed implemented solely because a similar general command exists.

## Delivery and maintenance principles

- Extend the shared engine so batch, do-files, desktop and terminal inherit the same statistical behaviour.
- Keep syntax descriptions, completion, command help, result objects, Learn examples and export tables in sync.
- Make untested methods fail clearly. Avoid automatic substitution of ordinary OLS/weights for complex-design or missing-data inference.
- Distinguish compatibility with supported syntax from agreement with Stata-specific numerical/finite-sample conventions.
- Run native-platform checks before promising the associated packaging/GUI behaviour.
- Preserve the independent-software trademark and GNU GPL provenance requirements. Review third-party source/assets before redistributing.

Historical priorities and research sources remain in [ROADMAP_RESEARCH.md](ROADMAP_RESEARCH.md). Earlier 0.4 workflow additions are documented in [ROADMAP_WORKFLOWS.md](ROADMAP_WORKFLOWS.md) and [CHANGELOG.md](../CHANGELOG.md).
