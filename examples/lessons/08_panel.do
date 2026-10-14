* 8. Panel fixed effects
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: panel"
set seed 871
set obs 240
generate id = ceil(_n/6)
generate year = 2010 + mod(_n-1,6)
bysort id: generate effect = rnormal() if _n == 1
bysort id: replace effect = effect[1]
generate x = 3 + effect + rnormal()
generate y = 1 + .8*x + effect + .2*(year-2010) + rnormal()

* YOUR TURN: Declare id and year, then fit fixed effects with x, year indicators and clustering by id.

* HINT: Use xtset id year, followed by xtreg y x i.year, fe vce(cluster id).
* THINK IT THROUGH: What does this result tell you, and what does it leave unanswered?

* SUGGESTED SOLUTION (uncomment after trying):
* xtset id year
* xtreg y x i.year, fe vce(cluster id)

* INTERPRETATION: Describe the result in its original units, state the assumptions, and distinguish evidence from proof.
* COMPATIBILITY: linearmodels FE covariance, residual degrees of freedom and R-squared reporting can differ from Stata xtreg. Read the compatibility notice before comparing outputs.
