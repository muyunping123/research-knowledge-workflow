# Management Research KB

`management-research-kb` is a Codex Plugin + Skill orchestration layer for using local literature in management-research ideation, writing, and audit work. It coordinates configured local PDFs, linked Obsidian category notes, independent Zotero metadata, manuscript context, and the `ai4management` rubric through an MCP dependency named `management-research-kb`.

The workflow is evidence-first and read-only by default. Every substantive skill run creates exactly two Codex subagents, gives both the same frozen evidence pack, merges their outputs in the parent, and closes both agents.

## What It Supports

- `build-knowledge`: analyze local PDFs by directory category and preview cross-linked Obsidian synthesis notes.
- `ideate`: construct a management-research idea from local and selectively verified scholarly evidence.
- `write`: draft or revise evidence-constrained Word, LaTeX, or Markdown paper content.
- `audit`: check management story, theory, novelty, venue fit, claim support, and citation integrity.

Local PDFs and Zotero remain independent. The workflow does not require a complete one-to-one mapping and does not bulk retrieve missing abstracts or full text.

## Repository Layout

```text
management-research-kb/
├─ .codex-plugin/plugin.json
├─ .mcp.json
├─ skills/
│  └─ management-research-kb/
│     ├─ SKILL.md
│     ├─ agents/openai.yaml
│     └─ references/
├─ mcp-server/
├─ config.example.toml
└─ README.md
```

The Skill discovers the MCP's actual tool schemas at runtime. This documentation does not assume tool names that the MCP server has not exposed.

## Prerequisites

- Codex with Plugin, Skill, MCP, and subagent support.
- An Obsidian vault containing or linking the local literature tree.
- Zotero with Better BibTeX when stable citekeys are needed.
- A registered MCP dependency whose identifier is `management-research-kb`.
- Installed `ai4management` skill for management-research reasoning.
- Installed `gs-search`, `gs-fulltext`, or `academic-search` skills for task-specific abstract verification when needed.

Obsidian's Zotero Integration may be used for personal reading workflows, but the Skill does not require every Obsidian PDF or note to have a matching Zotero item.

## Local Setup

Clone or download the plugin, then create its isolated Python environment and a private runtime config:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 `
  -VaultPath "C:\path\to\your\ObsidianVault" `
  -ManuscriptsRoot "C:\path\to\your\paper-projects"
```

The installer writes the private config to `%APPDATA%\management-research-kb\config.toml` and keeps the derived SQLite cache under `%LOCALAPPDATA%`. Add the repository as a local Codex plugin, reload Codex, and start a new task so the Skill and MCP server are rediscovered.

For a controlled first run, ask Codex to sync one relative directory such as `机器学习/多视图/渐进融合`. A whole-vault sync is optional and can be deferred.

## Configuration

Use [config.example.toml](config.example.toml) as the public configuration contract. Keep the real configuration outside version control and provide absolute local paths at runtime.

Configure at least:

- `vault_path`, which is both the Obsidian vault and local PDF discovery root;
- `notes_dir`, a relative directory inside the vault for generated category notes;
- optional `manuscripts_root`, which Codex may read when a project is active;
- `cache_dir`, outside OneDrive, Obsidian, or other synced folders;
- the loopback `zotero_base_url` used by the MCP service.

The MCP registration in `.mcp.json` must expose the dependency as `management-research-kb`. Restart or reload Codex after installing or changing the plugin so the Skill and MCP dependency are rediscovered.

## Build Knowledge Notes

Invoke:

```text
Use $management-research-kb in build-knowledge mode to analyze the PDFs under my configured literature root and preview category notes for the selected directories.
```

For a directory such as:

```text
机器学习/多视图/渐进融合/*.pdf
```

the proposed note is:

```text
机器学习_多视图_渐进融合.md
```

The two agents are:

1. **Local Literature Reader**: reads page-addressable PDF content, classifies papers by literature type, and produces evidence-linked synthesis.
2. **Cross-Link Auditor**: compares the synthesis with existing category notes and proposes meaningful Obsidian links, conflicts, and deduplication warnings.

Codex shows the complete new note or update diff first. It writes only after that preview has been approved and revalidated. PDFs remain in place, and the Markdown note contains synthesis rather than copied full text. The source inventory records the agent-assigned literature type and any verified Better BibTeX citekey.

Existing generated notes are searched live and passed to both agents as `lead_only` context. Generated content is enclosed by managed-block markers; `My Notes` remains outside that block. Replacing a note requires its preview-time digest, so an edit made in Obsidian between preview and apply is preserved as a conflict. A pre-existing note without valid managed markers is never adopted or overwritten silently.

## Ideation, Writing, and Audit

Examples:

```text
Use $management-research-kb in ideate mode to develop one evidence-grounded research idea about <topic>.
```

```text
Use $management-research-kb in write mode to draft the literature-review subsection <section> without editing my source file.
```

```text
Use $management-research-kb in audit mode to check <manuscript or idea> for unsupported claims and novelty risk.
```

These modes use exactly two agents:

1. **Idea Builder**: applies `ai4management` to management story, theory, research design, novelty, and venue fit.
2. **Evidence-Constrained Writer**: binds proposed prose to the claim ledger, evidence IDs, citekeys, and locators.

The parent retrieves and freezes the evidence pack. Workers do not call MCP tools, write files, or create agents.

## Zotero and Missing Full Text

Zotero supplies citation identity, collections, tags, notes, and available attachments. Attachment availability does not mean its content has been read. A local PDF may remain unmatched, and a Zotero record may remain metadata-only.

When a metadata-only Zotero paper is important to the active task, the parent may call an installed scholarly-search skill to locate and verify its abstract. This is narrow, demand-driven retrieval, not library completion. Abstract evidence supports only high-level claims explicitly stated in the abstract.

## Evidence Guarantees

- Detailed claims require page-located full-text evidence.
- Verified abstracts support only high-level aims, methods, settings, or conclusions.
- Metadata-only records support discovery and citation identity.
- Obsidian notes are leads until resolved to source evidence.
- Local no-hit results never prove novelty; novelty claims require traced external search.
- Every material claim is recorded in a claim ledger, and every search decision is recorded in a retrieval trace.

See the Skill's `references/` directory for the complete contracts.

## Manuscript Safety

The default result is an unapplied draft or diff. Word or LaTeX source files are changed only when the user explicitly requests an edit after seeing the preview.

- Preserve Zotero field codes, Word styles, comments, and tracked changes.
- Preserve LaTeX macros, labels, bibliography commands, and citekeys.
- Abort an apply operation when the target changed after preview.

## Validation

Validate the Skill metadata and structure with the Codex `skill-creator` validator:

```powershell
python C:\path\to\skill-creator\scripts\quick_validate.py .\skills\management-research-kb
```

Before publishing, also verify that:

- all Markdown links resolve;
- `SKILL.md` remains below 500 lines;
- the configured MCP dependency is discoverable;
- a test run starts exactly two agents, reuses their IDs across batches, and closes both;
- note and manuscript writes stop at preview until approved;
- no local paths, PDFs, notes, caches, manuscripts, Zotero data, or credentials are staged for Git.

## Privacy

Publish only source code, schemas, templates, and synthetic fixtures. Do not commit the Obsidian vault, generated notes, PDFs, Zotero databases or storage, exported private bibliographies, manuscript files, evidence packs, local indexes, configuration, credentials, or absolute personal paths.
