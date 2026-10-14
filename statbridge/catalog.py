# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Single command catalog shared by completion, help and documentation."""

COMMANDS = {
    "use": (
        'use "data.dta", clear',
        "ReadStat",
        "Reads local .dta, preserving variable/value labels and numeric date values.",
    ),
    "save": (
        'save "data.dta", replace',
        "ReadStat",
        "Writes Stata 15 format by default; version(13|14|15) supported.",
    ),
    "import": (
        'import delimited "data.csv", clear',
        "pandas",
        "CSV import; delimiter() and encoding().",
    ),
    "export": (
        'export delimited using "data.csv", replace',
        "pandas",
        "CSV export; delimiter().",
    ),
    "clear": (
        "clear [all]",
        "pandas",
        "Clear dataset, or all session estimation/macro state.",
    ),
    "set": (
        "set obs 100 | set seed 42 | set databackend auto|polars|pandas",
        "NumPy",
        "Observation count, PCG64 seed, confidence level; StatBridge data-backend selection.",
    ),
    "describe": ("describe [varlist]", "pandas", "Types, labels, shape."),
    "codebook": (
        "codebook [varlist]",
        "pandas",
        "Missingness, distinct counts, examples.",
    ),
    "list": ("list [varlist] [if exp] [in range]", "pandas", "Display up to 500 rows."),
    "count": ("count [if exp] [in range]", "pandas", "Observation count in r(N)."),
    "summarize": (
        "summarize [varlist] [if exp] [aw=weight|fw=count] [, detail]",
        "NumPy/SciPy",
        "Type-2 percentiles and sample SD; analytic weights for basic summaries, frequency weights also for detail.",
    ),
    "generate": (
        "generate [double|float|int|long|byte|str#] name = exp [if exp]",
        "NumPy/pandas",
        "Vectorised safe expressions, including L/F/D/S time operators; numeric storage is float64.",
    ),
    "replace": (
        "replace name = exp [if exp] [in range]",
        "NumPy/pandas",
        "Replace selected observations.",
    ),
    "egen": (
        "egen name = mean(x), by(group)",
        "Polars/pandas",
        "mean sum total sd min max median count rowmean rowtotal group.",
    ),
    "drop": (
        "drop varlist | drop if exp | drop in range",
        "pandas",
        "Drop variables or observations.",
    ),
    "keep": (
        "keep varlist | keep if exp | keep in range",
        "pandas",
        "Keep variables or observations.",
    ),
    "rename": ("rename old new", "pandas", "Rename one variable."),
    "order": ("order varlist", "pandas", "Move variables to the beginning."),
    "sort": ("sort varlist", "Polars/pandas", "Stable ascending sort, missing last."),
    "gsort": ("gsort [-]varlist", "Polars/pandas", "Signed ascending/descending sort."),
    "duplicates": (
        "duplicates report|list|drop [varlist] [, force]",
        "Polars/pandas",
        "Report, list, or remove repeated rows.",
    ),
    "isid": ("isid varlist", "pandas", "Assert unique nonmissing identifiers."),
    "assert": (
        "assert exp [if exp] [in range]",
        "expression interpreter",
        "Stop do-file on failed assertion.",
    ),
    "preserve": ("preserve", "pandas", "Save an in-memory dataset snapshot."),
    "restore": (
        "restore",
        "pandas",
        "Restore last preserve, including dataset metadata.",
    ),
    "append": (
        'append using "data.dta"',
        "pandas/ReadStat",
        "Append one local dataset; incompatible column types rejected.",
    ),
    "merge": (
        'merge 1:1|1:m|m:1 keys using "data.dta" [, nogen]',
        "pandas/ReadStat",
        "Validated merge with _merge codes; master wins overlapping values.",
    ),
    "collapse": (
        "collapse (mean) x (sum) y, by(group)",
        "Polars/pandas",
        "mean sum count sd min max median first last.",
    ),
    "reshape": (
        "reshape long stubnames, i(id) j(time)",
        "pandas",
        "Long/wide with numeric suffixes.",
    ),
    "encode": (
        "encode textvar, generate(code)",
        "pandas",
        "Sorted string categories with value labels.",
    ),
    "decode": (
        "decode code, generate(textvar)",
        "pandas",
        "Decode existing value labels.",
    ),
    "destring": (
        'destring varlist, replace [ignore(",")] [force]',
        "pandas",
        "Explicit string to numeric conversion.",
    ),
    "label": (
        'label variable name "Label" | label define name 0 "No" 1 "Yes" | label values var name',
        "ReadStat metadata",
        "Dataset, variable and named value labels.",
    ),
    "format": (
        "format varlist %9.2f",
        "ReadStat metadata",
        "Preserve display format on export; grid uses general format.",
    ),
    "correlate": (
        "correlate varlist [if exp]",
        "pandas",
        "Listwise Pearson correlations.",
    ),
    "pwcorr": (
        "pwcorr varlist [, sig obs]",
        "SciPy",
        "Pairwise Pearson correlations, p-values and counts.",
    ),
    "tabulate": (
        "tabulate var [var2] [, missing chi2 row col]",
        "pandas/SciPy",
        "One/two-way counts; Pearson chi-square without Yates correction.",
    ),
    "ttest": (
        "ttest x == 0 | ttest x == y | ttest x, by(group) [unequal]",
        "SciPy",
        "One-sample, paired or independent t tests.",
    ),
    "ranksum": (
        "ranksum x, by(group)",
        "SciPy",
        "Two-sided Mann-Whitney; asymptotic tie/continuity conventions reported.",
    ),
    "signrank": ("signrank x = y", "SciPy", "Two-sided Wilcoxon signed-rank."),
    "swilk": ("swilk varlist", "SciPy", "Shapiro-Wilk normality tests."),
    "regress": (
        "regress y x1 x2 i.group [if exp] [aw=w|fw=f|pw=w] [, vce(robust)]",
        "statsmodels OLS/WLS",
        "OLS; HC1/HC2/HC3 and one-way clusters. AW/FW/PW weighted fits support classical/HC1/cluster covariance as appropriate; noconstant; level().",
    ),
    "logit": (
        "logit y x1 x2 [, vce(robust)]",
        "statsmodels Logit",
        "Binary maximum likelihood, coefficients.",
    ),
    "logistic": (
        "logistic y x1 x2",
        "statsmodels Logit",
        "Binary model, odds ratios and transformed confidence limits.",
    ),
    "probit": (
        "probit y x1 x2",
        "statsmodels Probit",
        "Binary probit maximum likelihood.",
    ),
    "poisson": (
        "poisson y x1 x2 [, exposure(t) irr]",
        "statsmodels Poisson",
        "Poisson counts; offset() or exposure().",
    ),
    "nbreg": (
        "nbreg y x1 x2 [, irr]",
        "statsmodels NegativeBinomial",
        "NB2 likelihood; alpha parameterisation differs.",
    ),
    "qreg": (
        "qreg y x1 x2 [, quantile(.5)]",
        "statsmodels QuantReg",
        "Quantile regression; kernel/bandwidth SE differences reported.",
    ),
    "glm": (
        "glm y x1 x2, family(gaussian) link(identity)",
        "statsmodels GLM",
        "Gaussian, binomial, poisson, gamma; identity/log/logit/probit/inverse links.",
    ),
    "ivregress": (
        "ivregress 2sls y x (endogenous = instruments) [, vce(robust)]",
        "linearmodels IV2SLS",
        "Instrumental variables, robust or clustered covariance.",
    ),
    "tsset": (
        "tsset timevar [, delta(number)]",
        "pandas",
        "Declare a numeric unique time index and positive delta (default 1); operators respect gaps.",
    ),
    "version": (
        "version number",
        "interpreter",
        "Reports that Stata version-specific semantics are not emulated.",
    ),
    "xtset": (
        "xtset panelvar [timevar] [, delta(number)]",
        "pandas",
        "Validate panel identity and optional unique panel-time pairs; declared delta governs time operators.",
    ),
    "xtreg": (
        "xtreg y x i.year, fe|re [vce(cluster id)]",
        "linearmodels",
        "Fixed/random effects; covariance and R² differences reported.",
    ),
    "estimates": (
        "estimates store name | restore name | dir | table names",
        "model registry",
        "Store and compare models in session.",
    ),
    "hausman": (
        "hausman fixed random",
        "NumPy/SciPy",
        "Classical covariance-difference test; refuses robust and invalid covariance differences.",
    ),
    "predict": (
        "predict name [, xb residuals pr]",
        "model backend",
        "Estimation-sample predictions only, reported explicitly.",
    ),
    "estat": (
        "estat vif | hettest | ic",
        "statsmodels",
        "OLS VIF and Breusch-Pagan; AIC/BIC where available.",
    ),
    "test": (
        "test x1 x2",
        "NumPy/SciPy",
        "Joint zero-coefficient Wald test using fitted covariance.",
    ),
    "lincom": (
        "lincom x1 - x2",
        "model covariance",
        "Linear coefficient combination with fitted-model inference.",
    ),
    "margins": (
        "margins, dydx(*)",
        "statsmodels",
        "Logit/probit average marginal effects; binary/dummy handling reported.",
    ),
    "pca": (
        "pca varlist [, components(#) covariance]",
        "NumPy SVD",
        "PCA eigenvalues/loadings; sign convention may differ. Scores are not generated.",
    ),
    "dfuller": (
        "dfuller var [, lags(#) trend noconstant]",
        "statsmodels ADF",
        "Augmented Dickey-Fuller with fixed lags and MacKinnon p-values.",
    ),
    "arima": (
        "arima y, arima(p,d,q) [noconstant]",
        "statsmodels ARIMA",
        "Univariate nonseasonal ARIMA; likelihood/initialisation differences reported.",
    ),
    "histogram": (
        'histogram x [, bin(#) frequency percent density title("text")]',
        "matplotlib",
        "Histogram displayed in Graphs tab.",
    ),
    "scatter": ('scatter y x [, title("text")]', "matplotlib", "Scatter plot."),
    "line": ('line y x [, sort title("text")]', "matplotlib", "Line plot."),
    "graph": ('graph export "plot.png", replace', "matplotlib", "PNG/PDF/SVG export."),
    "sample": (
        "sample 10 [, count]",
        "NumPy",
        "Sample without replacement; seed/draws differ from Stata.",
    ),
    "bsample": (
        "bsample [#]",
        "NumPy",
        "Sample with replacement; seed/draws differ from Stata.",
    ),
    "bootstrap": (
        "bootstrap _b[x], reps(100) seed(42): regress y x",
        "NumPy/model backend",
        "One coefficient, normal-based bootstrap SE/CI; no BCa.",
    ),
    "local": (
        'local name "value" | local name = exp',
        "macro interpreter",
        "Simple local macros expanded with backtick and apostrophe.",
    ),
    "global": (
        'global name "value"',
        "macro interpreter",
        "Global macros expanded using $name or ${name}.",
    ),
    "scalar": (
        "scalar name = exp",
        "expression interpreter",
        "Named scalar expressions.",
    ),
    "display": (
        'display "text" | display exp',
        "expression interpreter",
        "Evaluate expressions and stored r()/e() results, _b[name] and _se[name].",
    ),
    "return": ("return list", "result registry", "Show r() results."),
    "ereturn": ("ereturn list", "result registry", "Show e() results."),
    "if": (
        "if scalar_expression { ... }",
        "do-file interpreter",
        "Conditional blocks; else and else if supported. A variable expression uses its first observation with a notice.",
    ),
    "else": (
        "else { ... } | else if scalar_expression { ... }",
        "do-file interpreter",
        "Alternative branch after a closing if brace.",
    ),
    "#delimit": (
        "#delimit ; | #delimit cr",
        "do-file interpreter",
        "Switch between semicolon and newline command delimiters.",
    ),
    "foreach": (
        "foreach x in a b c { ... }",
        "do-file interpreter",
        "Block loops; of varlist and of numlist supported.",
    ),
    "forvalues": (
        "forvalues i = 1/10 { ... }",
        "do-file interpreter",
        "Inclusive integer ranges and start(step)stop.",
    ),
    "do": (
        'do "script.do"',
        "do-file interpreter",
        "UTF-8/UTF-8-BOM local do-files; stop on first uncaptured error.",
    ),
    "run": (
        'run "script.do"',
        "do-file interpreter",
        "Run local do-file without command echo.",
    ),
    "log": (
        'log using "session.log", text replace | log close',
        "text log",
        "Plain UTF-8 text log, not SMCL.",
    ),
    "cd": (
        'cd "folder"',
        "pathlib",
        "Session working directory; cd .. goes up, cd ~ goes home, cd - returns to the previous folder.",
    ),
    "ls": (
        'ls ["folder"|"*.do"] [, all]',
        "pathlib",
        "List files/folders with sizes and dates. Also accepts -a, -l, -h; dir is an alias. At most 1,000 entries shown.",
    ),
    "findfile": (
        'findfile "filename-or-pattern" [, depth(4)]',
        "pathlib",
        "Search working directory and subfolders, without following directory symlinks. Bounded to 20,000 scanned entries. StatBridge extension; not Stata ado-path search.",
    ),
    "mkdir": (
        'mkdir "folder" [, parents]',
        "pathlib",
        "Create a directory; parents also creates missing parent folders.",
    ),
    "pwd": ("pwd", "pathlib", "Display session working directory."),
    "help": (
        "help [command]",
        "command catalog",
        "Supported syntax and translation backend.",
    ),
    "about": ("about", "runtime metadata", "Application and backend versions."),
    "compatibility": (
        'compatibility [export "report.json"]',
        "audit ledger",
        "Known differences plus per-command backend/version history.",
    ),
    "exit": ("exit", "do-file interpreter", "Stop current do-file; GUI stays open."),
}
ALIASES = {
    "dir": "ls",
    "chdir": "cd",
    "su": "summarize",
    "sum": "summarize",
    "summ": "summarize",
    "gen": "generate",
    "g": "generate",
    "repl": "replace",
    "reg": "regress",
    "regress": "regress",
    "des": "describe",
    "desc": "describe",
    "tab": "tabulate",
    "ta": "tabulate",
    "corr": "correlate",
    "di": "display",
    "disp": "display",
    "qui": "quietly",
    "cap": "capture",
    "est": "estimates",
    "hist": "histogram",
}

