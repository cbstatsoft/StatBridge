* 9. Clean special missing codes
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: recode"
set obs 8
generate score = 10*_n
replace score = 99 in 3
clonevar raw_score = score

* YOUR TURN: Convert 99 in score to missing, then create band: 1 for 0 to 40 and 2 for 41 to 100, retaining missing.

* HINT: Use mvdecode score, mv(99), then recode with gen(band).
* THINK IT THROUGH: Why would including 99 change the mean? Is 99 always a missing code?

* SUGGESTED SOLUTION (uncomment after trying):
* mvdecode score, mv(99)
* recode score (0/40=1) (41/100=2), gen(band)

* INTERPRETATION: It would be counted as an observed score and increase the mean here. Only the data dictionary can justify treating it as missing.
* COMPATIBILITY: Ordinary missing is supported; extended Stata missing tags are not preserved.
