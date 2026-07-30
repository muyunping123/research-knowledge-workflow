---
name: management-research-kb
description: "Orchestrate an evidence-grounded management-research knowledge base across local PDFs, linked Obsidian category notes, independent Zotero metadata, and Word or LaTeX manuscript projects through the management-research-kb MCP. Use when Codex needs to build knowledge notes from classified literature, construct or audit research ideas, draft or revise paper sections, retrieve local scholarly evidence, or check claims and citations. Every substantive run creates exactly two Codex subagents and uses ai4management for management story, theory, novelty, and venue-fit reasoning."
---

# Management Research KB

Act as the parent orchestrator. Use the `management-research-kb` MCP for local discovery, retrieval, staging, and approved writes. Inspect the MCP's actual tool schemas at runtime; never claim an unavailable capability.

## Load References

For every substantive run, read:

- [dual-agent-contract.md](references/dual-agent-contract.md)
- [evidence-schema.md](references/evidence-schema.md)

Also read:

- `build-knowledge`: [knowledge-note-schema.md](references/knowledge-note-schema.md) and [retrieval-policy.md](references/retrieval-policy.md)
- `ideate`, `write`, or `audit`: [retrieval-policy.md](references/retrieval-policy.md) and [ai4management-bridge.md](references/ai4management-bridge.md)

## Select One Mode

- `build-knowledge`: analyze local PDFs by relative parent directory and preview linked Obsidian category notes.
- `ideate`: construct a management-research idea grounded in an evidence pack.
- `write`: draft or revise an evidence-constrained paper section without silently editing source files.
- `audit`: test an idea or manuscript for story, theory, novelty, venue fit, claim support, and citation integrity.

Treat all four modes as substantive. Setup explanations and deterministic application of an already approved, unchanged preview are not substantive research runs.

## Enforce Core Invariants

1. Create exactly two Codex subagents for each substantive invocation. Do not create a third agent for review, retries, or replacement.
2. Reuse the same two agent IDs across every retrieval or document batch in that invocation.
3. Keep MCP orchestration, evidence-pack freezing, merge decisions, previews, writes, and agent closure in the parent.
4. Send both agents the same immutable evidence-pack version. Give them different role briefs, not different evidence.
5. Retry a failed worker through its existing agent ID. If that ID cannot continue, return `partial` or `blocked`; never spawn a replacement.
6. Close both agents before ending the substantive invocation, including error and cancellation paths.
7. Default to read-only. Show an exact note or manuscript preview before requesting write approval.
8. Treat Zotero as an independent metadata and reference source. Never require complete Zotero-to-PDF mapping.
9. Treat notes and `ai4management` output as reasoning leads, never as scholarly evidence.
10. Never infer novelty from a local no-hit result.

## Common Orchestration

1. Resolve the mode, target, configured roots, output language, and requested write scope.
2. Ask only for information that cannot be safely inferred, especially an ambiguous target or missing write permission.
3. Use the MCP to retrieve task-relevant local PDFs, notes, Zotero records, and manuscript context. For `build-knowledge`, sync only the selected directory subtree unless the user explicitly requests a whole-vault refresh. Do not bulk ingest unrelated material.
4. Normalize provenance without forcing local PDFs and Zotero records into one-to-one relationships.
5. Build and freeze an evidence pack that follows `evidence-schema.md`. Record a digest, limitations, and retrieval trace.
6. Start exactly two agents with the roles required below and send each the identical frozen pack.
7. For additional batches, freeze a new pack version and send it to the same two IDs. Do not let workers call MCP tools, create agents, or write files.
8. Merge by claim ID. Prefer page-located full text over abstracts, metadata, notes, or unsupported reasoning.
9. Return the merged result, claim ledger, retrieval trace, conflicts, and unresolved evidence needs.
10. If a write was requested, present the proposed create/update diff. Apply it only after the user has seen and approved that preview and the target has not changed.
11. Close both agents and report their terminal status.

## Mode: Build Knowledge

Use the roles **Local Literature Reader** and **Cross-Link Auditor**.

