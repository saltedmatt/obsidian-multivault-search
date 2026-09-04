"""Matching search terms against notes and extracting their context.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

from ._meta import PROG
from .markdown import clean_markdown

TERM_SEP = " | "

HIGHLIGHT = "\x1b[1;33m"
RESET = "\x1b[0m"


def build_patterns(
    terms: Iterable[str],
    *,
    regex: bool = False,
    whole_word: bool = False,
    case_sensitive: bool = False,
) -> list[re.Pattern[str]]:
    flags = 0 if case_sensitive else re.IGNORECASE
    patterns: list[re.Pattern[str]] = []
    for term in terms:
        body = term if regex else re.escape(term)
        if whole_word:
            body = rf"(?<!\w)(?:{body})(?!\w)"
        try:
            patterns.append(re.compile(body, flags))
        except re.error as exc:
            raise SystemExit(f"{PROG}: invalid search pattern {term!r}: {exc}")
    return patterns


def context_for(text: str, match: re.Match[str], words: int, color: bool) -> str:
    """Context of a match: up to `words` words before and after it."""
    start, end = match.start(), match.end()
    if end == start:  # zero-length pattern (only possible in regex mode)
        end = min(len(text), start + 1)
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    while end < len(text) and not text[end].isspace():
        end += 1

    core = text[start:end].strip()
    if color:
        core = f"{HIGHLIGHT}{core}{RESET}"
    before = text[:start].rsplit(None, words)[-words:] if words else []
    after = text[end:].split(None, words)[:words] if words else []
    return " ".join([*before, core, *after])


def search_note(
    path: Path,
    patterns: Sequence[re.Pattern[str]],
    excludes: Sequence[re.Pattern[str]],
    words: int,
    require_all: bool,
    color: bool,
) -> str | None:
    """Return the note's context string, or None if it does not match."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"{PROG}: {path}: {exc}", file=sys.stderr)
        return None
    text = clean_markdown(raw)

    for pattern in excludes:
        if pattern.search(text) is not None:
            return None
    if not patterns:  # exclusions only: the note matches, without context
        return ""

    contexts: list[str] = []
    for pattern in patterns:
        match = pattern.search(text)
        if match is None:
            if require_all:
                return None
            continue
        contexts.append(context_for(text, match, words, color))
    if not contexts:
        return None
    return TERM_SEP.join(contexts)
