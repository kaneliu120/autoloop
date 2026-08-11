# Security Policy

## Supported versions

Security fixes are made on the current `main` branch. The project is currently
pre-1.0, so users should update to the latest commit before reporting a bug.

## Reporting a vulnerability

Please do **not** disclose vulnerabilities in public issues, discussions, pull
requests, logs, or examples. Use the repository's **Security** tab and select
**Report a vulnerability** to create a private report:

<https://github.com/kaneliu120/autoloop/security/advisories/new>

Include affected version or commit, reproduction steps, impact, and a minimal
proof of concept that contains no real credentials or production data. The
maintainer will acknowledge reports within seven days, assess reproducibility,
and coordinate a fix and disclosure timeline privately.

## Scope

Reports are especially useful for model-driven command execution, work-directory
paths and file writes, MCP arguments, API-key handling, custom API endpoints,
CI or dependency changes, and supply-chain risks. See
[`docs/SECURITY.md`](docs/SECURITY.md) for the current threat model and runtime
boundaries.
