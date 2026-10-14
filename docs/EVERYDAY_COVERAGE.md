# Everyday workflow coverage in 0.7.0

StatBridge targets routine student and applied-analysis workflows. It is **not a full Stata replacement**. There is no representative usage dataset behind a “95% of users” claim. A command name covers only the documented syntax. Run `coverage` or choose **Help > Workflow coverage and limits** for the audit inside the app.

## Added in this release

- `mean`, `total`, `proportion`, `ci means/proportions` with stored descriptive covariance or exact/Wilson binary intervals.
- `prtest`, `sdtest`, `kwallis`, `tab1`, `tab2`, `inspect`, `compare`.
- `xtdescribe`, `xtsum`, `tsfill`, `fillin`, `ipolate`, including grouped interpolation.
- `mlogit`, `ologit`, `oprobit`, `newey`.
- Right-censored `stset`, `stsum`, `sts list/graph/test`, `stcox`.
- One-stage `svyset`, `svy: mean/total/proportion/regress`, including `subpop()`.
- `graph box`, `graph bar (mean|sum|count)`.
- Seven additional variable-selection analysis forms, context-aware command/variable completion, and four optional Learn exercises (30 total).
- Fixed numeric logical arithmetic: `(x>0)+(z>0)` now counts conditions instead of applying pandas boolean addition.

## Statistical scope and differences

### Descriptive estimates and tests

`mean`, `total` and `proportion` use unweighted complete-case samples, joint IID covariance and symmetric t(N-1) intervals. `over()` uses domain influence vectors and overall N-1 degrees of freedom. Group small-sample and transformed-proportion conventions may differ from Stata. Proportion limits may extend outside [0,1]. `total` estimates the unweighted sample total; use `svy: total` for population expansion weights.

`ci means` uses Student-t intervals on each variable's available cases. `ci proportions` requires 0/1 data and defaults to exact Clopper-Pearson; `wilson` is available. Proportion z tests are asymptotic and independent-sample. `sdtest` assumes independent normal samples, including when two columns occur on the same rows; it is not a paired variance test. Kruskal-Wallis uses tie correction and asymptotic chi-square inference. Most of these commands do not support weights.

### Categorical models

`mlogit` defaults to the most frequent category, lowest in a tie, as the base. `baseoutcome(#)` changes it. Equation-labelled coefficients and `rrr` are supported. Ordered models transform backend threshold parameters and their full covariance into actual latent-scale cutpoints.

```
mlogit choice age income, baseoutcome(1)
predict p_choice2, pr outcome(2)
ologit satisfaction age income
predict p_high, pr outcome(4)
```

Unweighted ML and model-based covariance only. Predictions are estimation-sample probabilities. No robust/clustered VCE, margins, IIA or proportional-odds diagnostics for these estimators. Optimizer and separation checks differ from Stata. Stored estimates and tables work; multi-equation linear-restriction expressions are not implemented.

### Newey-West

```
tsset month
newey outcome exposure control, lag(4)
```

Bartlett HAC with N/(N-k) correction and residual-df t inference. Requires a single series and consecutive times in the complete estimation sample. No `force`, automatic bandwidth, prewhitening or panel HAC. HAC uncertainty does not fix omitted variables or a misspecified mean.

### Survey

```
svyset psu [pw=weight], strata(stratum)
svy: mean income
svy, subpop(adult): regress income education age
```

One-stage, with-replacement Taylor linearization. Scores are summed by PSU within stratum, centered and scaled by n_h/(n_h-1). Inference uses PSUs minus strata degrees of freedom. All design PSUs are retained for subpopulations, with zero scores outside the domain. Incomplete outcome rows are excluded from point estimates and assigned zero scores. PSU identifiers repeated across strata are distinct sampling units.

Identifiers must be nonmissing, weights finite and positive, and every stratum must have at least two PSUs. No FPC, multistage/replicate designs, singleton adjustment, calibration, design effects, survey logit or other nonlinear survey estimators. `if/in` is refused; use a nonmissing 0/1 `subpop()` indicator. Only `level()` is accepted by the underlying survey estimator. Proportion intervals are symmetric t intervals, not transformed intervals. Ordinary WLS likelihood/IC are not reported as survey fit statistics.

### Survival

```
stset duration, failure(failed) id(subject)
sts graph, by(treatment)
sts test treatment
stcox age i.treatment, strata(site) ties(efron)
predict relative_hazard, hr
```

