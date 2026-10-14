* 11. Interpret an interaction
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: interactions"
set seed 31
set obs 160
generate group = mod(_n,2)
generate x = 4*runiform()
generate y = 2 + x + 3*group + 2*x*group + rnormal()
regress y c.x##i.group

* YOUR TURN: Use lincom to estimate the x slope for group 1.

* HINT: Read the coefficient names in the fitted table and combine x with x#1.group.
* THINK IT THROUGH: Does the x coefficient alone describe the slope in both groups?

* SUGGESTED SOLUTION (uncomment after trying):
* lincom x + x#1.group

* INTERPRETATION: No. It is the reference-group slope; group 1's slope adds the interaction. Neither association is automatically causal.
* COMPATIBILITY: This uses implemented factor expansion and linear contrasts. Unweighted OLS/logit/probit margins with factors and interactions is also available.
