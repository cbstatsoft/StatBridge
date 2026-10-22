# Compatibility contract

StatBridge translates commands into Python statistical calls. It is not a Stata interpreter with complete behavioural equivalence. Every output belongs to the named Python backend. The audit records executed commands, their outcome, backend names, runtime package versions and known differences. It does **not** run Stata in parallel or automatically measure numerical differences against it.

The command registry and option validators define the accepted subset. Unsupported commands, options, weight combinations, malformed valued options, and collinear designs fail explicitly. Some commands support only one syntax form. Having a familiar command name does not imply all of Stata's options are implemented.

## Phase B OLS influence diagnostics

`estat influence [, top(#)]` is restricted to **unweighted conventional OLS**. Cook's distance, the hat-matrix diagonal and internally studentised residuals come from statsmodels' OLS influence implementation. The display is sorted by Cook's distance; data indexes are shown rather than assuming uninterrupted Stata observation numbers. The nominal `2k/N` leverage and `4/N` Cook's-distance markers are exploratory screening heuristics, **not tests of significance**. Influence calculations never delete observations or refit the active model.

The command refuses robust/clustered covariance, weighted regression, non-OLS fits, a changed estimation sample and undefined or nonfinite statistics. It does not imply diagnostic parity with Stata or support for complex-design influence functions.

## Numerical and statistical choices

