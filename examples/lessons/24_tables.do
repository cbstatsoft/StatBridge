* 24. Compare and export models
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: tables"
set seed 94
set obs 120
generate x = rnormal()
generate z = .4*x+rnormal()
generate y = 1+2*x+z+rnormal()
regress y x
estimates store short
regress y x z, vce(robust)
estimates store adjusted

* YOUR TURN: Compare short and adjusted with etable. Use the Results menu to copy or export if desired.

* HINT: Use etable, estimates(short adjusted). Export is optional and not needed for the check.
* THINK IT THROUGH: Must the larger model have the more credible causal coefficient?

* SUGGESTED SOLUTION (uncomment after trying):
* etable, estimates(short adjusted)

* INTERPRETATION: No. Control selection depends on the causal question and design; additional controls can themselves introduce bias.
* COMPATIBILITY: The table reports coefficients on the fitted scale. CSV/HTML/LaTeX export is a bounded subset, not the complete Stata collect/estout system.
