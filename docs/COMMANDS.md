# Implemented command reference

Generated from the application catalogue for StatBridge Qt 0.7.1. Entries are syntax subsets, not claims of full Stata compatibility. StatBridge extensions are identified in their descriptions. Use `help command`, `coverage` and `compatibility` in the application.

## #delimit

```text
#delimit ; | #delimit cr
```

Backend: do-file interpreter.

Switch between semicolon and newline command delimiters.

## _pctile

```text
_pctile variable [, percentiles(25 50 75) altdef]
```

Backend: NumPy.

Unweighted percentile values in r(r1), r(r2), ...; nquantiles() is an alternative.

## about

```text
about
```

Backend: runtime metadata.

Application and backend versions.

## anova

```text
anova response factor1 [factor2] [factor1#factor2] [, partial|sequential]
```

Backend: statsmodels OLS / NumPy.

Unweighted one- or two-factor classical ANOVA, with optional two-way interaction (`a##b`). Partial drop-term or order-dependent sequential SS; see [ANOVA scope](ANOVA.md). Reference-coded partial main effects with interactions need not match Stata's default partial SS. No repeated measures or weights.

## append

```text
append using "data.dta"
```

Backend: pandas/ReadStat.

Append one local dataset; incompatible column types rejected.

## areg

```text
areg response predictors, absorb(group) [vce(robust) level(#)]
```

Backend: statsmodels OLS.

One integer absorbed factor via explicit indicators, normalised intercept and transformed covariance. Up to 500 groups/10 million design cells; use xtreg for large panels. No weights.

## arima

```text
arima y, arima(p,d,q) [noconstant]
```

Backend: statsmodels ARIMA.

Univariate nonseasonal ARIMA; likelihood/initialisation differences reported.

## assert

```text
assert exp [if exp] [in range]
```

Backend: expression interpreter.

Stop do-file on failed assertion.

## bootstrap

```text
bootstrap _b[x], reps(100) seed(42): regress y x
```

Backend: NumPy/model backend.

One coefficient, normal-based bootstrap SE/CI; no BCa.

## bsample

```text
bsample [#]
```

Backend: NumPy.

Sample with replacement; seed/draws differ from Stata.

## cd

```text
cd "folder"
```

Backend: pathlib.

Session working directory; cd .. goes up, cd ~ goes home, cd - returns to the previous folder.

## ci

```text
ci means|proportions varlist [if/in] [, level(#) exact wilson]
```

Backend: SciPy/statsmodels.

Variablewise Student-t mean intervals, exact Clopper-Pearson or Wilson binary proportion intervals.

## clear

```text
clear [all]
```

Backend: pandas.

Clear dataset, or all session estimation/macro state.

## clonevar

```text
clonevar new = old [if exp]
```

Backend: pandas.

Copy a variable with its label/value-label/format metadata; unselected observations become missing.

## codebook

```text
codebook [varlist]
```

Backend: pandas.

Missingness, distinct counts, examples.

## collapse

```text
collapse (mean) x (sum) y, by(group)
```

Backend: Polars/pandas.

mean sum count sd min max median first last.

## compare

```text
compare x y
```

Backend: pandas.

Counts of equal, different and missing observations.

## compatibility

```text
compatibility [export "report.json"]
```

Backend: audit ledger.

Known differences plus per-command backend/version history.

## contract

```text
contract varlist [, freq(name) percent(name) nomiss]
```

Backend: pandas.

Replace data with observed joint frequencies and optional percentages. Zero-frequency combinations are not generated.

## correlate

```text
correlate varlist [if exp]
```

Backend: pandas.

Listwise Pearson correlations.

## count

```text
count [if exp] [in range]
```

Backend: pandas.

Observation count in r(N).

## coverage

```text
coverage
```

Backend: StatBridge.

Audited workflow scope and remaining gaps. Command count is not usage coverage.

## decode

```text
decode code, generate(textvar)
```

Backend: pandas.

Decode existing value labels.

## describe

```text
describe [varlist]
```

Backend: pandas.

Types, labels, shape.

## destring

```text
destring varlist, replace [ignore(",")] [force]
```

Backend: pandas.

Explicit string to numeric conversion.

## dfuller

```text
dfuller var [, lags(#) trend noconstant]
```