| Area | Implementation | Compatibility implication |
| --- | --- | --- |
| Numeric storage | float64 for generated numeric variables | Stata defaults to float storage in many contexts. Rounding, overflow and memory use differ. Declared integer/float widths are not emulated. |
| Ordinary numeric missing | NaN internally; treated as larger than finite values in comparisons | `x > 5` includes ordinary missing, while `x < .` excludes it. Missing is nonzero in conditions. Extended tagged missing values are not represented. |
| Extended missing | `.a` to `.z` normalised on `.dta` import with a notice | Tag distinctions are lost. Extended-missing literals are rejected in expressions. Keep original source files for archival fidelity. |
| Random numbers | NumPy Generator with PCG64 | Same seed does not yield Stata draws. `sample`, `bsample` and bootstrap select different observations. |
| Sorting | Stable Polars/pandas sorting, depending on the selected data backend | Order within ties can differ. `gsort` always puts missing last, including descending sorts, unlike some Stata orderings. |
| Percentiles | NumPy `averaged_inverted_cdf`, Hyndman-Fan type 2 | Implements the ordinary unweighted Stata percentile rule rather than NumPy's linear default. Frequency-weighted detail uses the corresponding replicated-observation percentiles; analytic-weighted detail is rejected. |
| SD, skewness, kurtosis | Sample SD; population central-moment skewness/kurtosis; kurtosis includes 3 | Ordinary unweighted conventions targeted. Floating-point accumulation can still differ. |
| OLS | statsmodels OLS; intercept unless `noconstant` | Coefficients and ordinary covariance checked independently. Rank-deficient designs are rejected instead of using Stata omission rules. |
| OLS robust | HC1 (robust), HC2 or HC3; t inference with residual df | HC1 checked by independent matrix calculation; HC2/HC3 follow statsmodels. Weighted HC2/HC3 are rejected. |
| Weighted OLS | statsmodels WLS coefficients with explicit AW/FW/PW covariance and N corrections | Frequency weights count replicated observations; analytic and probability weights are normalised to the retained row count. FW classical/HC1/cluster covariance checked against expanded rows. AW covariance checked against independent matrix formulas. PW defaults to robust; conventional PW covariance is rejected. No survey strata/FPC or multiway clusters. |
| Clustered OLS | One-way sandwich with G/(G-1) and (N-1)/(N-K); t(G-1) | Independently checked. This does not imply support for survey estimation, multiway clustering or other model-specific Stata corrections. |
| Likelihood models | statsmodels optimisation; normal inference | Convergence, tolerances, likelihood constants and parameter ordering can differ. Nonconvergence is rejected when the backend exposes the flag. Backend warnings remain visible. |
| Nonlinear robust covariance | HC0 sandwich | Finite-sample corrections may differ from Stata. Clustered nonlinear inference also follows the backend. |
| NB regression | NB2 with directly estimated alpha | Stata often reports `/lnalpha`; ancillary parameters and likelihood reporting differ. `irr` exponentiates regression coefficients and leaves ancillary alpha on its original scale. |
| Quantile regression | Iterative statsmodels QuantReg; robust kernel covariance | Default Epanechnikov kernel and Hall-Sheather bandwidth can yield different SEs from Stata. Iteration warnings are shown. |
| GLM | Selected families/links, backend IRLS and scale | Gaussian/binomial/Poisson/gamma supported, with compatible identity/log/logit/probit/inverse links. No binomial trial-count specification, survey weighting or full Stata family syntax. |
| Panel FE/RE | linearmodels PanelOLS/RandomEffects | R² definitions, absorbed regressors, singletons, variance components and finite-sample df can differ. Panel `robust` clusters on entity, but reported inference follows linearmodels residual df. FE slopes checked against independent within estimation. |
| IV/2SLS | linearmodels IV2SLS, non-debiased covariance, normal inference | First-stage, exogeneity and bounded overidentification diagnostics are available; see ROADMAP_WORKFLOWS.md. Small-sample options are not fully reproduced. |
| Factors/interactions | Treatment coding of `i.var`, `ib#.var`, `c.var`; products for `#`/`##` | Expansion, omitted/base cells and labels can differ, especially `#` without main effects. Factor levels must be nonnegative integers. Grouped factor syntax such as `i.(a b)` is unsupported. |
| Time operators | `L#.x`, `F#.x`, `D#.x`, `S#.x` and compositions in expressions and model terms | Respect panel boundaries, gaps and `delta(number)`. `D2.x` is a second difference; `S2.x` is x minus its two-period lag. Grouped time syntax such as `L(1/3).x` is unsupported. |
| Hausman | Classical difference of common slope estimates/covariances | Refuses weighted models, robust/cluster covariance, unequal samples/data revisions/outcomes and non-positive-definite covariance differences. No `sigmamore`/`sigmaless` or `suest`; balanced-panel robust Mundlak is available separately. |
| Predictions | Unweighted OLS: eligible in- and out-of-sample observations; other estimators and weighted OLS: documented estimation-sample subset | OLS supports xb/residuals/stdp with frozen factor bases; unknown factor levels fail. Conventional OLS also supports stdf and in-sample influence diagnostics. Data mutations invalidate active estimation; restoring an older model does not permit stale predictions. Panel and areg fitted values omit individual effects. No time-series forecasting. |
| Margins | Unweighted OLS/logit/logistic/probit, factor/interactions, at()/over(), delta method | Estimation sample, fixed empirical covariates. Numeric variables give derivatives; factor variables give discrete changes. No weights, unconditional VCE, post or time operators. |
| Rank tests | SciPy two-sided asymptotic tests with stated continuity/tie conventions | Statistics and p-values can differ from Stata's displayed z/rank sums or exact methods. |
| Shapiro-Wilk | SciPy approximation | Reports W and p only, not Stata V/z; large-sample approximations can differ. |
| PCA | NumPy SVD on correlation-standardised variables by default | Eigenvector signs arbitrary. Eigenvalues/loadings only; scores/predict and rotation not implemented. Clears active model. |
| ADF | Fixed user-specified lag count, statsmodels MacKinnon approximations | Requires one complete, consecutive time series spaced by the declared delta; p-values/critical values can differ. |
| ARIMA | statsmodels nonseasonal state-space model | Likelihood, initialisation, trend/constant parameterisation, covariance and stationarity constraints differ. Default first-difference model uses drift. No seasonal/exogenous models or forecasting. |
| Bootstrap | IID complete-case sample; one `_b[coefficient]`; sample SD of successful fits; normal CI | No clustered/stratified/BCa/studentised resampling. Failed fits counted and excluded. Original fitted model is retained, so subsequent postestimation refers to it rather than the bootstrap distribution. |
| Graphs | matplotlib | Histogram automatic binning, styling, ticks and fonts are not Stata graphics. Specify `bin()` to set bin count. |

