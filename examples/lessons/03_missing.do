* 3. The missing-value trap
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: missing"
set obs 6
generate x = _n
replace x = . in 3
list x
count if x > 4

* YOUR TURN: Count nonmissing x values greater than 4.

* HINT: Combine x > 4 with x < . using &.
* THINK IT THROUGH: What does this result tell you, and what does it leave unanswered?

* SUGGESTED SOLUTION (uncomment after trying):
* count if x > 4 & x < .

* INTERPRETATION: Describe the result in its original units, state the assumptions, and distinguish evidence from proof.
* COMPATIBILITY: StatBridge implements ordinary missing ordering. Extended tags .a through .z are not retained on import.
