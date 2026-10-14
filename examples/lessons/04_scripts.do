* 4. Repeatable do-files
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: scripts"
set obs 5
generate x = _n

* YOUR TURN: Create power1, power2 and power3 containing x, x squared and x cubed, using a loop.

* HINT: Use forvalues p = 1/3 {, then generate power`p' = x^`p', then close the brace.
* THINK IT THROUGH: What does this result tell you, and what does it leave unanswered?

* SUGGESTED SOLUTION (uncomment after trying):
* forvalues p = 1/3 {
*     generate power`p' = x^`p'
* }

* INTERPRETATION: Describe the result in its original units, state the assumptions, and distinguish evidence from proof.
* COMPATIBILITY: Simple local macros, nested loops, if/else and CR/semicolon delimiters are supported. The complete Stata programming language is not.
