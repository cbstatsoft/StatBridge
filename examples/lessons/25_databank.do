* Run from the extracted release root folder.
* 25. Merge World Bank indicator files
* Synthetic teaching data. This replaces data in memory.
clear all
label data "StatBridge lesson: databank"
dtabnk "examples/dtabnk/gdp.csv" "examples/dtabnk/life_expectancy.csv", merge clear
label data "StatBridge lesson: databank"

* YOUR TURN: Encode Country into country_id and declare the panel with Year as the time variable. Inspect which countries lack each indicator.

* HINT: Use encode Country, generate(country_id), then xtset country_id Year. Inspect list to see unmatched indicators.
* SOLUTION:
* encode Country, generate(country_id)
* xtset country_id Year
* list

* REFLECT: Would replacing unmatched indicators with zero fix missing data?
* No. An unmatched or unavailable observation is not an observed zero. Investigate source coverage, units, definitions, country identifiers and time periods before analysis.
