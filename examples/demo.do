* StatBridge introductory demonstration. All data are synthetic.
clear all
set more off
set seed 934
set obs 400
generate id = ceil(_n/5)
generate year = 2016 + mod(_n-1,5)
generate education = 10 + 6*runiform()
generate experience = 2 + 25*runiform()
generate urban = runiform() > .45
generate wage = 2 + .7*education + .12*experience + 1.4*urban + rnormal(0,2)
label variable wage "Hourly wage (synthetic units)"
label variable education "Years of education"
label define urban_label 0 "Rural" 1 "Urban"
label values urban urban_label
summarize wage education experience, detail
regress wage education experience i.urban, vce(robust)
estimates store ols
predict fitted
predict residual, residuals
xtset id year
xtreg wage education experience i.year, fe vce(cluster id)
estimates store fixed
estimates table ols fixed
histogram residual, bin(25) title("Residuals from the synthetic wage model")
compatibility
