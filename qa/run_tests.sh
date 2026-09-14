#!/usr/bin/env bash
# =============================================================================
# qa/run_tests.sh — Build and run every hermetic C unit test in qa/.
#
# Each qa/test_*.c file owns its own main() and is compiled against the full
# EEC_*.c source set (src/main.c is excluded by the src/EEC_*.c glob, so there
# is no main()/main() clash). Every test is self-contained (uses tmpfile()/a
# portable temp dir, never a hardcoded path) and must be runnable from the
# repository root so relative library/*.json paths resolve correctly.
#
# Usage:
#   ./qa/run_tests.sh
#
# Add a new test: drop qa/test_<name>.c and add "<name>" to TESTS below.
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TESTS=(
    test_naming_convention
    test_library_import_export
    test_dbc_roundtrip
    test_es3_ecu_import
    test_busload_b9
    test_dbc_validate
    test_j1939_pgn
    test_power_budget_p1
    test_swc_dbc_import
    test_uibuilder_v8_export
    test_uibuilder_v7_swc_export
)

declare -a RESULTS=()
overall_status=0

for name in "${TESTS[@]}"; do
    src="qa/${name}.c"
    bin="qa/${name}"

    echo
    echo "========================================================================"
    echo "[BUILD] ${name}"
    echo "========================================================================"
    if ! gcc -std=c11 -Iinc -Wall -Wextra -O2 "$src" src/EEC_*.c -lm -o "$bin"; then
        echo "[FAIL]  ${name}: compilation failed"
        RESULTS+=("FAIL  ${name}  (build error)")
        overall_status=1
        continue
    fi
    echo "[OK]    Compiled -> $bin"

    echo
    echo "[RUN]   $bin"
    echo
    set +e
    "$bin"
    status=$?
    set -e

    if [ "$status" -eq 0 ]; then
        echo "[OK]    ${name} passed"
        RESULTS+=("OK    ${name}")
    else
        echo "[FAIL]  ${name} exited $status"
        RESULTS+=("FAIL  ${name}  (exit $status)")
        overall_status=1
    fi
done

echo
echo "========================================================================"
echo "  QA SUMMARY"
echo "========================================================================"
for line in "${RESULTS[@]}"; do
    echo "  $line"
done
echo "------------------------------------------------------------------------"
if [ "$overall_status" -eq 0 ]; then
    echo "[OK]    All qa test suites passed"
else
    echo "[FAIL]  One or more qa test suites failed"
fi
exit "$overall_status"
