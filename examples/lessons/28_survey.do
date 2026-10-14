* 28. A survey domain keeps the full design
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: survey"
set seed 713
set obs 120
generate psu = ceil(_n/5)
generate stratum = ceil(psu/6)
generate weight = 1+mod(psu,3)
generate adult = mod(_n,3)>0
generate income = 20+5*rnormal()

* YOUR TURN: Declare psu, weight and stratum, then estimate mean income for adults using subpop().

* Suggested solution
svyset psu [pw=weight], strata(stratum)
svy, subpop(adult): mean income
