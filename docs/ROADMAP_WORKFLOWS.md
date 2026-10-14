# Using the new workflows

These commands run in Qt, the curses terminal and do-files through the same engine. Start with `examples/roadmap_workflows.do`, or open Learn for exercises 19 through 24. The examples below assume suitable named variables.

## Adjusted predictions and effects

```stata
regress score c.hours##i.group, vce(robust)
margins group, at(hours=(0 2 4))
marginsplot
margins, dydx(hours) over(group)
export results using "effects.csv", replace
```

`margins` uses the estimation sample, rebuilding interactions when raw predictors change. `at(hours=(0(1)4))` accepts a stepped grid; only one `at()` option, with up to 500 combinations, is supported. `over()` averages separately within observed groups. A factor in `dydx()` produces differences from its fitted reference level. Numeric variables, including numeric 0/1 variables fitted without `i.`, produce derivatives. This corrects the older numeric-binary backend shortcut.

Confidence intervals use the active model covariance, including supported robust or clustered covariance, with its t or normal reference distribution. The empirical covariates are treated as fixed. No weights, unconditional VCE, time operators, `post`, general contrast syntax, or individual prediction intervals are implemented. Nonlinear intervals are delta-method intervals and are not forced into [0,1]. `marginsplot` explicitly plots the last successful margins result, which can remain available after another command.

## Tables and exports

```stata
regress score hours
estimates store simple
regress score hours age, vce(robust)
estimates store adjusted
etable, estimates(simple adjusted) export("models.html", replace)
esttab simple adjusted using "models.csv", se replace
dtable score hours, by(group) export("summary.tex", replace)
```

Tables contain coefficients on the fitted scale, SEs, p-values, interval bounds and sample information. `logistic`'s comparison coefficients remain log odds, as the table title states. N and covariance must be considered when comparing models. The bounded `esttab` wrapper is not the full community estout package. Numeric `dtable` is available-case and unweighted; it does not yet tabulate categorical frequencies.

**Results > Copy latest table** copies a tab-separated table. **Export latest table** opens a file chooser for CSV, HTML or LaTeX. The reproducible command `export results using "file.csv"` is a StatBridge extension and also works in the terminal. Files are written atomically, and existing files require `replace`. An export failure does not corrupt the existing file. Spreadsheet applications may interpret CSV text according to their own import settings; Excel workbook exports deliberately retain strings literally.

## CRE and Mundlak

```stata
xtset id year
xtreg outcome x i.year, cre vce(cluster id)
estat mundlak
```

CRE adds separately identified panel means of expanded time-varying regressors. Time-invariant covariates remain in the original design; redundant means are not added. The current implementation requires balanced complete-case panels and a common time grid. It refuses an unbalanced analysis sample rather than approximating Stata's additional corrections.

`estat mundlak` also works after supported FE or RE fits, estimates the augmented model internally and leaves the active model unchanged. It uses a Wald chi-square on the added means. `vce(robust)` clusters by panel. The test remains asymptotic and unreliable with very few clusters. Rejection challenges the extra RE restrictions; non-rejection does not prove them. The Learn reference discusses why this is different from classical Hausman with clustered covariance.

## Instrumental variables

```stata
ivregress 2sls y control (x = instrument1 instrument2), vce(robust)
estat firststage
estat endogenous
estat overid
```

First-stage `f.dist` is authoritative: unadjusted covariance gives F inference; robust/clustered covariance gives Wald chi-square. The name `f.stat` alone is not a reason to apply an F > 10 cutoff. Exogeneity tests use conventional Wu-Hausman F or Wooldridge regression Wald with the selected robust/clustered covariance. All nominated endogenous regressors are tested jointly.

Overidentification requires more excluded instruments than endogenous regressors. Conventional fits use Sargan; heteroskedasticity-robust fits use Wooldridge's score test, not Hansen J. Clustered overidentification is refused. No weak-IV-robust intervals or Stock-Yogo critical values are supplied. Instrument validity still requires a substantive identification argument.

## Excel and dates

