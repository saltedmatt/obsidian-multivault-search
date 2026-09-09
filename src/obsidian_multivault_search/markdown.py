"""Stripping markdown formatting off note text.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import re

_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+.!|~=<>-])")
_FENCE_LINE = re.compile(r"^[ \t]*(?:```|~~~).*$", re.MULTILINE)
_RULE_LINE = re.compile(r"^[ \t]*([-*_])(?:[ \t]*\1){2,}[ \t]*$", re.MULTILINE)
# Delimiter row of a markdown table, e.g. |---|:--:|
_TABLE_RULE = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(?:\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*$",
    re.MULTILINE,
)
_WIKILINK = re.compile(r"!?\[\[([^\]|\n]*?)(?:\|([^\]\n]*?))?\]\]")
_MDLINK = re.compile(r"!?\[([^\]\n]*)\]\([^)\n]*\)")
_HTML_TAG = re.compile(r"</?[A-Za-z][^>\n]{0,200}>")
_LINE_PREFIX = re.compile(
    r"^[ \t]{0,8}(?:>[ \t]?)*[ \t]*"
    r"(?:#{1,6}[ \t]+|[-*+][ \t]+(?:\[[ xX~/!?-]\][ \t]+)?|\d+[.)][ \t]+)",
    re.MULTILINE,
)
_QUOTE_PREFIX = re.compile(r"^[ \t]{0,8}(?:>[ \t]?)+", re.MULTILINE)
_EMPHASIS = re.compile(r"\*+|~~+|==+|`+")
_UNDERSCORE = re.compile(r"(?<!\w)_+|_+(?!\w)")
_WHITESPACE = re.compile(r"\s+")
# An escaped character is literal text, so it has to be hidden from every
# pattern below - unescaping first would turn "\#" into a heading marker that
# is then stripped again. None of the substitutions can produce a NUL byte,
# and NUL is not whitespace, so the marker comes out the other end intact.
_MARKER = re.compile("\x00(\\d+)\x00")


def clean_markdown_lines(text: str) -> list[str]:
    """Clean every line on its own and drop the ones that end up empty.

    Every substitution below is anchored to a line or to single characters, so
    cleaning line by line gives the same result as cleaning the whole note at
    once. Keeping the lines apart is what lets the caller cut a context that
    stops at the end of the line the match was found on.
    """
    return [cleaned for line in text.splitlines() if (cleaned := _clean_line(line))]


def clean_markdown(text: str) -> str:
    """Strip markdown formatting characters and flatten the text into a
    single, normalised line."""
    return " ".join(clean_markdown_lines(text))


def _clean_line(text: str) -> str:
    escaped: list[str] = []

    def hide(match: re.Match[str]) -> str:
        char = match.group(1)
        # "|" separates the contexts in the output and never survives,
        # whether it was escaped or not.
        if char == "|":
            return " "
        escaped.append(char)
        return f"\x00{len(escaped) - 1}\x00"

    def restore(match: re.Match[str]) -> str:
        index = int(match.group(1))
        # A note containing NUL bytes can carry a marker of its own.
        return escaped[index] if index < len(escaped) else match.group(0)

    text = _ESCAPE.sub(hide, text)
    text = _FENCE_LINE.sub(" ", text)
    text = _RULE_LINE.sub(" ", text)
    text = _TABLE_RULE.sub(" ", text)
    text = _WIKILINK.sub(lambda m: m.group(2) or m.group(1), text)
    text = _MDLINK.sub(r"\1", text)
    text = _HTML_TAG.sub(" ", text)
    text = _LINE_PREFIX.sub("", text)
    text = _QUOTE_PREFIX.sub("", text)
    text = _EMPHASIS.sub("", text)
    text = _UNDERSCORE.sub("", text)
    # Drop table pipes: "|" separates the contexts in the output.
    text = text.replace("|", " ")
    text = _WHITESPACE.sub(" ", text).strip()
    return _MARKER.sub(restore, text) if escaped else text
