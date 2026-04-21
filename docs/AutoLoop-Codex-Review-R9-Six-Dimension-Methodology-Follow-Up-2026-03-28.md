# AutoLoop Codex Review R9 - Six-Dimension Methodology Re-review

**Review date**: 2026-03-28  
**Review tool**: OpenAI Codex CLI (xhigh reasoning effort + web_search_cached)  
**Review scope**: the full `~/Projects/autoloop` repository (R8 repaired pass)  
**Token usage**: 350,642  
**Review mode**: static source review (read-only)  
**Prior review**: R8 (3.7/10) → 23 repairs → this R9 re-review

---

## Total Score

| Dimension | Weight | R8 score | R9 score | Delta | Weighted (R9) |
|-----------|--------|---------|---------|-------|--------------|
| Measurement validity and consistency | 20% | 4.0 | **5.0** | +1.0 | 1.00 |
| Data-to-strategy closed loop | 20% | 3.0 | **4.8** | +1.8 | 0.96 |
| Convergence performance | 20% | 4.0 | **5.5** | +1.5 | 1.10 |
| Gate discriminative power | 10% | 4.0 | **4.0** | 0.0 | 0.40 |
| Task model fit | 10% | 5.0 | **5.0** | 0.0 | 0.50 |
| Self-evolution and compounding ability | 20% | 3.0 | **4.8** | +1.8 | 0.96 |
| **Weighted total** | **100%** | **3.7** | **4.9** | **+1.2** | **4.92** |

---

## Validation of R8 Repairs

| # | R8 issue | Repair status | Notes |
|---|----------|---------------|-------|
| 7 | TSV columns 13 → 15 | **Fixed** | The repository is now consistently 15 columns |
| 1 | Scorer / renderer format mismatch | **Partially fixed** | The base format is aligned, but single-paragraph findings still trigger the "≥2 information points" rule; completeness still mis-handles separate `Source:` lines |
| 2 | Experience registry not embedded in command layer | **Partially fixed** | All 7 commands reference OBSERVE / REFLECT, but the templates do not record registry I/O fields |
| 3 | Stagnation thresholds not wired into EVOLVE | **Partially fixed** | Thresholds are wired in, but evolution-rules still has conflicting rollback behavior |
| 6 | Self-evolution not embedded into the execution path | **Partially fixed** | The registry lifecycle is better, but dispatch still does not require registry-derived context |
| 10 | Governance cross-references | **Partially fixed** | Scope statements were added, but rollback semantics and version increments still diverge |
| 4 | Gate policy contradictions | **Unresolved** | The hard / soft matrix was added, but T1/T2/T5 pause rules still conflict, and `exempt` has no roll-up rule |
| 5 | Task-model bypass | **Unresolved** | Direct subcommands still bypass routing; README still encourages "direct template selection" |
| 8 | add-finding drops data | **Unresolved** | The guard was added, but render drops `strategy_id` and validate cannot find it, so the chain still breaks |
| 9 | Version semantics drift | **Unresolved** | loop-protocol now has a single definition, but state.py / init.py still reference the old semantics |

---

## Detailed Findings

### 1. Measurement Validity and Consistency (5.0/10, +1.0)

**Improvements**:
- The scorer added `_split_all_sections` / `_is_dimension_section` / `_count_info_points`, which adapts to the renderer's `###` dimension + separate `Source:` format
- TSV schema was aligned to 15 columns across the repository

**Still needs work**:
- Single-paragraph findings still trigger the "≥2 information points" rule, causing under-scoring
- Completeness still mis-handles separate `Source:` lines
- `add-finding` stored IDs are dropped by the renderer, breaking validation that expects them in markdown
- Version references in state.py and init.py still disagree with the loop-protocol source of truth

---

### 2. Data-to-Strategy Closed Loop (4.8/10, +1.8)

**Improvements**:
- The experience registry is now a mandatory OBSERVE input and REFLECT output at the protocol layer
- All 7 command files now reference experience-registry reads / writes
- experience-registry.md now has real lifecycle semantics

**Still needs work**:
- The runtime templates do not expose registry I/O audit fields
- The pipeline still only writes once at the end; there is no pipeline-level OBSERVE read
- Dispatch still wants local reflection context instead of registry-derived global context
- The state → render → validate chain still loses `strategy_id`, so traceability remains incomplete

---

### 3. Convergence Performance (5.5/10, +1.5)

