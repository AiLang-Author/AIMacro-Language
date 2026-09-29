#!/usr/bin/env bash
# CPython 3.11 Lib/test regrtest (568 files). TestCase methods must run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
exec python3 tools/aimacro_cpython_runner.py \
  --output-json results/aimacro_regrtest.json \
  --output-md AIMacro/CONFORMANCE.md \
  "$@"
