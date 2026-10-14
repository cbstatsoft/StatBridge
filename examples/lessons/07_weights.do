* 7. Choose the right weight
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: weights"
set obs 12
generate x = _n
generate y = 2 + .7*x + sin(x)
generate frequency = 1 + mod(_n,3)
list x y frequency

* YOUR TURN: Regress y on x using frequency as a frequency weight.

* HINT: Place [fw=frequency] after the variable list.
* THINK IT THROUGH: What does this result tell you, and what does it leave unanswered?

* SUGGESTED SOLUTION (uncomment after trying):
* regress y x [fw=frequency]

* INTERPRETATION: Describe the result in its original units, state the assumptions, and distinguish evidence from proof.
* COMPATIBILITY: Frequency covariance and sample size are checked against explicitly replicated rows. Probability weights alone do not specify strata, clusters or a finite-population correction.
