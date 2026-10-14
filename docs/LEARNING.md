# Optional learning support

StatBridge is intended to give students a usable statistical desktop without a Stata installation or licence key. The same complete set of implemented features is available to students and experienced users. Teaching is an optional layer over the shared engine.

Click **Learn** in the toolbar or Help menu. It is off by default. Its visibility is remembered between sessions. Close the dock or click Learn again to hide it.

## Practice

Search by lesson or command, filter by topic, then choose an exercise, read the explanation, and click **Open in do-file editor**. This fills the editor after its normal unsaved-edit check. It does not run commands or change the dataset. Each setup starts with `clear all` and states that it replaces the in-memory data. Save your dataset before running a setup.

Run the setup with Ctrl+D, enter your answer in Command or the editor, then click **Check my result**. The check reads current results without rerunning commands. **Show solution** reveals a suggested answer. Explain the answer in your own words and try a modified example before moving on. These are outcome checks, not grades or proof of understanding.

| Exercise | Focus |
| --- | --- |
| 1. Data and summary statistics | Read observations, variables, means and standard deviations. |
| 2. Conditions and subsets | Use an if qualifier without deleting observations. |
| 3. The missing-value trap | Exclude numeric missing values intentionally. |
| 4. Repeatable do-files | Use a macro and a loop to create related variables. |
| 5. Interpret a regression | Fit a slope and distinguish association from causation. |
| 6. Coefficients versus uncertainty | Understand what robust standard errors change. |
| 7. Choose the right weight | Distinguish repeated observations from survey weights. |
| 8. Panel fixed effects | Estimate within-panel associations and cluster uncertainty. |
| 9. Clean special missing codes | Preserve raw values and treat missing codes explicitly. |
| 10. Reshape repeated measurements | Turn wide repeated measures into a long panel. |
| 11. Interpret an interaction | Compute the slope for a specified group using coefficient covariance. |
| 12. Test several restrictions | Distinguish a joint test from separate coefficient tests. |
| 13. Fitted values and residuals | Separate a prediction from its error and from uncertainty. |
| 14. Odds versus probabilities | Read binary-outcome results on the correct scale. |
| 15. Interpret a Hausman comparison | Compare FE and RE while stating the assumptions and limits. |
| 16. Diagnose functional form | Use RESET as evidence, not a specification recipe. |
| 17. Compare means with uncertainty | Read a mean-difference interval in outcome units. |
| 18. Instruments and identification | Distinguish a fitted 2SLS model from a credible instrument. |
| 19. Predictions with interactions | Interpret adjusted predictions for each group. |
| 20. Mundlak with clustered uncertainty | Assess RE restrictions while retaining panel clustering. |
| 21. Diagnose a 2SLS model | Read instrument strength, exogeneity and overidentification separately. |
| 22. Two-period difference-in-differences | Interpret a treatment-by-post change under parallel trends. |
| 23. Numeric dates and display formats | Keep numeric date units separate from calendar display. |
| 24. Compare and export models | Build a structured comparison without confusing samples or covariance. |
| 25. Merge World Bank indicator files | Preserve unmatched indicators, encode country IDs and declare the resulting panel. |

The editable setup scripts are also in `examples/lessons/`. They use synthetic data. Instructors can adapt them without introducing an account or internet requirement after dependencies are installed.

## Explain

This tab explains the latest command, including errors and any compatibility notices. For fitted models it discusses coefficients, standard errors, confidence intervals, p-values and the selected covariance. Model-specific notes distinguish odds ratios from changes in probability and warn against interpreting regression significance as proof of causality.

The explanation is built into the application and runs locally. It is not a remote chatbot. It cannot evaluate the substantive quality of a research design, replace a course textbook or certify that a result matches Stata. Consult the compatibility ledger before comparing numerical output.

## Tests

The third tab provides thirteen offline reference guides. Each states the null or question, what rejection and non-rejection mean, the assumptions, and sensible next steps. VIF is explicitly identified as a diagnostic without a null hypothesis or p-value. The IV guide distinguishes instrument relevance from validity, and distinguishes implemented diagnostics from remaining weak-IV and clustered-overidentification gaps.

**Explain** also reads the current p-value for supported successful tests. It illustrates a 5% threshold and explains that the level should be chosen before examining results. A p-value is not the probability the null is true. Failed tests never reuse an earlier p-value as their result. Test explanations and exercise checks do not rerun commands or modify data, results, the random-number stream or the compatibility ledger.

