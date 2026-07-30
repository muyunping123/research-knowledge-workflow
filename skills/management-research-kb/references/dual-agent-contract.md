# Dual-Agent Contract

This contract governs every substantive invocation of the skill.

## Cardinality Invariant

- Create exactly two Codex subagents, excluding the parent.
- Create both before delegating substantive analysis.
- Keep both alive for the invocation and reuse their IDs for every batch.
- Never create a supervisor, tie-breaker, replacement, or convenience agent.
- Do not allow either worker to create further agents.
- Close both workers before the parent returns, even on failure or cancellation.

A setup-only explanation or deterministic application of a previously approved and unchanged preview is not a substantive invocation. All `build-knowledge`, `ideate`, `write`, and `audit` analysis is substantive.

## Role Assignment

| Mode | Agent 1 | Agent 2 |
|---|---|---|
| `build-knowledge` | Local Literature Reader | Cross-Link Auditor |
| `ideate` | Idea Builder | Evidence-Constrained Writer |
| `write` | Idea Builder | Evidence-Constrained Writer |
| `audit` | Idea Builder | Evidence-Constrained Writer |

Do not switch roles during an invocation.

### Local Literature Reader

- Analyze the local PDF group by literature type.
- Extract page-located problems, theories, methods, settings, findings, limitations, and disagreements.
- Distinguish source statements from synthesis or inference.
- Return note-ready paraphrases and claim-ledger rows, never copied full text.

### Cross-Link Auditor

- Inspect the same PDF evidence plus existing and concurrently previewed category notes.
- Propose Obsidian wikilinks only when a relationship can be explained.
- Detect duplicate category notes, stale links, inconsistent terminology, conflicting findings, and filename collisions.
- Mark unresolved link targets instead of inventing notes or silently renaming files.

### Idea Builder

- Use `$ai4management` as a reasoning rubric for management story, theory, novelty, method logic, falsifiability, and venue fit.
- Generate or audit a focused research contribution from evidence IDs.
- Distinguish evidence-backed prior work from proposed mechanisms and hypotheses.

### Evidence-Constrained Writer

- Use `$ai4management` to preserve the management argument while drafting or auditing.
- Bind every material sentence to claim IDs, evidence IDs, citekeys, and locators.
- Flag unsupported, overclaimed, contradictory, or project-incompatible text.
- Preserve the target project's terminology and citation conventions.

## Parent-Only Responsibilities

Only the parent may:

- call the `management-research-kb` MCP or scholarly-search skills;
- select and normalize sources;
- freeze, version, and hash evidence packs;
- decide whether retrieval is sufficient;
- merge worker results;
- generate the final preview;
- request write approval;
- write through the MCP after approval;
- close agents.

Workers are read-only reasoning processes. They may request additional evidence by ID or query suggestion, but they may not retrieve or write it themselves.

## Dispatch Envelope

Send each worker its role brief plus the same envelope:

```yaml
task_id: ""
mode: "build-knowledge | ideate | write | audit"
agent_role: "role-specific value"
target: {}
goal: ""
constraints: []
evidence_pack:
  pack_id: ""
  version: 1
  digest: ""
  payload: {}
output_contract: "evidence-schema.md#agent-result-envelope"
permissions:
  mcp: false
  external_search: false
  filesystem_write: false
  spawn_agents: false
```

Role instructions may differ; `evidence_pack.payload`, version, and digest must not.

## Batch Lifecycle

1. Spawn the two required roles and record both IDs.
2. Freeze evidence pack version 1 and send it to both IDs.
3. Wait for both results and validate their pack IDs, versions, and digests.
4. If either requests justified evidence, the parent retrieves it, freezes the complete version 2, and sends version 2 to the same IDs.
5. Repeat within the configured budget without creating agents.
6. Merge only results produced from the same final pack version.
7. Close both IDs and record terminal status.

For multiple PDF groups, keep the two IDs and issue a new task segment plus a newly frozen pack version for each batch. Reset role-local conclusions between groups unless the new pack explicitly includes prior accepted synthesis.

## Recovery Rules

- Invalid output: ask the same agent ID once to repair its structure against the output contract.
- Timeout: wait or prompt the same agent ID within the remaining budget.
- Worker reports insufficient evidence: retrieve through the parent, then send the same new pack to both agents.
- Worker becomes unavailable: do not spawn a replacement. Mark the run `partial` or `blocked`, close the remaining worker, and return completed artifacts with the failure.
- Conflicting workers: the parent resolves by evidence level and locator quality. Preserve unresolved conflicts; never create a third opinion.

## Merge Rules

Merge by stable `claim_id` or category-note section ID:

1. Accept statements supported by appropriate evidence and consistent with the task.
2. Downgrade wording when support is abstract-only, indirect, or partial.
3. Mark useful unsupported ideas as hypotheses or `[EVIDENCE_NEEDED]`.
4. Reject fabricated, contradicted, out-of-scope, or untraceable content.
5. Preserve minority or conflicting evidence when it changes interpretation.

The parent owns the final result and must not represent worker agreement as scholarly evidence.

## Preview and Closure

For note or manuscript changes, finish the research run with an unapplied preview and source snapshot. Close both agents while awaiting user approval. A later apply-only action may proceed without agents only when the preview digest and target snapshot still match; otherwise start a new substantive invocation with exactly two agents.
