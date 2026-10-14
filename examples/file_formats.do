* Run from a writable folder. Output is created under statbridge-format-demo.
clear all
set obs 6
generate id = _n
generate income = 1000 + 125 * id
replace income = . in 3
generate day = 21915 + id
format day %td
label variable income "Monthly income"
label data "Synthetic format interoperability example"
mkdir "statbridge-format-demo", parents
export parquet using "statbridge-format-demo/students.parquet", compression(zstd) replace
export sav using "statbridge-format-demo/students.zsav", replace
export xport using "statbridge-format-demo/students.xpt", replace
export rdata using "statbridge-format-demo/students.RData", object(students) replace
export rds using "statbridge-format-demo/students.rds", replace
export feather using "statbridge-format-demo/students.feather", replace
export arrow using "statbridge-format-demo/students.arrow", replace
export sqlite using "statbridge-format-demo/students.sqlite", table(students) replace
export excel using "statbridge-format-demo/students.xlsx", firstrow(variables) replace
export ods using "statbridge-format-demo/students.ods", replace
export mat using "statbridge-format-demo/students.mat", replace
export hdf5 using "statbridge-format-demo/students.h5", replace
export json using "statbridge-format-demo/students.json", replace
export jsonl using "statbridge-format-demo/students.jsonl", replace
export delimited using "statbridge-format-demo/students.tsv", replace
import auto "statbridge-format-demo/students.parquet", preview rows(3)
use "statbridge-format-demo/students.parquet", clear
describe
summarize income
