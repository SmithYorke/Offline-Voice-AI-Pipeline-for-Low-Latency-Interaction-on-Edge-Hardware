#!/usr/bin/env bash
set -euo pipefail
NOVA_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "${NOVA_PYTHON:-python3}" "$NOVA_SCRIPT_DIR/thermal_throttle_monitor.py" "$@"
