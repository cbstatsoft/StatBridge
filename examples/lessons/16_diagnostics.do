* 16. Diagnose functional form
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: diagnostics"
set seed 34
set obs 150
generate x = 4*runiform()
generate y = 1 + x + x^2 + rnormal()
regress y x

* YOUR TURN: Run the implemented RESET test and explain what it can and cannot establish.

* HINT: Use estat ovtest after conventional OLS.
* THINK IT THROUGH: If RESET rejects, does that prove x squared is the right correction in real data?

* SUGGESTED SOLUTION (uncomment after trying):
* estat ovtest

* INTERPRETATION: No. We know the synthetic generating formula here, but in real data several specification problems can yield rejection. Use theory and residual patterns.
* COMPATIBILITY: Uses fitted-value powers 2 through 4 and conventional unweighted OLS. Rank tolerances may differ from Stata.
