* 15. Interpret a Hausman comparison
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: hausman"
set seed 871
set obs 600
generate id = ceil(_n/6)
generate year = 1 + mod(_n-1,6)
bysort id: generate effect = rnormal() if _n == 1
bysort id: replace effect = effect[1]
generate x = .2*effect + rnormal()
generate y = 1 + .8*x + effect + rnormal()
xtset id year

* YOUR TURN: Store conventional FE as fixed and RE as random, then run hausman fixed random. Read Explain my command.

* HINT: Estimate xtreg y x, fe and store fixed; estimate with re and store random. Put fixed first in hausman.
* THINK IT THROUGH: What would p = 0.30 establish? What if the covariance difference is invalid?

* SUGGESTED SOLUTION (uncomment after trying):
* xtreg y x, fe
* estimates store fixed
* xtreg y x, re
* estimates store random
* hausman fixed random

* INTERPRETATION: At a prechosen 5% level, 0.30 means insufficient evidence against the RE restrictions, not proof of validity. An invalid covariance difference gives no valid decision. Do not remove needed clustering to force a test to run.
* COMPATIBILITY: This deliberately illustrates classical covariance assumptions. Robust/clustered, weighted, unequal-sample and non-positive-definite comparisons are refused. No sigmamore/sigmaless adjustment. Cluster-robust estat mundlak is available for balanced complete-case panels. NumPy's random stream differs from Stata's for the same seed.
