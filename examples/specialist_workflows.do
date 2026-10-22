* StatBridge Phase C bounded workflows; synthetic observations only.
* This demonstration replaces the in-memory dataset. Save your work first.

* Gaussian random-intercept model.
clear all
set seed 417
set obs 300
generate school = ceil(_n/10)
generate x = rnormal()
generate y = 2+1.5*x+2*sin(school)+rnormal(0,.5)
mixed y x, group(school)

* Balanced repeated-measures ANOVA.
clear all
set seed 418
set obs 90
generate person = ceil(_n/3)
generate visit = mod(_n-1,3)
generate score = 2+.3*visit+sin(person)+rnormal()
anovarm score, subject(person) within(visit)

* Continuous chained-equation predictive-mean matching.
clear all
set seed 419
set obs 120
generate x = rnormal()
generate z = rnormal()
generate y = 2+1.4*x-.5*z+rnormal()
replace x = . if mod(_n,7)==0
mi regress y x z, m(5) burnin(5) between(2) seed(9)
export results using "mi_results.csv", replace

* Consecutive time series VAR with fitted stability and forecasts.
clear all
set seed 420
set obs 120
generate period = _n
generate a = rnormal()
generate b = .5*a+rnormal()
tsset period
var a b, lags(2)
varstable
varforecast, steps(5)

* Unadjusted cohort-period DiD against never-treated controls.
clear all
set seed 421
set obs 315
generate id = ceil(_n/7)
generate year = mod(_n-1,7)+1
generate first_treat = cond(id<=15,0,cond(id<=30,4,5))
generate treated_effect = cond(first_treat==4 & year>=4,2,cond(first_treat==5 & year>=5,3,0))
generate y = 2+.3*year+sin(id)+treated_effect+rnormal(0,.4)
xtset id year
attgt y, cohort(first_treat)

* One-stage finite-population correction.
clear all
set seed 422
set obs 90
generate psu = _n
generate stratum = ceil(_n/30)
generate fpc_frac = .15+.05*stratum
generate weight = 1+runiform()
generate outcome = rnormal()+stratum
svyset psu [pw=weight], strata(stratum) fpc(fpc_frac)
svy: mean outcome
