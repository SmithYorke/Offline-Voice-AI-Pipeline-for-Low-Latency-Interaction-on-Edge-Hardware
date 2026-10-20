#!/usr/bin/env bash
# Restored entry point; process orchestration is now in nova/pipeline.py.
set -euo pipefail
NOVA_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$NOVA_ROOT"
exec "${NOVA_PYTHON:-python3}" -m nova run "$@"
