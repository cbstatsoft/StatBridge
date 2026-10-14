* Synthetic panel analysis, deliberately without a Stata parity claim.
clear all
set seed 8431
set obs 600
generate id = ceil(_n/6)
generate year = 2010 + mod(_n-1,6)
bysort id: generate effect = rnormal() if _n == 1
bysort id: replace effect = effect[1]
generate income = 5 + effect + rnormal()
generate investment = 2 + .8*income + effect + .15*(year-2010) + rnormal()
xtset id year
xtreg investment income i.year, fe
estimates store fixed
xtreg investment income i.year, re
estimates store random
estimates table fixed random
* Classical Hausman can have a non-positive covariance difference.
* capture allows this example to proceed while retaining the explicit error.
capture hausman fixed random
xtreg investment income i.year, fe vce(cluster id)
test income
