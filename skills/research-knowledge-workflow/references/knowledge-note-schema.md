# Knowledge Note Schema

Create one linked synthesis note for each relative parent-directory group of local PDFs. The note represents a literature category, not an individual Zotero item.

## Grouping and Filename

Given a configured PDF root, compute each PDF's relative parent directory. Join all parent path components with `_` and append `.md`.

```text
PDF root/
  机器学习/
    多视图/
      渐进融合/
        paper-a.pdf
        paper-b.pdf

Knowledge note: 机器学习_多视图_渐进融合.md
```

Rules:

- Ignore the PDF filename when deriving the category-note name.
- Normalize path separators before joining components.
- Replace characters illegal in the target filesystem without changing the semantic path.
- Keep a reversible `category_path` in frontmatter.
- If two configured roots produce the same target name for different categories, stop at preview with a collision. Do not overwrite or silently add a suffix.
- Keep PDFs in their original locations.

## Literature Types

Classify each paper into one primary type and record confidence:

- `review_or_meta_analysis`
- `theoretical_or_conceptual`
- `empirical_quantitative`
- `empirical_qualitative_or_case`
- `method_model_algorithm_or_optimization`
- `dataset_system_or_application`
- `unknown`

Use document evidence, not the filename alone. Preserve `unknown` when the type cannot be established reliably.

## Frontmatter

```yaml
---
type: "category-knowledge"
schema_version: 1
category_path: "机器学习/多视图/渐进融合"
category_key: "机器学习_多视图_渐进融合"
source_root_id: "configured-root-id"
source_count: 2
source_snapshot: "sha256:<digest>"
status: "preview | reviewed"
generated_at: "ISO-8601 timestamp"
updated_at: "ISO-8601 timestamp"
aliases: []
tags: []
related_notes: []
---
```

Use vault-relative paths and links. Do not expose unnecessary machine-specific absolute paths in the note.

## Body Template

```markdown
# <Category display name>

## Scope
<What this directory's literature covers and does not cover.>

<!-- MRKB:BEGIN GENERATED -->
## Literature Map
### Review and Meta-analysis
### Theory and Concepts
### Empirical Studies
### Methods, Models, Algorithms, and Optimization
### Datasets, Systems, and Applications

## Core Themes
<Evidence-linked synthesis using source IDs and page locators.>

## Methods and Data
<Comparison of methods, settings, datasets, assumptions, and evaluation designs.>

## Agreements, Tensions, and Boundary Conditions
<Convergent findings, contradictions, and limits.>

## Research Opportunities
<Questions or hypotheses clearly separated from established findings.>

## Related Notes
- [[Existing_Category_Note]] - <relationship supported by the analysis>

## Source Inventory
| Source ID | Paper | Type | Local PDF | Evidence coverage | Zotero reference |
|---|---|---|---|---|---|
<!-- MRKB:END GENERATED -->

## My Notes
<!-- User-authored content; never replace automatically. -->
```

## Content Rules

- Synthesize and paraphrase; never copy full paper text into Markdown.
- Attach page locators to detailed claims and comparisons.
- Keep abstract-only sources visibly labeled and limited to high-level claims.
- Keep Zotero-only metadata out of substantive synthesis unless a relevant abstract is verified for the active task.
- Use source IDs in prose or tables so claims resolve to the source inventory and evidence pack.
- Separate established findings, cross-paper synthesis, and proposed research opportunities.
- Record uncertainty, OCR limitations, and conflicting evidence.

## Cross-Link Rules

The Cross-Link Auditor proposes links after inspecting the same evidence pack as the reader.

- Link to an existing note or another note in the same approved preview batch.
- Explain the relationship: shared theory, method, dataset, decision setting, contradiction, extension, or boundary condition.
- Prefer a small number of meaningful links over broad keyword links.
- Put missing targets in an unresolved list; do not create them implicitly.
- Use Obsidian wikilinks with the exact target note name.
- Do not treat link density as evidence quality.

## Update and Write Safety

1. Read the current target note and compute its source snapshot.
2. Preserve all content outside the managed generated block.
3. Build a full creation preview or a bounded generated-block diff.
4. Show added, changed, removed, and unresolved sources and links.
5. Require explicit approval after the preview is visible.
6. Before applying, verify that the target snapshot still matches.
7. If the note changed, abort the apply and produce a fresh two-agent preview.
8. Never delete a source note, PDF, attachment, or user-authored section as part of category-note generation.

If an existing note lacks managed-block markers, preview a non-destructive adoption plan. Do not assume its whole body is generated content.