COMMANDS.update(
    {
        "clonevar": (
            "clonevar new = old [if exp]",
            "pandas",
            "Copy a variable with its label/value-label/format metadata; unselected observations become missing.",
        ),
        "recode": (
            'recode varlist (1/3=1 "Low") (4/5=2 "High") [, generate(names) prefix(text) copyrest]',
            "NumPy/pandas",
            "Ordered, first-match numeric/range/min/max/missing/nonmissing/else rules; optional quoted integer value labels on generated variables.",
        ),
        "tostring": (
            "tostring varlist, generate(names)|replace [format(%12.6g) force]",
            "pandas",
            "Numeric-to-string conversion, with a round-trip precision check unless force is specified.",
        ),
        "split": (
            'split stringvar [, parse(",") generate(prefix) limit(#) destring]',
            "pandas",
            "Split one string variable into numbered new columns; numeric conversion where possible.",
        ),
        "mvdecode": (
            "mvdecode varlist, mv(-99 -98)",
            "pandas",
            "Convert listed finite numeric codes to ordinary missing, with if/in support.",
        ),
        "mvencode": (
            "mvencode varlist, mv(-99) [override]",
            "pandas",
            "Convert ordinary numeric missing to one finite code; existing-code collision check unless override.",
        ),
        "misstable": (
            "misstable summarize|patterns [varlist] [, all]",
            "pandas",
            "Missing counts or patterns; numeric missing and empty strings are included. Display/r() are a documented subset.",
        ),
        "ds": (
            "ds [varlist] [, has(type numeric|string) not]",
            "pandas",
            "List selected variable names in r(varlist); optional numeric/string filter or complement.",
        ),
        "levelsof": (
            "levelsof variable [, local(name) missing clean separate(text)]",
            "pandas",
            "Sorted distinct values in r(levels) and optionally a local macro. Compound-quoted string levels are unsupported.",
        ),
        "xtile": (
            "xtile new = expression [, nquantiles(#) altdef cutpoints(var)]",
            "NumPy",
            "Unweighted quantile categories. Boundary ties go in the lower category. Quantile options and cutpoints are mutually exclusive.",
        ),
        "pctile": (
            "pctile new = expression [, nquantiles(#) altdef genp(new)]",
            "NumPy",
            "Store percentile cutpoints in the first rows; optional percentile levels in genp().",
        ),
        "_pctile": (
            "_pctile variable [, percentiles(25 50 75) altdef]",
            "NumPy",
            "Unweighted percentile values in r(r1), r(r2), ...; nquantiles() is an alternative.",
        ),
        "expand": (
            "expand expression [if exp] [, generate(new)]",
            "NumPy/pandas",
            "Duplicate observations; nearest-integer counts, minimum one original row. Optional 0/1 copy indicator. Five-million-row allocation limit.",
        ),
        "contract": (
            "contract varlist [, freq(name) percent(name) nomiss]",
            "pandas",
            "Replace data with observed joint frequencies and optional percentages. Zero-frequency combinations are not generated.",
        ),
        "tabstat": (
            "tabstat varlist [, statistics(n mean sd min p25 median p75 max) by(group) missing columns(statistics|variables)]",
            "NumPy/pandas",
            "Unweighted per-variable and grouped descriptive tables; default quantile convention. Returns N, not Stata's saved matrices.",
        ),
        "oneway": (
            "oneway response group [, tabulate bonferroni|sidak|scheffe]",
            "NumPy/SciPy",
            "Classical equal-variance one-way ANOVA, optionally group summaries and pooled-variance Bonferroni, Sidak or Scheffe post-hoc comparisons; no Bartlett/Welch or repeated measures.",
        ),
        "anova": (
            "anova response factor1 [factor2] [factor1#factor2] [, partial|sequential]",
            "statsmodels OLS / NumPy",
            "One/two categorical factors with optional two-way interaction; partial drop-term or ordered sequential SS. Reference-coded partial main effects with interaction may differ from Stata. No repeated measures/weights.",
        ),
        "areg": (
            "areg response predictors, absorb(group) [vce(robust) level(#)]",
            "statsmodels OLS",
            "One integer absorbed factor via explicit indicators, normalised intercept and transformed covariance. Up to 500 groups/10 million design cells; use xtreg for large panels. No weights.",
        ),
        "testparm": (
            "testparm i.group x*",
            "model covariance",
            "Joint zero restrictions for estimated coefficient names, wildcards and i./c. factor components; no equality option.",
        ),
        "spearman": (
            "spearman varlist [, pw stats(rho p obs)]",
            "SciPy",
            "Listwise or pairwise rank correlations; average ties and asymptotic p-values, not exact small-sample inference.",
        ),
    }
)
COMMANDS["egen"] = (
    "egen new = function(varlist) [, by(group)]",
    "Polars/pandas/NumPy",
    "mean/sum/total/sd/min/max/median/count/rowmean/rowtotal/group plus rowmiss/rownonmiss/rowmin/rowmax/rowsd/std/tag/rank/pctile/concat. See CORE_WORKFLOWS.md for function-specific options.",
)
COMMANDS["merge"] = (
    'merge 1:1|1:m|m:1 keys using "file.dta" [, keep(match master) assert(match) keepusing(vars) generate(name) nogen]',
    "pandas/ReadStat",
    "Validated merge with status filtering, assertions and selected using columns. Master wins overlaps; failed assertions leave original data intact.",
)
COMMANDS["duplicates"] = (
    "duplicates report|list|drop|tag [varlist] [, force generate(name)]",
    "Polars/pandas",
    "Tag records the number of other rows with the same key; generate() is required for tag.",
)
COMMANDS["test"] = (
    "test x z | test x=z | test (x=0) (z=1)",
    "model covariance",
    "Joint linear Wald restrictions with fitted covariance and degrees of freedom; redundant restrictions fail explicitly.",
)
COMMANDS["lincom"] = (
    "lincom 2*x-z [, level(#) eform]",
    "model covariance",
    "Linear coefficient combinations, constants, _b[] references and optional exponentiation.",
)
ALIASES.update({"lev": "levelsof", "bys": "bysort"})

