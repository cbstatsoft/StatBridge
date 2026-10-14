* Synthetic data. Running this script replaces data in memory.
clear all
set obs 30
generate time = 2*_n
generate x = _n
generate y = 2 + .8*x + sin(x)
generate frequency = 1 + mod(_n,3)
summarize y [fw=frequency], detail
regress y x [fw=frequency], vce(robust)
display _b[x]
display _se[x]
lincom x

tsset time, delta(2)
generate lag_y = L.y
generate change_y = D.y
generate second_difference = D2.y
generate seasonal_difference = S2.y
list time y lag_y change_y second_difference seasonal_difference in 1/6

regress y x [fw=frequency], vce(robust)
if _b[x] > 0 {
    display "Positive fitted slope. This alone does not establish causality."
}
else {
    display "Nonpositive fitted slope."
}

#delimit ;
summarize change_y; count if !missing(change_y);
#delimit cr
