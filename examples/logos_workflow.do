* Logos — a deterministic English and formal-logic alternative.
* Data generation remains Stata syntax through explicit stata: escapes.
syntax logos
stata: clear
stata: set obs 120
stata: set seed 902
stata: generate education = 7 + mod(_n, 11)
stata: generate experience = 1 + mod(_n, 20)
create income as 1000 + 180*education + 85*experience + 120*rnormal()
create adult as experience ≥ 5
show variables
summarise income and education
count rows where (adult = 1) ∧ (income is not missing)
regress income on education and experience
predict residuals as error
correlate education and experience
tabulate adult
syntax stata
summarize error
