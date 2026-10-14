# dtabnk attribution

`statbridge/_vendor/dtabnk.py` is adapted from [cbstatsoft/dtabnk](https://github.com/cbstatsoft/dtabnk), copyright Connor Baird 2026, under GPL-3.0-or-later. The GPL text is included in `LICENSE`. StatBridge is also GPL-3.0-or-later.

Source retrieved 12 October 2026:

- Repository commit: `a1af2b0cfc87cedef12b416d2fa2ae6ff341ff63`
- `dtabnk.py` Git blob: `fba498bf4835cf00b0bf61c7f365af07ebea14d3`

The adaptation removes the standalone CLI and runtime dependency bootstrap, routes progress through a thread-local callback, validates annual year conversion with coercion diagnostics, supports single-entity year-row detection and reports merge column mappings. StatBridge adapters add source parsing, explicit duplicate policy, column-collision handling, preserved code identifiers, preview/import state protection, output controls and Qt integration. The updated upstream `PanelMerger` supplies validated joining and source-specific column naming.

See `docs/DTABNK.md` for supported behavior and differences from the original program. This is not a StataCorp product or an official World Bank application.

## Minitab portable layout

`statbridge/legacy_io.py` implements the numeric-column portable layout informed by R `foreign/src/minitab.c`, copyright Douglas M. Bates and Saikat DebRoy (1999), GPL-2.0-or-later. Source Git blob `9088e20b3645b7804eac3ed5945bdb27edb79c27`, retrieved 13 October 2026 from https://github.com/cran/foreign/blob/master/src/minitab.c. StatBridge distributes this adaptation under GPL-3.0-or-later; see LICENSE. It rejects non-column objects, validates lengths, handles malformed records explicitly and retains stored numeric precision rather than the R wrapper's six-significant-digit rounding.

## ReadStat validation fixture

`tests/fixtures/readstat-sample.sas7bdat` is the unmodified `test_data/basic/sample.sas7bdat` from Roche/pyreadstat, Git blob `cba665fee37dafdbaaa95e77b5223577c150cd78`, retrieved 13 October 2026. The upstream license is retained in `tests/fixtures/PYREADSTAT_LICENSE`. This independent native SAS fixture covers strings, dates (including 1583), times and missing values.

## Application branding and separately installed dependencies

StatBridge original code, documentation, synthetic examples and SVG toolbar glyphs:
Copyright (C) 2026 Connor Baird, GPL-3.0-or-later. Screenshots show StatBridge.
Stata is a registered trademark of StataCorp LLC. StatBridge is not affiliated
with, sponsored by or endorsed by StataCorp LLC. No Stata software, manuals,
logos or licence keys are bundled. Official documentation is linked for reference.

Python libraries are installed separately by pip, not redistributed inside this
source archive/wheel. Their upstream copyright and licence notices still apply.
Future frozen distributions must inventory and comply with every bundled
component's terms. See docs/LICENSING.md for release provenance and distribution policy.
