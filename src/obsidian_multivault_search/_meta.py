"""Package metadata shared by all modules: version and program name.

Kept in its own module so that the package `__init__` can import the CLI
without the CLI importing a half-initialised package back.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import os
import sys

__version__ = "0.1.1"


def _program_name() -> str:
    """Name the tool was invoked as, so that messages match whatever the user
    typed (the long command or the short `obmvs` alias).

    Not every invocation carries a usable name: `python -m` leaves `-m` in
    argv[0] while the package is being imported and replaces it with the path
    of `__main__.py` afterwards, `python -c` leaves `-c`.
    """
    name = os.path.basename(sys.argv[0])
    if not name or name.startswith("-") or name == "__main__.py":
        return "obsidian-multivault-search"
    return name


PROG = _program_name()
