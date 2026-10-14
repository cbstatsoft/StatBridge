* 14. Odds versus probabilities
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: logit"
set seed 33
set obs 240
generate x = rnormal()
generate probability = 1/(1+exp(-(.2+.8*x)))
generate outcome = runiform() < probability

* YOUR TURN: Fit logit outcome x, then request average marginal effects.

* HINT: Use margins, dydx(*) after fitting the logit model.
* THINK IT THROUGH: If a probability-scale effect is 0.10, is that a 10% relative increase?

* SUGGESTED SOLUTION (uncomment after trying):
* logit outcome x
* margins, dydx(*)

* INTERPRETATION: It is 10 percentage points for a unit change (locally for a continuous derivative). Relative percent change needs a baseline probability.
* COMPATIBILITY: margins supports unweighted OLS/logit/logistic/probit, factors, interactions and marginsplot. Numeric 0/1 predictors give derivatives; use factor notation for discrete changes.