Backend: statsmodels ADF.

Augmented Dickey-Fuller with fixed lags and MacKinnon p-values.

## didregress

```text
didregress (y [controls]) (treated), group(groupvar) time(timevar) [vce(cluster groupvar) level(#)]
```

Backend: AbsorbingLS.

Two-period repeated-cross-section additive DiD only; treatment starts in period 2; at least two treated and two control groups. Complete data, clustering by group. No staggered adoption.

## display

```text
display "text" | display exp
```

Backend: expression interpreter.

Evaluate expressions and stored r()/e() results, _b[name] and _se[name].

## do

```text
do "script.do"
```

Backend: do-file interpreter.

UTF-8/UTF-8-BOM local do-files; stop on first uncaptured error.

## drop

```text
drop varlist | drop if exp | drop in range
```

Backend: pandas.

Drop variables or observations.

## ds

```text
ds [varlist] [, has(type numeric|string) not]
```

Backend: pandas.

List selected variable names in r(varlist); optional numeric/string filter or complement.

## dtable

```text
dtable numeric_varlist [if ...] [in ...] [, by(group) export("file.csv|html|tex", replace)]
```

Backend: pandas.

Unweighted available-case N, mean, SD, minimum and maximum, optionally by group.

## dtabnk

```text
dtabnk "source.csv" ["second.xlsx"] [, merge on(Country Year) join(outer|inner|left) conflicts(suffix|error) layout(auto|wide|wide_header_series|long|year_rows) id(name) yearcol(name) valuecol(name) seriescol(name) sheet(name) headerrow(#) delimiter(text) long aggregate(error|mean) safe minfree(MB) lazy(MB) parquet(MB) preview rows(#) saving("file.dta|sav|parquet|RData") version(11..15) noload replace clear]
```

Backend: dtabnk / Polars.

World Bank annual panel conversion and validated multi-file merge. StatBridge extension. Preview preserves data; clear permits replacement. Explicit aggregation for duplicates. See docs/DTABNK.md.

## duplicates

```text
duplicates report|list|drop|tag [varlist] [, force generate(name)]
```

Backend: Polars/pandas.

Tag records the number of other rows with the same key; generate() is required for tag.

## egen

```text
egen new = function(varlist) [, by(group)]
```

Backend: Polars/pandas/NumPy.

mean/sum/total/sd/min/max/median/count/rowmean/rowtotal/group plus rowmiss/rownonmiss/rowmin/rowmax/rowsd/std/tag/rank/pctile/concat. See CORE_WORKFLOWS.md for function-specific options.

## else

```text
else { ... } | else if scalar_expression { ... }
```

Backend: do-file interpreter.

Alternative branch after a closing if brace.

## encode

```text
encode textvar, generate(code)
```

Backend: pandas.

Sorted string categories with value labels.

## ereturn

```text
ereturn list
```

Backend: result registry.

Show e() results.

## estat

```text
estat vif|hettest|ic|ovtest|influence [, top(#)]|mundlak|firststage|endogenous|overid
```

Backend: statsmodels / linearmodels.

OLS diagnostics, balanced-panel Mundlak, and IV first-stage/exogeneity/overidentification subsets. `estat influence [, top(10)]` reports conventional unweighted OLS Cook’s distance, leverage and internally studentised residuals, sorted by Cook’s distance. The `2k/N` and `4/N` flags are heuristics, not significance tests. Clustered IV overidentification is explicitly refused.

## estimates

```text
estimates store name | restore name | dir | table names
```

Backend: model registry.

Store and compare models in session.

## esttab

```text
esttab [names] [using "file.csv|html|tex"] [, se level(#) replace]
```

Backend: pandas / scipy.

Bounded community esttab-style wrapper. Full estout syntax is not implemented.

## etable

```text
etable [, estimates(names) level(#) export("file.csv|html|tex", replace)]
```

Backend: pandas / scipy.

Structured model comparison: coefficients, SEs, p-values, intervals, N and R-squared; bounded syntax.

## exit

```text
exit
```

Backend: do-file interpreter.

Stop current do-file; GUI stays open.

## expand

```text
expand expression [if exp] [, generate(new)]
```

Backend: NumPy/pandas.