```stata
import excel "course.xlsx", sheet("Data") cellrange(A1:D500) firstrow clear
generate daydate = daily(raw_date, "DMY")
format daydate %td
generate monthdate = mofd(daydate)
format monthdate %tm
export excel using "clean.xlsx", firstrow(variables) sheet("Clean") replace
```

Use **File > Import Excel** for worksheet, range, header and all-string controls with a command preview. Only `.xlsx` is supported. Headers must be unique valid variable names; omit `firstrow` to use Excel column letters. Mixed-type columns become strings. Formula cells use cached values, possibly blank, and are not evaluated. Date-formatted cells are interpreted using the workbook's 1900/1904 system and converted to Stata numeric dates. `allstring` preserves the interpreted cell content as strings.

Export creates a workbook. `replace` replaces the entire workbook, not just a sheet. Strings beginning with `=` remain literal strings. Daily and clock values with `%td`/`%tc` export as Excel dates. Monthly and quarterly values remain numeric. No worksheet append/modify is implemented.

| Function | Meaning / accepted masks |
| --- | --- |
| `date(s,mask)`, `daily(s,mask)` | Daily date; `YMD`, `DMY`, `MDY` |
| `monthly(s,mask)` | Monthly date; `YM`, `MY` |
| `quarterly(s,mask)` | Quarterly date; `YQ`, `QY` |
| `clock(s,mask)` | Milliseconds; `YMDhms`, `DMYhms`, `MDYhms` |
| `mdy(m,d,y)`, `ym(y,m)`, `yq(y,q)` | Construct daily, monthly or quarterly values |
| `year(d)`, `month(d)`, `day(d)`, `dow(d)` | Extract from a daily date; Sunday = 0 |
| `dofm(m)`, `mofd(d)`, `dofq(q)`, `qofd(d)` | Convert between daily and monthly/quarterly units |
| `dofc(c)`, `cofd(d)` | Convert clock milliseconds and daily dates |

Masks require four-digit years, numeric or English month names, and the documented component order. Invalid dates become ordinary missing. Custom date pictures, locale parsing, two-digit-year rules and leap seconds are not implemented. `%td`, `%tm`, `%tq` and `%tc` are displayed in `list` and the Qt grid; editing uses the underlying numeric value. A format never converts the stored units.

## Graphs and absorbed models

```stata
twoway (scatter y x) (lfit y x), title("Outcome and fitted line")
reghdfe y x, absorb(id year) vce(cluster id year)
predict residual, residuals
rvfplot
qnorm residual
graph export "diagnostic.svg", replace
```

`twoway` supports parenthesised scatter, line and lfit layers, or `||` separators, with qualifiers per layer and `sort` for line layers. `lfit` is unweighted bivariate OLS. Q-Q plotting positions and the reference line use SciPy conventions.

Absorbed effects are categorical. Singleton observations are removed iteratively unless `keepsingletons` is requested. The intercept lies in the absorbed space and no normalisation-dependent constant is reported. One or two cluster dimensions are supported; two-way covariance uses inclusion-exclusion with backend corrections and t inference with the smaller cluster count minus one. Invalid covariance is refused. Corrections for absorbed df and effects nested in clusters are not claimed identical to reghdfe. Weights, heterogeneous slopes and IV absorption are not implemented. `predict, residuals` is available; other absorbed-model prediction types are refused.

## Two-period DiD

```stata
xtset id time
xtdidregress (y control) (treated), group(region) time(time)
```

For repeated cross-sections use `didregress`. There must be exactly two periods, no treatment in the first, and group-period treatment must be constant. All groups must be observed in both periods, with at least two treated and two control groups. Panel DiD additionally requires two observations per person and stable group membership. Outcomes and controls must be complete; prepare the analysis sample explicitly.

The additive model absorbs group or person effects and time effects and clusters by `group()`. Its treatment coefficient is a common conditional effect under parallel trends, no anticipation and no interference. With one pre-period it cannot test parallel trends. This is not a staggered-adoption or heterogeneous-treatment estimator and does not include an event-study command or wild-cluster bootstrap.
