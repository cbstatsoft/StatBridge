# Common student workflows

Version 0.3.0 expands everyday cleaning, descriptive statistics and regression work. It adds 20 command entries, bringing the catalog to 114, and extends existing commands. This count includes interpreter constructs and utility commands; it is not a measurement of the proportion of Stata features or real-world use cases supported.

Run the self-contained synthetic example from the project directory:

```sh
python -m statbridge --batch examples/core_workflows.do
```

Or open it in the do-file editor and press Ctrl+D. It creates 240 observations and requires no downloads. Running it replaces the current in-memory dataset. Existing examples cover panel models, weighted regression, time operators and scripting; optional Learn lessons remain available.

## New command families

| Workflow | Added commands | Implemented scope |
| --- | --- | --- |
| Cleaning and conversion | `clonevar`, `recode`, `tostring`, `split`, `mvdecode`, `mvencode` | Copy metadata; ordered numeric recodes; checked numeric-to-string conversion; literal string splitting; ordinary missing-code conversions. |
| Inspecting variables and missing data | `ds`, `levelsof`, `misstable` | Numeric/string selection; unique levels and local macros; missing summaries and observed missing patterns. |
| Quantiles and summaries | `xtile`, `pctile`, `_pctile`, `tabstat` | Unweighted quantile groups/cutpoints; scalar percentiles; selected statistics, optionally by group. |
| Reshaping observation counts | `expand`, `contract` | Replicate rows; replace data with observed cell frequencies and optional percentages. |
| Models and inference | `oneway`, `anova`, `areg`, `testparm`, `spearman` | One-factor ANOVA; one absorbed categorical effect; coefficient-set tests; listwise or pairwise rank correlation. |

## Clean and describe

```stata
clonevar original_income = income
mvdecode income, mv(-99 -98)
recode age (min/29=1 "Under 30") (30/49=2 "30 to 49") (50/max=3 "50 plus"), gen(age_group)
misstable summarize income age
xtile income_quartile = income, nq(4)
tabstat income age, stat(n mean sd p25 median p75) by(region)
_pctile income, p(25 50 75)
display r(r2)
```

Recode rules are evaluated in order, with the first matching rule winning. Unmatched selected values are copied. With `generate()`, unselected observations are missing unless `copyrest` is supplied. Quoted value labels require new output variables and integer codes. Extended missing tags are unsupported.

`tostring x, generate(text)` rejects lossy conversion unless `force` is supplied. Its `format()` accepts a numeric f/g/e subset, not the complete Stata display-format language. `split contact, parse(",") generate(part)` creates part1, part2, etc. `destring` converts output columns where possible and leaves other columns as strings. Split delimiters are literal strings; default separators follow Python whitespace rules. Empty fields, Unicode rules and storage widths can differ from Stata.

`mvdecode` and `mvencode` ignore string variables. `mvencode x, mv(-99)` rejects an existing -99 unless `override` is supplied. Only ordinary missing is implemented. `misstable` treats both numeric missing and empty strings as missing and has a simpler output layout and returned-result set than Stata.

Quantiles use NumPy's averaged-inverted-CDF definition, with Weibull interpolation for `altdef`. `xtile` puts observations equal to a cutpoint in the lower category, keeping ties together. Weights are unsupported. `contract` includes observed cells only; `expand` is capped at five million output rows and can produce a different row ordering from Stata.

## Work with groups and variables

```stata
bysort id (year): generate wave = _n
duplicates tag id year, generate(duplicate)
egen observed = rownonmiss(income education)
egen unique_person = tag(id)
egen z_income = std(income)
egen income_rank = rank(income), by(region)
levelsof region, local(regions)
foreach r in `regions' {
    summarize income if region == `r'
}
ds, has(type numeric)
local numeric_vars `r(varlist)'
```

The added `egen` functions are `rowmiss`, `rownonmiss`, `rowmin`, `rowmax`, `rowsd`, `std`, `tag`, `rank`, `pctile` and `concat`. `group(), missing` is also available. `rank()` uses average ranks for ties. Only documented function-specific options are accepted. `levelsof` supports ordinary quoted strings; compound quoting is unsupported.

`by`/`bysort` now accepts parenthesised secondary sort keys. Supported grouped commands are summarize, count, tabulate, correlate, tabstat, generate, replace, egen, recode, xtile and clonevar. Their output and returned results are not the complete Stata by-prefix contract.

## Merge with checks

```stata
merge m:1 id using "lookup.dta", keepusing(region) assert(match master) keep(match) generate(link_status)
```

`keep()` and `assert()` accept `master`, `using`, `match` or 1, 2, 3. `assert()` checks the full merge before `keep()` filters it. A failed assertion leaves the in-memory dataset unchanged. `generate()` renames the merge indicator; `nogen` omits it. Cardinality is checked. Master values still win overlapping variables; `update` and `replace` are unsupported.

## Regression and postestimation

```stata
regress wage education age i.region if year < 2023
predict fitted, xb
predict mean_se, stdp
predict residual, resid
testparm i.region
test (education=.8) (age=.06)
lincom education + age, level(90)
estat ovtest
areg wage education age, absorb(region) vce(robust)
oneway wage region, tabulate
anova wage region
spearman wage education age, stats(rho p obs)
```

Unweighted OLS can now predict fitted values, residuals and mean standard errors for eligible observations outside the estimation sample. Factor bases are retained from estimation; new factor levels are rejected. `stdf`, `hat`/`leverage`, `rstandard` and `cooksd` require conventional covariance; influence diagnostics are in-sample only. Data changes that invalidate a model still prevent stale predictions. Weighted OLS and other estimators retain their documented sample-only prediction subset. This does not add time-series forecasting.

`test` supports multiple parenthesised linear equalities. `lincom` accepts constants, coefficient arithmetic and `_b[]` references; `eform` exponentiates the estimate and confidence interval. Nonlinear coefficient expressions and redundant test restrictions are rejected. `testparm` supports ordinary coefficient names, wildcards and implemented factor components, not the full factor-variable shorthand language.

`areg` implements one absorbed integer categorical variable using explicit dummy-variable OLS. The reported intercept is normalised using estimation-sample group shares. Model R-squared includes the absorbed effects. It supports conventional, robust and one-way cluster covariance through the OLS backend, but no weights, multiple absorbed effects or `noconstant`. It is capped at 500 groups and ten million design cells; use the panel implementation for larger supported panel workflows. Its `xb` omits individual absorbed effects; residuals include them.

`anova` is restricted to one categorical factor and stores the corresponding indicator OLS fit. `oneway` reports the classical between/within ANOVA table; Bartlett tests and post-hoc comparisons are absent. `estat ovtest` is conventional unweighted OLS Ramsey RESET using fitted-value powers 2, 3 and 4. `spearman` uses average ranks and SciPy asymptotic p-values; exact tests and some Stata small-sample conventions differ.

## Completion, performance and validation

Context completion includes new commands, live variable lists, string-only split inputs, `absorb()`/`cutpoints()` variables, model coefficients, merge outcomes and supported statistic names. Press Tab to extend a common prefix or accept the selected completion.

Existing Polars acceleration remains active for supported sorting, duplicate reporting/removal, collapse and grouped numeric egen. Most newly added data commands use pandas/NumPy; this release does not make every command Polars-native.

See COMMANDS.md for exact command help, COMPATIBILITY.md for the broader contract and VALIDATION.md for numerical and GUI checks. No Stata executable was available for direct parity testing. Unsupported syntax fails explicitly, and known implementation differences are shown with results and recorded in the compatibility audit.
