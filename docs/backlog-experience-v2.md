# Experience Registry v2 Capability Backlog (P-05)

This document aggregates the capabilities in `references/experience-registry.md` that are marked as **v2 reserved** and currently **not implemented in v1** into an epic backlog for scheduling purposes; it **does not** change v1 behavior. For cross-reference with the repository-level technical debt index, see `docs/TECH_DEBT.md`.

| Topic | Registry reference | Notes |
|------|--------------------|------|
| Canary validation | lifecycle diagram `[v2] Canary validation` | Promote only after one successful validation for the same task type |
| command promotion | write command, user confirmation, patch+1 | Make strategies executable as automation commands |
| promotion rollback | v2 rollback section | Remove from command after two consecutive deltas <= 0 |
| hierarchical labels strategic/procedural/tool | tagging rules, read priority | OBSERVE filters by layer and budget |
| table field expansion | `memory_layer`, `last_validated_date` columns | v1 can use `description @date` as an equivalent |
| strategy composition and ablation | separate section | multi-strategy A/B and attribution |
| protocol-change impact tracking | protocol change impact tracking table | governance and regression baseline |

Before implementing any topic, update `experience-registry.md` and `loop-protocol.md`, and add contract tests.
