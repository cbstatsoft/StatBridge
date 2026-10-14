# ANOVA and pairwise comparisons (post-beta roadmap phase)

StatBridge implements a **bounded, unweighted, classical** set of fixed-effects analysis-of-variance procedures for independent groups. It does not implement Stata's full ANOVA syntax, repeated-measures ANOVA, the full set of marginal contrasts, or certified numerical parity.

## Commands

For a ready-to-run self-contained synthetic script, use [`examples/anova_phase.do`](../examples/anova_phase.do) from the repository working directory.

```stata
oneway score group, tabulate
oneway score group, bonferroni
oneway score group, sidak
oneway score group, scheffe

pwmean score, over(group) mcompare(tukey)
pwmean score, over(group) mcompare(bonferroni) level(99)

anova score group
anova score group treatment
anova score group##treatment
anova score group##treatment, sequential
anova score group treatment group#treatment, partial
```

### One-way ANOVA

`oneway response group` retains its classical one-way F-test (groups must have pooled positive within-group variance). The optional `tabulate` reports group counts, means, and standard deviations. Select **at most one** adjustment:

| Option | Pairwise p-values | Simultaneous intervals |
| --- | --- | --- |
| `bonferroni` | Bonferroni familywise correction | Two-sided t critical value using alpha / number of comparisons |
| `sidak` | Šidák familywise correction | Two-sided t critical value using Šidák family alpha |
| `scheffe` | Scheffé F-family adjustment | Scheffé critical value for any linear contrast |

All methods use the **pooled within-group MSE** and `N-k` residual degrees of freedom. They are meaningful under independent, homoskedastic, normal residuals. They do not account for sampling clusters, paired data, unequal population variances, or repeated measures. Corrected pairwise p-values and intervals use the same adjustment.

### Pairwise means: `pwmean`

`pwmean response, over(group) [mcompare(tukey|bonferroni|sidak|scheffe) level(#)]` prints counts, group means, standard deviations, and all pairwise differences. The default correction is `tukey` (Tukey-Kramer for potentially unequal group sizes), which uses SciPy's studentized range distribution. Supported `level()` values lie strictly between 0 and 100. No weights, `effects` option, robust covariance, postestimation of fitted adjusted means, or prediction is implemented. To avoid excessive output there is a 100-group limit.

Tukey-Kramer simultaneous intervals use the pooled group variance and a studentized-range critical value. Scheffé gives a simultaneous envelope for any linear contrast, not only the displayed pairs. Other methods adjust for the number of displayed pairs.

### Factorial `anova`

The accepted grammar is `anova response factor1 [factor2] [factor1#factor2] [, partial|sequential]`; `factor1##factor2` adds both main effects and an interaction. Prefixing factor names with `i.` is optional. There may be **at most two** nonnegative, integer-coded categorical factors. Interaction terms require both corresponding main effects. `if` and `in` qualifiers use the same sample selection as the regression engine.

`anova` fits an ordinary OLS indicator design with an intercept, preserving a fitted model for supported prediction and coefficient tests. It reports factor SS, degrees of freedom, MS, F, and p-values against the model's common residual MSE.

- **`sequential`** uses term-by-term (Type I) residual SS reductions **in the order entered**. The reported effects are order-dependent in unbalanced designs.
- **`partial`**, the default, removes each term in turn from the full reference-coded design (conditional or drop-term SS). Main-effect results in a model that also includes interactions can depend on the choice of reference category. These **are not guaranteed numerically equivalent to Stata's default partial SS** in interacted/unbalanced designs.

In particular, these are **not generalized repeated-measures or random-effects ANOVA procedures**. Missing factorial cells, collinear design matrices, insufficient residual degrees of freedom, zero residual variance, weights, and unsupported options are rejected rather than approximated. A preflight guard refuses estimated indicator designs over **256 columns or 5 million design cells**, before allocating the full model matrix. `anova` does not implement `margins` or `pwcompare` postestimation for this fitted-model command.

## Why the distinction matters

A significant factor F-test does not identify which individual groups differ. Pairwise multiple-comparison tests address a different family of hypotheses and depend on their stated simultaneous-error method. ANOVA p-values are conditional on the chosen model and variance assumptions.

For interacting factors, consider whether main effects at the **reference category** are scientifically meaningful before using partial estimates. Sequential ANOVA is useful for explicitly ordered nested-model comparisons, but swapping terms can change SS when predictors are correlated or the design is unbalanced.

## Validation status

Synthetic reference tests have been **added** for one-way F statistics, three pooled pairwise adjustments, Tukey-Kramer unequal-group intervals, nested-model sequential factorial SS, and rejection of unsupported syntax. These tests require execution in the normal test suite before this phase should be treated as validated.

```sh
python -m pytest -q tests/test_anova_phase.py
python -m pytest -q
```

The new feature code has not been run against a licensed Stata instance. Verify numerical choices for important research datasets.

## Primary references

- [Stata `oneway` manual](https://www.stata.com/manuals/roneway.pdf)
- [Stata `anova` manual](https://www.stata.com/manuals/ranova.pdf)
- [SciPy studentized-range distribution](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.studentized_range.html)
