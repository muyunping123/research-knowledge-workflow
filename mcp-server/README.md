# Management Research KB MCP Server

A local, read-first MCP server that indexes PDFs beneath an Obsidian vault,
queries Zotero through its local read-only API, and materializes agent-written
group knowledge notes only after an explicit `apply=true` call.

## Install and run

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test]"
Copy-Item config.example.toml config.toml
$env:MANAGEMENT_RESEARCH_KB_CONFIG = (Resolve-Path .\config.toml)
.venv\Scripts\python -m management_research_kb
```

The server uses stdio. Logs go to stderr; stdout is reserved for MCP protocol
messages. An explicit config can also be supplied with `--config`:

```powershell
.venv\Scripts\python -m management_research_kb --config C:\path\to\config.toml
```

The SQLite index is derived data and must be outside the Obsidian vault. PDF
files and the Zotero database are never modified. `kb_sync` accepts an optional
vault-relative `group_path`, so a first run can index only the selected
literature type. Knowledge notes can be read and searched, but remain reasoning
leads rather than scholarly evidence. `kb_write_knowledge_note` previews by
default and refuses to replace an existing note unless `apply=true`,
`overwrite=true`, and the preview-time `expected_existing_digest` all agree.
The tool accepts optional per-source literature types and citekeys for its
source inventory, replaces only its managed generated block, and preserves the
user-authored `My Notes` tail.

A Zotero PDF attachment reports availability only. It is not labeled full-text
evidence until a matched local PDF has actually been indexed and retrieved.

## Test

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

All tests use temporary vaults and mocked Zotero responses; no network is used.