For Hausman, the explanation distinguishes an actual FE-followed-by-RE comparison from other stored-model comparisons. It covers the RE exogeneity restriction, the limits of non-rejection, sample/specification comparability and invalid covariance differences. Classical Hausman is not appropriate with robust/clustered covariance. Do not drop necessary clustering merely to obtain a p-value. Robust Mundlak/CRE is available for balanced complete-case panels. The guides explain its limits and the supported IV diagnostics.

The 25 scripts also work in the terminal through `do`; the interactive Learn panel is currently Qt-only. The reference below can be read offline in either workflow.

## Offline test reference

### Hausman: fixed versus random effects

**Null or question:** No systematic difference between the compared slopes, under the specification and efficiency assumptions. In the usual FE/RE comparison, RE requires regressors to be uncorrelated with the unobserved panel effect; FE allows that correlation.

**Larger value or rejection:** Evidence against the RE restrictions in this FE/RE comparison. FE or an appropriate correlated random-effects specification may be more defensible, provided its own assumptions hold.

**Smaller value or non-rejection:** Insufficient evidence against the RE restrictions. This does not prove RE is valid or that the two models are equivalent. Limited power can hide important differences.

**Assumptions:** Put the estimator consistent under both hypotheses first: hausman fixed random. FE still requires appropriate exogeneity of the idiosyncratic error. Classical covariance-difference inference is unsuitable with robust or clustered covariance. Compare the same outcome, observations and compatible specifications. A non-positive-definite covariance difference is an invalid test, not a vote for RE.

**Next step:** Report the statistic, degrees of freedom, p-value, sample and assumptions. Do not choose solely by a threshold. If clustering is needed, consider a correctly specified robust Mundlak/CRE approach. StatBridge supports estat mundlak and xtreg, cre for balanced complete-case panels. Unbalanced CRE corrections and sigmamore/sigmaless are not implemented.

```stata
xtreg y x, fe
estimates store fixed
xtreg y x, re
estimates store random
hausman fixed random
```

### Wald: joint restrictions and contrasts

**Null or question:** All specified coefficient restrictions hold simultaneously. test x z tests both slopes equal to zero; test x = z tests their equality. lincom tests the displayed linear combination equal to zero before exponentiation.

**Larger value or rejection:** Evidence that at least one restriction fails. A joint rejection does not identify which coefficient or restriction differs.

**Smaller value or non-rejection:** Insufficient evidence against the restrictions. This is not proof that an effect is zero or practically negligible.

**Assumptions:** Inference depends on the fitted model and its covariance, sample size and cluster count. Standard errors of contrasts require coefficient covariances. For lincom, eform, the null on the reported ratio scale is one.

**Next step:** Report the contrast, its units and interval as well as its p-value. Choose hypotheses in advance; account for multiple testing when making many comparisons.

```stata
test x = z
testparm i.group
lincom x - z
```

### t-test: means and paired differences

**Null or question:** The population mean equals the specified value, or the mean difference equals zero. A paired test concerns within-pair differences.

**Larger value or rejection:** Evidence against the specified equality of means under the sampling assumptions.

**Smaller value or non-rejection:** Insufficient evidence of a difference. A wide interval may include both meaningful benefits and harms; non-rejection is not equivalence.

**Assumptions:** Independent observations or independent pairs are needed. The pooled two-sample test assumes equal variances; unequal requests Welch inference. Pairing and cluster dependence cannot be ignored. Small samples require attention to the distribution of errors or differences.

**Next step:** Read the confidence interval in outcome units. For by(), the difference is first sorted group minus second. Assess magnitude, design and uncertainty together.

```stata
ttest score == 50
ttest after == before
ttest score, by(group) unequal
```

### Breusch-Pagan: heteroskedasticity

**Null or question:** The error variance is constant against the variance relationship tested here, which uses fitted values.

**Larger value or rejection:** Evidence of nonconstant variance of the specified form. Conventional OLS uncertainty may be inappropriate.

**Smaller value or non-rejection:** This test did not detect that variance pattern. Other forms of heteroskedasticity may remain.

**Assumptions:** StatBridge uses the original normality-based Breusch-Pagan LM test with fitted values, not every Stata hettest variant. It requires an appropriate mean specification; residual plots remain useful.