COMMANDS["predict"] = (
    "predict [double] new [if exp] [, xb residuals pr stdp stdf hat rstandard cooksd]",
    "model backend",
    "Unweighted OLS supports out-of-sample xb/residuals/stdp, conventional stdf and in-sample influence diagnostics. Other estimators retain sample-only xb/residuals/pr where supported. Unknown factor levels fail.",
)
COMMANDS["estat"] = (
    "estat vif | hettest | ic | ovtest",
    "statsmodels",
    "OLS VIF/Breusch-Pagan and conventional-OLS Ramsey RESET; AIC/BIC where available.",
)

COMMANDS.update({
    'margins': ('margins [factor[#factor]] [, dydx(varlist|*) at(x=(values) ...) over(group) level(#)]', 'NumPy / scipy delta method', 'OLS/logit/logistic/probit average predictions and effects, with factors/interactions. Unweighted estimation sample; numeric variables give derivatives, factors give base-level discrete changes.'),
    'marginsplot': ('marginsplot [, title(text)]', 'matplotlib', 'Plot the last successful structured margins result with confidence intervals.'),
    'etable': ('etable [, estimates(names) level(#) export("file.csv|html|tex", replace)]', 'pandas / scipy', 'Structured model comparison: coefficients, SEs, p-values, intervals, N and R-squared; bounded syntax.'),
    'esttab': ('esttab [names] [using "file.csv|html|tex"] [, se level(#) replace]', 'pandas / scipy', 'Bounded community esttab-style wrapper. Full estout syntax is not implemented.'),
    'dtable': ('dtable numeric_varlist [if ...] [in ...] [, by(group) export("file.csv|html|tex", replace)]', 'pandas', 'Unweighted available-case N, mean, SD, minimum and maximum, optionally by group.'),
    'xtreg': ('xtreg y x [if ...] [, fe|re|cre vce(robust|cluster var) level(#)]', 'linearmodels', 'FE/RE or balanced complete-case correlated RE with identified panel means. CRE supports only an intercept model; no weights.'),
    'estat': ('estat vif|hettest|ic|ovtest|mundlak|firststage|endogenous|overid', 'statsmodels / linearmodels', 'OLS diagnostics, balanced-panel Mundlak, and IV first-stage/exogeneity/overidentification subsets. Clustered IV overidentification is explicitly refused.'),
    'reghdfe': ('reghdfe y x [if ...] [, absorb(categorical_vars) vce(robust|cluster var1 [var2]) level(#) keepsingletons]', 'linearmodels AbsorbingLS', 'Categorical absorption with iterative singleton removal and one/two-way clustering. Backend df/covariance corrections differ from community reghdfe; no weights or heterogeneous slopes.'),
    'didregress': ('didregress (y [controls]) (treated), group(groupvar) time(timevar) [vce(cluster groupvar) level(#)]', 'AbsorbingLS', 'Two-period repeated-cross-section additive DiD only; treatment starts in period 2; at least two treated and two control groups. Complete data, clustering by group. No staggered adoption.'),
    'xtdidregress': ('xtdidregress (y [controls]) (treated), group(groupvar) time(timevar) [level(#)]', 'AbsorbingLS', 'Balanced two-period panel DiD after xtset id time. Stable group membership, common conditional effect and parallel-trends assumptions. No staggered adoption/event-study estimator.'),
    'lfit': ('lfit y x [if ...] [in ...] [, title(text)]', 'NumPy / matplotlib', 'Unweighted bivariate least-squares line.'),
    'twoway': ('twoway (scatter y x) (lfit y x) [(line y x, sort)] [, title(text)]', 'matplotlib', 'Layered scatter, line and fitted lines; qualifiers per layer. Most graph styling options are not implemented.'),
    'rvfplot': ('rvfplot [, title(text)]', 'matplotlib', 'Stored estimation-sample residuals versus fitted values for linear models; read panel fitted-component notice.'),
    'qnorm': ('qnorm var [if ...] [in ...] [, title(text)]', 'scipy / matplotlib', 'Normal Q-Q plot with SciPy plotting positions and fitted reference line, which differ from Stata.'),
    'import': ('import delimited "file.csv" [, clear delimiter(text) encoding(text)] | import excel "file.xlsx" [, sheet(name) cellrange(A1:D20) firstrow allstring clear]', 'pandas / openpyxl', 'CSV or .xlsx import. Excel headers must be unique valid names. Cached formula values only; date cells become Stata numeric dates; mixed columns become strings.'),
    'export': ('export delimited using "file.csv" [, replace] | export excel [varlist] using "file.xlsx" [, firstrow(variables) sheet(name) cell(B2) replace]', 'pandas / openpyxl', 'Whole-workbook .xlsx export with literal strings; replace replaces the whole file. No sheet append/modify. Daily/clock formats export as Excel dates.'),
})