Duplicate observations; nearest-integer counts, minimum one original row. Optional 0/1 copy indicator. Five-million-row allocation limit.

## export

```text
export stata|sav|por|xport|rdata|rds|parquet|feather|arrow|delimited|json|jsonl|ods|sqlite|mat|hdf5 [varlist] [if/in] using "file" [, replace compression(method) object(name) table(name) sheet(name) version(#)] | export excel [varlist] using "file.xlsx", firstrow(variables) | export results using "file.csv|html|tex"
```

Backend: ReadStat / Arrow / pandas / SciPy / h5py / pyreadr.

Atomic exports with format-specific options and loss notices. SAS7BDAT is import-only; use XPORT for SAS export. MAT/HDF5 support numeric vectors. Embedded labels/date formats survive StatBridge Arrow/Parquet/Feather round trips.

## fillin

```text
fillin varlist
```

Backend: pandas.

Add absent combinations of observed categories; _fillin marks additions. Original duplicates retained, two-million-combination cap.

## findfile

```text
findfile "filename-or-pattern" [, depth(4)]
```

Backend: pathlib.

Search working directory and subfolders, without following directory symlinks. Bounded to 20,000 scanned entries. StatBridge extension; not Stata ado-path search.

## foreach

```text
foreach x in a b c { ... }
```

Backend: do-file interpreter.

Block loops; of varlist and of numlist supported.

## format

```text
format varlist %9.2f
```

Backend: ReadStat metadata.

Preserve display format on export; grid uses general format.

## forvalues

```text
forvalues i = 1/10 { ... }
```

Backend: do-file interpreter.

Inclusive integer ranges and start(step)stop.

## generate

```text
generate [double|float|int|long|byte|str#] name = exp [if exp]
```

Backend: NumPy/pandas.

Vectorised safe expressions, including L/F/D/S time operators; numeric storage is float64.

## glm

```text
glm y x1 x2, family(gaussian) link(identity)
```

Backend: statsmodels GLM.

Gaussian, binomial, poisson, gamma; identity/log/logit/probit/inverse links.

## global

```text
global name "value"
```

Backend: macro interpreter.

Global macros expanded using $name or ${name}.

## graph

```text
graph box varlist [, over(group) title(text)] | graph bar [(mean|sum|count)] varlist [, over(group) title(text)] | graph export "plot.png", replace
```

Backend: matplotlib.

Boxplots and summary bars; one over() group. PNG/PDF/SVG export; quartile and order conventions may differ.

## gsort

```text
gsort [-]varlist
```

Backend: Polars/pandas.

Signed ascending/descending sort.

## hausman

```text
hausman fixed random
```

Backend: NumPy/SciPy.

Classical covariance-difference test; refuses robust and invalid covariance differences.

## help

```text
help [command]
```

Backend: command catalog.

Supported syntax and translation backend.

## histogram

```text
histogram x [, bin(#) frequency percent density title("text")]
```

Backend: matplotlib.

Histogram displayed in Graphs tab.

## if

```text
if scalar_expression { ... }
```

Backend: do-file interpreter.

Conditional blocks; else and else if supported. A variable expression uses its first observation with a notice.

## import

```text
import auto|stata|spss|sav|por|sas|xport|rdata|rds|parquet|feather|arrow|delimited|json|jsonl|workbook|sqlite|mat|hdf5|mtp [using] "file" [, clear preview rows(#) rename object(name) table(name) sheet(name) group(path) delimiter(text) encoding(text)] | import excel "file.xlsx" [, firstrow clear]
```

Backend: ReadStat / Arrow / pandas / SciPy / h5py / pyreadr.

Load directly into the workspace after validation; preview leaves data unchanged. Options depend on format. R support uses pyreadr. See docs/FILE_FORMATS.md for fidelity and supported variants.

## inspect

```text
inspect [varlist]
```

Backend: pandas.

Missingness, distinct counts and numeric sign counts.

## ipolate

```text
ipolate y x [if/in], generate(new) [epolate]
```

Backend: NumPy.

Linear interpolation, repeated x uses mean observed y; explicit extrapolation. Supports bysort grouping.

## isid

```text
isid varlist
```

Backend: pandas.

Assert unique nonmissing identifiers.

## ivregress

