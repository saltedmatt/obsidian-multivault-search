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
        help=f"words before/after the match (default: {DEFAULT_CONTEXT_WORDS})",
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

    color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty())
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
    `__main__` module.
    """
    try:
        return main()
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        # Point stdout at /dev/null so that the interpreter's final flush
        # does not raise the same error again on the way out.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 141