**Next step:** Consider robust covariance or clustering appropriate to the study design. Robust errors do not repair confounding, endogeneity or a misspecified mean.

```stata
regress y x
estat hettest
```

### RESET: functional form

**Null or question:** Coefficients on added powers of fitted values are jointly zero. StatBridge adds powers 2, 3 and 4.

**Larger value or rejection:** Evidence of a detectable specification problem. The test does not tell you which variable is missing or which transformation is correct.

**Smaller value or non-rejection:** No detected departure of this form. The model is not thereby certified correct or causal.

**Assumptions:** The implemented F test requires conventional unweighted OLS with an intercept. Its calibration depends on classical regression assumptions.

**Next step:** Inspect residual patterns and use subject knowledge to consider nonlinearities or interactions. Do not keep changing specifications merely to obtain a large p-value.

```stata
regress y x
estat ovtest
```

### VIF: collinearity, not a hypothesis test

**Null or question:** There is no null hypothesis or p-value. For a nonconstant regressor, VIF = 1/(1 - R-squared) from regressing that regressor on the others with an intercept.

**Larger value or rejection:** A large VIF signals imprecise separation of correlated predictors, not a statistically significant finding.

**Smaller value or non-rejection:** A small VIF does not demonstrate good identification or rule out omitted-variable bias.

**Assumptions:** There is no universal cutoff. Interactions and polynomial terms can naturally be correlated. The intercept's VIF is usually not substantively useful.

**Next step:** Inspect coefficient intervals and the estimand of interest. Do not delete a necessary confounder solely to reduce VIF; centring changes interpretation but does not add information.

```stata
regress y x z
estat vif
```

### ADF: unit roots and stationarity

**Null or question:** The series has a unit root, under the selected deterministic terms and lag specification.

**Larger value or rejection:** Evidence against a unit root in this specification. With a trend included, the alternative allows stationarity around a deterministic trend.

**Smaller value or non-rejection:** Insufficient evidence against a unit root. This is not proof of a unit root; short samples, structural breaks and near-unit-root behaviour can reduce power.

**Assumptions:** Choose intercept/trend terms and lag length deliberately. Too few lags can leave serial correlation; too many can reduce power. StatBridge fixes lags() and uses statsmodels MacKinnon approximations.

**Next step:** Plot the series, inspect the study context and assess sensitivity to defensible specifications. Do not difference a series solely because one p-value exceeds 0.05.

```stata
tsset time
dfuller y, lags(1)
```

### One-way ANOVA: group means

**Null or question:** All group population means are equal.

**Larger value or rejection:** Evidence that at least one group mean differs. The omnibus test does not identify which pair differs.

**Smaller value or non-rejection:** Insufficient evidence of unequal means. This is not evidence that all groups are equivalent.

**Assumptions:** The classical F test assumes independent errors, equal within-group variances and an appropriate error distribution for finite-sample calibration. This implementation does not provide Welch ANOVA.

**Next step:** Inspect group summaries and effect sizes. Use planned contrasts and account for multiple comparisons when following up.

```stata
oneway score group, tabulate
```

### IV: relevance, exclusion and endogeneity

**Null or question:** Different diagnostics ask different questions: an endogeneity test typically treats the nominated regressors as exogenous under its null; an overidentification test assesses joint moment restrictions under additional assumptions.

**Larger value or rejection:** An endogeneity-test rejection challenges OLS exogeneity if the instruments and test assumptions are valid. Overidentification rejection flags incompatible moment restrictions, not a named bad instrument.

**Smaller value or non-rejection:** Non-rejection does not establish exogeneity or instrument validity. Weak instruments can make conventional inference unreliable.

**Assumptions:** Instruments need relevance and a defensible exclusion/exogeneity argument. The familiar first-stage F > 10 rule is not a universal threshold, especially for multiple endogenous regressors or robust/clustered tests. IV Wu-Hausman and panel FE/RE Hausman are different tests.

**Next step:** Report first-stage strength and the identification argument. Use estat firststage and estat endogenous; estat overid supports conventional or heteroskedasticity-robust fits but refuses clustered fits. Weak-IV-robust intervals are not implemented.

```stata
ivregress 2sls y control (x = instrument)
```

### Mundlak: correlated random effects

**Null or question:** All identified panel-mean coefficients are jointly zero in the augmented RE model, assessing the additional RE restrictions.

