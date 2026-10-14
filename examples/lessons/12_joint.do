* 12. Test several restrictions
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: joint"
set seed 32
set obs 120
generate x = rnormal()
generate z = rnormal()
generate y = 1 + x + .2*z + rnormal()
regress y x z, vce(robust)

* YOUR TURN: Test jointly that the x and z slopes are zero.

* HINT: Use test followed by both coefficient names.
* THINK IT THROUGH: If this test rejects, must the z slope be significant separately?

* SUGGESTED SOLUTION (uncomment after trying):
* test x z

* INTERPRETATION: No. Rejection concerns the restrictions jointly, not each coefficient individually.
* COMPATIBILITY: Wald inference uses the fitted covariance and backend degrees of freedom; this is not a likelihood-ratio test.
