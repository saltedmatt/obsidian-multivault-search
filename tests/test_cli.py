"""End-to-end tests of the command line interface.

`main` returns the process exit code and writes to stdout/stderr, so the
contract documented in the README - output format, exit codes 0/1/2 - is
tested here by calling it directly, without a subprocess.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from obsidian_multivault_search import __version__, cli, main
from obsidian_multivault_search.search import HIGHLIGHT, RESET

# The package exports a function named `cli`, which shadows the submodule of
# the same name; the module object has to be fetched explicitly.
cli_module = importlib.import_module("obsidian_multivault_search.cli")

MakeVault = Callable[[Path, str], Path]


@pytest.fixture
def run(tree: Path, capsys: pytest.CaptureFixture[str]):
    """Run the CLI against the fixture tree and return code, rows and stderr.

    Every call passes `-d`, so no test ever depends on the real home
    directory, and `--color never` unless the test asks otherwise.
    """

    def _run(*argv: str, area: Path | None = None) -> tuple[int, list[str], str]:
        args = ["-d", str(area if area is not None else tree), *argv]
        code = main(args)
        captured = capsys.readouterr()
        rows = captured.out.splitlines()
        return code, rows, captured.err

    return _run


def fields(rows: list[str], sep: str = "\t") -> list[list[str]]:
    return [row.split(sep) for row in rows]


class TestUsageErrors:
    def test_no_term_at_all(self, run) -> None:
        code, rows, err = run()
        assert code == 2
        assert rows == []
        assert "no search term given" in err

    def test_negative_context(self, run) -> None:
        code, _, err = run("kubernetes", "-C", "-1")
        assert code == 2
        assert "--context must not be negative" in err

    def test_unknown_option(self, run) -> None:
        with pytest.raises(SystemExit) as exc:
            run("--nope")
        assert exc.value.code == 2

    def test_invalid_color_choice(self, run) -> None:
        with pytest.raises(SystemExit) as exc:
            run("kubernetes", "--color", "bogus")
        assert exc.value.code == 2

    def test_invalid_regex(self, run) -> None:
        with pytest.raises(SystemExit) as exc:
            run("a[", "-e")
        assert "invalid search pattern" in str(exc.value)

    def test_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0
        assert __version__ in capsys.readouterr().out


class TestListVaults:
    def test_lists_name_and_path(self, run, tree: Path) -> None:
        code, rows, _ = run("-L")
        assert code == 0
        assert fields(rows) == [
            ["alpha", str(tree / "alpha")],
            ["beta", str(tree / "beta")],
            ["inner", str(tree / "beta" / "inner")],
        ]

    def test_no_vaults_found(self, run, empty_area: Path) -> None:
        code, rows, _ = run("-L", area=empty_area)
        assert code == 1
        assert rows == []

    def test_honours_the_field_separator(self, run) -> None:
        _, rows, _ = run("-L", "-F", ";")
        assert all(";" in row for row in rows)


class TestSearch:
    def test_matches_across_vaults(self, run) -> None:
        code, rows, _ = run("kubernetes")
        assert code == 0
        assert [(f[0], f[1]) for f in fields(rows)] == [
            ("alpha", "deploy"),
            ("alpha", "old"),
            ("inner", "deep"),
        ]

    def test_context_is_the_third_field(self, run) -> None:
        _, rows, _ = run("kubernetes")
        assert fields(rows)[2] == ["inner", "deep", "kubernetes inside the inner"]

    def test_context_width(self, run) -> None:
        _, rows, _ = run("kubernetes", "-C", "1")
        assert fields(rows)[2][2] == "kubernetes inside"

    def test_no_match_exits_one(self, run) -> None:
        code, rows, _ = run("nonexistentterm")
        assert code == 1
        assert rows == []

    def test_no_vaults_is_reported(self, run, empty_area: Path) -> None:
        code, rows, err = run("kubernetes", area=empty_area)
        assert code == 1
        assert rows == []
        assert "no Obsidian vaults found" in err

    def test_notes_outside_a_vault_are_ignored(self, run) -> None:
        """plain/README.md and node_modules/skipped/dep.md contain the term
        as well, but neither is part of a searchable vault."""
        _, rows, _ = run("kubernetes")
        assert {f[1] for f in fields(rows)} == {"deploy", "old", "deep"}

    def test_nested_vault_owns_its_note(self, run) -> None:
        """deep.md sits below beta but belongs to inner."""
        _, rows, _ = run("kubernetes")
        assert ["inner", "deep"] in [f[:2] for f in fields(rows)]

    def test_several_terms_are_anded(self, run) -> None:
        _, rows, _ = run("kubernetes", "helm")
        assert [f[:2] for f in fields(rows)] == [["alpha", "old"]]

    def test_or_mode(self, run) -> None:
        _, rows, _ = run("helm", "ideas", "-o")
        assert [f[:2] for f in fields(rows)] == [["alpha", "old"], ["beta", "ideas"]]

    def test_or_mode_joins_the_contexts_of_the_terms_that_matched(self, run) -> None:
        _, rows, _ = run("kubernetes", "helm", "-o")
        contexts = {f[1]: f[2] for f in fields(rows)}
        assert " | " in contexts["old"]
        assert " | " not in contexts["deploy"]

    def test_exclusion(self, run) -> None:
        _, rows, _ = run("kubernetes", "-n", "helm")
        assert [f[:2] for f in fields(rows)] == [["alpha", "deploy"], ["inner", "deep"]]

    def test_exclusion_applies_in_or_mode_too(self, run) -> None:
        _, rows, _ = run("kubernetes", "helm", "-o", "-n", "helm")
        assert [f[:2] for f in fields(rows)] == [["alpha", "deploy"], ["inner", "deep"]]

    def test_exclusion_only_has_no_context_column(self, run) -> None:
        code, rows, _ = run("-n", "kubernetes")
        assert code == 0
        assert fields(rows) == [["beta", "ideas"]]

    def test_case_sensitive(self, run) -> None:
        assert run("Kubernetes")[0] == 0
        assert run("Kubernetes", "-s")[0] == 1

    def test_whole_word(self, run) -> None:
        assert run("kube")[0] == 0  # plain search matches inside a word
        assert run("kube", "-w")[0] == 1
        assert run("kubernetes", "-w")[0] == 0

    def test_regex_mode(self, run) -> None:
        _, rows, _ = run("kuber.*tes", "-e")
        assert len(rows) == 3

    def test_relpath_shows_the_path_below_the_vault(self, run) -> None:
        _, rows, _ = run("kubernetes", "-p")
        assert [f[1] for f in fields(rows)] == ["archive/old", "deploy", "deep"]

    def test_custom_separator(self, run) -> None:
        _, rows, _ = run("kubernetes", "-F", ";")
        assert all("\t" not in row for row in rows)
        assert fields(rows, ";")[0][:2] == ["alpha", "deploy"]

    def test_jobs_do_not_change_the_result(self, run) -> None:
        assert run("kubernetes", "-j", "1")[1] == run("kubernetes", "-j", "8")[1]

    def test_max_depth_limits_the_vaults_searched(self, run) -> None:
        """`inner` lies too deep to be recognised as a vault, so its note is
        attributed to the enclosing vault rather than dropped."""
        _, rows, _ = run("kubernetes", "--max-depth", "1")
        assert [f[:2] for f in fields(rows)] == [
            ["alpha", "deploy"],
            ["alpha", "old"],
            ["beta", "deep"],
        ]


class TestColor:
    def test_never(self, run) -> None:
        _, rows, _ = run("kubernetes", "--color", "never")
        assert all(HIGHLIGHT not in row for row in rows)

    def test_always(self, run) -> None:
        _, rows, _ = run("kubernetes", "--color", "always")
        assert all(f"{HIGHLIGHT}kubernetes{RESET}" in row for row in rows)

    def test_auto_stays_plain_when_stdout_is_not_a_terminal(self, run) -> None:
        _, rows, _ = run("kubernetes", "--color", "auto")
        assert all(HIGHLIGHT not in row for row in rows)


class TestSorting:
    def test_vault_then_note_case_insensitively(
        self, tmp_path: Path, make_vault: MakeVault, capsys: pytest.CaptureFixture[str]
    ) -> None:
        for vault_name, note_names in [("Beta", ["b", "A"]), ("alpha", ["Z"])]:
            vault = make_vault(tmp_path, vault_name)
            for note_name in note_names:
                (vault / f"{note_name}.md").write_text("term\n", encoding="utf-8")

        assert main(["-d", str(tmp_path), "term"]) == 0
        rows = capsys.readouterr().out.splitlines()
        assert [row.split("\t")[:2] for row in rows] == [
            ["alpha", "Z"],
            ["Beta", "A"],
            ["Beta", "b"],
        ]


class TestEntryPoints:
    def test_cli_returns_the_exit_code_of_main(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["obmvs"])
        assert cli() == 2  # no search term given

    def test_keyboard_interrupt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def interrupt(argv=None):
            raise KeyboardInterrupt

        monkeypatch.setattr(cli_module, "main", interrupt)
        assert cli() == 130

    def test_broken_pipe(self) -> None:
        """`cli` redirects stdout to /dev/null on the way out, so this one
        has to run in a process of its own."""
        script = (
            "import importlib, sys\n"
            "m = importlib.import_module('obsidian_multivault_search.cli')\n"
            "def boom(argv=None):\n"
            "    raise BrokenPipeError\n"
            "m.main = boom\n"
            "sys.exit(m.cli())\n"
        )
        assert (
            subprocess.run([sys.executable, "-c", script], check=False).returncode
            == 141
        )

    def test_python_dash_m(self, tree: Path) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "obsidian_multivault_search", "-d", str(tree), "-L"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "alpha" in result.stdout