`regress` supports analytic, frequency and probability weights; `summarize` supports analytic weights for basic summaries and frequency weights for basic/detail summaries. Weights on other commands, importance weights, weighted analytic detail, weighted bootstrap, weighted `estat` diagnostics and weighted Hausman tests are rejected. Zero/missing weights are excluded, negative weights rejected and frequency counts must be integers. Weighted fits report corrected N and covariance; likelihood/AIC/BIC are omitted rather than reporting inappropriate WLS row-count statistics. Coefficient tests, `lincom` and predictions use the weighted fitted model. Stata's `svy`, `mi`, survival, multilevel, GMM, SEM, spatial, multivariate time-series and general treatment-effects suites are not implemented in this release.

## Data backend selection

`set databackend auto|polars|pandas` is a StatBridge extension, not Stata syntax. The session defaults to auto. Polars is eligible from 100,000 rows for sort/gsort, duplicate detection/removal, numeric collapse and grouped numeric egen. Smaller inputs stay in pandas. Explicit modes override the size decision. Other operations retain their existing backends.

Only required columns are converted, with numeric NaN converted to Polars null for calculations. Stable ties, missing-last sorting, missing-key grouping, nonmissing counts, sample SD and missing-skipping first/last are explicitly implemented. Sort and duplicate selection return row positions, retaining the original payload columns. Floating-point reduction order can differ between backends, producing small rounding differences. Aggregated output storage dtypes can also differ.

Categorical, date/time, complex and nested/object types outside supported scalar columns are not accelerated. Auto mode records the reason for pandas fallback; explicit Polars mode rejects unsupported input before modifying data. The per-command `data_backends` audit entries name the actual backend and reason, and the version manifest includes Polars and PyArrow. No dataset or backend cache is retained between conversions. Current data and estimation interfaces still materialise pandas/NumPy arrays; this is not out-of-core processing.

## Data transformations

- Variable wildcards, ordered ranges and unique abbreviations are supported in ordinary varlists. Command abbreviations are restricted to the explicit alias table.
- `by`/`bysort` are limited to summarize, count, tabulate, correlate, tabstat, generate, replace, egen, recode, xtile and clonevar. Parenthesised secondary sort keys are supported. `_n` and `_N` then refer to each group.
- `merge` supports 1:1, 1:m and m:1, validates cardinality, and emits `_merge` 1/2/3. Master values win overlapping variables in matched rows, even if the master value is missing. `keep()`, `assert()`, `keepusing()`, `generate()` and `nogen` are supported. Failed merge assertions leave data unchanged. There is no update/replace merge option.
- `append` checks overlapping numeric/string types. Master labels take precedence; conflicts are not reconciled automatically.
- `collapse` requires explicit statistic groups. `first`/`last` use pandas missing-skipping behaviour. Weighted statistics and Stata's full percentile catalogue are not implemented.
- `reshape` supports numeric suffixes and integer `j()` only. Newly created names do not inherit complete Stata metadata. `reshape wide` checks nonreshaped variables are constant within the identifier.
- `encode` uses Python Unicode sort order, not a Stata locale. Empty string is missing for encode/decode. Missing-string counting in generic pandas aggregations may differ from Stata; inspect string variables before aggregation.
- `format` retains the format for `.dta` export; the grid/results use general numeric display. `label` supports the forms in the command reference, not the complete Stata label language.
- `_n` is one-based. `_N`, numeric/string comparisons, booleans, arithmetic and observation subscripts are supported by the restricted expression parser. NumPy rounding uses ties-to-even and produces a notice.
- Supported functions: `ln`, `log`, `log10`, `exp`, `sqrt`, `abs`, `floor`, `ceil`, `int`, `sin`, `cos`, `normal`, `invnormal`, `logit`, `invlogit`, `runiform`, `rnormal`, `missing`, `cond`, `inrange`, `inlist`, rowwise `min`/`max`, `mod`, running `sum`, `lower`, `upper`, `trim`, `strlen`, `real`, `string`, `substr`, `round`. Compound quoting, full Unicode/string formatting, date conversion functions and arbitrary function invocation are unsupported.

