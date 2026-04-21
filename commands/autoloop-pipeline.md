# autoloop-pipeline — Multi-Template Chain Execution

**Trigger words**: `pipeline`, `chain execution`, `research to delivery`, `end-to-end pipeline`

---

## Execution Flow

### Step 1: Determine the Pipeline Mode

**User specifies the chain**: parse the node sequence directly.
**User describes the goal**: recommend a matching predefined pipeline (see the predefined templates in `references/orchestration.md`).

Quick selection for predefined pipelines:
```
A) Research-to-Deliver: T1→T2→T4→T7 (research → compare → deliver → review)
B) Quality-then-Optimize: T7→T8 (review → optimize)
C) Research-to-Report: T1→T6 (research → batch generation)
D) Custom: specify the node sequence manually
```

### Step 2: Collect Parameters for Each Node

For each node in the pipeline:
1. Break down the node's specific goal from the overall pipeline objective
2. Confirm the input source (first node = user input, later nodes = upstream output)
3. Confirm whether any gate overrides are needed (default is no override)

After parameter collection, call `/autoloop:plan` to generate `autoloop-plan.md` with `type: pipeline`.

### Step 3: Initialize the Pipeline

1. Create `autoloop-pipeline-progress.md` in the working directory (format in `references/orchestration.md`)
2. Create a separate plan file for each node: `autoloop-plan-node{N}.md`
3. Create the standard runtime files (`findings` / `progress` / `results.tsv`)

### Step 4: Execute Node by Node

```text
for each node in pipeline:
  1. [Handoff] Read the upstream node output and map it to this node's input
     - Mapping rules are in the "output-to-input mapping" table in references/orchestration.md
     - Skip this step for the first node

  2. [Execute] Dispatch the corresponding template command
     - T1 → /autoloop:research
     - T2 → /autoloop:compare
     - T3 → /autoloop:design
     - T4 → /autoloop:deliver
     - T5 → /autoloop:iterate
     - T6 → /autoloop:generate
     - T7 → /autoloop:quality
     - T8 → /autoloop:optimize

  3. [Gate Check] Check gates after the node completes
     - All pass → extract output fields, update pipeline-progress.md, continue to the next node
     - Not pass → handle according to the failure strategy (see below)

  4. [Handoff Log] Record transferred fields and values in pipeline-progress.md
```

### Step 5: Failure Handling

The failure strategy is determined by the `node_failure` field in `autoloop-plan.md`:

| Strategy | Behavior |
|------|------|
| `retry_then_pause` (default) | Retry once → if it still fails, pause and ask the user to choose: retry / skip / abort |
| `skip_and_continue` | Mark as skipped, and let downstream nodes use the partial output that already exists |
| `abort_pipeline` | Abort the entire pipeline and output the results of the nodes completed so far |

**Cross-node rollback**: no automatic rollback. Pause and report the decision to the user.

### Step 6: Pipeline Completion

1. Aggregate all node results into the final report
2. Record pipeline-level lessons in `experience-registry.md`
3. Output a completion summary

```text
Pipeline completion summary:
  Goal: {goal}
  Nodes: {completed}/{total}
  Total elapsed: {N} rounds (across {M} nodes)
  Final result: {description}
```

---

## Data Transfer Rules Between Nodes

### Automatic Mapping (No Configuration Needed)

| Upstream Template | Downstream Template | Transferred Field | Description |
|---------|---------|---------|------|
| T1 | T2 | `key_conclusions` → candidate option list | T1 findings → T2 comparison |
| T2 | T4 | `recommendation` → requirement description | T2 recommendation → T4 implementation |
| T4 | T7 | code path → scan target | T4 delivery → T7 review |
| T7 | T8 | `remaining_issues` → optimization starting point | T7 leftovers → T8 optimization |

### Manual Mapping (Specified in the Pipeline Config)

```markdown
| From Node | To Node | Field |
|--------|--------|------|
| node_1 | node_3 | node_1.findings_path → node_3.reference_doc |
```

---

## Constraints

- Maximum of 5 nodes
- Only linear chains are supported (no branching or parallelism)
- Nested pipelines are not supported
- Each node fully reuses the single-template logic; the pipeline does not intervene
