"""Tests for finding vaults and collecting the notes that belong to them.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

import pytest

from obsidian_multivault_search.vaults import find_vaults, iter_notes

MakeVault = Callable[[Path, str], Path]
WriteNote = Callable[[Path, str, str], Path]


def names(paths: Iterable[Path]) -> list[str]:
    return sorted(p.name for p in paths)


class TestFindVaults:
    def test_finds_vaults_and_ignores_plain_directories(self, tree: Path) -> None:
        assert names(find_vaults([tree])) == ["alpha", "beta", "inner"]

    def test_nested_vault_is_found_as_well(self, tree: Path) -> None:
        assert tree / "beta" / "inner" in find_vaults([tree])

    def test_pruned_directories_are_not_entered(self, tree: Path) -> None:
        """A vault below node_modules stays invisible."""
        assert tree / "node_modules" / "skipped" not in find_vaults([tree])

    def test_hidden_directories_are_not_entered(
        self, tmp_path: Path, make_vault: MakeVault
    ) -> None:
        make_vault(tmp_path / ".hidden", "buried")
        assert find_vaults([tmp_path]) == []

    def test_overlapping_roots_are_deduplicated(self, tree: Path) -> None:
        found = find_vaults([tree, tree / "beta"])
        assert names(found) == ["alpha", "beta", "inner"]

    def test_a_vault_given_as_the_root_is_found(self, tree: Path) -> None:
        assert names(find_vaults([tree / "alpha"])) == ["alpha"]

    def test_paths_are_expanded_and_resolved(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # `~` is read from HOME on POSIX and from USERPROFILE on Windows;
        # setting both keeps the test on the same footing everywhere.
        monkeypatch.setenv("HOME", str(tree))
        monkeypatch.setenv("USERPROFILE", str(tree))
        assert names(find_vaults(["~"])) == ["alpha", "beta", "inner"]

    @pytest.mark.parametrize(
        ("max_depth", "expected"),
        [
            (0, []),
            (1, ["alpha", "beta"]),
            (2, ["alpha", "beta", "inner"]),
            (None, ["alpha", "beta", "inner"]),
        ],
    )
    def test_max_depth_limits_the_descent(
        self, tree: Path, max_depth: int | None, expected: list[str]
    ) -> None:
        assert names(find_vaults([tree], max_depth=max_depth)) == expected

    def test_missing_root_is_reported_and_skipped(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        found = find_vaults([tree / "nowhere", tree])
        assert names(found) == ["alpha", "beta", "inner"]
        assert "not a directory" in capsys.readouterr().err

    def test_file_as_root_is_reported_and_skipped(
        self,
        tmp_path: Path,
        write_note: WriteNote,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        note = write_note(tmp_path, "loose.md", "text\n")
        assert find_vaults([note]) == []
        assert "not a directory" in capsys.readouterr().err

    def test_symlinks_are_only_followed_on_request(
        self, tmp_path: Path, make_vault: MakeVault, symlinks_available: None
    ) -> None:
        target = tmp_path / "outside"
        make_vault(target, "linked")
        root = tmp_path / "area"
        root.mkdir()
        (root / "link").symlink_to(target, target_is_directory=True)

        assert find_vaults([root]) == []
        assert names(find_vaults([root], follow_symlinks=True)) == ["linked"]


class TestIterNotes:
    def test_collects_markdown_recursively(self, tree: Path) -> None:
        alpha = tree / "alpha"
        assert names(iter_notes(alpha, {alpha})) == ["deploy.md", "old.md"]

    def test_hidden_directories_are_skipped(self, tree: Path) -> None:
        """`.trash/gone.md` must not show up."""
        alpha = tree / "alpha"
        assert "gone.md" not in names(iter_notes(alpha, {alpha}))

    def test_nested_vault_owns_its_own_notes(self, tree: Path) -> None:
        vaults = set(find_vaults([tree]))
        beta, inner = tree / "beta", tree / "beta" / "inner"
        assert names(iter_notes(beta, vaults)) == ["ideas.md"]
        assert names(iter_notes(inner, vaults)) == ["deep.md"]

    def test_without_the_vault_set_nested_notes_are_included(self, tree: Path) -> None:
        assert names(iter_notes(tree / "beta", set())) == ["deep.md", "ideas.md"]

    def test_only_markdown_files(
        self, tmp_path: Path, make_vault: MakeVault, write_note: WriteNote
    ) -> None:
        vault = make_vault(tmp_path, "v")
        write_note(vault, "note.md", "x")
        write_note(vault, "image.png", "x")
        write_note(vault, "data.markdown", "x")
        assert names(iter_notes(vault, {vault})) == ["note.md"]

    def test_extension_check_is_case_insensitive(
        self, tmp_path: Path, make_vault: MakeVault, write_note: WriteNote
    ) -> None:
        vault = make_vault(tmp_path, "v")
        write_note(vault, "Shouty.MD", "x")
        assert names(iter_notes(vault, {vault})) == ["Shouty.MD"]