```text
ivregress 2sls y x (endogenous = instruments) [, vce(robust)]
```

Backend: linearmodels IV2SLS.

Instrumental variables, robust or clustered covariance.

## keep

```text
keep varlist | keep if exp | keep in range
```

Backend: pandas.

Keep variables or observations.

## kwallis

```text
kwallis outcome [if/in], by(group)
```

Backend: SciPy.

Tie-corrected Kruskal-Wallis H, asymptotic chi-square p-value.

## label

```text
label variable name "Label" | label define name 0 "No" 1 "Yes" | label values var name
```

Backend: ReadStat metadata.

Dataset, variable and named value labels.

## levelsof

```text
levelsof variable [, local(name) missing clean separate(text)]
```

Backend: pandas.

Sorted distinct values in r(levels) and optionally a local macro. Compound-quoted string levels are unsupported.

## lfit

```text
lfit y x [if ...] [in ...] [, title(text)]
```

Backend: NumPy / matplotlib.

Unweighted bivariate least-squares line.

## license

```text
license
```

Backend: StatBridge.

Display offline GNU GPL v3 or later, copyright and third-party notices. StatBridge extension.

## lincom

```text
lincom 2*x-z [, level(#) eform]
```

Backend: model covariance.

Linear coefficient combinations, constants, _b[] references and optional exponentiation.

## line

```text
line y x [, sort title("text")]
```

Backend: matplotlib.

Line plot.

## list

```text
list [varlist] [if exp] [in range]
```

Backend: pandas.

Display up to 500 rows.

## local

```text
local name "value" | local name = exp
```

Backend: macro interpreter.

Simple local macros expanded with backtick and apostrophe.

## log

```text
log using "session.log", text replace | log close
```

Backend: text log.

Plain UTF-8 text log, not SMCL.

## logistic

```text
logistic y x1 x2
```

Backend: statsmodels Logit.

Binary model, odds ratios and transformed confidence limits.

## logit

```text
logit y x1 x2 [, vce(robust)]
```

Backend: statsmodels Logit.

Binary maximum likelihood, coefficients.

## ls

```text
ls ["folder"|"*.do"] [, all]
```

Backend: pathlib.

List files/folders with sizes and dates. Also accepts -a, -l, -h; dir is an alias. At most 1,000 entries shown.

## margins

```text
margins [factor[#factor]] [, dydx(varlist|*) at(x=(values) ...) over(group) level(#)]
```

Backend: NumPy / scipy delta method.

OLS/logit/logistic/probit average predictions and effects, with factors/interactions. Unweighted estimation sample; numeric variables give derivatives, factors give base-level discrete changes.

## marginsplot

```text
marginsplot [, title(text)]
```

Backend: matplotlib.

Plot the last successful structured margins result with confidence intervals.

## mean

```text
mean varlist [if/in] [, over(group) level(#)]
```

Backend: NumPy/SciPy.

Unweighted complete-case means, joint IID covariance and t(N-1) intervals. Group df conventions may differ.

## merge

```text
merge 1:1|1:m|m:1 keys using "file.dta" [, keep(match master) assert(match) keepusing(vars) generate(name) nogen]
```

Backend: pandas/ReadStat.

Validated merge with status filtering, assertions and selected using columns. Master wins overlaps; failed assertions leave original data intact.

## misstable

```text
misstable summarize|patterns [varlist] [, all]
```

Backend: pandas.

Missing counts or patterns; numeric missing and empty strings are included. Display/r() are a documented subset.

## mkdir

```text
mkdir "folder" [, parents]
```

Backend: pathlib.

Create a directory; parents also creates missing parent folders.

## mlogit

```text
mlogit outcome predictors [if/in] [, baseoutcome(#) rrr level(#)]
```

Backend: statsmodels MNLogit.

Unweighted ML, model-based covariance. Most frequent base category; no margins or robust VCE.

## mvdecode

```text
mvdecode varlist, mv(-99 -98)
```

Backend: pandas.

Convert listed finite numeric codes to ordinary missing, with if/in support.

## mvencode

```text
mvencode varlist, mv(-99) [override]
```

Backend: pandas.

Convert ordinary numeric missing to one finite code; existing-code collision check unless override.

## nbreg

