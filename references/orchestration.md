# Orchestration — Multi-Template Composition Protocol

## Overview

Multi-template orchestration (Pipeline) is an advanced AutoLoop capability: it chains multiple templates by dependency into one execution flow, enabling a fully automated "from research to delivery" process. A single template is the atomic unit of AutoLoop; a Pipeline is the molecule.

**Relationship to other files**:
- `loop-protocol.md`: defines the OODA loop for a single template; each node in a Pipeline follows that loop
- `quality-gates.md`: each node's termination criteria still come from the corresponding template's gates
- `parameters.md`: each node has independent iteration parameters; the Pipeline does not override node parameters
- `evolution-rules.md`: Pipeline-level changes such as skipping or inserting nodes require user confirmation

---

## Core Concepts

### Pipeline

An ordered chain of template executions. Each node is one template instance (T1-T8), and nodes are connected by **output-to-input mapping**.

```text
Pipeline = [Node_1] → [Node_2] → ... → [Node_N]
```

### Node

One execution unit in the Pipeline. Each node contains:
- **template**: the template to use (T1-T8)
- **goal**: the node's specific goal, broken down from the Pipeline goal
- **input_from**: input source (upstream node output fields)
- **output_fields**: fields produced by the node for downstream use
- **gate_override**: optional gate override (only loosening is allowed; tightening is not)

### Output-to-Input Mapping (Handoff)

The data transfer rules between nodes. Each template has normalized output fields:

| Template | Standard Output Fields | Description |
|------|------------|------|
| T1 Research | `findings_path`, `dimensions`, `key_conclusions` | research results, dimension list, key conclusions |
| T2 Compare | `recommendation`, `ranked_options`, `comparison_matrix` | recommended option, ranking, comparison matrix |
| T5 Iterate | `final_kpi`, `improvement_log`, `best_strategy` | final KPI value, improvement log, best strategy |
| T6 Generate | `output_files`, `pass_rate`, `average_score` | generated file list, pass rate, average score |
| T4 Deliver | `deployed_url`, `verification_status`, `delivery_report` | deployment URL, verification status, delivery report |
| T7 Quality | `audit_report`, `score_summary`, `remaining_issues` | audit report, score summary, remaining issues |
| T8 Optimize | `audit_report`, `score_summary`, `optimizations_applied` | audit report, score summary, applied optimizations |

**Mapping rules**:
- T1 → T2: T1 `key_conclusions` automatically become T2's candidate option list
- T2 → T4: T2 `recommendation` automatically fills T4's requirement description
- T4 → T7: T4's delivered code path automatically becomes T7's scan target
- T7 → T8: T7 `remaining_issues` automatically become T8's optimization starting point
- Custom mapping: users may define any mapping in the Pipeline config

---

## Pipeline Configuration

Pipelines are configured in `autoloop-plan.md` (enabled when `type: pipeline`):

```markdown
## Pipeline Configuration

type: pipeline
goal: {one-line end-to-end goal description}

### Node Definitions

| Order | Template | Goal | Input Source | Gate Override |
|------|------|------|---------|---------|
| 1 | T1 | Research technical solutions for {domain} | — | — |
| 2 | T2 | Compare the top 3 solutions found in T1 | node_1.key_conclusions | — |
| 3 | T4 | Implement the solution recommended by T2 | node_2.recommendation | — |
| 4 | T7 | Review the code quality delivered by T4 | node_3.deployed_url | — |

### Failure Strategy

node_failure: retry_then_pause
max_retries_per_node: 1
```

---

## Execution Flow

### Phase 1: Pipeline Initialization

1. Parse the Pipeline configuration and build the execution DAG (the current version only supports a linear chain)
2. Generate a separate `autoloop-plan-node{N}.md` for each node
3. Create `autoloop-pipeline-progress.md` to track Pipeline-level progress

### Phase 2: Node Execution

Execute each node in order:

```text
1. Read the upstream node output (skip for the first node)
2. Map the input into this node's plan parameters
3. Run the standard OODA loop (fully reusing single-template logic)
4. After the node completes, write the output fields into pipeline-progress.md
5. Move to the next node
```

**Key principle**: the internal execution logic of a node **does not change** at all. The Pipeline only handles the handoff between nodes and does not interfere with the node's OODA loop.

### Phase 3: Pipeline Completion

After all nodes complete:
1. Generate the final Pipeline report (aggregating results from all nodes)
2. Record Pipeline-level experience in `experience-registry.md`

---

## Failure Handling

### Node Failure Strategies

| Strategy | Behavior | When to Use |
|------|------|---------|
| `retry_then_pause` | node fails → retry once → if it still fails, pause and wait for the user's decision | default strategy |
| `skip_and_continue` | node fails → mark skipped → continue with the next node | non-critical nodes |
| `abort_pipeline` | node fails → abort the entire Pipeline | critical path nodes |

### Rollback Rules

- **Single-node rollback**: handle node-level failures using the standard rollback mechanism in `loop-protocol.md`
- **Cross-node rollback**: automatic cross-node rollback is not supported. If T4 discovers that T2's recommendation is flawed, pause the Pipeline and report the decision to the user
- **Reason**: cross-node rollback requires re-running upstream nodes, which is expensive and unpredictable. Human judgment is needed to decide whether it is worth it

---

## Predefined Pipeline Templates

### Research-to-Deliver

```
T1 Research → T2 Compare → T4 Deliver → T7 Quality
```
Use when you need to research technical solutions first, compare candidates, then implement and review.

### Quality-then-Optimize

```
T7 Quality → T8 Optimize
```
Use when you want to review the existing code quality first and then optimize the issues that were found.

### Research-to-Report

```
T1 Research → T6 Generate
```
Use when you want to research first and then batch-generate content such as reports or copy.

---

## Constraints

1. **Linear chain only**: the current version supports only linear Pipelines (A→B→C), not branching or parallel nodes. Future versions may expand to DAGs.
2. **Maximum node count**: a single Pipeline may contain at most 5 nodes. If more are needed, split it into multiple Pipelines.
3. **No nesting**: a Pipeline node cannot contain another Pipeline.
4. **Gate inheritance**: each node uses the standard gates for its template. `gate_override` may only relax a gate (for example lowering coverage from 85% to 70%); it cannot tighten one.

**gate_override constraints**:
- Only Hard Gates may be downgraded to Soft Gates (recorded but non-blocking); gates cannot be removed entirely
- The override reason must be declared in the pipeline plan
- Hard Gates for the security dimension cannot be overridden (the P1=0 rule cannot be downgraded)
5. **Independent experience**: each node produces its own experience entry in `experience-registry.md`; Pipeline-level tracking records only the overall execution efficiency.

---

## Pipeline Progress File Format

`autoloop-pipeline-progress.md` records Pipeline-level progress:

```markdown
# Pipeline Progress

## Overview
- Pipeline: {goal}
- Node count: {N}
- Current node: {M}/{N}
- Status: running / completed / paused

## Node Status

| Node | Template | Status | Gate Score | Time (rounds) | Output Summary |
|------|------|------|---------|-----------|---------|
| 1 | T1 | Completed | Coverage 92% | 3 rounds | Found 5 candidate solutions |
| 2 | T2 | Running | — | 1 round | — |
| 3 | T4 | Pending | — | — | — |
| 4 | T7 | Pending | — | — | — |

## Handoff Log

| From | To | Transferred Field | Value Summary |
|----|----|---------|--------|
| Node 1 | Node 2 | key_conclusions | [Solution A, Solution B, Solution C] |
```
