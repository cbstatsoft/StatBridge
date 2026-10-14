* 19. Predictions with interactions
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: margins"
set seed 91
set obs 160
generate group = mod(_n,2)
generate x = 4*runiform()
generate y = 2 + x + 3*group + 2*x*group + rnormal()
regress y c.x##i.group

* YOUR TURN: Estimate group predictions at x = 1 and x = 3, then graph their intervals.

* HINT: Use margins group, at(x=(1 3)), then marginsplot.
* THINK IT THROUGH: Does evaluating everyone at x = 3 establish an intervention effect?

* SUGGESTED SOLUTION (uncomment after trying):
* margins group, at(x=(1 3))
* marginsplot

* INTERPRETATION: No. It is a model-based counterfactual prediction; a causal interpretation additionally needs identification assumptions.
* COMPATIBILITY: Unweighted OLS/logit/probit only. Delta-method covariance conditions on the empirical covariates; these are not individual prediction intervals.
