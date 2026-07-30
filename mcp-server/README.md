# Research Knowledge Workflow MCP Server

A local, read-first MCP server that indexes PDFs beneath an Obsidian vault,
queries Zotero through its local read-only API, and materializes agent-written
group knowledge notes only after an explicit `apply=true` call.

## Install and run

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test]"
Copy-Item config.example.toml config.toml
$env:RESEARCH_KNOWLEDGE_WORKFLOW_CONFIG = (Resolve-Path .\config.toml)
& .venv\Scripts\research-knowledge-workflow-mcp.exe
```

The server uses stdio. Logs go to stderr; stdout is reserved for MCP protocol
messages. An explicit config can also be supplied with `--config`:

```powershell
& .venv\Scripts\research-knowledge-workflow-mcp.exe --config C:\path\to\config.toml
```

The SQLite index is derived data and must be outside the Obsidian vault. PDF
files and the Zotero database are never modified. `kb_sync` accepts an optional
vault-relative `group_path`, so a first run can index only the selected
literature type. `kb_prepare_topic` first scans PDF filenames and relative paths
without extracting the whole vault, ranks candidate directory groups, selectively
indexes only the selected groups, and returns bounded page text for knowledge-note
synthesis. Supply `search_terms` with useful bilingual synonyms when filenames and
the research question use different languages. Supply `required_terms` for the
domain or research object when a broad concept could retrieve unrelated fields;
for example, multimodal marketing can require one of `营销`, `marketing`, `sales`,
or `commerce`. Knowledge notes can be read and searched, but remain reasoning
leads rather than scholarly evidence. `kb_write_knowledge_note` previews by
default and refuses to replace an existing note unless `apply=true`,
`overwrite=true`, and the preview-time `expected_existing_digest` all agree.
The tool accepts optional per-source literature types and citekeys for its
source inventory, replaces only its managed generated block, and preserves the
user-authored `My Notes` tail.

A Zotero PDF attachment reports availability only. It is not labeled full-text
evidence until a matched local PDF has actually been indexed and retrieved.

Typical topic bootstrap:

1. Call `kb_search_notes` for existing navigation leads.
2. On an empty or incomplete result, call `kb_prepare_topic` with a topic and bounded synonyms.
3. Continue through each returned context cursor and let the workflow's two agents synthesize the selected groups.
4. Call `kb_write_knowledge_note` with its default `apply=false`; write only after review and explicit approval.

## Test

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

All tests use temporary vaults and mocked Zotero responses; no network is used.
