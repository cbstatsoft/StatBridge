* 10. Reshape repeated measurements
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: reshape"
set obs 4
generate id = _n
generate score1 = 40 + id
generate score2 = 45 + id

* YOUR TURN: Reshape score1 and score2 into score with occasion in wave, then declare id and wave.

* HINT: The stub is score. Use reshape long with i(id) j(wave), then xtset.
* THINK IT THROUGH: Why are the resulting eight rows not necessarily eight independent people?

* SUGGESTED SOLUTION (uncomment after trying):
* reshape long score, i(id) j(wave)
* xtset id wave

* INTERPRETATION: There are four people observed twice. Repeated observations from a person may be dependent.
* COMPATIBILITY: This exercise covers a numeric-suffix reshape subset. Reshaping does not create independent observations.
