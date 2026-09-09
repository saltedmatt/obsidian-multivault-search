"""Matching search terms against notes and extracting their context.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import bisect
import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

from ._meta import PROG
from .markdown import clean_markdown_lines

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


def context_for(
    text: str,
    match: re.Match[str],
    words: int,
    color: bool,
    bounds: tuple[int, int] | None = None,
) -> str:
    """Context of a match: adjacent words before and after it, `words` per side.

    The count is in words, not lines. `bounds` limits the context to the note
    line the match sits on; the words on the other side of a line break belong
    to a different paragraph or heading often enough that reaching into them
    only misleads. Without `bounds` the whole of `text` is available.

    A side that runs out of words early hands its share to the other one, so
    the window keeps its total width of `2 * words` even when the match sits
    at the beginning or the end of its line.
    """
    low, high = bounds if bounds is not None else (0, len(text))
    start, end = match.start(), match.end()
    if end == start:  # zero-length pattern (only possible in regex mode)
        end = min(high, start + 1)
    while start > low and not text[start - 1].isspace():
        start -= 1
    while end < high and not text[end].isspace():
        end += 1

    core = text[start:end].strip()
    if color:
        core = f"{HIGHLIGHT}{core}{RESET}"

    before_words = text[low:start].split()
    after_words = text[end:high].split()
    # Both sides are capped a second time, so the hand-over works in either
    # direction without either side ever exceeding what its line offers.
    budget = 2 * words
    take_before = min(words, len(before_words))
    take_after = min(budget - take_before, len(after_words))
    take_before = min(budget - take_after, len(before_words))

    # Not `before_words[-take_before:]`: that would return the whole list for
    # a count of zero.
    before = before_words[len(before_words) - take_before :]
    return " ".join([*before, core, *after_words[:take_after]])


def _line_bounds(
    starts: Sequence[int], ends: Sequence[int], match: re.Match[str]
) -> tuple[int, int]:
    """Span of the note lines the match touches, as offsets into the joined text."""
    if not starts:
        return (0, 0)
    first = bisect.bisect_right(starts, match.start()) - 1
    last = bisect.bisect_right(starts, max(match.start(), match.end() - 1)) - 1
    return (starts[first], ends[last])


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
    lines = clean_markdown_lines(raw)
    # Terms are still matched against the whole note as one line, so a phrase
    # broken across a line break is found just as before; only the context is
    # cut back to the line it was found on.
    text = " ".join(lines)

    for pattern in excludes:
        if pattern.search(text) is not None:
            return None
    if not patterns:  # exclusions only: the note matches, without context
        return ""

    starts: list[int] = []
    ends: list[int] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        ends.append(offset + len(line))
        offset += len(line) + 1  # the single space `join` put in

    contexts: list[str] = []
    for pattern in patterns:
        match = pattern.search(text)
        if match is None:
            if require_all:
                return None
            continue
        bounds = _line_bounds(starts, ends, match)
        contexts.append(context_for(text, match, words, color, bounds))
    if not contexts:
        return None
    return TERM_SEP.join(contexts)