**Larger value or rejection:** Evidence against these RE restrictions. Consider FE or a defensible CRE specification, subject to their own exogeneity assumptions.

**Smaller value or non-rejection:** Insufficient evidence against the restrictions, not proof of random-effects validity. Power and the chosen set of means matter.

**Assumptions:** This implementation requires balanced complete-case panels with a common time grid. It tests identified means of expanded time-varying regressors. The selected covariance is used; robust clusters by panel. The Wald chi-square is asymptotic and can be unreliable with few clusters.

**Next step:** Report the mean terms, statistic, degrees of freedom, p-value and covariance. Do not remove required clustering to get a classical Hausman result. estat mundlak does not replace the active model.

```stata
xtreg y x, cre vce(cluster id)
estat mundlak
```

### IV first stage: relevance and strength

**Null or question:** For each endogenous regressor, excluded-instrument coefficients are jointly zero in its first stage, conditional on included exogenous regressors.

**Larger value or rejection:** Evidence of relevance does not by itself establish sufficient strength for reliable conventional IV inference.

**Smaller value or non-rejection:** Weak evidence of relevance raises concern about identification, but the p-value alone is not a complete weak-instrument diagnostic.

**Assumptions:** Read f.dist. Unadjusted covariance uses F; robust/clustered covariance uses a Wald chi-square. The f.stat column name does not change that distribution. A universal F > 10 rule is not appropriate for every design.

**Next step:** Report partial R-squared, the statistic and distribution. Substantiate exclusion separately. Stock-Yogo cutoffs and weak-IV-robust confidence sets are not supplied.

```stata
ivregress 2sls y control (x = instrument)
estat firststage
```

### IV exogeneity test

**Null or question:** All regressors nominated as endogenous can be treated as exogenous, assuming the instruments and maintained model are valid.

**Larger value or rejection:** Evidence against exogeneity under those assumptions. This is not an independent demonstration that the instruments are valid.

**Smaller value or non-rejection:** Insufficient evidence against exogeneity. Weak instruments or limited power can hide endogeneity.

**Assumptions:** Conventional 2SLS uses Wu-Hausman F. Robust or clustered fits use Wooldridge regression Wald with the fitted covariance. This is distinct from the panel FE/RE Hausman comparison.

**Next step:** Report which test was used, its assumptions and instrument-strength evidence. Preserve the study's required covariance structure.

```stata
estat endogenous
```

### IV overidentifying restrictions

**Null or question:** The tested instrument moment restrictions hold jointly under the maintained model and covariance assumptions.

**Larger value or rejection:** Some joint restrictions or maintained assumptions are incompatible with the data. The test does not identify which instrument is invalid.

**Smaller value or non-rejection:** Insufficient evidence against the restrictions, not proof that instruments satisfy exclusion or exogeneity.

**Assumptions:** There must be more excluded instruments than endogenous regressors. Conventional fits use Sargan; heteroskedasticity-robust fits use Wooldridge score, not Hansen J. Clustered overidentification is not implemented and is refused.

**Next step:** Use design knowledge to assess exclusion and sensitivity to instrument choices. Do not select instruments solely to obtain a non-significant test.

```stata
estat overid
```

## Documentation behind the guidance

- [Stata Hausman manual](https://www.stata.com/manuals/rhausman.pdf) and [Mundlak specification test](https://www.stata.com/new-in-stata/mundlak-specification-test/).
- [SciPy independent t-test](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html).
- [statsmodels Breusch-Pagan](https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.het_breuschpagan.html), [RESET](https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.linear_reset.html) and [ADF](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.adfuller.html).
- [linearmodels first-stage diagnostics](https://bashtage.github.io/linearmodels/iv/iv/linearmodels.iv.results.FirstStageResults.diagnostics.html).

Sources checked 5 October 2026. See the compatibility documentation for actual supported options. Synthetic random draws use NumPy, so a Stata seed with the same integer will not reproduce these datasets.

Release 0.6.0 adds lesson 26: Check what survives a file conversion. It uses a small Parquet round trip to teach labels, date units, missing values and interoperability limits.


Release 0.7.0 adds lessons 27–30: confidence intervals, survey subpopulations, hazard ratios and ordered-category probabilities. Each has runnable setup/solution, hints, reflection and a non-mutating result check.
