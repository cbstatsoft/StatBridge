# Building and releasing

0.7.1 is a public beta source release. Do not label it a fully compatible replacement for Stata. It includes a Python wheel, complete application source, tests, examples and licence notices. Dependencies download during installation. There are no standalone executables.

## Build

Use a clean Python 3.12 environment. From the source root:

```sh
python -m pip install -e ".[dev]"
python tools/build_release.py --output ../artifacts
```

The builder synchronises offline licence resources, runs tests, creates an sdist and a wheel in a temporary staging tree, validates author/licence/version metadata and packaged legal resources, installs the wheel into an isolated target and runs all 30 lessons plus three example do-files, then produces a ZIP plus SHA256SUMS. It excludes local environments, caches, old builds and unlisted binary assets. It never publishes anything.

The ZIP includes RELEASE.json with hashes for its contents and the test summary. Run `python tools/verify_release.py` inside the extracted archive to detect a mismatched or damaged package. Running the application or tests creates caches/output files; verification tolerates those but verifies every originally packaged file.

## Before announcing wider platform support

- Run the provided CI matrix on Windows, macOS and Linux using Python 3.11, 3.12 and 3.13.
- Manually check native display, keyboard completion, Unicode paths, high DPI, theme icons, data import/export, terminal interaction and cancellation on each operating system.
- Check the wheel and sdist from an unrelated directory; run all bundled lessons and at least demo.do plus everyday_coverage.do.
- Read docs/VALIDATION.md and disclose any platform checks still outstanding.
- Review the asset provenance and dependency obligations in docs/LICENSING.md.
- Publish source and wheel together, with checksums, changelog, known limitations and an actual support route. Repository/package names must be verified before publication.

The included CI workflow is a configuration, not evidence that native checks have passed. The local build records only checks actually run. This release has not been uploaded to GitHub Releases or PyPI by the build script.

