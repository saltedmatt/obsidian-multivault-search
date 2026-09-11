"""Shared fixtures: helpers for building temporary trees of Obsidian vaults.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from obsidian_multivault_search import vaults as vaults_module

MakeVault = Callable[[Path, str], Path]
WriteNote = Callable[[Path, str, str], Path]
WriteConfig = Callable[[Any], Path]


def _make_vault(parent: Path, name: str) -> Path:
    """Create a directory that counts as a vault (has an `.obsidian` folder)."""
    vault = parent / name
    (vault / ".obsidian").mkdir(parents=True)
    return vault


def _write_note(directory: Path, relpath: str, text: str) -> Path:
    note = directory / relpath
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(text, encoding="utf-8")
    return note


@pytest.fixture
def make_vault() -> MakeVault:
    return _make_vault


@pytest.fixture
def write_note() -> WriteNote:
    return _write_note


@pytest.fixture
def symlinks_available(tmp_path: Path) -> None:
    """Skip the test unless this process may create directory symlinks.

    On POSIX that is always the case. Windows grants the privilege only with
    developer mode or elevation, so the check has to be the attempt itself
    rather than the platform: where the privilege is there, the test runs and
    covers the same behaviour as everywhere else.
    """
    probe = tmp_path / "symlink-probe"
    try:
        probe.symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"creating symlinks is not permitted here: {exc}")
    probe.unlink()


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every variable a home or config directory is derived from here.

    Windows reads `USERPROFILE` and `APPDATA`, POSIX reads `HOME`, Linux also
    `XDG_CONFIG_HOME`. Setting them all keeps the tests on one footing, so
    that the platform the suite happens to run on does not decide what it
    covers.
    """
    home = tmp_path / "home"
    home.mkdir()
    for name in ("HOME", "USERPROFILE", "APPDATA", "XDG_CONFIG_HOME"):
        monkeypatch.setenv(name, str(home))
    return home


@pytest.fixture
def write_config(fake_home: Path) -> WriteConfig:
    """Write Obsidian's vault list to the place it is read from here.

    Which place that is differs per platform, so the location comes from the
    code under test rather than being spelled out a second time.
    """

    def write(data: Any) -> Path:
        config = vaults_module._config_files()[0]
        config.parent.mkdir(parents=True, exist_ok=True)
        text = data if isinstance(data, str) else json.dumps(data)
        config.write_text(text, encoding="utf-8")
        return config

    return write


@pytest.fixture
def empty_area(tmp_path: Path) -> Path:
    """A search area that contains no vault at all."""
    area = tmp_path / "empty"
    area.mkdir()
    return area


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A search area covering the cases the traversal has to get right.

    alpha/                  vault
        deploy.md
        archive/old.md
        .trash/gone.md      hidden directory, never searched
    beta/                   vault
        ideas.md
        inner/              vault inside a vault
            deep.md
    plain/README.md         no .obsidian, so not a vault
    node_modules/skipped/   vault below a pruned directory
    """
    root = tmp_path / "area"
    root.mkdir()

    alpha = _make_vault(root, "alpha")
    _write_note(alpha, "deploy.md", "# Deploy notes\n\nWe run **kubernetes** here.\n")
    _write_note(alpha, "archive/old.md", "Old kubernetes notes about helm charts.\n")
    _write_note(alpha, ".trash/gone.md", "kubernetes in the trash\n")

    beta = _make_vault(root, "beta")
    _write_note(beta, "ideas.md", "Just some ideas, nothing more.\n")
    inner = _make_vault(beta, "inner")
    _write_note(inner, "deep.md", "kubernetes inside the inner vault\n")

    _write_note(root, "plain/README.md", "kubernetes but not in a vault\n")

    skipped = _make_vault(root / "node_modules", "skipped")
    _write_note(skipped, "dep.md", "kubernetes in a dependency\n")

    return root
