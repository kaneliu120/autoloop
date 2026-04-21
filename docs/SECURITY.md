# AutoLoop Security Notes

## Threat Model (Summary)

AutoLoop scripts run mainly on the **user's local machine** and are invoked through Claude Code / MCP / CLI. Typical inputs include:

- Workdir path
- `autoloop-state.json` and the rendered Markdown / TSV content
- Field paths and values written through `autoloop-state.py update` and similar commands

## User-Controlled Paths and Subprocesses

The following entry points use externally supplied paths for file I/O or `subprocess`:

- `autoloop-controller.py`, `autoloop-state.py`, `autoloop-score.py`, and `autoloop-validate.py` all treat the **first argument as the workdir** and open `autoloop-state.json` plus adjacent files.
- `autoloop-controller.py`'s `run_tool` calls fixed script names from the same directory and does not execute arbitrary shell strings.
- **Strict mode** (`AUTOLOOP_STRICT` / `--strict`) can block later stages when VERIFY fails, reducing the risk of continuing in a broken state. ACT is still constrained by the operator, so only whitelist scripts and in-repo commands are recommended.

**Recommendation**: run only in trusted workdirs; in automated contexts, normalize the workdir path and reject escapes containing `..` (if a multi-tenant interface is exposed later, enforce this at the integration layer).

## Optional: ACT Command Allowlist (Configuration)

The SSOT can set `plan.template_params.allowed_script_globs` (string array) or `allowed_commands` (list of string fragments) for `autoloop-controller.py` to reference as **ACT-stage guidance**; the controller does not execute shell commands based on this list. When unset, behavior matches the legacy flow, and the operator remains responsible for constraining command sources during ACT.

## Credentials and Secrets

- Do not write API keys into `autoloop-state.json` or commit them to Git.
- Common runtime files are already ignored by `.gitignore`; use a dedicated workdir for sensitive environments.

## Reporting Issues

If you find command injection, path traversal, or subprocess abuse, report it privately through your team channel.
