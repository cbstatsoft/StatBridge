* StatBridge 0.4.0 roadmap workflows, synthetic data.
* Replaces in-memory data. Writes only when export lines are uncommented.
clear all
set seed 104
set obs 400
generate id = ceil(_n/5)
generate time = mod(_n-1,5)
generate group = mod(id,2)
bysort id: generate effect = rnormal() if _n == 1
bysort id: replace effect = effect[1]
generate x = .4*effect+rnormal()
generate y = 1+2*x+effect+.2*time+rnormal()

regress y c.x##i.group i.time, vce(cluster id)
estimates store interacted
margins group, at(x=(-1 0 1))
marginsplot
margins, dydx(x) over(group)
* export results using "marginal_effects.csv", replace
etable, estimates(interacted)
dtable x y, by(group)
* export results using "summary.html", replace

xtset id time
xtreg y x i.time, cre vce(cluster id)
estat mundlak
reghdfe y x, absorb(id time) vce(cluster id)
predict error, residuals
qnorm error
rvfplot
twoway (scatter y x) (lfit y x), title("Observed outcomes and linear fit")

* Overidentified IV example with two independent synthetic instruments.
generate instrument1 = rnormal()
generate instrument2 = rnormal()
generate disturbance = rnormal()
generate endogenous = instrument1+instrument2+disturbance+rnormal()
generate outcome = 1+2*endogenous+disturbance
ivregress 2sls outcome (endogenous = instrument1 instrument2), vce(robust)
estat firststage
estat endogenous
estat overid

* Dates: display changes, numeric storage does not.
generate daydate = daily("2020-02-29","YMD")
format daydate %td
generate monthdate = mofd(daydate)
format monthdate %tm
list daydate monthdate in 1/3
* export excel using "teaching_data.xlsx", firstrow(variables) replace
* import excel "teaching_data.xlsx", firstrow clear

* Complete two-period, common-adoption panel design.
keep if time < 2
generate treated = (id>40) & (time==1)
generate did_outcome = id/10+2*time+4*treated+rnormal()
xtset id time
xtdidregress (did_outcome) (treated), group(id) time(time)
