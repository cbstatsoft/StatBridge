# Contributing to StatBridge

StatBridge Qt is maintained by Connor Baird and distributed under GNU GPL version 3 or later. Contributions are welcome under the same licence. Preserve existing third-party notices and document the origin, licence and modifications of any imported material.

## Development

Use Python 3.12 in a virtual environment:

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python launch.py --doctor
python launch.py --batch examples/demo.do
```

On a headless machine set QT_QPA_PLATFORM=offscreen before running GUI tests. Windows terminal use requires the terminal extra. See docs/RELEASING.md for build and release checks.

## Changes and bug reports

Provide the version, operating system, a minimal synthetic dataset/do-file, expected result, actual result and the relevant compatibility notice. Copy Help > Installation diagnostics when useful. Never post private research data, full command history, credentials or identifying paths.

New statistical translations need a documented syntax subset, explicit refusal of unsupported options, meaningful checks against independent calculations or published mathematical definitions, completion/help, and compatibility notices for different conventions. Keep GUI and terminal behaviour in the shared engine. A matching coefficient alone does not validate standard errors, samples, degrees of freedom or postestimation.

The repository's issue tracker is the appropriate place for ordinary bugs once the project is hosted. Do not imply support by StataCorp. No dedicated support email has been set up in this release.

## Provenance

Do not copy Stata source, ado/Mata programs, manuals, help files, logos, screenshots or datasets into the project without an applicable redistribution licence and recorded permission. Write original explanations and synthetic examples; link to official reference documentation. Do not derive test fixtures by redistributing proprietary files. Record any legally obtained reference results separately with provenance and rights review.

See docs/LICENSING.md and THIRD_PARTY_NOTICES.md. No copyright assignment is required by this project.

