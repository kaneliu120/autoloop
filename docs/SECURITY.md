# AutoLoop Security Notes

## Threat Model (Summary)

AutoLoop scripts run mainly on the **user's local machine** and are invoked through Claude Code / MCP / CLI. Typical inputs include:

- Workdir path
- `autoloop-state.json` and the rendered Markdown / TSV content
- Field paths and values written through `autoloop-state.py update` and similar commands
- Model-produced `planned_commands` in the optional unattended Runner
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and other environment configuration

## User-Controlled Paths and Subprocesses

The following entry points use externally supplied paths for file I/O or `subprocess`:

- `autoloop-controller.py`, `autoloop-state.py`, `autoloop-score.py`, and `autoloop-validate.py` all treat the **first argument as the workdir** and open `autoloop-state.json` plus adjacent files.
- `autoloop-controller.py`'s `run_tool` calls fixed script names from the same directory and does not execute arbitrary shell strings.
- **Strict mode** (`AUTOLOOP_STRICT` / `--strict`) can block later stages when VERIFY fails, reducing the risk of continuing in a broken state.
- The unattended Runner parses commands with `shlex`, uses `shell=False`, and
  requires a complete command-glob match. Its default allowlist resolves only
  bundled AutoLoop scripts, not paths under the task work directory.

**Remaining boundary**: a work directory is not a sandbox. Run only trusted
workdirs. A multi-tenant integration must enforce a canonical root directory,
reject symlink escapes, and separately authorize writes and Git operations.

## Optional: ACT Command Allowlist (Configuration)

The SSOT can set `plan.template_params.allowed_script_globs` or
`allowed_commands` as a string array for the Runner. Each pattern is matched
against the entire normalized command, never as a substring. This is trusted
operator configuration: do not allow `*`, a bare interpreter name, or a broad
shell command. Keep the default unless a reviewed task needs more.

## Credentials and Secrets

- Do not write API keys into `autoloop-state.json` or commit them to Git.
- Common runtime files are already ignored by `.gitignore`; use a dedicated workdir for sensitive environments.
- The Runner removes recognized credential variables from model-planned child
  processes. It does not replace operating-system sandboxing or protect an
  operator who deliberately permits an untrusted command.
- `OPENAI_BASE_URL` accepts HTTPS OpenAI and Azure OpenAI hosts by default. A
  custom compatible host requires `AUTOLOOP_ALLOW_CUSTOM_OPENAI_BASE_URL=1`
  because the OpenAI client sends the API key to that host.

## Reporting Issues

Do not put exploit details, credentials, or proof-of-concept code in a public
issue. Use the repository's private vulnerability reporting flow described in
[`SECURITY.md`](../SECURITY.md). Include only synthetic data in a proof of
concept and wait for acknowledgement before public disclosure.
