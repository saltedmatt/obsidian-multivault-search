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
        # Escapes are resolved first, so the unescaped characters that appear
        # are not treated as formatting afterwards.
        (r"\*not emphasis\*", "not emphasis"),
        # The brackets survive as literal text: there is no link to unwrap.
        (r"\[not a link\]", "[not a link]"),
        (r"a \| b", "a b"),
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


@pytest.mark.xfail(
    strict=True,
    reason="known defect: _ESCAPE runs before _LINE_PREFIX, so an escaped "
    "marker at the start of a line unescapes into a real marker and is "
    "then stripped along with the escape",
)
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (r"\# not a heading", "# not a heading"),
        (r"\- not a bullet", "- not a bullet"),
        (r"\> not a quote", "> not a quote"),
    ],
)
def test_escaped_line_marker_keeps_its_character(raw: str, expected: str) -> None:
    """An escaped marker is literal text and should survive as such."""
    assert clean_markdown(raw) == expected


def test_cleaning_is_stable_on_already_clean_text() -> None:
    once = clean_markdown("# Title\n\nSome **text** with a [link](x).")
    assert once == "Title Some text with a link."
    assert clean_markdown(once) == once