## Common workflows added in 0.3.0

See [CORE_WORKFLOWS.md](CORE_WORKFLOWS.md) for cleaning, quantiles, grouped summaries, merge controls, single-factor ANOVA, absorbed OLS and expanded postestimation. These remain documented subsets. New commands generally use pandas/NumPy; the existing Polars eligibility rules are unchanged. `areg` uses explicit indicator OLS with a size cap; `anova` accepts only one factor; rank-correlation p-values use SciPy asymptotic conventions. These differences are reported at execution.

## File fidelity

DTA reading is delegated to the installed ReadStat version. Writing supports Stata 13/14/15 format selections, with 15 the default. Reading a file written by a later Stata release depends on whether it uses a format supported by ReadStat. The software does not claim universal forward compatibility.

Variable labels, value labels, dataset labels and original display formats are retained when supported. Date/time numbers remain in Stata's original units, including the epoch; Python datetime conversion is deliberately disabled. Notes, dataset characteristics, sort markers, strL internals and original storage widths are not preserved. Metadata edited by transformations may be dropped where it no longer maps cleanly. CSV import has pandas' missing-string/type inference, not Stata's. CSV exports omit labels.

## Do-file boundaries

Supported: UTF-8/BOM do-files using newline or `#delimit ;` command delimiters; quote-aware line/block comments and continuation; simple macros; scalar `r()`/`e()` results, `_b[]`, `_se[]` and `e(sample)`; loops; brace-based `if`/`else if`/`else` blocks; nested do-files with local scope; selected prefixes. `version #` produces a notice, and does not change backend or emulate historical Stata semantics.

Not supported: compound/nested quoting, extended macro functions, `program`, `syntax`, ado/SSC installation, Mata, Stata matrices, general Stata programming return conventions, arbitrary shell/Python commands, or every Stata abbreviation. Use exact implemented syntax. Comments and URL-like strings inside ordinary double quotes are preserved.

Control-flow conditions use scalar values; variable-valued conditions use the first observation, with a notice. Use an `if` qualifier to filter observations. Braces and delimiters are checked before a do-file starts, but runtime errors can still leave earlier successful mutations in memory. `exit` stops the current do-file, including from nested blocks.

## Teaching support

The optional Learn panel reads the same engine results and compatibility notices used by the full workspace. It never changes estimation settings, random state, data or command execution. Lesson setup scripts explicitly clear the current data when run. Outcome checks are practice aids, not grades or evidence of conceptual understanding.

## Filesystem commands

`ls`/`dir`, `cd`/`chdir`, `pwd`, `mkdir` and `findfile` use Python filesystem operations without invoking a shell. Flags and returned results are the documented StatBridge subset. `findfile` searches under the session working directory, not Stata's ado-path search; this difference is reported. Directory listing and recursive search have explicit entry/depth limits. See NAVIGATION.md. Missing do-files and DTA inputs now return r(601) with the working directory and navigation hints.

## Documentation consulted

These are primary implementation references. Accessed 30 September 2026; see the audit for the versions actually executing.

