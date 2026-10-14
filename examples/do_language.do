clear all
set obs 10
local prefix "series"
forvalues j = 1/3 {
    generate `prefix'`j' = _n * `j'
}
foreach v of varlist series1-series3 {
    summarize `v', meanonly
    display r(mean)
}
generate valid = series1 < . & series1 > 3
count if valid
assert r(N) == 7
preserve
keep if valid
summarize
restore
