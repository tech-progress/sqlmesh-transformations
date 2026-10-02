#!/usr/bin/env bash
set -euo pipefail
python scripts/check-ready.py
exec sqlmesh run prod "$@"