COMMANDS['export'] = (COMMANDS['export'][0] + ' | export results using "file.csv|html|tex" [, replace]', COMMANDS['export'][1], COMMANDS['export'][2] + ' StatBridge extension: export results writes the latest structured table.')

COMMANDS['dtabnk'] = ('dtabnk "source.csv" ["second.xlsx"] [, merge on(Country Year) join(outer|inner|left) conflicts(suffix|error) layout(auto|wide|wide_header_series|long|year_rows) id(name) yearcol(name) valuecol(name) seriescol(name) sheet(name) headerrow(#) delimiter(text) long aggregate(error|mean) safe minfree(MB) lazy(MB) parquet(MB) preview rows(#) saving("file.dta|sav|parquet|RData") version(11..15) noload replace clear]', 'dtabnk / Polars', 'World Bank annual panel conversion and validated multi-file merge. StatBridge extension. Preview preserves data; clear permits replacement. Explicit aggregation for duplicates. See docs/DTABNK.md.')
COMMANDS['export'] = (COMMANDS['export'][0] + ' | export sav|parquet|rdata using "file" [, replace]', COMMANDS['export'][1] + ' / pyreadstat / Polars', COMMANDS['export'][2] + ' Additional formats export data and supported variable labels, not all Stata metadata. RData requires the optional rdata extra.')

