# ai4management Bridge

Use the installed `$ai4management` skill as a management-research reasoning and audit rubric. It is not a database, source, citation, or evidence item.

## Attach the Rubric

For `ideate`, `write`, and `audit` modes, instruct both research agents to load and apply `$ai4management`:

- **Idea Builder** uses it primarily for management story, theory, research question, method logic, novelty comparison, falsification, and venue fit.
- **Evidence-Constrained Writer** uses it to keep the prose centered on the decision problem, mechanism, contribution, and audience while enforcing the claim ledger.

Do not start a separate ai4management agent. The two required workers remain the only subagents.

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

If the central management story cannot be inferred, return at most three focused clarification questions rather than manufacturing a context.

## Evidence Boundary

- Cite only evidence items from the frozen pack.
- Treat ai4management suggestions, scores, and inferred mechanisms as analysis artifacts.
- Convert a suggested factual claim into prose only after the parent retrieves suitable evidence and freezes a new pack version for both agents.
- Present proposed mechanisms and hypotheses explicitly as proposals, not prior findings.
- Never use local library coverage, a Zotero no-hit, or an Obsidian no-hit as proof of a research gap.

## Novelty Gate

Before evaluating novelty, the parent must perform and trace an external scholarly search. Compare the closest verified work on:

- management setting;
- decision maker and decision variable;
- managerial tension or phenomenon;
- mechanism or theory;
- method;
- data and unit of analysis;
- validation or identification design.

Use only these verdicts:

- `not_assessed`: external verification is incomplete.
- `collision`: closest work covers the central management problem and mechanism.
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

If `$ai4management` cannot be loaded, mark its checks `not_run` and report the missing dependency. Do not silently imitate its verdicts or describe the audit as complete.
