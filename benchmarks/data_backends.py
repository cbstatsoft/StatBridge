"""Conversion-inclusive benchmarks; run from project root with PYTHONPATH=.

No dataset, backend cache or fitted model is reused between timed commands.
Input generation and initial session assignment are outside the timer.
"""

import argparse
import importlib.metadata
import json
import os
import platform
import statistics
import time
from pathlib import Path
import numpy as np
import pandas as pd
import polars as pl
from statbridge.engine import Engine


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=1_000_000)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--output", default="docs/benchmark-results.json")
    args = p.parse_args()
    rng = np.random.default_rng(431)
    df = pd.DataFrame(
        {
            "g": rng.integers(0, 10000, args.rows).astype(float),
            "h": rng.integers(0, 20, args.rows).astype(float),
            "x": rng.normal(size=args.rows),
            "y": rng.normal(size=args.rows),
        }
    )
    df.loc[::113, "x"] = np.nan
    commands = [
        "sort g h x",
        "duplicates report g h",
        "collapse (mean) avg=x (sum) total=y (sd) sd=x (median) med=y, by(g h)",
        "egen avg=mean(x), by(g h)",
    ]
    results = []
    # Warm imports and worker pool before timing either backend.
    for mode in ("pandas", "polars"):
        e = Engine()
        e.data_backend = mode
        e.df = df.iloc[:1000].copy()
        assert e.execute(commands[2])
    for command in commands:
        samples = {mode: [] for mode in ("pandas", "polars")}
        for repeat in range(args.repeats):
            # Alternate order to avoid always favouring the second backend.
            for mode in (
                ("pandas", "polars") if repeat % 2 == 0 else ("polars", "pandas")
            ):
                e = Engine()
                e.data_backend = mode
                e.df = df.copy(deep=True)
                start = time.perf_counter()
                assert e.execute(command), e.events[-1]
                samples[mode].append(time.perf_counter() - start)
        result = {
            "command": command,
            "seconds": samples,
            "median_seconds": {m: statistics.median(v) for m, v in samples.items()},
        }
        result["speedup_pandas_over_polars"] = (
            result["median_seconds"]["pandas"] / result["median_seconds"]["polars"]
        )
        results.append(result)
        print(
            command,
            result["median_seconds"],
            "speedup",
            round(result["speedup_pandas_over_polars"], 2),
            flush=True,
        )
    out = {
        "rows": args.rows,
        "repeats": args.repeats,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "logical_cpus": os.cpu_count(),
        "polars_threads": pl.thread_pool_size(),
        "versions": {
            m: importlib.metadata.version(m)
            for m in ("pandas", "polars", "pyarrow", "numpy")
        },
        "method": "Median wall time for Engine.execute, including parsing, conversion, computation, final pandas output and command audit; excludes source generation and initial session assignment. Warmed imports and pool; alternating backend order.",
        "results": results,
    }
    Path(args.output).write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
