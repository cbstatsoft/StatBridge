* 29. A hazard ratio is not a risk ratio
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: survival"
set seed 714
set obs 300
generate x = rnormal()
generate eventtime = -ln(runiform())/exp(.5*x)
generate censortime = -3*ln(runiform())
generate duration = min(eventtime,censortime)
generate failure = eventtime<=censortime

* YOUR TURN: Declare survival data, inspect Kaplan-Meier survival, then fit Cox with x.

* Suggested solution
stset duration, failure(failure)
sts list
stcox x