COMMANDS['import'] = ('import auto|stata|spss|sav|por|sas|xport|rdata|rds|parquet|feather|arrow|delimited|json|jsonl|workbook|sqlite|mat|hdf5|mtp [using] "file" [, clear preview rows(#) rename object(name) table(name) sheet(name) group(path) delimiter(text) encoding(text)] | import excel "file.xlsx" [, firstrow clear]', 'ReadStat / Arrow / pandas / SciPy / h5py / pyreadr', 'Load directly into the workspace after validation; preview leaves data unchanged. Options depend on format. R support uses pyreadr. See docs/FILE_FORMATS.md for fidelity and supported variants.')
COMMANDS['export'] = ('export stata|sav|por|xport|rdata|rds|parquet|feather|arrow|delimited|json|jsonl|ods|sqlite|mat|hdf5 [varlist] [if/in] using "file" [, replace compression(method) object(name) table(name) sheet(name) version(#)] | export excel [varlist] using "file.xlsx", firstrow(variables) | export results using "file.csv|html|tex"', 'ReadStat / Arrow / pandas / SciPy / h5py / pyreadr', 'Atomic exports with format-specific options and loss notices. SAS7BDAT is import-only; use XPORT for SAS export. MAT/HDF5 support numeric vectors. Embedded labels/date formats survive StatBridge Arrow/Parquet/Feather round trips.')

from .coverage import NEW_COMMANDS
COMMANDS.update(NEW_COMMANDS)
COMMANDS['graph']=('graph box varlist [, over(group) title(text)] | graph bar [(mean|sum|count)] varlist [, over(group) title(text)] | graph export "plot.png", replace','matplotlib','Boxplots and summary bars; one over() group. PNG/PDF/SVG export; quartile and order conventions may differ.')
COMMANDS['predict']=(COMMANDS['predict'][0]+' | predict new, pr outcome(category) | predict new, hr',COMMANDS['predict'][1],COMMANDS['predict'][2]+' Categorical probabilities, Cox xb/hr and Newey/survey-linear xb/residuals use estimation sample only.')

COMMANDS["license"] = ("license", "StatBridge", "Display offline GNU GPL v3 or later, copyright and third-party notices. StatBridge extension.")
