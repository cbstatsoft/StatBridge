* 2. Conditions and subsets
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: filters"
set obs 8
generate score = 40 + 5*_n
list score

* YOUR TURN: Count observations with score at least 60.

* HINT: Use count with an if qualifier. There are five qualifying observations.
* THINK IT THROUGH: What does this result tell you, and what does it leave unanswered?

* SUGGESTED SOLUTION (uncomment after trying):
* count if score >= 60

* INTERPRETATION: Describe the result in its original units, state the assumptions, and distinguish evidence from proof.
* COMPATIBILITY: An if block makes a control-flow decision. An if qualifier filters rows for one command. They are different constructs.
