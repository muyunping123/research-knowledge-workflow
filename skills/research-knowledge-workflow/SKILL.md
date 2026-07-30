---
name: research-knowledge-workflow
description: "Build and use an evidence-grounded research knowledge base across local PDFs, linked Obsidian notes, independent Zotero metadata, and Word, LaTeX, or Markdown manuscript projects through the research-knowledge-workflow MCP. Use when Codex needs to synthesize classified literature, create cross-linked knowledge notes, develop or audit research ideas, draft or revise paper sections, retrieve local scholarly evidence, or check claims and citations in any academic discipline. Every substantive run creates exactly two Codex subagents; domain skills such as ai4management are optional reasoning adapters, never evidence sources."
---

# Research Knowledge Workflow

Act as the parent orchestrator. Use the `research-knowledge-workflow` MCP for local discovery, retrieval, staging, and approved writes. Inspect the MCP's actual tool schemas at runtime; never claim an unavailable capability.

## Load References

For every substantive run, read:

- [dual-agent-contract.md](references/dual-agent-contract.md)
- [evidence-schema.md](references/evidence-schema.md)

Also read:

- `build-knowledge`: [knowledge-note-schema.md](references/knowledge-note-schema.md) and [retrieval-policy.md](references/retrieval-policy.md)
- `ideate`, `write`, or `audit`: [retrieval-policy.md](references/retrieval-policy.md)
- tasks explicitly using management or business research: [ai4management-bridge.md](references/ai4management-bridge.md)

## Select One Mode

- `build-knowledge`: analyze local PDFs by relative parent directory and preview linked Obsidian topic notes.
- `ideate`: construct a research idea grounded in a frozen evidence pack.
- `write`: draft or revise an evidence-constrained paper section without silently editing source files.
- `audit`: test an idea or manuscript for problem clarity, contribution, method fit, novelty boundary, claim support, and citation integrity.

Treat all four modes as substantive. Setup explanations and deterministic application of an already approved, unchanged preview are not substantive research runs.

## Enforce Core Invariants

1. Create exactly two Codex subagents for each substantive invocation. Do not create a third agent for review, retries, domain adaptation, or replacement.
2. Reuse the same two agent IDs across every retrieval or document batch in that invocation.
3. Keep MCP orchestration, evidence-pack freezing, merge decisions, previews, writes, and agent closure in the parent.
4. Send both agents the same immutable evidence-pack version. Give them different role briefs, not different evidence.
5. Retry a failed worker through its existing agent ID. If that ID cannot continue, return `partial` or `blocked`; never spawn a replacement.
6. Close both agents before ending the substantive invocation, including error and cancellation paths.
7. Default to read-only. Show an exact note or manuscript preview before requesting write approval.
8. Treat Zotero as an independent metadata and reference source. Never require complete Zotero-to-PDF mapping.
9. Treat Obsidian notes, domain-skill output, and agent synthesis as reasoning leads, never as scholarly evidence.
10. Never infer novelty from a local no-hit result.

## Common Orchestration

1. Resolve the mode, target, configured roots, output language, discipline, and requested write scope.
2. Ask only for information that cannot be safely inferred, especially an ambiguous target or missing write permission.
3. Use the MCP to retrieve task-relevant local PDFs, notes, Zotero records, and manuscript context. A note or cache miss is not a local-library miss: call `kb_prepare_topic` with the topic plus bounded Chinese/English synonyms to discover unindexed PDFs by filename and directory, selectively sync only the strongest candidate groups, and retrieve their page-addressable context. Pass the task's domain or research-object vocabulary as `required_terms` when a broad concept such as multimodal, optimization, or causality would otherwise cross unrelated disciplines. Never run a whole-vault full-text sync merely because notes are missing.
4. Normalize provenance without forcing local PDFs and Zotero records into one-to-one relationships.
5. Build and freeze an evidence pack following `evidence-schema.md`. Record its digest, limitations, and retrieval trace.
6. Start exactly two agents with the mode-specific roles below and send each the identical frozen pack.
7. For additional batches, freeze a new complete pack version and send it to the same two IDs. Do not let workers call MCP tools, create agents, or write files.
8. Merge by claim ID. Prefer page-located full text over abstracts, metadata, notes, or unsupported reasoning.
9. Return the merged result, claim ledger, retrieval trace, conflicts, and unresolved evidence needs.
10. If a write was requested, present the proposed create/update diff. Apply it only after the user has seen and approved that preview and the target has not changed.
11. Close both agents and report their terminal status.

## Mode: Build Knowledge

Use the roles **Local Literature Reader** and **Cross-Link Auditor**.