1. Use the MCP to group local PDFs by their parent directory relative to a configured PDF root.
2. Derive one category-note filename by joining the relative parent path components with `_` and adding `.md`. For example, `机器学习/多视图/渐进融合/*.pdf` maps to `机器学习_多视图_渐进融合.md`.
3. Leave every PDF in place. Retrieve page-addressable text in bounded batches and preserve each source's vault-relative path.
4. Read the existing target note and search nearby category notes through the MCP. Include those notes, their digests, and current wikilinks in the same evidence pack as non-evidentiary leads.
5. Ask the Local Literature Reader to classify and synthesize papers by literature type with page locators.
6. Ask the Cross-Link Auditor to propose evidence-backed relationships, contradictions, duplicates, and Obsidian wikilinks to existing or concurrently previewed notes.
7. Merge into the schema in `knowledge-note-schema.md`. Do not copy paper full text into Markdown and do not invent missing metadata.
8. Optionally enrich a source with Zotero metadata only when DOI or title-year evidence supports the match. An unmatched source is valid.
9. Preview the full new note or a bounded update diff. Never overwrite manual note content or resolve a filename collision silently.
10. Save through the MCP only after preview approval. When replacing an existing generated note, pass the exact preview-time digest so a concurrent edit causes a conflict instead of data loss.

## Modes: Ideate, Write, Audit

Use the roles **Idea Builder** and **Evidence-Constrained Writer**. In both role briefs, require use of the installed `$ai4management` skill according to `ai4management-bridge.md`.

Retrieve in this order: active manuscript context, linked Obsidian notes, local full text, Zotero metadata, then narrowly scoped external evidence when required. A Zotero PDF attachment is only an availability signal until its text has actually been retrieved. If a relevant Zotero item has metadata but no retrieved local full text, invoke an installed `$gs-search`, `$gs-fulltext`, or `$academic-search` workflow only for that active item and verify its abstract. Never bulk fill the Zotero library.

### Ideate

- Have the Idea Builder construct the management phenomenon, decision maker, decision variable, tension, mechanism, research question, method, empirical setting, and falsification path.
- Have the Evidence-Constrained Writer test whether each proposed contribution is supportable and writable from the frozen pack.
- Require external literature search before any novelty conclusion. Otherwise label novelty `not_assessed`.

### Write

- Have the Evidence-Constrained Writer draft blocks tied to claim IDs, evidence IDs, citekeys, and locators.
- Have the Idea Builder audit story continuity, theoretical contribution, alternative explanations, and venue fit.
- Do not introduce factual claims outside the claim ledger. Mark gaps as `[EVIDENCE_NEEDED: claim_id]`.

### Audit

- Have the Idea Builder audit novelty, management story, theory, method logic, and venue fit.
- Have the Evidence-Constrained Writer audit sentence-level support, citation placement, evidence level, terminology, and project compatibility.
- Classify each challenged claim as `accept`, `downgrade`, `needs_evidence`, or `reject`.

## Evidence and Writing Boundaries

- Use page-located local or external full text for detailed factual claims.
- Use verified abstracts only for high-level aims, broad methods, and conclusions explicitly stated there.
- Use metadata-only records for discovery and citation identity only.
- Use Obsidian notes as leads that must resolve to source evidence.
- Record every material assertion in the claim ledger and every search decision in the retrieval trace.
- Do not fabricate titles, authors, years, DOI values, citekeys, page numbers, findings, or quotations.
- Do not edit Word or LaTeX source unless the user explicitly requests it. Preserve Word Zotero fields, styles, comments, and tracked changes; preserve LaTeX macros, labels, bibliography commands, and citekeys.

## Required Result

Return:

- `status`: `ready`, `partial`, `needs_clarification`, or `blocked`
- selected mode and target
- evidence-pack ID, version, and digest
- the two agent IDs, assigned roles, and terminal status
- merged deliverable or write preview
- claim ledger and retrieval trace
- conflicts, limitations, and unresolved evidence needs
- proposed changes and whether they remain unapplied
