* 21. Diagnose a 2SLS model
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: ivdiagnostics"
set seed 92
set obs 500
generate instrument1 = rnormal()
generate instrument2 = rnormal()
generate control = rnormal()
generate error = rnormal()
generate x = instrument1+.7*instrument2+.5*control+error+rnormal()
generate y = 1+2*x+control+error
ivregress 2sls y control (x = instrument1 instrument2), vce(robust)

* YOUR TURN: Inspect first-stage strength, test exogeneity, then test overidentifying restrictions.

* HINT: Use estat firststage, estat endogenous, and estat overid, in that order.
* THINK IT THROUGH: Could strong instruments still violate exclusion?

* SUGGESTED SOLUTION (uncomment after trying):
* estat firststage
* estat endogenous
* estat overid

* INTERPRETATION: Yes. Relevance and exclusion are different requirements. A high first-stage statistic cannot validate the exclusion argument.
* COMPATIBILITY: Robust overidentification uses Wooldridge score, not Hansen J. Clustered overidentification is refused. Exactly identified models have no overidentification test.