```text
nbreg y x1 x2 [, irr]
```

Backend: statsmodels NegativeBinomial.

NB2 likelihood; alpha parameterisation differs.

## newey

```text
newey y predictors [if/in], lag(#) [noconstant level(#)]
```

Backend: statsmodels HAC.

Bartlett HAC, N/(N-k) correction, t inference. Single regular complete time series only.

## ologit

```text
ologit outcome predictors [if/in] [, level(#)]
```

Backend: statsmodels OrderedModel.

Proportional-odds ML, latent-scale thresholds and transformed covariance; no robust VCE/margins.

## oneway

```text
oneway response group [, tabulate bonferroni|sidak|scheffe]
```

Backend: NumPy/SciPy.

Classical equal-variance ANOVA, with pooled-variance adjusted pairwise differences and simultaneous intervals for Bonferroni, Šidák, or Scheffé. One correction at a time. No Welch, paired/repeated designs, or weights; [details](ANOVA.md).

## oprobit

```text
oprobit outcome predictors [if/in] [, level(#)]
```

Backend: statsmodels OrderedModel.

Ordered probit ML, transformed latent thresholds, model-based covariance only.

## order

```text
order varlist
```

Backend: pandas.

Move variables to the beginning.

## pca

```text
pca varlist [, components(#) covariance]
```

Backend: NumPy SVD.

PCA eigenvalues/loadings; sign convention may differ. Scores are not generated.

## pctile

```text
pctile new = expression [, nquantiles(#) altdef genp(new)]
```

Backend: NumPy.

Store percentile cutpoints in the first rows; optional percentile levels in genp().

## poisson

```text
poisson y x1 x2 [, exposure(t) irr]
```

Backend: statsmodels Poisson.

Poisson counts; offset() or exposure().

## predict

```text
predict [double] new [if exp] [, xb residuals pr stdp stdf hat rstandard cooksd] | predict new, pr outcome(category) | predict new, hr
```

Backend: model backend.

Unweighted OLS supports out-of-sample xb/residuals/stdp, conventional stdf and in-sample influence diagnostics. Other estimators retain sample-only xb/residuals/pr where supported. Unknown factor levels fail. Categorical probabilities, Cox xb/hr and Newey/survey-linear xb/residuals use estimation sample only.

## preserve

```text
preserve
```

Backend: pandas.

Save an in-memory dataset snapshot.

## probit

```text
probit y x1 x2
```

Backend: statsmodels Probit.

Binary probit maximum likelihood.

## proportion

```text
proportion varlist [if/in] [, over(group) level(#)]
```

Backend: NumPy/SciPy.

Categorical proportions, joint covariance, symmetric t intervals. Use ci proportions for exact/Wilson binary intervals.

## prtest

```text
prtest binary = # | prtest binary, by(group) [level(#)]
```

Backend: statsmodels.

Independent asymptotic proportion z test; pooled null variance for two groups.

## pwmean

```text
pwmean response, over(group) [mcompare(tukey|bonferroni|sidak|scheffe) level(95)]
```

Backend: SciPy / pooled-variance OLS.

One response and one grouping variable, 2-100 groups. Returns unweighted means and adjusted pairwise tests/intervals, with Tukey-Kramer as the default. See [ANOVA details](ANOVA.md).

## pwcorr

```text
pwcorr varlist [, sig obs]
```

Backend: SciPy.

Pairwise Pearson correlations, p-values and counts.

## pwd

```text
pwd
```

Backend: pathlib.

Display session working directory.

## qnorm

```text
qnorm var [if ...] [in ...] [, title(text)]
```

Backend: scipy / matplotlib.

Normal Q-Q plot with SciPy plotting positions and fitted reference line, which differ from Stata.

## qreg

```text
qreg y x1 x2 [, quantile(.5)]
```

Backend: statsmodels QuantReg.

Quantile regression; kernel/bandwidth SE differences reported.

## ranksum

```text
ranksum x, by(group)
```

Backend: SciPy.

Two-sided Mann-Whitney; asymptotic tie/continuity conventions reported.

## recode

```text
recode varlist (1/3=1 "Low") (4/5=2 "High") [, generate(names) prefix(text) copyrest]
```

Backend: NumPy/pandas.

