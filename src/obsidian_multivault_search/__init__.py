"""obsidian-multivault-search - search notes across multiple Obsidian vaults.

A vault is a directory containing an `.obsidian` subfolder; the vault name is
the name of that directory. Only `.md` files inside such vaults are searched.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

from ._meta import PROG, __version__
from .cli import cli, main

__all__ = ["PROG", "__version__", "cli", "main"]
