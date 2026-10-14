* 20. Mundlak with clustered uncertainty
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: mundlak"
set seed 871
set obs 600
generate id = ceil(_n/6)
generate time = 1+mod(_n-1,6)
bysort id: generate effect = rnormal() if _n == 1
bysort id: replace effect = effect[1]
generate x = .5*effect+rnormal()
generate y = 1+.8*x+effect+rnormal()
xtset id time

* YOUR TURN: Fit correlated RE with clustering by id, then test the panel means.

* HINT: Use xtreg y x, cre vce(cluster id), then estat mundlak.
* THINK IT THROUGH: Does non-rejection prove the random-effects assumptions?

* SUGGESTED SOLUTION (uncomment after trying):
* xtreg y x, cre vce(cluster id)
* estat mundlak

* INTERPRETATION: No. State the tested restrictions and power limitations. The test also cannot establish exogeneity of the remaining idiosyncratic error.
* COMPATIBILITY: Balanced complete-case panel subset. Stata unbalanced-panel corrections are not implemented. Clustered Wald chi-square is asymptotic; few clusters remain problematic.
