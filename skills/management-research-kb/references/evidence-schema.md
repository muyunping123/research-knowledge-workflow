# Evidence Schema

Use stable IDs so every drafted assertion can be traced back to a retrieved source and locator.

## Evidence Levels

| Level | Allowed use | Prohibited use |
|---|---|---|
| `fulltext_page` | Detailed definitions, methods, findings, numbers, limitations, and comparisons with page or figure/table locators | Claims outside the inspected passage |
| `abstract_only` | Aim, broad method, setting, and conclusion explicitly stated in a verified abstract | Detailed mechanisms, coefficients, sample details not stated, page claims, or direct quotations from the paper |
| `metadata_only` | Discovery, deduplication, citation identity, and candidate ranking | Substantive claims about what the paper demonstrates |
| `note_lead` | Query expansion, concept navigation, and candidate source discovery | Final evidentiary support |
| `project_context` | Preserve the manuscript's current argument, wording, citations, and formatting constraints | Independent validation of manuscript claims |

`ai4management` output and subagent reasoning are not evidence levels. Store them as analysis artifacts, not evidence items.

## Frozen Evidence Pack

Both subagents receive the exact same serialized pack version.

```yaml
pack_id: "EP-<task-id>"
version: 1
digest: "sha256:<digest>"
frozen_at: "ISO-8601 timestamp"
mode: "build-knowledge | ideate | write | audit"
target:
  project: null
  manuscript: null
  section: null
  category_path: null
query:
  user_request: ""
  normalized_terms: []
scope:
  pdf_roots: []
  note_roots: []
  zotero_scope: []
items: []
existing_notes: []
project_context: []
limitations: []
retrieval_trace_id: "RT-<task-id>"
```

Freeze means that an item, locator, or limitation cannot change within a pack version. New retrieval creates the next version. Send the complete new version to both existing agent IDs.

## Evidence Item

```yaml
evidence_id: "E001"
source_kind: "local_pdf | external_fulltext | verified_abstract | zotero_metadata | obsidian_note | manuscript"
evidence_level: "fulltext_page | abstract_only | metadata_only | note_lead | project_context"
identity:
  title: null
  authors: []
  year: null
  doi: null
  citekey: null
  zotero_item_key: null
locator:
  pdf_path: null
  note_path: null
  page_label: null
  pdf_page: null
  section: null
  figure_or_table: null
  url: null
content:
  paraphrase: ""
  minimal_excerpt: null
provenance:
  retrieved_via: "management-research-kb | gs-search | gs-fulltext | academic-search"
  retrieved_at: "ISO-8601 timestamp"
  identity_confidence: "exact | strong | probable | unmatched | conflict"
  text_quality: "native | ocr | partial | unavailable"
supports: []
limitations: []
```

Keep excerpts minimal and necessary for verification. Do not place copied full text in an evidence pack or knowledge note.

## Claim Ledger

Create one row for every material, externally checkable assertion and every consequential inference.

```yaml
claim_id: "C001"
claim: ""
argument_role: "background | gap | theory | hypothesis | method | result | discussion | contribution"
status: "supported | partial | needs_evidence | contradicted | inference"
evidence_ids: []
citekeys: []
locators: []
support_type: "direct | partial | contextual | contradictory | none"
confidence: "high | medium | low"
draft_block_ids: []
notes: ""
```

Rules:

- Require `fulltext_page` evidence for detailed empirical, numerical, definitional, methodological, or controversy claims.
- Allow `abstract_only` evidence only within its explicit scope and use appropriately cautious wording.
- Never cite `metadata_only` or `note_lead` as support.
- Distinguish a source author's conclusion from the agent's inference.
- Place citations after the smallest sentence group they support.
- Use `[EVIDENCE_NEEDED: Cxxx]` rather than guessing.
- Record contradictory evidence rather than averaging it away.

## Retrieval Trace

```yaml
trace_id: "RT-<task-id>"
started_at: "ISO-8601 timestamp"
completed_at: null
queries:
  - query_id: "Q001"
    terms: []
    source: "obsidian | local_pdf | zotero | gs-search | gs-fulltext | academic-search | external"
    filters: {}
    result_ids: []
    selected_ids: []
    rejected:
      - id: ""
        reason: ""
source_failures: []
association_decisions: []
coverage_limitations: []
stop_reason: ""
```

Record no-hit queries, unavailable sources, parsing failures, and uncertain associations. A reproducible trace is part of the result, not optional debug output.

## Agent Result Envelope

Each subagent returns:

```yaml
status: "ready | partial | needs_evidence | blocked"
agent_role: ""
pack_id: ""
pack_version: 1
pack_digest: ""
analysis: []
draft_blocks: []
claim_ledger: []
link_proposals: []
conflicts: []
unresolved: []
```

Reject or rerun through the same agent ID any result whose pack identity differs from the dispatched pack.
