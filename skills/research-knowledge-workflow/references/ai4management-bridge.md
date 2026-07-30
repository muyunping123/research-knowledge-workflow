# Optional ai4management Adapter

Use the installed `$ai4management` skill only when the user requests it or the active task belongs to management, business, information systems, operations, marketing, finance, or a related interdisciplinary setting. It is a reasoning and audit rubric, not a database, source, citation, or evidence item.

## Attach the Adapter

For applicable `ideate`, `write`, and `audit` runs, add `$ai4management` to both existing role briefs:

- **Idea Builder** uses it for the managerial phenomenon, decision problem, theory or mechanism, research question, method logic, novelty comparison, falsification, and venue fit.
- **Evidence-Constrained Writer** uses it to keep prose centered on the decision maker, mechanism, contribution, and audience while enforcing the claim ledger.

Do not start a separate ai4management agent. The two required workers remain the only subagents. For non-management tasks, skip this adapter and use the general role contracts.

## Input Mapping

Map the task and frozen evidence pack into these fields without inventing missing values:

```yaml
management_story:
  setting: null
  decision_maker: null
  decision_variable: null
  managerial_tension: null
  theory_or_mechanism: null
  available_data: null
research_design:
  question: null
  method: null
  unit_of_analysis: null
  identification_or_validation: null
  target_venue_family: null
known_context:
  accepted_claim_ids: []
  rejected_ideas: []
  closest_work_evidence_ids: []
```

If the central management context cannot be inferred, return at most three focused clarification questions rather than manufacturing one.

## Evidence Boundary

- Cite only evidence items from the frozen pack.
- Treat ai4management suggestions, scores, and inferred mechanisms as analysis artifacts.
- Convert a suggested factual claim into prose only after the parent retrieves suitable evidence and freezes a new pack version for both agents.
- Present proposed mechanisms and hypotheses explicitly as proposals, not prior findings.
- Never use local library coverage, a Zotero no-hit, or an Obsidian no-hit as proof of a research gap.

## Novelty Gate

Before evaluating novelty, the parent must perform and trace an external scholarly search. Compare the closest verified work on:

- management setting and decision maker;
- decision variable and managerial tension;
- mechanism or theory;
- method and data;
- unit of analysis;
- validation or identification design.

Use only these verdicts:

- `not_assessed`: external verification is incomplete.
- `collision`: closest work covers the central problem and mechanism.
- `weak_delta`: a difference exists but does not yet support a clear contribution.
- `provisionally_distinct`: verified closest work differs on multiple material axes within the documented search boundary.

Never claim "first," "no prior work," or equivalent universal novelty. State the databases, queries, and cutoff date that bound a provisional result.

## Mode Responsibilities

### Ideate

Produce one focused idea with:

1. management phenomenon and decision problem;
2. research question;
3. theory or mechanism;
4. method and empirical setting;
5. falsification or validation path;
6. evidence-grounded prior-work comparison;
7. novelty and venue-fit audit;
8. next research loop.

### Write

Use the approved argument and evidence ledger to write the requested section. Maintain distinctions among prior evidence, the paper's proposed contribution, hypotheses, results, and interpretation. Do not let venue language justify unsupported claims.

### Audit

Return `pass`, `revise`, `fail`, or `not_assessed` for:

- management story;
- theoretical contribution;
- method and evidence fit;
- novelty;
- falsifiability or validation;
- venue fit.

Tie every reason to claim IDs or clearly label it as rubric-based reasoning.

## Degraded Operation

If a management task requests `$ai4management` but it cannot be loaded, mark its checks `not_run` and report the missing optional dependency. Continue the general evidence workflow when useful, but do not imitate ai4management verdicts or describe the domain audit as complete.
