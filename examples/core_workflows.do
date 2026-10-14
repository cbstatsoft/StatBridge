* StatBridge: common student workflows. Entirely synthetic, no downloads.
clear all
set seed 2031
set obs 240
generate id = ceil(_n/6)
generate year = 2018 + mod(_n-1,6)
generate region = mod(id,4)
generate age = 18 + mod(_n,45)
generate education = 8 + mod(_n,12)
generate training = mod(_n,2)
generate wage = 5 + .8*education + .06*age + .5*region + rnormal(0,2)
generate survey_code = cond(mod(_n,25)==0,-99,wage)
clonevar original_code = survey_code
mvdecode survey_code, mv(-99)
misstable summarize wage survey_code
recode age (min/29=1 "Under 30") (30/49=2 "30 to 49") (50/max=3 "50 plus"), gen(age_group)
xtile wage_quartile = wage, nq(4)
egen observed = rownonmiss(wage survey_code)
egen first_person = tag(id)
egen standard_wage = std(wage)
egen regional_mean = mean(wage), by(region)
bysort id (year): generate wave = _n
assert wave >= 1 & wave <= 6
duplicates tag id year, generate(duplicate)
assert duplicate == 0
levelsof region, local(regions)
foreach r in `regions' {
    count if region == `r'
    assert r(N) > 0
}
ds, has(type numeric)
local numeric_vars `r(varlist)'
tabstat wage education age, stat(n mean sd p25 median p75) by(region)
_pctile wage, p(25 50 75)
scalar wage_median = r(r2)
regress wage education age i.region if year < 2023
predict fitted, xb
predict residual, resid
predict mean_se, stdp
assert !missing(fitted) if year == 2023
testparm i.region
test (education=.8) (age=.06)
lincom education + age, level(90)
estat ovtest
estimates store pooled
areg wage education age, absorb(region) vce(robust)
estimates store absorbed
oneway wage region, tabulate
anova wage region
spearman wage education age, stats(rho p obs)
preserve
contract region age_group, freq(people) percent(share)
list
restore
generate contact = "London,UK"
split contact, parse(",") generate(place)
tostring id, generate(id_text)
assert place1 == "London"
assert place2 == "UK"
display "CORE WORKFLOWS COMPLETE"
