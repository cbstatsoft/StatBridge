# Specialist statistical workflows: bounded Phase C additions

These commands are StatBridge **supported subsets**, not representations of full Stata syntax or numerical equivalence. They are implemented through the shared command engine, so they work in Qt command input, do-files, the curses terminal and batch execution. The underlying libraries are statsmodels, NumPy and SciPy.

## Gaussian mixed-effects models

\`\`\`stata
mixed score age education, group(school_id)
mixed score age, group(school_id) slope(age) mle
\`\`\`

\`mixed\` estimates a Gaussian random-intercept model with \`group()\`, or a correlated random-intercept/random-slope model with \`slope()\`. Restricted maximum likelihood is the default; \`mle\` requests ordinary maximum likelihood. Estimates, model-based fixed-effect covariance, residual variance and random-effect variance components are retained in the model result. Covariance and intervals follow the Python backend's fixed-effect normal approximation.

**Guards:** At least five clusters and 30 complete observations, at least two observations per cluster, full-rank fixed design and sufficient sample size. Random slopes require within-cluster variation and at least ten clusters. Nonfinite, collinear or unconverged fits are refused. The implementation does **not** support complex nested/crossed variance components, GLMM links, weights, cluster-robust SEs, small-sample denominator-df corrections, or random-effect BLUP forecasts. In the model object, \`predicted\` contains only the fixed-component fitted mean.

## Balanced repeated-measures ANOVA

\`\`\`stata
anovarm score, subject(participant) within(visit)
anovarm score, subject(participant) within(visit condition)
\`\`\`

This StatBridge extension uses statsmodels AnovaRM for one or two within-subject factors. It requires **exactly one nonmissing observation per participant/factor combination** and every participant in every within-cell. The response and all identifiers must be observed, with at least three participants. All F/df/p outputs use statsmodels' conventions.

No Greenhouse–Geisser or Huynh–Feldt corrections, between-subject factors, unequal repeated observations, missing cells, mixed/random effects or post-hoc contrasts. **Sphericity is assumed for within-subject effects with more than two levels.**

## Multiple imputation for continuous OLS

\`\`\`stata
mi regress income education age, m(10) burnin(10) between(5) seed(42)
\`\`\`

This is a **StatBridge extension**, not Stata's \`mi estimate:\` interface. It creates multiple transient completed datasets using statsmodels MICEData predictive mean matching (PMM). After burn-in, it advances the chained equations between completed datasets, fits ordinary unweighted OLS in each, and combines fixed coefficients and covariance using Rubin's within/between-imputation formula.

The reported per-coefficient degrees of freedom use the **original large-sample Rubin approximation**, not Barnard–Rubin small-sample adjustments. A user-specified seed is used for reproducible runs and the ambient NumPy RNG state is restored on completion. The original dataset is unchanged. Pooled output is stored in the latest structured results table and can be exported with \`export results\`. The active regression model is cleared to avoid pretending that any one completed dataset is the fitted model.

**Restrictions:** Numeric continuous variables only; no categorical/factor imputation, passive variables, non-Gaussian models, imputation diagnostics/convergence assessment, survey/cluster variance, auxiliary-variable syntax, stored imputation datasets or reliable missing-at-random assumption tests. At least 40 records, 20 observed donors and six observed distinct values per variable, 5–30 completed datasets, 3–50 burn-in passes and 1–20 update passes between imputations. No generalized Stata \`mi\` command syntax is accepted. Treat estimates as exploratory without independent diagnostics and substantive assumptions.

## Vector autoregression

\`\`\`stata
tsset quarter
var gdp inflation, lags(2)
varstable
varforecast, steps(8)
\`\`\`

A bounded statsmodels Gaussian VAR using the declared \`tsset\` time variable. It accepts two to six continuous series, explicit lag order 1–12, a constant (default) or \`noconstant\`. Time must be finite and **consecutive at the declared delta**, with no missing observation or series entry. Order selection is not automated; AIC/BIC and coefficient matrices are returned from the estimated model.

\`varstable\` checks inverse characteristic roots against the unit circle. \`varforecast\` produces 1–60 conditional mean point predictions from stable models and returns the corresponding future time values. Any dataset or time-declaration change invalidates a previously fitted VAR.

**Not implemented:** VECM, cointegration tests, structural VAR, impulse responses, FEVD, forecast intervals, robust covariance, exogenous regressors or advanced trend choices. A stable fitted VAR is not proof that the data generating process is stationary.

## Validation and roadmap boundaries

Synthetic tests independently compare random-intercept mixed-model estimates and covariance to direct statsmodels usage, repeated ANOVA tables, VAR coefficients/forecasts, and Rubin pooled total variance. They also cover failure guards, MI reproducibility, read-only dataset behaviour and VAR stale fits. These tests must pass in GitHub Actions on supported Python/platform combinations before this work should be described as validated.

The following roadmap items remain **unimplemented**, not renamed as complete:

- Full random-effects/GLMM architecture with heterogeneous/nested/crossed variance structures and model-comparison inference.
- Full Stata \`mi\` register/impute/chained/estimate, variable-type models and diagnostics.
- Complex survey designs (multistage PSUs, FPC, replicate weights, poststratification, multivariate inference).
- Staggered-treatment cohort/time DiD with reliable parallel-trends diagnostics and robust event-study inference.
- Weak-IV-robust confidence sets and clustered overidentification.
- VECM, cointegration, structural time-series, ARCH/GARCH, specialist SEM/Bayesian and multivariate suites.
- External licensed Stata validation and native OS packaging certification.

Implementing any of these without the correct design assumptions and reference validation would overstate the statistical results.

### References

- [statsmodels Gaussian mixed models](https://www.statsmodels.org/stable/mixed_linear.html)
- [statsmodels repeated measures ANOVA](https://www.statsmodels.org/stable/generated/statsmodels.stats.anova.AnovaRM.html)
- [statsmodels multiple imputation](https://www.statsmodels.org/stable/imputation.html)
- [statsmodels VAR](https://www.statsmodels.org/stable/vector_ar.html)
