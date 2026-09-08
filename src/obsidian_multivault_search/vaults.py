"""Finding vaults and the notes that belong to them.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

from ._meta import PROG

# Directories that are never entered while searching (in addition to every
# hidden directory, notably .obsidian, .trash and .git).
SKIP_DIRS = frozenset({"node_modules", "__pycache__", "venv", ".venv", "site-packages"})


def _prunable(names: list[str], skip: set[str] | frozenset[str]) -> list[str]:
    return sorted(n for n in names if not n.startswith(".") and n not in skip)


def find_vaults(
    roots: Iterable[str | os.PathLike[str]],
    max_depth: int | None = None,
    follow_symlinks: bool = False,
) -> list[Path]:
    """All vault directories below the given roots."""
    vaults: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            root = Path(root).expanduser().resolve()
        except OSError as exc:
            print(f"{PROG}: {root}: {exc}", file=sys.stderr)
            continue
        if not root.is_dir():
            print(f"{PROG}: {root}: not a directory", file=sys.stderr)
            continue
        base_depth = len(root.parts)
        for dirpath, dirnames, _ in os.walk(
            root, followlinks=follow_symlinks, onerror=lambda e: None
        ):
            here = Path(dirpath)
            if ".obsidian" in dirnames and here not in seen:
                seen.add(here)
                vaults.append(here)
            if max_depth is not None and len(here.parts) - base_depth >= max_depth:
                dirnames[:] = []
                continue
            dirnames[:] = _prunable(dirnames, SKIP_DIRS)
    return vaults


def iter_notes(
    vault: Path, other_vaults: set[Path], follow_symlinks: bool = False
) -> Iterator[Path]:
    """All .md files of a vault; nested vaults own their own notes."""
    for dirpath, dirnames, filenames in os.walk(
        vault, followlinks=follow_symlinks, onerror=lambda e: None
    ):
        here = Path(dirpath)
        dirnames[:] = [
            n for n in _prunable(dirnames, SKIP_DIRS) if here / n not in other_vaults
        ]
        for name in filenames:
            if name.lower().endswith(".md"):
                yield here / name
