* 27. Confidence intervals are about a procedure
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: confidence"
set seed 712
set obs 100
generate score = 60+12*rnormal()

* YOUR TURN: Compute a 95% interval for the mean score.

* Suggested solution
ci means score
