"""Command line interface: argument parsing, search run and output.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ._meta import PROG, __version__
from .search import build_patterns, search_note
from .vaults import find_vaults, iter_notes

DEFAULT_CONTEXT_WORDS = 3
DEFAULT_FIELD_SEP = "\t"

# Console mode flag and stream handle of the Windows API, needed to get a
# classic console host to interpret escape sequences.
_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
_STD_OUTPUT_HANDLE = -11


def use_utf8_output() -> None:
    """Put stdout and stderr on UTF-8, whatever the locale would prescribe.

    Notes are read as UTF-8, so every character in them can end up in the
    output. A redirected stream, however, encodes in the locale's codepage -
    cp1252 on a German Windows - which carries the accented letters but not
    the arrow, the check mark or the emoji that sit in a note just as often.
    Without this, `obmvs term > out.txt` ends in a UnicodeEncodeError over one
    such character instead of writing the result. On a console Python already
    encodes in UTF-8, so nothing changes there.

    `backslashreplace` covers the way back: a file name that the file system
    hands over as undecodable bytes stays printable as an escape instead of
    ending the run.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, OSError, ValueError):
            # Not a reconfigurable text stream - a caller may have replaced it
            # with anything, and `pythonw` has no streams at all. Whatever it
            # is, it stays as it is.
            continue


def _ansi_is_understood() -> bool:
    """Whether escape sequences reach the terminal as escape sequences.

    Outside Windows they always do. A Windows console interprets them only
    once the mode is set: Windows Terminal and PowerShell 7 set it themselves,
    the classic console host of `cmd.exe` does not and would spell the raw
    sequences out into the output.
    """
    if os.name != "nt":
        return True
    try:
        # Windows only, so the import cannot live at module level.
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False  # no console behind stdout, so nothing to switch on
        if mode.value & _ENABLE_VIRTUAL_TERMINAL_PROCESSING:
            return True
        return bool(
            kernel32.SetConsoleMode(
                handle, mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
            )
        )
    except (ImportError, AttributeError, OSError, ValueError):
        # No ctypes in this build, no `windll` behind it, or the call refused:
        # colour is a comfort, and none of this is worth a failed run.
        return False


def use_color(choice: str) -> bool:
    """Whether matches are highlighted, for `--color auto|always|never`."""
    if choice == "never":
        return False
    if choice == "auto" and not sys.stdout.isatty():
        return False
    # `always` is what one types to send colour through a pipe or into a file,
    # where there is no console mode to be switched on in the first place. It
    # keeps its promise even when the switch fails; `auto` stays plain rather
    # than littering the output with sequences nobody will interpret.
    return _ansi_is_understood() or choice == "always"


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Search notes across multiple Obsidian vaults.",
        epilog="Multiple search terms are combined with AND; "
        'quote phrases that belong together ("foo bar"). '
        "Terms excluded with -n always apply in addition (AND NOT).",
    )
    parser.add_argument("terms", nargs="*", metavar="TERM", help="search term(s)")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-n",
        "--not",
        dest="excludes",
        action="append",
        metavar="TERM",
        help="term that must NOT occur (repeatable)",
    )
    parser.add_argument(
        "-d",
        "--dir",
        dest="roots",
        action="append",
        metavar="PATH",
        help="search area (repeatable, default: home directory)",
    )
    parser.add_argument(
        "-C",
        "--context",
        type=int,
        default=DEFAULT_CONTEXT_WORDS,
        metavar="N",
        # Words, not lines - and the context never leaves the line the match
        # was found on, so N words per side is what a full line offers, not
        # what every match gets.
        help="adjacent words before/after the match, on its line "
        f"(default: {DEFAULT_CONTEXT_WORDS})",
    )
    parser.add_argument(
        "-s",
        "--case-sensitive",
        action="store_true",
        help="respect upper/lower case",
    )
    parser.add_argument(
        "-w", "--word", action="store_true", help="match whole words only"
    )
    parser.add_argument(
        "-e", "--regex", action="store_true", help="treat search terms as regexes"
    )
    parser.add_argument(
        "-o",
        "--or",
        dest="any_term",
        action="store_true",
        help="combine with OR instead of AND",
    )
    parser.add_argument(
        "-p",
        "--relpath",
        action="store_true",
        help="print the path relative to the vault instead of the note name",
    )
    parser.add_argument(
        "-F",
        "--sep",
        default=DEFAULT_FIELD_SEP,
        metavar="CHAR",
        help="output field separator (default: tab)",
    )
    parser.add_argument(
        "-L",
        "--list-vaults",
        action="store_true",
        help="list the vaults that were found and exit",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        metavar="N",
        help="maximum depth when looking for vaults",
    )
    parser.add_argument(
        "--follow", action="store_true", help="follow symlinks (default: no)"
    )
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="highlight matches (default: auto)",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=min(32, (os.cpu_count() or 4) * 4),
        metavar="N",
        help="parallel reads",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    excludes: list[str] = args.excludes or []
    if not args.terms and not excludes and not args.list_vaults:
        print(f"{PROG}: no search term given", file=sys.stderr)
        return 2
    if args.context < 0:
        print(f"{PROG}: --context must not be negative", file=sys.stderr)
        return 2

    roots = args.roots or [Path.home()]
    vaults = find_vaults(roots, max_depth=args.max_depth, follow_symlinks=args.follow)

    if args.list_vaults:
        for vault in sorted(vaults, key=lambda v: (v.name.casefold(), str(v))):
            print(f"{vault.name}{args.sep}{vault}")
        return 0 if vaults else 1

    if not vaults:
        print(f"{PROG}: no Obsidian vaults found", file=sys.stderr)
        return 1

    color = use_color(args.color)
    pattern_opts = dict(
        regex=args.regex,
        whole_word=args.word,
        case_sensitive=args.case_sensitive,
    )
    patterns = build_patterns(args.terms, **pattern_opts)
    exclude_patterns = build_patterns(excludes, **pattern_opts)
    vault_set = set(vaults)

    notes = [
        (vault, note)
        for vault in vaults
        for note in iter_notes(vault, vault_set, follow_symlinks=args.follow)
    ]

    def work(item: tuple[Path, Path]) -> tuple[str, str, str] | None:
        vault, note = item
        context = search_note(
            note,
            patterns,
            exclude_patterns,
            args.context,
            not args.any_term,
            color,
        )
        if context is None:
            return None
        if args.relpath:
            name = str(note.relative_to(vault).with_suffix(""))
        else:
            name = note.stem
        return (vault.name, name, context)

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = [r for r in pool.map(work, notes) if r is not None]

    results.sort(key=lambda r: (r[0].casefold(), r[1].casefold(), r[2]))
    for row in results:
        # Without positive search terms (-n only) there is no context.
        print(args.sep.join(row if row[2] else row[:2]))
    return 0 if results else 1


def cli() -> int:
    """Entry point of the installed console script.

    The generated wrapper only does `sys.exit(cli())`, so the handling of an
    interrupted or truncated run has to live here rather than in the
    `__main__` module. The same goes for the streams: owning them is the
    program's business, not that of `main`, which stays callable from code
    that has arranged its own output.
    """
    use_utf8_output()
    try:
        return main()
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        # Point stdout at /dev/null so that the interpreter's final flush
        # does not raise the same error again on the way out.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 141
