"""Stripping markdown formatting off note text.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import re

_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+.!|~=<>-])")
_FENCE_LINE = re.compile(r"^[ \t]*(?:```|~~~).*$", re.M)
_RULE_LINE = re.compile(r"^[ \t]*([-*_])(?:[ \t]*\1){2,}[ \t]*$", re.M)
# Delimiter row of a markdown table, e.g. |---|:--:|
_TABLE_RULE = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(?:\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*$", re.M
)
_WIKILINK = re.compile(r"!?\[\[([^\]|\n]*?)(?:\|([^\]\n]*?))?\]\]")
_MDLINK = re.compile(r"!?\[([^\]\n]*)\]\([^)\n]*\)")
_HTML_TAG = re.compile(r"</?[A-Za-z][^>\n]{0,200}>")
_LINE_PREFIX = re.compile(
    r"^[ \t]{0,8}(?:>[ \t]?)*[ \t]*"
    r"(?:#{1,6}[ \t]+|[-*+][ \t]+(?:\[[ xX~/!?-]\][ \t]+)?|\d+[.)][ \t]+)",
    re.M,
)
_QUOTE_PREFIX = re.compile(r"^[ \t]{0,8}(?:>[ \t]?)+", re.M)
_EMPHASIS = re.compile(r"\*+|~~+|==+|`+")
_UNDERSCORE = re.compile(r"(?<!\w)_+|_+(?!\w)")
_WHITESPACE = re.compile(r"\s+")


def clean_markdown(text: str) -> str:
    """Strip markdown formatting characters and flatten the text into a
    single, normalised line."""
    text = _ESCAPE.sub(r"\1", text)
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
    return _WHITESPACE.sub(" ", text).strip()