**Improvements**:
- Template-specific stagnation thresholds really are wired into the protocol path
- T3 (<2%)/T6 (<0.3)/T7 (<0.5) have explicit values
- The stagnation state machine now points to replacement strategies instead of being purely declarative

**Still needs work**:
- evolution-rules still has conflicting rollback behavior: medium-risk changes are described as both "auto rollback" and "enter rollback evaluation"
- The same section uses `patch+1` for formal rule changes, which still does not fully match the version SSOT

---

### 4. Gate Discriminative Power (4.0/10, 0.0)

**Improvements**:
- T5 delivery flow is now stricter and clearer
- The gate-classification overview matrix has been added at the top of quality-gates.md

**Still needs work**:
- hard / soft semantics still conflict in several places: the matrix says soft gates are non-blocking and roll up as pass, but the quick matrix still pauses T1/T2/T5 for any unmet gate
- `gate_status` includes `exempt`, but no roll-up rule exists for it
- T5 Phase 4 still hardens service checks into blocking gates
- `gate_override` in orchestration.md still allows gate relaxation

---

### 5. Task Model Fit (5.0/10, 0.0)

**Improvements**:
- The plan path better centralizes template reasoning and confirmation
- Domain-pack hooks exist

**Still needs work**:
- Direct template bypass is still fully available
- README still says "select the template directly" is normal usage
- Domain packs remain opt-in, so omitting them loses stack-specific P1/P2 checks

---

### 6. Self-Evolution and Compounding Ability (4.8/10, +1.8)

**Improvements**:
- The registry now has lifecycle semantics
- The command path includes writeback descriptions
- Version semantics now have a single authoritative definition

**Still needs work**:
- Dispatch does not require registry-derived context
- The pipeline has no registry-fed loop
- Templates do not expose auditable learning I/O
- The findings projection is lossy, so IDs / links do not survive into downstream validation

---

## Top 3 Remaining Systemic Problems

| # | Problem | Root cause | Impacted dimension |
|---|---------|------------|--------------------|
| 1 | The state → render → validate chain is lossy | state.py stores finding IDs → render.py drops them → validate.py expects them in markdown | Measurement validity + closed loop |
| 2 | Gate semantics are internally inconsistent | The quality-gates matrix says soft gates are non-blocking, but rows and other sections still pause; `exempt` has no roll-up rule | Gate discriminative power |
| 3 | Task / template / domain-pack bypass is still possible | Direct subcommands are exposed + README encourages them + domain packs are opt-in | Task model fit |

## Top 3 Next Improvements

| # | Improvement | Expected impact |
|---|-------------|-----------------|
| 1 | Make JSON state the only validation contract, or make render output all IDs / links | Stops validating fields that render does not preserve |
| 2 | Merge gate semantics into one SSOT and define exact roll-up rules for hard / soft / exempt | Fixes contradictions across the orchestration path |
| 3 | Force plan-derived template selection and domain-pack loading in every entry point, and add registry I/O audit fields to templates | Improves task fit and self-evolution |

---

## Review Comparison

| Round | Date | Score | Delta | Main change |
|------|------|------|-------|-------------|
| R2 (Codex) | 03-26 | 2.9/10 | — | Initial architecture defects |
| R3-R7 (Claude) | 03-28 | 6.8/10 | — | Protocol documentation maturity (different review framework) |
| R8 (Codex) | 03-28 | 3.7/10 | — | Six-dimension methodology effectiveness (new framework) |
| **R9 (Codex)** | **03-28** | **4.9/10** | **+1.2** | **Review after 23 fixes** |

---

## Repair ROI Analysis

**Input**: 23 repairs, 25 files, +397 / -150 lines  
**Output**: +1.2 points (3.7 → 4.9)

| Dimension | Repairs invested | Delta produced | ROI |
|-----------|------------------|----------------|-----|
| Closed loop | F5+F2+F6+L1 (4 items) | +1.8 | High |
| Self-evolution | F5+F8+F10+L3 (4 items) | +1.8 | High |
| Convergence performance | F7+F6 (2 items) | +1.5 | Highest |
| Measurement validity | F1+F3+L5+F4+L4 (5 items) | +1.0 | Medium |
| Gate discriminative power | F4+L11 (2 items) | 0.0 | Low (needs deeper repair) |
| Task fit | F9+L6+F11+F12+L2 (5 items) | 0.0 | Low (needs structural change) |

**Conclusion**: protocol-level statement repairs have high ROI (closed loop + self-evolution + convergence), but gate power and task fit require **structural fixes at the end of the chain** (render / validate / dispatch / template), not just more references.
