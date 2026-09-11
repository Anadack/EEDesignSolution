#!/usr/bin/env bash
# =============================================================================
# qa/run_tests.sh — Build and run the library import/export/mapping test
#
# Compiles qa/test_library_import_export.c against the same EEC_*.c
# sources used by the main app (src/main.c is swapped out for the test's
# own main()), then runs it from the repository root so relative
# library/*.json paths resolve correctly.
#
# Usage:
#   ./qa/run_tests.sh
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/qa/test_library_import_export"

cd "$ROOT"

echo "[BUILD] Compiling test harness..."
gcc -Iinc -Wall -Wextra -O2 \
    qa/test_library_import_export.c \
    src/EEC_main_helpers.c    \
    src/EEC_library.c         \
    src/EEC_architecture.c    \
    src/EEC_verify.c          \
    src/EEC_export.c          \
    src/EEC_connect.c         \
    src/EEC_types.c           \
    src/EEC_agco.c            \
    src/EEC_log.c             \
    src/EEC_pin_helpers.c     \
    src/EEC_estimation.c      \
    src/EEC_component_loader.c \
    src/EEC_naming.c          \
    -lm -o "$BIN"
echo "[OK]    Compiled -> $BIN"

echo
echo "[RUN]   $BIN"
echo
set +e
"$BIN"
STATUS=$?
set -e

# ── DBC import/export round-trip test ───────────────────────────────────────
DBC_BIN="$ROOT/qa/test_dbc_roundtrip"
echo
echo "[BUILD] Compiling DBC round-trip test..."
gcc -Iinc -Wall -Wextra -O2 -std=c11 \
    qa/test_dbc_roundtrip.c \
    src/EEC_architecture.c  \
    src/EEC_message.c       \
    src/EEC_dbc.c           \
    src/EEC_types.c         \
    src/EEC_log.c           \
    src/EEC_naming.c        \
    src/EEC_pin_helpers.c   \
    -lm -o "$DBC_BIN"
echo "[OK]    Compiled -> $DBC_BIN"
echo
echo "[RUN]   $DBC_BIN"
echo
set +e
"$DBC_BIN"
DBC_STATUS=$?
set -e

echo
if [ "$STATUS" -eq 0 ] && [ "$DBC_STATUS" -eq 0 ]; then
    echo "[OK]    All checks passed"
else
    echo "[FAIL]  One or more checks failed (library=$STATUS dbc=$DBC_STATUS)"
    exit 1
fi
exit "$STATUS"