1. If the user supplies a directory, sync only that subtree. If the user supplies a topic or an Obsidian search has no adequate note, call `kb_prepare_topic`; review its ranked groups and use the selectively indexed full-text context instead of concluding that the local library has no evidence.
2. Join the relative parent path components with `_` and add `.md`. For example, `机器学习/多视图/渐进融合/*.pdf` maps to `机器学习_多视图_渐进融合.md`.
3. Leave every PDF in place. Retrieve page-addressable text in bounded batches and preserve each source's vault-relative path.
4. Read the target note and search nearby topic notes through the MCP. Include their digests and current wikilinks in the evidence pack as non-evidentiary leads.
5. Ask the Local Literature Reader to classify and synthesize papers by literature type with page locators.
6. Ask the Cross-Link Auditor to identify evidence-backed relationships, disagreements, duplicates, terminology conflicts, and meaningful Obsidian wikilinks.
7. Merge into `knowledge-note-schema.md`. Do not copy paper full text into Markdown or invent missing metadata.
8. Enrich a source with Zotero metadata only when DOI or title-year evidence supports the match. An unmatched source is valid.
9. Preview the full new note or a bounded update diff. Never overwrite manual content or resolve a filename collision silently.
10. Save through the MCP only after approval. For an existing generated note, pass the preview-time digest so concurrent edits become conflicts instead of data loss.

For topic-directed preparation, generate one preview per selected parent-directory group. `kb_prepare_topic` may update only the derived local index; it never writes a Markdown note. Use its `pending_knowledge_notes`, full-text context, and cursors with the same two agents, then preview each note through `kb_write_knowledge_note(apply=false)`.

## Modes: Ideate, Write, Audit

Use the roles **Idea Builder** and **Evidence-Constrained Writer**.

Retrieve in this order: active manuscript context, linked Obsidian notes, topic-directed local PDF discovery and full text, Zotero metadata, then narrowly scoped external evidence when required. If note retrieval is empty or incomplete, run `kb_prepare_topic` before reporting a local no-hit. When a selected group lacks a note, include a knowledge-note preview as a navigation artifact while keeping every factual claim tied to the PDF pages. A Zotero attachment is only an availability signal until its text has been retrieved. If a relevant item has metadata but no retrieved full text, invoke an installed `$gs-search`, `$gs-fulltext`, or `$academic-search` workflow only for that active item and verify the result. Never bulk fill the Zotero library.

### Ideate

- Have the Idea Builder define the phenomenon or technical problem, research object, unresolved tension, candidate mechanism, research question, method, data or experimental setting, contribution, and falsification path.
- Have the Evidence-Constrained Writer test whether each proposed contribution is supportable and writable from the frozen pack.
- Require external closest-work search before any novelty conclusion. Otherwise label novelty `not_assessed`.

### Write

- Have the Evidence-Constrained Writer draft blocks tied to claim IDs, evidence IDs, citekeys, and locators.
- Have the Idea Builder audit argument continuity, conceptual or theoretical contribution, alternative explanations, method fit, and target audience.
- Do not introduce factual claims outside the claim ledger. Mark gaps as `[EVIDENCE_NEEDED: claim_id]`.

### Audit

- Have the Idea Builder audit problem framing, contribution, conceptual logic, method fit, alternatives, validation, and novelty boundary.
- Have the Evidence-Constrained Writer audit sentence-level support, citation placement, evidence level, terminology, and project compatibility.
- Classify each challenged claim as `accept`, `downgrade`, `needs_evidence`, or `reject`.

## Domain Adapters

Use a domain Skill only when the user explicitly requests it or the task clearly belongs to that domain. Apply it inside the existing two role briefs; never create an extra domain agent.

For management, business, information-systems, operations, or related research, use `$ai4management` according to `ai4management-bridge.md`. For other disciplines, use the domain-neutral role contracts above unless another installed Skill is explicitly applicable.

Treat every domain rubric, score, suggested mechanism, and venue recommendation as analysis. Convert it into a factual statement only after the parent retrieves suitable scholarly evidence and freezes a new pack version for both workers.

## Evidence and Writing Boundaries

- Use page-located local or external full text for detailed factual claims.
- Use verified abstracts only for high-level aims, broad methods, settings, or conclusions explicitly stated there.
- Use metadata-only records for discovery and citation identity only.
- Use Obsidian notes as leads that must resolve to source evidence.
- Record every material assertion in the claim ledger and every search decision in the retrieval trace.
- Do not fabricate titles, authors, years, DOI values, citekeys, page numbers, findings, or quotations.
- Do not edit Word or LaTeX source unless the user explicitly requests it. Preserve Word Zotero fields, styles, comments, and tracked changes; preserve LaTeX macros, labels, bibliography commands, and citekeys.

## Required Result

Return:

- `status`: `ready`, `partial`, `needs_clarification`, or `blocked`
- selected mode, target, and detected discipline
- evidence-pack ID, version, and digest
- the two agent IDs, assigned roles, and terminal status
- merged deliverable or write preview
- claim ledger and retrieval trace
- conflicts, limitations, and unresolved evidence needs
- domain adapters used, or `none`
- proposed changes and whether they remain unapplied
