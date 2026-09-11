#!/usr/bin/env bash
# =============================================================================
# qa/run_naming_tests.sh — Build and run naming convention unit tests
#
# Compiles qa/test_naming_convention.c against the naming convention
# library (src/EEC_naming.c) and runs it to verify all naming convention
# functions work correctly.
#
# Usage:
#   ./qa/run_naming_tests.sh
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/qa/test_naming_convention"

cd "$ROOT"

echo "[BUILD] Compiling naming convention test harness..."
gcc -Iinc -Wall -Wextra -O2 \
    qa/test_naming_convention.c \
    src/EEC_naming.c          \
    src/EEC_types.c           \
    -lm -o "$BIN"
echo "[OK]    Compiled -> $BIN"

echo
echo "[RUN]   $BIN"
echo
"$BIN"
STATUS=$?

echo
if [ "$STATUS" -eq 0 ]; then
    echo "[OK]    All naming convention tests passed"
else
    echo "[FAIL]  One or more tests failed (exit $STATUS)"
fi
exit "$STATUS"
