"""Finding vaults and the notes that belong to them.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

from ._meta import PROG

# Directories that are never entered while searching (in addition to every
# hidden directory, notably .obsidian, .trash and .git).
SKIP_DIRS = frozenset({"node_modules", "__pycache__", "venv", ".venv", "site-packages"})

# The file in which Obsidian itself keeps every vault it has ever opened.
CONFIG_NAME = "obsidian.json"


def _prunable(names: list[str], skip: set[str] | frozenset[str]) -> list[str]:
    return sorted(n for n in names if not n.startswith(".") and n not in skip)


def _config_files() -> list[Path]:
    """Where Obsidian's vault list may sit, per platform.

    Only the first existing one is of interest in practice, but a sandboxed
    installation on Linux puts its configuration somewhere else entirely, so
    every candidate is read and the results are merged.
    """
    try:
        home = Path.home()
    except (OSError, RuntimeError):
        return []
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        dirs = [Path(appdata) if appdata else home / "AppData" / "Roaming"]
    elif sys.platform == "darwin":
        dirs = [home / "Library" / "Application Support"]
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        dirs = [
            Path(xdg) if xdg else home / ".config",
            home / ".var" / "app" / "md.obsidian.Obsidian" / "config",  # Flatpak
            home / "snap" / "obsidian" / "current" / ".config",  # Snap
        ]
    return [d / "obsidian" / CONFIG_NAME for d in dirs]


def registered_vaults() -> list[Path]:
    """The vault directories Obsidian knows about, read from its own config.

    This is what lets a vault on another drive be found without walking that
    drive - the common case on Windows, where the home directory need not
    hold a vault at all.

    The file is no documented interface, so everything about it is treated as
    optional: a missing file, unreadable JSON, an unexpected shape or a path
    that has since been deleted is passed over silently, leaving the home
    directory as the source it has always been.
    """
    found: list[Path] = []
    seen: set[Path] = set()
    for config in _config_files():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        entries = data.get("vaults") if isinstance(data, dict) else None
        if not isinstance(entries, dict):
            continue
        for entry in entries.values():
            path = entry.get("path") if isinstance(entry, dict) else None
            if not isinstance(path, str) or not path:
                continue
            try:
                vault = Path(path).expanduser().resolve()
            except OSError:
                continue
            if vault not in seen and vault.is_dir():
                seen.add(vault)
                found.append(vault)
    return found


def _without_nested(roots: Iterable[Path]) -> list[Path]:
    """Drop every root that already lies inside another one.

    Overlapping roots yield the same vaults either way - `find_vaults` sees to
    that - but each one is walked again, and the home directory swallows most
    registered vaults anyway.
    """
    kept: list[Path] = []
    for root in sorted(set(roots), key=lambda p: (len(p.parts), str(p))):
        if not any(k == root or k in root.parents for k in kept):
            kept.append(root)
    return kept


def default_roots() -> list[Path]:
    """The search area when no `-d` is given.

    The home directory, as before, plus every vault Obsidian has on file -
    the latter covers what lies outside the home directory, the former the
    vaults that have never been opened in Obsidian.
    """
    roots = registered_vaults()
    try:
        roots.append(Path.home().resolve())
    except (OSError, RuntimeError):
        # No home to speak of; whatever came out of the config has to do.
        pass
    return _without_nested(roots)


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
