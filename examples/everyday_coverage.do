* Synthetic self-contained examples. Running clears the workspace.
clear all
set seed 716
set obs 240
generate id = ceil(_n/6)
generate stratum = ceil(id/10)
generate time = mod(_n-1,6)+1
generate x = rnormal()
generate z = rnormal()
generate y = 2+.8*x+z+rnormal()
generate binary = y>2
generate weight = 1+mod(id,3)
generate domain = mod(_n,3)>0
mean y x
ci means y
ci proportions binary, wilson
prtest binary = .5
tab1 stratum binary
kwallis y, by(stratum)
xtset id time
xtdescribe
xtsum y x
graph box y, over(stratum)
svyset id [pw=weight], strata(stratum)
svy: mean y x
svy, subpop(domain): regress y x z
estimates store survey_linear
predict survey_fit, xb
clear all
set seed 717
set obs 250
generate t = _n
generate x = rnormal()
generate y = 1+x+rnormal()
tsset t
newey y x, lag(3)
generate category = (y>0)+(y>2)
ologit category x
predict p_high, pr outcome(2)
mlogit category x, baseoutcome(0)
predict p_mid, pr outcome(1)
generate eventtime = -ln(runiform())/exp(.5*x)
generate censortime = -3*ln(runiform())
generate duration = min(eventtime,censortime)
generate failure = eventtime<=censortime
stset duration, failure(failure)
sts list
stsum
stcox x
predict relative_hazard, hr
coverage
