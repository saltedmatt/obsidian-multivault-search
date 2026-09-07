"""Tests for stripping markdown formatting off note text.

`clean_markdown` is what every search term is matched against, so each regex
it applies is pinned here individually; the cases at the end cover the
interactions between them, which is where the order of the substitutions
matters.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import pytest

from obsidian_multivault_search.markdown import clean_markdown


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Fences drop out, the code between them stays searchable.
        ("```python\ncode here\n```", "code here"),
        ("~~~\nfenced\n~~~", "fenced"),
        # Horizontal rules.
        ("---", ""),
        ("***", ""),
        ("* * *", ""),
        ("___", ""),
        # A table keeps its cells but loses the delimiter row and the pipes,
        # because "|" separates the contexts in the output.
        ("| a | b |\n|---|:--:|\n| 1 | 2 |", "a b 1 2"),
        ("text with | pipe", "text with pipe"),
        # Links: the display text survives, the target does not.
        ("[[Note Title]]", "Note Title"),
        ("[[Note|Alias]]", "Alias"),
        ("![[image.png]]", "image.png"),
        ("[text](http://example.com)", "text"),
        ("![alt](img.png)", "alt"),
        ("[](http://example.com)", ""),
        # HTML.
        ("<b>bold</b> and <br/>", "bold and"),
        # Line prefixes.
        ("## Heading", "Heading"),
        ("###### Deep", "Deep"),
        ("- item", "item"),
        ("* item", "item"),
        ("+ item", "item"),
        ("1. first\n2) second", "first second"),
        ("- [ ] todo item", "todo item"),
        ("- [x] done", "done"),
        ("> quoted\n>> deep", "quoted deep"),
        ("> - [ ] nested task", "nested task"),
        # Inline emphasis.
        ("**bold** _em_ `code` ==mark== ~~strike~~", "bold em code mark strike"),
        # Underscores inside a word are kept: identifiers stay searchable.
        ("snake_case_name and _leading", "snake_case_name and leading"),
        # Whitespace is flattened to single spaces on one line.
        ("a\n\nb   c", "a b c"),
        ("  padded  ", "padded"),
        ("", ""),
    ],
)
def test_clean_markdown(raw: str, expected: str) -> None:
    assert clean_markdown(raw) == expected


def test_hash_without_space_is_not_a_heading() -> None:
    """A tag keeps its text; only `#` followed by a space starts a heading."""
    assert clean_markdown("#tag stays") == "#tag stays"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Inline markers.
        (r"\*not emphasis\*", "*not emphasis*"),
        (r"\`not code\`", "`not code`"),
        (r"\[not a link\]", "[not a link]"),
        (r"\_leading underscore", "_leading underscore"),
        (r"a \< b \> c", "a < b > c"),
        # Line markers: these only get stripped at the start of a line, which
        # is exactly where unescaping too early used to lose them.
        (r"\# not a heading", "# not a heading"),
        (r"\- not a bullet", "- not a bullet"),
        (r"\> not a quote", "> not a quote"),
        (r"\--- not a rule", "--- not a rule"),
        # A backslash can escape itself.
        (r"a \\ b", "a \\ b"),
        # Structure around an escape is still recognised.
        (r"# Heading with \*stars\*", "Heading with *stars*"),
        # An escaped bracket means there is no link to unwrap, so the target
        # stays visible instead of being swallowed.
        (r"\[not a link\](http://example.com)", "[not a link](http://example.com)"),
        # Several escapes in one line keep their order.
        (r"\#one \*two\* \#three", "#one *two* #three"),
    ],
)
def test_escaped_characters_stay_literal(raw: str, expected: str) -> None:
    """An escaped character is text, not formatting: it has to survive every
    substitution unchanged."""
    assert clean_markdown(raw) == expected


def test_escaped_pipe_is_still_dropped() -> None:
    """The one exception: "|" separates the contexts in the output, so it may
    not reach it even when the note escaped it."""
    assert clean_markdown(r"a \| b") == "a b"


def test_nul_bytes_in_a_note_do_not_confuse_the_escape_handling() -> None:
    """The internal marker is built from NUL bytes, which a note may contain
    itself; an unknown marker is left alone rather than crashing."""
    assert clean_markdown("a \x000\x00 b") == "a \x000\x00 b"
    assert clean_markdown("\\# x \x009\x00") == "# x \x009\x00"


def test_cleaning_is_stable_on_already_clean_text() -> None:
    once = clean_markdown("# Title\n\nSome **text** with a [link](x).")
    assert once == "Title Some text with a link."
    assert clean_markdown(once) == once
