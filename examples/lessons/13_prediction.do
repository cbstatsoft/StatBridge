* 13. Fitted values and residuals
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: prediction"
set obs 30
generate x = _n/3
generate y = 2 + .7*x + sin(_n)
regress y x

* YOUR TURN: Create fitted containing fitted values and error containing residuals.

* HINT: Use predict fitted, xb and predict error, residuals.
* THINK IT THROUGH: Would a small residual on training data establish good prediction on new data?

* SUGGESTED SOLUTION (uncomment after trying):
* predict fitted, xb
* predict error, residuals

* INTERPRETATION: No. Assess predictions on suitable held-out data and consider whether the new population differs.
* COMPATIBILITY: Eligible unweighted OLS can predict outside its estimation sample; other paths retain estimation-sample and data-revision restrictions.
