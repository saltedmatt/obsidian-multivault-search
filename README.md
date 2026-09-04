# obsidian-multivault-search

Command-line search for notes across multiple Obsidian vaults.
Pure Python, standard library only, no dependencies (Python ≥ 3.9).

The command is available under two names: `obsidian-multivault-search` and the
short alias `obmvs`. Both do exactly the same; this README uses `obmvs`.

## Installation

```bash
pipx install obsidian-multivault-search
# or
uv tool install obsidian-multivault-search
```

Both install the two commands `obsidian-multivault-search` and `obmvs`.
To try the tool without installing it:

```bash
uvx --from obsidian-multivault-search obmvs TERM
```

There are no dependencies, so plain `pip install obsidian-multivault-search`
into a virtual environment works just as well. From a clone of this repository:

```bash
uv tool install .          # installs both commands
# or, without installing anything:
python -m obsidian_multivault_search TERM   # with src/ on PYTHONPATH
```

## Project layout

```
src/obsidian_multivault_search/
├── __init__.py    public API: cli(), main(), __version__
├── __main__.py    python -m obsidian_multivault_search
├── _meta.py       version and invoked program name
├── markdown.py    stripping markdown formatting off note text
├── vaults.py      finding vaults and their notes
├── search.py      matching terms, extracting context
└── cli.py         argument parsing, search run, output
```

## Usage

```bash
obmvs TERM [TERM ...]        # searches the whole home directory
obmvs -d ~/w/vaults TERM     # searches only below that path
obmvs -L                     # list the vaults that were found
```

* **Vault** = a directory containing an `.obsidian` subfolder; the vault name is
  the name of that directory. Only such directories are searched. If a vault
  lies inside another vault, its notes belong to the inner (nearest) vault.
* **Note** = a `.md` file. Hidden folders (`.obsidian`, `.trash`, `.git` …) are
  skipped, symlinks are not followed by default.
* **Search**: substring, case-insensitive. Multiple terms are ANDed together.
  Quote phrases containing spaces: `obmvs "open invoice" 2025`.
* **Exclusion**: `-n TERM` excludes notes containing the term (repeatable).
  Exclusions always apply in addition to the search terms, `-o` included. If
  *only* `-n` is given, every note that contains none of the terms is listed –
  without a context column in that case.

## Output

One line per matching note, fields separated by tabs, sorted by vault name and
note name:

```
vault-name<TAB>note-name<TAB>context
```

The context shows the match with up to three words before and after it.
Markdown formatting (headings, `*`/`_`/`` ` ``, links, wikilinks, table rules,
HTML tags …) is stripped; for links the display text is kept. Only the **first**
match per note and search term is shown; with multiple terms the contexts are
separated by ` | `.

## Options

| Option | Meaning |
|---|---|
| `-n, --not TERM` | term that must **not** occur (repeatable) |
| `-d, --dir PATH` | search area (repeatable, default: `$HOME`) |
| `-C, --context N` | words before/after the match (default: 3) |
| `-s, --case-sensitive` | respect upper/lower case |
| `-w, --word` | match whole words only |
| `-e, --regex` | treat search terms as regular expressions |
| `-o, --or` | combine with OR instead of AND |
| `-p, --relpath` | print the path relative to the vault instead of the note name |
| `-F, --sep CHAR` | output field separator (default: tab) |
| `-L, --list-vaults` | only list the vaults that were found |
| `--max-depth N` | maximum depth when looking for vaults |
| `--follow` | follow symlinks |
| `--color auto\|always\|never` | highlight matches (default: auto, terminal only) |
| `-j, --jobs N` | parallel reads |
| `-V, --version` | print the version and exit |

Exit codes: `0` = matches, `1` = no matches / no vaults, `2` = usage error.

## Examples

```bash
# notes containing both terms
obmvs kubernetes deployment

# kubernetes, but without any mention of helm or docker
obmvs kubernetes -n helm -n docker

# all notes that do not contain "status"
obmvs -n status

# whole words only, more context, readable columns
obmvs -w -C 6 backup | column -t -s $'\t'

# post-process note names only
obmvs -p invoice | cut -f1,2
```

## License

Licensed under either of

* Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or
  <http://www.apache.org/licenses/LICENSE-2.0>)
* MIT license ([LICENSE-MIT](LICENSE-MIT) or
  <http://opensource.org/licenses/MIT>)

at your option (SPDX: `Apache-2.0 OR MIT`).

Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in this work by you shall be dual licensed as above, without any
additional terms or conditions.
