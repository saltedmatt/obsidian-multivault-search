"""Tests for pattern building, context extraction and note matching.

SPDX-License-Identifier: Apache-2.0 OR MIT
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from obsidian_multivault_search.search import (
    HIGHLIGHT,
    RESET,
    TERM_SEP,
    build_patterns,
    context_for,
    search_note,
)

SENTENCE = "one two three four TARGET five six seven eight"


def one_context(text: str, term: str, words: int = 3, color: bool = False, **opts):
    """Context of the first match of a single term, as the CLI would build it."""
    pattern = build_patterns([term], **opts)[0]
    match = pattern.search(text)
    assert match is not None
    return context_for(text, match, words, color)


class TestBuildPatterns:
    def test_plain_terms_are_literal(self) -> None:
        (pattern,) = build_patterns(["a.c"])
        assert pattern.search("a.c") is not None
        assert pattern.search("abc") is None

    def test_regex_mode_keeps_metacharacters(self) -> None:
        (pattern,) = build_patterns([r"a.c"], regex=True)
        assert pattern.search("abc") is not None

    def test_case_insensitive_by_default(self) -> None:
        (pattern,) = build_patterns(["target"])
        assert pattern.search("TARGET") is not None

    def test_case_sensitive_on_request(self) -> None:
        (pattern,) = build_patterns(["target"], case_sensitive=True)
        assert pattern.search("TARGET") is None
        assert pattern.search("target") is not None

    def test_whole_word_does_not_match_inside_a_word(self) -> None:
        (pattern,) = build_patterns(["foo"], whole_word=True)
        assert pattern.search("foobar") is None
        assert pattern.search("bar foo baz") is not None

    def test_whole_word_wraps_alternations_as_a_group(self) -> None:
        """Without the group around the body, `foo|bar` would bind the word
        boundaries to the first and last branch only."""
        (pattern,) = build_patterns(["foo|bar"], regex=True, whole_word=True)
        assert pattern.search("barbecue") is None
        assert pattern.search("a bar") is not None

    def test_empty_term_list(self) -> None:
        assert build_patterns([]) == []

    def test_invalid_regex_exits_with_a_message(self) -> None:
        with pytest.raises(SystemExit) as exc:
            build_patterns(["a["], regex=True)
        assert "invalid search pattern" in str(exc.value)


class TestContextFor:
    def test_words_before_and_after(self) -> None:
        assert one_context(SENTENCE, "target") == "two three four TARGET five six seven"

    def test_no_context_words(self) -> None:
        assert one_context(SENTENCE, "target", words=0) == "TARGET"

    def test_more_words_than_available(self) -> None:
        assert one_context(SENTENCE, "target", words=99) == SENTENCE

    def test_match_at_the_start_spends_the_unused_share_on_the_other_side(
        self,
    ) -> None:
        """Nothing before the match, so all six words come from behind it."""
        assert one_context("TARGET a b c d e f g", "target") == "TARGET a b c d e f"

    def test_match_at_the_end_spends_the_unused_share_on_the_other_side(self) -> None:
        assert one_context("a b c d e f g TARGET", "target") == "b c d e f g TARGET"

    def test_the_hand_over_cannot_exceed_what_is_there(self) -> None:
        """Four words in total, although the budget would allow six."""
        assert one_context("a b TARGET c d", "target") == "a b TARGET c d"

    def test_match_is_widened_to_the_whole_word(self) -> None:
        text = "one prefixTARGETsuffix two"
        assert one_context(text, "target") == text

    def test_match_spanning_several_words(self) -> None:
        text = "a b c one two d e f"
        assert one_context(text, "one two") == text

    def test_zero_length_match_still_yields_context(self) -> None:
        """Only reachable in regex mode; without the guard in `context_for`
        the empty match would produce an empty core."""
        assert one_context("alpha beta gamma", "x*", regex=True) == "alpha beta gamma"

    def test_color_wraps_only_the_match(self) -> None:
        result = one_context(SENTENCE, "target", color=True)
        assert result == f"two three four {HIGHLIGHT}TARGET{RESET} five six seven"


class TestSearchNote:
    @staticmethod
    def note(tmp_path: Path, text: str, name: str = "note.md") -> Path:
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path

    def search(self, path: Path, terms, excludes=(), words=3, require_all=True):
        return search_note(
            path,
            build_patterns(terms),
            build_patterns(excludes),
            words,
            require_all,
            False,
        )

    def test_match_returns_context(self, tmp_path: Path) -> None:
        path = self.note(tmp_path, "# Title\n\nsome **kubernetes** text here\n")
        assert self.search(path, ["kubernetes"]) == "some kubernetes text here"

    def test_context_stops_at_the_line_it_was_found_on(self, tmp_path: Path) -> None:
        """The heading below belongs to another section; pulling its words in
        would suggest a connection to the match that does not exist."""
        path = self.note(tmp_path, "notes on backup\n\n## Unrelated\n\nOther topic\n")
        assert self.search(path, ["backup"]) == "notes on backup"

    def test_miss_returns_none(self, tmp_path: Path) -> None:
        path = self.note(tmp_path, "nothing of interest\n")
        assert self.search(path, ["kubernetes"]) is None

    def test_all_terms_required_by_default(self, tmp_path: Path) -> None:
        path = self.note(tmp_path, "alpha only\n")
        assert self.search(path, ["alpha", "beta"]) is None

    def test_contexts_of_several_terms_are_joined(self, tmp_path: Path) -> None:
        path = self.note(tmp_path, "alpha one two three four five six beta there\n")
        result = self.search(path, ["alpha", "beta"])
        assert result == TERM_SEP.join(
            ["alpha one two three four five six", "two three four five six beta there"]
        )

    def test_any_term_is_enough_with_require_all_off(self, tmp_path: Path) -> None:
        path = self.note(tmp_path, "alpha only\n")
        assert self.search(path, ["alpha", "beta"], require_all=False) == "alpha only"

    def test_exclusion_wins_over_a_match(self, tmp_path: Path) -> None:
        path = self.note(tmp_path, "alpha and beta\n")
        assert self.search(path, ["alpha"], excludes=["beta"]) is None

    def test_exclusion_only_matches_without_context(self, tmp_path: Path) -> None:
        """With no positive terms every note that avoids the exclusions
        matches, and the caller prints no context column for it."""
        path = self.note(tmp_path, "alpha only\n")
        assert self.search(path, [], excludes=["beta"]) == ""
        assert self.search(path, [], excludes=["alpha"]) is None

    def test_exclusion_applies_in_or_mode_too(self, tmp_path: Path) -> None:
        path = self.note(tmp_path, "alpha and beta\n")
        assert (
            self.search(path, ["alpha"], excludes=["beta"], require_all=False) is None
        )

    def test_terms_match_across_markdown_formatting(self, tmp_path: Path) -> None:
        """The note text is cleaned before matching, so a term spanning a
        wikilink or emphasis is found."""
        path = self.note(tmp_path, "see [[Deploy Notes|the notes]] for details\n")
        assert self.search(path, ["the notes"]) is not None

    def test_undecodable_bytes_do_not_abort(self, tmp_path: Path) -> None:
        path = tmp_path / "binary.md"
        path.write_bytes(b"alpha \xff\xfe beta\n")
        assert self.search(path, ["alpha"]) is not None

    def test_unreadable_note_is_reported_and_skipped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        missing = tmp_path / "gone.md"
        assert self.search(missing, ["alpha"]) is None
        assert str(missing) in capsys.readouterr().err

    def test_precompiled_patterns_are_used_as_given(self, tmp_path: Path) -> None:
        path = self.note(tmp_path, "TARGET\n")
        assert search_note(path, [re.compile("target")], [], 3, True, False) is None
