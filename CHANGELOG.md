# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The release workflow copies the section of the released version into the body
of the GitHub release, so entries are written for people using the tool, not as
a second commit log.

## [Unreleased]

### Added

- The test suite runs on Windows in CI as well, so `Operating System ::
  OS Independent` is now something the project checks rather than claims.
- The README describes what follows the platform on Windows: path separators,
  the encoding of the output and the console mode that colour needs.

### Fixed

- Redirecting the output no longer ends in a `UnicodeEncodeError` when the
  locale cannot encode what a note contains. `obmvs term > out.txt` used to
  fail over an arrow or a check mark on a German Windows, where a redirected
  stream encodes in cp1252; the output is UTF-8 now, on every platform.
- `--color auto` no longer writes escape sequences into a Windows console that
  prints them verbatim: the mode that interprets them is switched on first,
  and where that is refused the output stays plain. `--color always` keeps
  writing them, for piping colour on to something else.

## [0.1.1] - 2026-09-09

### Changed

- The README documents installation from PyPI - `pipx install`,
  `uv tool install` and `uvx` - instead of pointing at a clone of the
  repository.
- A match at the beginning or the end of its line now gets the context it
  cannot take from the short side from the other one. `-C N` shows up to
  `2 × N` adjacent words in that case rather than falling back to fewer.
- `-C, --context` counts adjacent *words*, not lines. `--help` and the README
  say so now, and both name the default of 3 again.

### Fixed

- The context of a match no longer reaches past the line the match was found
  on. A match at the end of a paragraph used to pull in the words that follow
  it in the file - occasionally the heading of an unrelated section, which
  suggested a connection that was not there.

## [0.1.0] - 2026-09-08

### Added

- First release: `obsidian-multivault-search` searches notes across every
  Obsidian vault below one or more directories, using the standard library
  only.
- Both `obsidian-multivault-search` and the short alias `obmvs` invoke the
  tool; messages follow whichever name was typed.
- Search terms are combined with AND, `-o` switches to OR, and `-n` excludes
  notes containing a term.
- `-s`, `-w` and `-e` select case-sensitive, whole-word and regular expression
  matching.
- Output is one tab-separated line per note with the match in context;
  markdown formatting is stripped from that context.
- `-d`, `--max-depth` and `--follow` control the searched area, `-L` only lists
  the vaults that were found.
- `-C`, `-p`, `-F` and `--color` shape the output, `-j` sets the number of
  parallel reads.

[Unreleased]: https://github.com/saltedmatt/obsidian-multivault-search/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/saltedmatt/obsidian-multivault-search/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/saltedmatt/obsidian-multivault-search/releases/tag/v0.1.0
