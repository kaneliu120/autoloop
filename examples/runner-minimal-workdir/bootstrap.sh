#!/usr/bin/env bash
# Minimal example: initialize the work_dir and then let the Runner tick (run from the repo root)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WD="${1:-"$ROOT/examples/runner-minimal-workdir/my-task"}"
PY="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then PY="$ROOT/.venv/bin/python"; fi
mkdir -p "$WD"
export PYTHONPATH="$ROOT/services${PYTHONPATH:+:$PYTHONPATH}"
"$PY" "$ROOT/scripts/autoloop-controller.py" "$WD" --init --template T1 --goal "runner minimal demo"
echo "Initialized. First tick (ORIENT slice, no API key needed):"
RUNNER_MOCK_LLM=1 "$PY" -m autoloop_runner.cli tick "$WD"
echo "checkpoint.last_completed_phase should be ORIENT. For DECIDE+, set OPENAI_API_KEY or RUNNER_MOCK_LLM=1 and tick again."
