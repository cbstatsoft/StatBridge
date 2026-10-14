* 6. Coefficients versus uncertainty
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: robust"
set seed 123
set obs 120
generate x = 1 + 4*runiform()
generate y = 2 + 1.5*x + x*rnormal()
regress y x
estimates store ordinary

* YOUR TURN: Fit the same regression with robust standard errors.

* HINT: Add , vce(robust) to regress y x.
* THINK IT THROUGH: What does this result tell you, and what does it leave unanswered?

* SUGGESTED SOLUTION (uncomment after trying):
* regress y x, vce(robust)

* INTERPRETATION: Describe the result in its original units, state the assumptions, and distinguish evidence from proof.
* COMPATIBILITY: OLS robust uses HC1 and residual-degree-of-freedom t inference. Robust covariance is not a universal remedy for model misspecification.
