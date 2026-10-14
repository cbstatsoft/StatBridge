* 5. Interpret a regression
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: ols"
set obs 30
generate hours = _n/3
generate score = 40 + 3*hours + 2*sin(_n)
scatter score hours

* YOUR TURN: Regress score on hours.

* HINT: The outcome goes first, followed by predictors.
* THINK IT THROUGH: What does this result tell you, and what does it leave unanswered?

* SUGGESTED SOLUTION (uncomment after trying):
* regress score hours

* INTERPRETATION: Describe the result in its original units, state the assumptions, and distinguish evidence from proof.
* COMPATIBILITY: OLS coefficients are checked against direct least squares, but collinearity omissions and all Stata reporting details are not replicated.
