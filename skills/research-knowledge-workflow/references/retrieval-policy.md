# Retrieval Policy

Use this policy for local knowledge construction, research ideation, manuscript writing, and evidence audits.

## Principles

1. Retrieve only what the active task needs.
2. Keep local PDFs, Obsidian notes, Zotero records, and external results as independently addressable sources.
3. Preserve provenance through every merge. Never upgrade evidence merely because two systems mention the same paper.
4. Prefer verified, page-addressable full text for substantive claims.
5. Record failed searches and inaccessible sources; absence is a coverage result, not a research finding.

## Source Roles

| Source | Primary role | Limitation |
|---|---|---|
| Local PDF | Detailed evidence and page-level analysis | Metadata may be incomplete or inconsistent |
| Obsidian note | Navigation, synthesis, concepts, and cross-links | Must resolve to source evidence before supporting a claim |
| Zotero | Citation identity, metadata, collections, tags, and available attachments | No complete mapping to the local PDF tree is required |
| Verified abstract | High-level evidence for a task-relevant paper without accessible full text | Cannot support fine-grained mechanisms, numbers, or page claims |
| External full text | Task-specific evidence and novelty checking | Must retain URL, version, access date, and page locator |
| Manuscript | Current argument, terminology, citations, and formatting context | Does not independently validate its own claims |

## Local Knowledge Build

1. Discover configured PDF roots through the MCP. For a topic rather than an explicit directory, use `kb_prepare_topic` with bounded bilingual synonyms so unindexed PDFs can be found from filenames and relative paths. Use `required_terms` for the domain or research object when the main concept is cross-disciplinary.
2. Group PDFs by relative parent directory, not by Zotero collection.
3. Selectively index only the strongest candidate groups, retrieve page-addressable context, and build one bounded evidence pack per directory group or batch. A Markdown-note miss must not bypass this local-PDF step.
4. Include an existing target note and nearby category notes so links can be audited.
5. Extract page-addressable text for analysis. If OCR or parsing is incomplete, mark the affected pages and lower confidence.
6. Do not search externally merely to make every local PDF complete.
7. Do not move, rename, or rewrite PDFs.

## Active Research Retrieval

Use the following order unless the task clearly requires another sequence:

1. Read the active project target, adjacent text, terminology, existing citations, and requested scope.
2. Search Obsidian filenames, frontmatter, aliases, tags, links, and note text for candidate concepts and papers.
3. Resolve promising note leads to local PDF pages. If notes are absent or insufficient, call `kb_prepare_topic` to scan the complete PDF catalog without extracting the complete vault, selectively index ranked parent-directory groups, and retrieve bounded full-text context.
4. Generate or update missing group knowledge notes as previews from that full-text context; notes remain navigation leads and require explicit approval before writing.
5. Search Zotero metadata and available attachments independently for additional candidates and citation identity.
6. Verify only task-relevant metadata-only candidates through an installed scholarly-search skill.
7. Run external prior-art search when assessing novelty or when local evidence is insufficient for a material claim.
8. Freeze the selected evidence and its limitations before dispatching the two agents.

## Optional PDF-Zotero Association

Associate records only when useful to the active task. Do not treat association as a migration or completeness goal.

Use confidence tiers:

- `exact`: identical normalized DOI.
- `strong`: normalized title and year agree, with compatible author information when available.
- `probable`: title similarity and year support a candidate, but a material field is missing.
- `unmatched`: no reliable candidate.
- `conflict`: DOI, title, year, or authors disagree materially.

Only `exact` and reviewed `strong` associations may supply Zotero citekeys to local PDF evidence. Keep `probable`, `unmatched`, and `conflict` records separate. Never overwrite source metadata to force a match.

## On-Demand Abstract Verification

Trigger abstract retrieval only when all are true:

1. A Zotero metadata-only paper is relevant to the active task.
2. No suitable local or Zotero full text is available.
3. Its abstract would materially affect selection, comparison, or a high-level claim.

Then:

1. Invoke the installed `$gs-search` workflow to locate the paper. Use `$academic-search` for structured metadata or source cross-checking, and `$gs-fulltext` only when a legitimate accessible full-text route is needed.
2. Verify title, authors, year, and DOI when present across the returned record and an authoritative landing page or scholarly metadata source.
3. Save the abstract as an evidence item with source URL, access time, and verification fields.
4. Limit claims to information explicitly present in the verified abstract.
5. Stop after resolving the active candidate set. Never iterate through Zotero to fill missing abstracts in bulk.

If the abstract cannot be verified, retain the item as `metadata_only` and record the failure.

## Novelty Search

Local absence never establishes novelty. Before writing a novelty claim:

1. Expand the query across the research object, problem formulation, concepts or theory, technical mechanism, synonyms, and adjacent terminology.
2. Search external scholarly indexes and verify the closest candidates at least at abstract level.
3. Compare the active idea with the closest work on problem setting, research object, mechanism or theory, method, data, evaluation or identification design, and claimed contribution.
4. Record query strings, sources, dates, filters, closest-work IDs, and coverage limitations.

Use `not_assessed` when external verification is incomplete. Even a provisionally distinct result must be bounded by the searched sources and date.

## Ranking and Stop Rules

Rank candidates by:

1. direct relevance to the active claim or category;
2. evidence level and locator quality;
3. bibliographic identity confidence;
4. recency or influence only when the task calls for it.

Stop retrieval when the evidence pack covers the requested claims, the configured budget is reached, or remaining candidates are unlikely to change the decision. Record the stop reason.

## Failure Handling

- Zotero unavailable: continue with local notes and PDFs; mark citation coverage incomplete.
- PDF parsing failed: retain metadata and file provenance; do not invent text or pages.
- Obsidian note unavailable: run topic-directed local PDF discovery before external retrieval; continue with page-located PDFs and mark the missing note for preview generation.
- Obsidian Vault unavailable: continue only with other configured sources; do not claim local PDF or link coverage.
- Scholarly search unavailable: keep metadata-only candidates and set novelty to `not_assessed` where applicable.
- Conflicting versions: keep both records and identify which version supports each claim.