One record per subject, right censoring and origin zero. Invalid times are excluded. Failure must evaluate to 0/1. `stset` creates/replaces `_t`, `_t0`, `_d`, `_st`. Kaplan-Meier lists event-time survival, risk sets and Greenwood SEs. Log-rank compares groups. Cox supports Breslow (default) or Efron ties and stratified baseline hazards, with model-based covariance only. `ties()` is the StatBridge option spelling.

Hazard ratios are displayed by default; `nohr` shows log-hazard coefficients. Sample-only `xb/hr` predictions. No delayed entry, time-varying records, weights, clustered VCE, baseline survival predictions, parametric survival, competing risks, interval censoring or proportional-hazards diagnostic. A significant slope does not establish proportional hazards.

Survey/survival declarations survive preserve/restore. Clear and fresh imports reset them. They are not serialized as Stata declaration characteristics in DTA exports, so re-declare after opening a file.

### Panel preparation and graphs

`tsfill` adds missing time rows on the declared delta grid, without imputing values; `full` uses the common observed panel range. `fillin` creates absent combinations with `_fillin`, retaining original duplicate combinations. Both have two-million-row/combination limits. `ipolate` is linear; repeated observed x values use mean y. Extrapolation requires `epolate`. Use `bysort id (time): ipolate y time, generate(filled)` to avoid mixing panels.

`xtdescribe` reports counts, not pattern diagrams. Equal counts do not prove common time support. `xtsum` within values subtract each panel mean and add the observation-weighted overall mean; between SD uses unweighted panel means. Box/bar graphs support one `over()` group; matplotlib quartile, whisker and category-order conventions can differ.

## Remaining priority gaps

Mixed/multilevel models; multiple imputation and pooling; factorial/repeated ANOVA; more complex survey designs and nonlinear estimators; broader margins/prediction/diagnostics; advanced survival; VAR/VECM/ARCH/GARCH; general treatment effects and staggered-adoption DiD; dynamic-panel GMM; SEM/Bayesian and specialist multivariate methods; full ado/program syntax; full graphics/reporting systems.

These matter to substantial groups of Stata users. Unsupported commands and options fail explicitly. Known differences appear in Results and the compatibility ledger. The release is not certified against licensed Stata executions and does not establish a measured user-coverage percentage.

## Primary reference points

[Stata features](https://www.stata.com/features/overview/), [Stata survey manual](https://www.stata.com/manuals/svy.pdf), [subpopulation estimation](https://www.stata.com/support/faqs/statistics/subpopulation-estimation/), [singleton PSUs](https://www.stata.com/support/faqs/statistics/standard-error-because-of-stratum/), [statsmodels survival methods](https://www.statsmodels.org/dev/duration.html). Feature inventories establish scope, not user frequency. Backend versions appear in the compatibility report.

## Workflow audit

| Workflow | Implemented scope | Remaining limits |
| --- | --- | --- |
| Files and reproducibility | DTA/DO, SPSS, SAS import/XPORT export, R, Arrow/Parquet, Excel, text, SQLite; logs/macros/loops | Bounded scripting and format variants; no full ado/program interpreter |
| Clean and reshape | Generate/replace, egen, dates, merge/append, reshape/collapse, recode, missingness, interpolation | Bounded functions and merge/reshape options |
| Describe and compare | Tables, correlations, means/totals/proportions/CI, t/rank/proportion/variance tests, one-way ANOVA | No full factorial/repeated ANOVA or multiple-comparison suite; mostly unweighted |
| Regression | OLS/weighted OLS, binary/count/GLM/quantile, multinomial/ordered, predictions, Wald tests, tables | Margins OLS/logit/probit only; new categorical models model-based VCE only |
| Panel and causal | FE/RE/CRE, absorbed effects, IV2SLS, Hausman/Mundlak/IV diagnostics, two-period DiD | No dynamic-panel GMM, staggered DiD, matching or general treatment-effects suite |
| Time series | Time operators, tsfill, ARIMA, ADF, Newey-West | No VAR/VECM, ARCH/GARCH, seasonal ARIMA or full forecasting |
| Survey | One-stage stratified-PSU means/totals/proportions/linear regression and subpopulations | No FPC/multistage/replicate/singleton designs or survey logit |
| Survival | Right-censored stset, KM, log-rank, Cox with strata and tie handling | No delayed entry, time-varying records, parametric survival, competing risks or PH diagnostic |
| Graphs and reporting | Histogram, scatter/line/lfit, box/bar, layers, marginsplot, tables and export | Bounded styling; no full graph editor or collect/putdocx |
| Specialist methods | PCA and bounded bootstrap | Mixed/multilevel, multiple imputation, SEM, Bayesian and general multivariate suite absent |
