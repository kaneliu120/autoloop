# Contributing to AutoLoop

Thank you for improving AutoLoop. The project combines a Codex Skill,
deterministic Python tools, an MCP server, and an optional unattended Runner,
so changes must preserve both the documented workflow and the executable
contracts.

## Before opening a pull request

1. Use Python 3.10 or later.
2. Install the development and Runner extras: `python -m pip install -e ".[dev,runner]"`.
3. Run `python3 -m unittest discover -s tests -v`.
4. Do not commit runtime artifacts, API keys, local logs, or files from a task
   work directory.

## Change requirements

- Keep core scripts standard-library-only unless a dependency is necessary and
  documented in `pyproject.toml`.
- Add a regression test for behavior changes in `scripts/`,
  `services/autoloop_runner/`, or `mcp-server/`.
- Update `README.md`, `docs/RUNNER.md`, or the relevant reference when a CLI,
  MCP, environment, state-schema, or security contract changes.
- Do not broaden a Runner command allowlist, file-write scope, or network
  endpoint without a documented threat-model update and maintainer review.
- Keep generated changes reviewable. AutoLoop must not merge, publish, or
  release model-generated changes without human approval.

## Pull request review

Explain the problem, the chosen behavior, the tests run, and any migration or
security impact. Maintainers may request a smaller change, more tests, or a
separate security review before merge.

## Security reports

Do not disclose a suspected vulnerability in a public issue. Follow
[`SECURITY.md`](SECURITY.md) to use the repository's private vulnerability
reporting flow.
