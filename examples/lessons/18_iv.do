* 18. Instruments and identification
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: iv"
set seed 36
set obs 500
generate instrument = rnormal()
generate control = rnormal()
generate disturbance = rnormal()
generate x = instrument + .5*control + disturbance + rnormal()
generate y = 1 + 2*x + control + disturbance

* YOUR TURN: Fit 2SLS for y on control, instrumenting x with instrument.

* HINT: Use ivregress 2sls y control (x = instrument).
* THINK IT THROUGH: Can a strong first-stage relationship prove exclusion?

* SUGGESTED SOLUTION (uncomment after trying):
* ivregress 2sls y control (x = instrument)

* INTERPRETATION: No. Relevance is different from exclusion. The latter needs a credible design and substantive argument; statistical diagnostics do not prove it.
* COMPATIBILITY: linearmodels supplies 2SLS. First-stage, endogeneity and selected overidentification diagnostics are available; weak-IV-robust intervals and clustered overidentification are not implemented. Panel Hausman is not the IV Wu-Hausman test.