Ordered, first-match numeric/range/min/max/missing/nonmissing/else rules; optional quoted integer value labels on generated variables.

## reghdfe

```text
reghdfe y x [if ...] [, absorb(categorical_vars) vce(robust|cluster var1 [var2]) level(#) keepsingletons]
```

Backend: linearmodels AbsorbingLS.

Categorical absorption with iterative singleton removal and one/two-way clustering. Backend df/covariance corrections differ from community reghdfe; no weights or heterogeneous slopes.

## regress

```text
regress y x1 x2 i.group [if exp] [aw=w|fw=f|pw=w] [, vce(robust)]
```

Backend: statsmodels OLS/WLS.

OLS; HC1/HC2/HC3 and one-way clusters. AW/FW/PW weighted fits support classical/HC1/cluster covariance as appropriate; noconstant; level().

## rename

```text
rename old new
```

Backend: pandas.

Rename one variable.

## replace

```text
replace name = exp [if exp] [in range]
```

Backend: NumPy/pandas.

Replace selected observations.

## reshape

```text
reshape long stubnames, i(id) j(time)
```

Backend: pandas.

Long/wide with numeric suffixes.

## restore

```text
restore
```

Backend: pandas.

Restore last preserve, including dataset metadata.

## return

```text
return list
```

Backend: result registry.

Show r() results.

## run

```text
run "script.do"
```

Backend: do-file interpreter.

Run local do-file without command echo.

## rvfplot

```text
rvfplot [, title(text)]
```

Backend: matplotlib.

Stored estimation-sample residuals versus fitted values for linear models; read panel fitted-component notice.

## sample

```text
sample 10 [, count]
```

Backend: NumPy.

Sample without replacement; seed/draws differ from Stata.

## save

```text
save "data.dta", replace
```

Backend: ReadStat.

Writes Stata 15 format by default; version(13|14|15) supported.

## scalar

```text
scalar name = exp
```

Backend: expression interpreter.

Named scalar expressions.

## scatter

```text
scatter y x [, title("text")]
```

Backend: matplotlib.

Scatter plot.

## sdtest

```text
sdtest x = y | sdtest outcome, by(group) [level(#)]
```

Backend: SciPy.

Independent normal-population variance-ratio F test and SD-ratio interval; not paired or robust.

## set

```text
set obs 100 | set seed 42 | set databackend auto|polars|pandas
```

Backend: NumPy.

Observation count, PCG64 seed, confidence level; StatBridge data-backend selection.

## signrank

```text
signrank x = y
```

Backend: SciPy.

Two-sided Wilcoxon signed-rank.

## sort

```text
sort varlist
```

Backend: Polars/pandas.

Stable ascending sort, missing last.

## spearman

```text
spearman varlist [, pw stats(rho p obs)]
```

Backend: SciPy.

Listwise or pairwise rank correlations; average ties and asymptotic p-values, not exact small-sample inference.

## split

```text
split stringvar [, parse(",") generate(prefix) limit(#) destring]
```

Backend: pandas.

Split one string variable into numbered new columns; numeric conversion where possible.

## stcox

```text
stcox predictors [if/in] [, ties(breslow|efron) strata(group) nohr level(#)]
```

Backend: statsmodels PHReg.

Cox partial likelihood, model-based covariance, hazard ratios by default; no PH diagnostic or robust VCE.

## sts

```text
sts list|graph [, by(group)] | sts test group
```

Backend: statsmodels/matplotlib.

Kaplan-Meier, Greenwood SEs, log-rank test. No confidence bands or censor marks.

## stset

```text
stset duration, failure(binary_or_expression) [id(subject) scale(#)] | stset, clear
```

Backend: pandas.

Single-record right-censored origin-zero survival declaration. No delayed entry or time-varying records.

## stsum

```text
stsum [, by(group)]
```

Backend: statsmodels.

Counts, failures, risk-time and Kaplan-Meier median.

## summarize

```text
summarize [varlist] [if exp] [aw=weight|fw=count] [, detail]
```

Backend: NumPy/SciPy.

Type-2 percentiles and sample SD; analytic weights for basic summaries, frequency weights also for detail.

## svy

```text
svy [, subpop(indicator)]: mean|total|proportion|regress varlist [, level(#)]
```