- [Stata regress manual](https://www.stata.com/manuals/rregress.pdf)
- [Stata language and time operators](https://www.stata.com/manuals/u11.pdf)
- [statsmodels WLS](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.WLS.html)
- [Stata summarize manual](https://www.stata.com/manuals/rsummarize.pdf)
- [Stata functions and expressions](https://www.stata.com/manuals/u13.pdf)
- [statsmodels OLS.fit](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.OLS.fit.html)
- [statsmodels API](https://www.statsmodels.org/stable/api.html)
- [linearmodels implementation choices](https://bashtage.github.io/linearmodels/panel/faq.html)
- [linearmodels mathematical details](https://bashtage.github.io/linearmodels/panel/mathematical-formula.html)
- [pyreadstat documentation](https://github.com/Roche/pyreadstat)
- [NumPy percentile methods](https://numpy.org/doc/stable/reference/generated/numpy.percentile.html)
- [Qt for Python QCompleter](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QCompleter.html)

- [Polars pandas conversion](https://docs.pola.rs/api/python/stable/reference/api/polars.from_pandas.html)
- [Polars stable sorting](https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.sort.html)
- [Polars window expressions](https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.over.html)

Additional primary references consulted for 0.3.0, accessed 1 October 2026:

- [Stata recode](https://www.stata.com/manuals/drecode.pdf)
- [Stata pctile and xtile](https://www.stata.com/manuals/dpctile.pdf)
- [Stata egen](https://www.stata.com/manuals/degen.pdf)
- [Stata split](https://www.stata.com/manuals/dsplit.pdf)
- [Stata missing-code conversion](https://www.stata.com/manuals/dmvencode.pdf)
- [Stata expand](https://www.stata.com/manuals/dexpand.pdf)
- [Stata oneway](https://www.stata.com/manuals/roneway.pdf)
- [Stata areg](https://www.stata.com/manuals/rareg.pdf)
- [Stata regress postestimation](https://www.stata.com/manuals/rregresspostestimation.pdf)


## Version 0.4.0 additions

See ROADMAP.md and ROADMAP_WORKFLOWS.md for the precise implemented subsets. Margins treats numeric 0/1 variables as continuous derivatives unless fitted as factors, corrects the old backend shortcut and rebuilds interactions for counterfactual rows. Margins covariance conditions on empirical covariates. Balanced CRE/Mundlak is supported; unbalanced selection corrections are refused. IV exogeneity uses Wu-Hausman or Wooldridge regression according to covariance; robust overidentification is Wooldridge score, not Hansen J. Clustered overidentification is refused.

AbsorbingLS inference uses its own finite-sample/absorbed-df corrections, which are not certified reghdfe-identical. Absorbed effects include the intercept and no normalisation-dependent constant is reported. Two-way covariance uses inclusion-exclusion, may be invalid, and is refused in that case. DiD supports only complete two-period common-adoption designs with group clustering; no staggered or heterogeneous event-study estimator.

Excel supports .xlsx and cached formula values, not formula evaluation or old .xls files. Date parsing uses explicit component masks and English month names, with invalid dates becoming ordinary missing; date display does not change numeric units. ReadStat DTA storage remains numeric. Tables and graph commands accept bounded syntax, not all Stata collection/graph options.


## dtabnk integration (0.5.0)

`dtabnk` and `export sav|parquet|rdata` are StatBridge extensions, not official Stata commands. See [DTABNK.md](DTABNK.md) for supported layouts, merge semantics and differences from the original CLI. Indicators are not automatically harmonised for units or definitions. Duplicate source keys fail by default, while upstream dtabnk ordinarily averages during a pivot; use `aggregate(mean)` only when averaging is substantively justified. The integration uses the updated dtabnk validated one-to-one merge implementation from commit `a1af2b0cfc87cedef12b416d2fa2ae6ff341ff63`.

## Dataset formats (0.6.0)

See [FILE_FORMATS.md](FILE_FORMATS.md) for the complete import/export matrix, metadata preservation, missing-value conversion, R date strings, proprietary-format gaps and atomic replacement semantics.


## 0.7.0 scope

See [everyday coverage](EVERYDAY_COVERAGE.md) for survey, survival, categorical, HAC and descriptive subsets and their covariance conventions. Unsupported designs/options fail explicitly. Survey and survival declaration state is not serialized in DTA files. No measured user-coverage percentage is claimed.
