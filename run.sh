#!/usr/bin/env bash
# =============================================================================
# run.sh — E/E Architect Design full build + report pipeline
#
# Executes in order:
#   1. Compile   — build the C framework binary (app)
#   2. Run       — execute app, refresh generated_doc/exports/
#   3. Arch HTML — architecture views (allocation, bus, signal-flow, pinout…)
#   4. Doc suite — signal dictionary, dataflow, safety trace, harness book…
#   5. Extras    — estimation, system overview, system config viewer
#   6. Draw.io   — print-ready .drawio exports (Polarion / A4)
#
# Usage:
#   ./run.sh                   full pipeline
#   ./run.sh --skip-build      reuse existing binary (re-run + reports only)
#   ./run.sh --skip-run        rebuild binary but skip app execution
#   ./run.sh --skip-build --skip-run   reports only (need generated_doc/exports/ already present)
#
# Release packaging is intentionally EXCLUDED from this pipeline.
# To package a release run separately:
#   python3 tools/scripts/package_release.py
# =============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$ROOT/tools/scripts"
GENDIR="$ROOT/generated_doc"
APP="$ROOT/app"

SKIP_BUILD=0
SKIP_RUN=0
WARN_COUNT=0
TOTAL_STEPS=8

for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=1 ;;
        --skip-run)   SKIP_RUN=1 ;;
        *) echo "[WARN] Unknown argument ignored: $arg" ;;
    esac
done

# -----------------------------------------------------------------------------
step() {
    echo
    echo "══════════════════════════════════════════════════════════════"
    printf "  STEP %d/%d  %s\n" "$1" "$TOTAL_STEPS" "$2"
    echo "══════════════════════════════════════════════════════════════"
}

py_run() {
    local script="$1"; shift
    echo "[PY]  $script"
    (cd "$TOOLS" && python3 "$TOOLS/$script" --root "$ROOT" "$@") \
        || { echo "[WARN] $script exited with errors" >&2; WARN_COUNT=$((WARN_COUNT + 1)); }
}

# =============================================================================
# STEP 1 — Compile C framework
# =============================================================================
step 1 "Compile C framework"

if [ "$SKIP_BUILD" -eq 0 ]; then
    cd "$ROOT"
    gcc -Iinc -Wall -Wextra -O2 \
        src/main.c                \
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
        src/EEC_message.c         \
        src/EEC_dbc.c             \
        src/EEC_datadict.c        \
        src/EEC_swc_loader.c      \
        src/EEC_zone.c            \
        -lm -o app
    echo "[OK]  Compiled → $APP"
else
    echo "[SKIP] --skip-build: reusing existing binary"
fi

# =============================================================================
# STEP 2 — Run C framework (populates generated_doc/exports/)
# =============================================================================
step 2 "Run C framework — refresh generated_doc/exports/"

if [ "$SKIP_RUN" -eq 0 ]; then
    cd "$ROOT"
    ./app
    echo "[OK]  Framework run complete — generated_doc/exports/ updated"
else
    echo "[SKIP] --skip-run: using existing generated_doc/exports/"
fi

# =============================================================================
# STEP 3 — Signal naming convention validation
# =============================================================================
step 3 "Signal naming convention validation (SYSTEM_Function_[POSITION_]TYPE)"

(cd "$TOOLS" && python3 validate_signal_naming.py --root "$ROOT") \
    || echo "[INFO]  Naming warnings emitted above — pipeline continues"

# =============================================================================
# STEP 4 — Architecture HTML reports
#
# Runs the architecture-level suite via generate_all_reports.py:
#   - Signal-to-ECU allocation matrix
#   - Bus backbone diagram
#   - Bus topology diagram
#   - ECU pin-out tables
#   - Signal flow (v1 and v2)
#   - Architecture tree
#   - Wiring overview
#   - Logical architecture view
#   - Library ECU pin-out
# =============================================================================
step 4 "Architecture HTML reports (allocation, bus, signal-flow, topology, wiring…)"

(cd "$TOOLS" && python3 generate_all_reports.py --root "$ROOT" --continue-on-error) \
    || { echo "[WARN] Some architecture reports failed" >&2; WARN_COUNT=$((WARN_COUNT + 1)); }

# =============================================================================
# STEP 5 — Documentation suite
#
# Runs the full v4 documentation suite via generate_all_architecture_docs.py:
#   - Signal dictionary  ← data dictionary (signal_dictionary.html + .csv)
#   - Communication matrix
#   - Dataflow context / system / signal-detail diagrams
#   - Power distribution
#   - Grounding architecture
#   - Harness & connector book
#   - Wiring netlist
#   - Diagnostics matrix
#   - Safety concept trace
#   - Variant/option matrix
#   - Change impact report
#   - Architecture completeness report
#   - Full documentation index
# =============================================================================
step 5 "Documentation suite — signal dictionary, dataflow, safety, harness…"

(cd "$TOOLS" && python3 generate_all_architecture_docs.py --root "$ROOT") \
    || { echo "[WARN] Some documentation reports failed" >&2; WARN_COUNT=$((WARN_COUNT + 1)); }

# =============================================================================
# STEP 6 — Standalone reports not covered by the suites above
# =============================================================================
step 6 "Standalone reports — estimation, system overview, config viewer, connector view"

py_run generate_estimation_html.py
py_run generate_system_overview_html.py
py_run generate_system_configuration_viewer_html.py
py_run generate_connector_view_html.py

# =============================================================================
# STEP 7 — Single-file architecture console (bundles every report above)
# =============================================================================
step 7 "Architecture console — single-file bundle of every report"

py_run generate_architecture_console_html.py

# =============================================================================
# STEP 8 — Print-ready draw.io exports (Polarion / A4)
#
# Kept as its own non-fatal step (like STEP 6/7 above, via py_run) rather
# than folded into generate_all_architecture_docs.py: this format is still
# being validated against a real Polarion instance, so a problem here must
# never be able to fail the --strict documentation gate CI runs separately —
# see generate_drawio_exports.py's own docstring.
# =============================================================================
step 8 "Print-ready draw.io exports (Polarion / A4)"

py_run generate_drawio_exports.py

# =============================================================================
# Summary
# =============================================================================
echo
echo "══════════════════════════════════════════════════════════════"
if [ "$WARN_COUNT" -gt 0 ]; then
    echo "  DONE — $WARN_COUNT step(s) reported warnings (see above)"
else
    echo "  ALL DONE — pipeline completed without errors"
fi
echo
echo "  Exports : $GENDIR/exports/"
echo "  Reports : $GENDIR/architecture_html/"
echo "  Console : $GENDIR/architecture_console.html  (single-file, all reports embedded)"
echo "  Draw.io : $GENDIR/drawio/  (Polarion / A4 print-ready)"
echo
echo "  Release packaging (separate step):"
echo "    python3 tools/scripts/package_release.py"
echo "══════════════════════════════════════════════════════════════"
