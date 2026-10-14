# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Offline notices shared by desktop, terminal and CLI."""

from importlib.resources import files

COPYRIGHT = "Copyright (C) 2026 Connor Baird"
NOTICE = (
    COPYRIGHT + "\n"
    "GNU GPL version 3 or later. You may redistribute and modify this program\n"
    "under that licence. This program comes with ABSOLUTELY NO WARRANTY.\n"
    "Type license for the full licence and third-party notices.\n"
    "Stata is a registered trademark of StataCorp LLC. StatBridge is independent\n"
    "and is not affiliated with, sponsored by or endorsed by StataCorp LLC."
)


def license_text():
    root = files("statbridge").joinpath("legal")
    return (
        NOTICE
        + "\n\n"
        + "\n\n".join(
            root.joinpath(name).read_text(encoding="utf-8")
            for name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md")
        )
    )
