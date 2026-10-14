* 30. Ordered categories and predicted probabilities
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: ordered"
set seed 715
set obs 300
generate x = rnormal()
generate u = runiform()
generate latent = .7*x+ln(u/(1-u))
generate rating = (latent>-.5)+(latent>.7)

* YOUR TURN: Fit ordered logit and generate category 2 probability as p_high.

* Suggested solution
ologit rating x
predict p_high, pr outcome(2)
