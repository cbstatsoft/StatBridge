# Data-backend performance

Measured on 30 September 2026 in the Linux development environment. This is a small reproducible synthetic benchmark, not a general claim that every Polars operation is faster.

One million rows, four numeric columns, missing values in x, and two group keys with up to 200,000 combinations. Three repetitions per backend, with alternating backend order; table reports median wall-clock seconds. The Polars worker pool and imports were warmed before timing either backend. Timings cover the complete command, including parsing, pandas-to-Polars conversion, computation, final pandas output and audit. Initial source generation and assignment to a fresh session are excluded. No converted-frame cache is reused.

| Command | pandas seconds | Polars seconds | pandas / Polars |
| --- | ---: | ---: | ---: |
| `sort g h x` | 0.4571 | 0.1688 | 2.71× |
| `duplicates report g h` | 0.0752 | 0.0704 | 1.07× |
| `collapse (mean) avg=x (sum) total=y (sd) sd=x (median) med=y, by(g h)` | 0.1525 | 0.0881 | 1.73× |
| `egen avg=mean(x), by(g h)` | 0.1127 | 0.0810 | 1.39× |

Runtime: Python 3.12.14, pandas 2.2.3, Polars 1.44.2, PyArrow 25.0.1, 8 Polars threads. Raw observations and environment metadata are in `benchmark-results.json`. A second run at 100,000 rows is in `benchmark-100k.json`.

## Reproduce

```sh
# Run from the extracted project after installing its dependencies.
PYTHONPATH=. python benchmarks/data_backends.py --rows 1000000 --repeats 3
```

On Windows PowerShell, use `$env:PYTHONPATH="."` before running the Python command.

Auto mode uses a transparent 100,000-row threshold, not an adaptive benchmark or a guarantee of a speedup. The best threshold depends on hardware, grouping cardinality, dtypes and operation. Users can force either backend with `set databackend polars` or `set databackend pandas`. Small inputs avoid conversion by default. pandas remains the data-editor/expression/model interface, and statistical fitting itself is not accelerated by these changes. Lazy or out-of-core execution, joins and CSV parsing have not been migrated.
