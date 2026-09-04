"""Support for `python -m obsidian_multivault_search`.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import sys

from .cli import cli

if __name__ == "__main__":
    sys.exit(cli())
