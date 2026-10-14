* 22. Two-period difference-in-differences
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: did"
set seed 93
set obs 160
generate id = ceil(_n/2)
generate time = mod(_n-1,2)
generate treated = (id>40) & (time==1)
generate y = id/10 + 2*time + 4*treated + rnormal()
xtset id time

* YOUR TURN: Estimate panel DiD using id as the treatment-group identifier and time as the period.

* HINT: Use xtdidregress (y) (treated), group(id) time(time).
* THINK IT THROUGH: Can this example test whether trends were parallel before treatment?

* SUGGESTED SOLUTION (uncomment after trying):
* xtdidregress (y) (treated), group(id) time(time)

* INTERPRETATION: No. There is only one pre-treatment period. More pre-periods can inform design assessment but still cannot prove the identifying counterfactual.
* COMPATIBILITY: Complete balanced two-period panels only. No staggered adoption, heterogeneous event-study estimator or wild-cluster bootstrap. AbsorbingLS corrections can differ from Stata.
