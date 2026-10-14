* 17. Compare means with uncertainty
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: ttest"
set seed 35
set obs 120
generate group = mod(_n,2)
generate score = 50 + 4*group + (3+3*group)*rnormal()

* YOUR TURN: Compare score across group using unequal-variance inference.

* HINT: Use ttest score, by(group) unequal.
* THINK IT THROUGH: Can a negative difference be consistent with higher scores in group 1?

* SUGGESTED SOLUTION (uncomment after trying):
* ttest score, by(group) unequal

* INTERPRETATION: Yes. This ordering subtracts group 1's mean from group 0's. State the ordering and score units explicitly.
* COMPATIBILITY: SciPy supplies Welch degrees of freedom and a two-sided confidence interval. The reported difference is group 0 minus group 1.
