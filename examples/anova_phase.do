* Post-beta ANOVA phase: fully synthetic independent observations.
* Running clears the current in-memory dataset. Save your work first.
clear all
set seed 814
set obs 180
generate group = mod(_n-1,3)
generate treatment = mod(ceil(_n/3)-1,2)
generate score = 4 + .6*group + 1.3*treatment + .2*group*treatment + rnormal(0,1)

* Independent-groups omnibus test and adjusted group comparisons.
oneway score group, tabulate bonferroni
pwmean score, over(group) mcompare(tukey)

* Two-factor model with explicit order-dependent (Type I) SS.
anova score group##treatment, sequential
* Partial drop-term F tests, conditional on reference-level coding.
anova score group##treatment, partial
