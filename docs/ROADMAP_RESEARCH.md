# Most worthwhile next improvements

Research and source audit: 5 October 2026. Baseline: StatBridge 0.3.2.

This ordering is a product judgment for students and applied econometrics: breadth of useful workflows, current gaps, reuse of existing backends, and the cost of validating inference. It is not a measured ranking of Stata command frequency. The catalog has 114 entries with bounded syntax; that count does not establish a percentage of Stata coverage or a 95% use-case claim.

The Learn expansion is implemented in this release. The command additions below are proposals, not implemented features.

| Priority | Proposed work | Why it earns its place | Current boundary and implementation approach |
| --- | --- | --- | --- |
| 1 | Broader `margins`, then `marginsplot` | Makes fitted models interpretable in outcome/probability units and makes interactions teachable [1,2] | Current margins is numeric-main-effect logit/logistic/probit `dydx(*)` only. Add OLS/logit/probit adjusted predictions, factor contrasts, `at()` and `over()` in stages. Preserve design metadata, rebuild interactions for counterfactual rows, use the fitted covariance for delta-method intervals, and store structured margins results before plotting. |
| 2 | Exportable descriptive and model-comparison tables | Completes the common assignment workflow from estimation to a readable report [3,4] | `estimates table` exists but is limited. Build a shared structured table result for GUI, terminal, clipboard and CSV/HTML/LaTeX exports. Add a documented `etable`/`dtable` subset first. `esttab` is a community command; only advertise an alias when its accepted syntax is explicit. |
| 3 | Panel specification tools: robust Mundlak/CRE | Addresses the gap students encounter when Hausman is incompatible with clustered inference [5,6] | FE/RE and guarded classical Hausman already exist. Implement correlated RE with panel means and a joint robust test of the mean terms. Validate unbalanced panels, the estimation-sample definition of means, time-invariant covariates and cluster degrees of freedom before exposing `estat mundlak`. |
| 4 | IV postestimation diagnostics | Turns an existing 2SLS fit into a more complete identification workflow [7,8] | Add `estat firststage`, then supported endogeneity and overidentification tests from linearmodels. Distinguish a robust Wald chi-square from a classical first-stage F statistic; expose reference distributions and assumptions. Reject undefined overidentification tests in exactly identified models. Weak-IV-robust intervals are a separate feature. |
| 5 | Excel and dates | Removes common barriers to using course and dissertation datasets [9] | Add sheet/range selection, explicit type/missing rules, predictable exports and Stata date conversion/display. Keep raw numeric Stata date values and display formats distinct. Test Windows paths, mixed columns, Excel date systems and DTA round trips. |
| 6 | Diagnostic and layered graphics | Helps students assess fits and present results without moving tools | Extend existing histogram/scatter/line and PNG/PDF/SVG exports with a bounded `twoway` grammar, `lfit`, residual-versus-fitted plots and Q-Q plots. Reuse plotting and prediction code; define sample selection, missingness and labels consistently. |
| 7 | Multiple absorbed effects and multiway clustering | Extends existing panel/areg coverage for applied work | Evaluate linearmodels/pyhdfe/PyFixest against a specified `reghdfe` subset. Record singleton removal, fixed-effect degrees of freedom, nested clusters and small-sample corrections; backend defaults need not match Stata/community commands [10]. |
| 8 | DiD and event-study workflows | Useful for policy courses, but requires careful estimand and design support [11] | Begin with explicit two-group/two-period and conventional designs; then evaluate cohort/time-specific effects for staggered adoption. Do not label a generic two-way-FE coefficient as a valid heterogeneous-treatment estimator. Provide assumptions and design diagnostics in Learn. |

## Work to do alongside those features

- Publish a syntax coverage matrix based on realistic course do-files, including the failed option/expression and its workaround. Count successful workflows rather than command names alone.
- Keep command help, completion, setup dialogs, return values, terminal output and Learn guidance aligned with each supported subset.
- Add reproducible reference fixtures with coefficients, covariance, sample membership and degrees of freedom. Use algebraic checks and backend comparisons now; claim Stata numerical agreement only for fixtures actually compared with Stata.
- Test packaged launches on Windows and macOS. The current Linux tests do not establish native platform behaviour.
- Keep Polars for operations where measured gains justify it. The current engine is a hybrid, with pandas and estimator conversions; replacing the dataframe layer alone will not speed every statistical fit.
- Treat survey design (`svy`) and multiple imputation (`mi`) as dedicated validation projects. Probability weights alone are not complex-survey inference, and imputation is not simply filling missing cells.

## Recommended implementation sequence

Start with structured table exports and the shared prediction/design infrastructure for broader margins. Add robust panel and IV diagnostics next, each with an executable teaching example and explicit unsupported cases. Excel/date support and better diagnostic graphics can follow without expanding the estimator list. This favours complete, understandable workflows over many shallow command wrappers.

For the user's immediate teaching request, 0.3.2 expands Learn to 18 executable exercises and nine interpretation guides. It explains classical Hausman rejection, non-rejection and invalid comparisons, without implementing robust Mundlak or silently changing the fitted model.

## Sources

Primary documentation checked on 5 October 2026. Feature descriptions establish scope, not user-frequency estimates. Python package defaults must still be checked against the exact installed version.

1. [Stata: marginal analysis](https://www.stata.com/features/overview/marginal-analysis/).
2. [Stata: margins plots](https://www.stata.com/features/overview/margins-plots/).
3. [Stata: tables of estimation results](https://www.stata.com/features/overview/tables-of-estimation-results/).
4. [Ben Jann: esttab documentation](https://repec.org/bocode/e/estout/esttab.html). Community package, not an official Stata command.
5. [Stata: Mundlak specification test](https://www.stata.com/new-in-stata/mundlak-specification-test/).
6. [Stata: Hausman manual](https://www.stata.com/manuals/rhausman.pdf).
7. [linearmodels: IV results API](https://bashtage.github.io/linearmodels/iv/iv/linearmodels.iv.results.IVResults.html).
8. [linearmodels: first-stage diagnostics](https://bashtage.github.io/linearmodels/iv/iv/linearmodels.iv.results.FirstStageResults.diagnostics.html).
9. [Stata: Excel import/export](https://www.stata.com/features/overview/excel-import-export/).
10. [PyFixest: small-sample corrections](https://pyfixest.org/explanation/ssc.html).
11. [Stata: heterogeneous difference-in-differences](https://www.stata.com/features/overview/heterogeneous-difference-in-differences/).