Backend: NumPy/SciPy.

Taylor stratified-PSU covariance, PSU-minus-strata t df. Domains retain full design; no nonlinear survey estimators.

## svyset

```text
svyset [psu] [pw=weight] [, strata(group)] | svyset, clear
```

Backend: NumPy/pandas.

One-stage with-replacement design. No FPC, multistage, replicate weights or singleton adjustment.

## swilk

```text
swilk varlist
```

Backend: SciPy.

Shapiro-Wilk normality tests.

## tab1

```text
tab1 varlist [if/in] [, missing]
```

Backend: pandas.

Separate one-way frequency tables.

## tab2

```text
tab2 varlist [if/in] [, missing chi2 row col]
```

Backend: pandas/SciPy.

Pairwise two-way tables, at most 20 variables.

## tabstat

```text
tabstat varlist [, statistics(n mean sd min p25 median p75 max) by(group) missing columns(statistics|variables)]
```

Backend: NumPy/pandas.

Unweighted per-variable and grouped descriptive tables; default quantile convention. Returns N, not Stata's saved matrices.

## tabulate

```text
tabulate var [var2] [, missing chi2 row col]
```

Backend: pandas/SciPy.

One/two-way counts; Pearson chi-square without Yates correction.

## test

```text
test x z | test x=z | test (x=0) (z=1)
```

Backend: model covariance.

Joint linear Wald restrictions with fitted covariance and degrees of freedom; redundant restrictions fail explicitly.

## testparm

```text
testparm i.group x*
```

Backend: model covariance.

Joint zero restrictions for estimated coefficient names, wildcards and i./c. factor components; no equality option.

## tostring

```text
tostring varlist, generate(names)|replace [format(%12.6g) force]
```

Backend: pandas.

Numeric-to-string conversion, with a round-trip precision check unless force is specified.

## total

```text
total varlist [if/in] [, over(group) level(#)]
```

Backend: NumPy/SciPy.

Unweighted sample totals and joint IID covariance. Use svy for population-weighted totals.

## tsfill

```text
tsfill [, full]
```

Backend: pandas.

Fill declared time grid, with missing non-key values; full uses common panel range.

## tsset

```text
tsset timevar [, delta(number)]
```

Backend: pandas.

Declare a numeric unique time index and positive delta (default 1); operators respect gaps.

## ttest

```text
ttest x == 0 | ttest x == y | ttest x, by(group) [unequal]
```

Backend: SciPy.

One-sample, paired or independent t tests.

## twoway

```text
twoway (scatter y x) (lfit y x) [(line y x, sort)] [, title(text)]
```

Backend: matplotlib.

Layered scatter, line and fitted lines; qualifiers per layer. Most graph styling options are not implemented.

## use

```text
use "data.dta", clear
```

Backend: ReadStat.

Reads local .dta, preserving variable/value labels and numeric date values.

## version

```text
version number
```

Backend: interpreter.

Reports that Stata version-specific semantics are not emulated.

## xtdescribe

```text
xtdescribe
```

Backend: pandas.

Panel counts, min/mean/max observations per panel; no pattern diagrams.

## xtdidregress

```text
xtdidregress (y [controls]) (treated), group(groupvar) time(timevar) [level(#)]
```

Backend: AbsorbingLS.

Balanced two-period panel DiD after xtset id time. Stable group membership, common conditional effect and parallel-trends assumptions. No staggered adoption/event-study estimator.

## xtile

```text
xtile new = expression [, nquantiles(#) altdef cutpoints(var)]
```

Backend: NumPy.

Unweighted quantile categories. Boundary ties go in the lower category. Quantile options and cutpoints are mutually exclusive.

## xtreg

```text
xtreg y x [if ...] [, fe|re|cre vce(robust|cluster var) level(#)]
```

Backend: linearmodels.

FE/RE or balanced complete-case correlated RE with identified panel means. CRE supports only an intercept model; no weights.

## xtset

```text
xtset panelvar [timevar] [, delta(number)]
```

Backend: pandas.

Validate panel identity and optional unique panel-time pairs; declared delta governs time operators.

## xtsum

```text
xtsum [varlist] [if/in]
```

Backend: pandas.

Overall, between and within spread; between SD uses unweighted panel means.

