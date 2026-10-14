# Security and privacy

This public beta is a local desktop/terminal application. It has no telemetry, account service or automatic upload of datasets. Installation downloads Python packages. Normal local analyses and bundled lessons work offline.

Do-files are instructions, not safe documents. They can read local files and write exports or logs to paths accessible to your account. Review scripts from other people before running them and keep backups. StatBridge does not provide a sandbox; unsupported shell, Python, ado and Mata commands are refused. File readers and numerical backends are third-party libraries, so keep your environment updated and avoid untrusted malformed files.

History and the working folder are remembered by default, as documented in README.md. Use the GUI History controls and the Remember working folder control, or terminal --no-history and --no-remember-cwd, on shared machines. Compatibility reports/logs can contain commands, values and file paths. Review them before sharing. Installation diagnostics contain package versions and basic platform information, without data, commands or personal paths.

Report ordinary bugs through the project's issue tracker where the release is hosted. For a suspected vulnerability use that host's private vulnerability reporting facility if enabled. If unavailable, request a private contact route from the maintainer without posting exploit details, credentials or sensitive files publicly. This package does not invent a security mailbox or promise response times.

No signed installers or automatic updater are included. Hashes in the archive detect accidental corruption; a checksum from the same untrusted source does not establish authenticity.

