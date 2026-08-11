# AutoLoop MCP setup for Codex

AutoLoop's MCP server is disabled until Codex is given a trusted workspace
root. This prevents model-supplied paths from reading or writing outside the
directory that the operator reviewed.

## Install

From the repository root, choose a directory that contains only task
workspaces you trust, then run:

```bash
bash mcp-server/install.sh /absolute/path/to/trusted-workspaces
```

The installer creates `mcp-server/.venv`, installs the bounded `mcp`
dependency there, and registers the stdio server with `codex mcp add`.
It sets `AUTOLOOP_MCP_WORKDIR_ROOT` only, so all MCP tools start read-only.
Review the chosen root before running it.

To enable mutating tools after that review, remove the existing registration
and reinstall with an explicit write switch:

```bash
codex mcp remove autoloop
bash mcp-server/install.sh --allow-write /absolute/path/to/trusted-workspaces
```

Verify the configuration with:

```bash
codex mcp list
```

## Experience-registry writes

`autoloop_experience write` is more restrictive than other write tools. It
requires `AUTOLOOP_MCP_EXPERIENCE_REGISTRY_PATH` to name an existing,
reviewed registry file inside the trusted root. After removing the existing
server, add it again with that environment variable only when that shared
registry is intentional:

```bash
codex mcp add autoloop \
  --env AUTOLOOP_MCP_WORKDIR_ROOT=/absolute/path/to/trusted-workspaces \
  --env AUTOLOOP_MCP_ALLOW_WRITE=1 \
  --env AUTOLOOP_MCP_EXPERIENCE_REGISTRY_PATH=/absolute/path/to/trusted-workspaces/references/experience-registry.md \
  -- /absolute/path/to/autoloop/mcp-server/.venv/bin/python \
     /absolute/path/to/autoloop/mcp-server/server.py
```

Do not point either path at a home directory, a repository checkout, or a
directory containing credentials. The MCP server rejects a missing root,
paths outside it, symlink escapes, and writes when the write flag is absent.
