#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
exec .mac-runtime/venv/bin/python scam_drift_qa.py "$@"
