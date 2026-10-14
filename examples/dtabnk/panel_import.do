* SYNTHETIC data, not World Bank estimates.
* Set the working folder to this examples/dtabnk directory first.
dtabnk "gdp.csv" "life_expectancy.csv", merge preview
* The outer merge preserves Kenya without life expectancy and Tanzania without GDP.
dtabnk "gdp.csv" "life_expectancy.csv", merge clear
encode Country, generate(country_id)
xtset country_id Year
list
* Optional exports, uncomment to write files:
* save "development_panel.dta", replace
* export parquet using "development_panel.parquet", replace
* export sav using "development_panel.sav", replace
