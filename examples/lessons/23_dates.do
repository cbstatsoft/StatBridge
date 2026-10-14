* 23. Numeric dates and display formats
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: dates"
set obs 4
generate raw = "2020-02-29"
replace raw = "1960-01-01" in 1
replace raw = "1959-12-31" in 2
replace raw = "2021-02-29" in 4

* YOUR TURN: Create daydate with daily(raw,"YMD") and give it %td format.

* HINT: Invalid calendar dates become missing; the first two values should be 0 and -1.
* THINK IT THROUGH: Does format daydate %tm convert days into months?

* SUGGESTED SOLUTION (uncomment after trying):
* generate daydate = daily(raw,"YMD")
* format daydate %td

* INTERPRETATION: No. Use mofd(daydate) to convert the units, then apply %tm to the new monthly variable.
* COMPATIBILITY: Explicit documented masks only, four-digit years and ordinary missing. Custom Stata date display pictures and leap-second clocks are not implemented.
