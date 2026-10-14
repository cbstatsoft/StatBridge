* 26. Check what survives a file conversion
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: file_formats"
set obs 4
generate id = _n
generate day = 21915 + id
format day %td
label variable day "Visit date"

* YOUR TURN: Export the data to lesson-formats.parquet, then import it back and confirm that Visit date and %td survive.

* Suggested solution
export parquet using "lesson-formats.parquet"
import parquet "lesson-formats.parquet", clear
describe
