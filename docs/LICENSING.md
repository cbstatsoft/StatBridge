# Licensing, provenance and Stata compatibility

StatBridge Qt: Copyright (C) 2026 Connor Baird. Original project material is released under **GNU GPL version 3 or later**, with the full unchanged text in LICENSE. NOTICE explains copying permissions and warranty terms. Package metadata, source notices, the desktop Help menu, terminal startup and the license command identify the licence. The source archive contains build scripts and tests; a separately distributed wheel must retain notices and be accompanied by access to its corresponding source under the GPL.

## Independent product

Stata is a registered trademark of StataCorp LLC. StatBridge is not affiliated with, sponsored by or endorsed by StataCorp. The name is used descriptively for supported syntax and dataset interoperability. Use StatBridge branding in release listings. Do not use the Stata logo, distinctive lettering, icons or marketing artwork.

The implementation delegates statistical calculations to Python libraries. Reading a user's .dta/.do files does not redistribute the Stata application. Command names and familiar statistical concepts do not justify copying protected implementation or documentation. Compatibility is partial, with differences documented and unsupported syntax refused. No claim of official certification, complete equivalence or a measured percentage of Stata usage is made.

## Material audit for 0.7.1

| Material | Source and treatment |
| --- | --- |
| Python implementation | StatBridge source, plus the declared dtabnk and Minitab adaptations below |
| Toolbar icons | Original SVG geometry in statbridge/icons.py |
| Screenshots | StatBridge workspace previews; no Stata application screenshots are distributed |
| Learn content and examples | Project explanations and synthetic data; external manuals are linked, not bundled |
| dtabnk adaptation | Connor Baird, GPL-3.0-or-later; upstream commit and modifications recorded |
| Minitab portable reader | Adapted layout from R foreign, GPL-2.0-or-later; original attribution retained; distributed here under GPL-3.0-or-later |
| Native SAS test fixture | pyreadstat sample with upstream licence retained in tests/fixtures/PYREADSTAT_LICENSE |
| Python/Qt/statistics packages | Not copied into the release archive; installed separately, with their own licences |

The release builder includes only the approved source/documentation/example directories and known root files, and rejects unlisted binary assets. Provenance review is still necessary when adding new assets; filename checks cannot establish ownership.

No Stata executables, licence keys, ado/Mata source, help files or manual PDFs are part of this release. Do not add them to future releases without an appropriate rights basis. Existing notices for third-party adaptations must remain.

## Distribution

Keep LICENSE, NOTICE and THIRD_PARTY_NOTICES.md with source and installed distributions. Do not claim ownership of third-party components. If producing a frozen executable in future, inventory every bundled dependency, retain all required notices and provide the corresponding source as required by each licence. The current release is source plus a Python wheel, with no frozen proprietary components.

This is an engineering and provenance review, not a legal opinion or a guarantee of clearance. Jurisdiction, actual provenance and future contributions can affect the legal analysis. Trademark clearance for the StatBridge name itself has not been established.

## Primary references reviewed 14 October 2026

- [StataCorp terms, copyright and trademarks](https://www.stata.com/terms-of-use/)
- [GNU guidance on applying the GPL](https://www.gnu.org/licenses/gpl-howto.en.html)
- [GNU GPL version 3](https://www.gnu.org/licenses/gpl-3.0.html)
- [Python packaging metadata and licence files](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)

Links are references and do not grant permission to relicense external material.

