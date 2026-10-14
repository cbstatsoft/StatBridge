* 1. Data and summary statistics
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: summaries"
set obs 8
generate score = 40 + 5*_n
label variable score "Synthetic assessment score"
list score in 1/3

* YOUR TURN: Summarize score, then check your result.

* HINT: The command starts with summarize, followed by the variable name.
* THINK IT THROUGH: What does this result tell you, and what does it leave unanswered?

* SUGGESTED SOLUTION (uncomment after trying):
* summarize score

* INTERPRETATION: Describe the result in its original units, state the assumptions, and distinguish evidence from proof.
* COMPATIBILITY: The unweighted sample SD and ordinary percentile conventions are targeted. Storage precision can differ from Stata.
