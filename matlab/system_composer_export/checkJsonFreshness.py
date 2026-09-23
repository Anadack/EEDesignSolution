#!/usr/bin/env python3
"""Detect EEDesignSolution system JSON files that are stale relative to
the System Composer model that produced them.

Every JSON written by exportEECSystemJSON.m carries a traceability stamp:

    "metadata": {
        "source_model": "BrakingSystem_ABS.slx",
        "exported_at": "2026-09-23T14:05:00.123Z",
        "exporter": "matlab/system_composer_export"
    }

This script needs no MATLAB and no System Composer. It compares each
JSON's exported_at timestamp against the CURRENT last-modified time of
its source .slx file (located under --models-dir). If the model file is
newer than the export, the model was saved again since — the JSON is
probably stale and should be re-exported.

This is a heuristic, not a proof: it flags "the model file changed after
this JSON was written", not "a tag-relevant property actually changed" —
a purely cosmetic canvas-layout save will also flag as stale. That is an
intentional trade-off (the same one `make` makes with file mtimes) for
not needing MATLAB to run the check at all — for example in CI, or as a
pre-commit hook, on a machine that has never had System Composer on it.
For an exact, no-false-positive answer, or to close the loop
automatically, see installAutoExportOnSave.m (re-exports and
re-validates on every model save) in this same folder.

Usage:
    python3 checkJsonFreshness.py --models-dir /path/to/slx/files
    python3 checkJsonFreshness.py --root /path/to/repo --models-dir /path/to/slx/files
    python3 checkJsonFreshness.py --models-dir /path/to/slx/files path/to/one.json path/to/two.json
    python3 checkJsonFreshness.py --models-dir /path/to/slx/files --json

With no explicit paths, checks every *.json under <root>/library/systems/.

Exit code: 0 if nothing is definitely STALE (FRESH / unverifiable files do
not fail the check — an unverifiable file just cannot be vouched for);
1 if at least one file is definitely STALE.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# exportEECSystemJSON.m stamps milliseconds (not whole seconds) on purpose:
# an auto-export-on-save can run within the same second as the model's own
# save. strptime's %f accepts 1-6 fractional digits, so MATLAB's 3-digit
# milliseconds parse here without a format mismatch.
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

# Absorbs residual clock/filesystem noise this script cannot control (some
# filesystems round mtimes to whole seconds regardless of the timestamp
# string's own precision). A model saved more than this long after the
# recorded export is STALE; anything within it is treated as the same
# moment, matching how build tools like `make` tolerate mtime granularity.
STALE_TOLERANCE_SECONDS = 2


def parse_exported_at(value):
    return datetime.strptime(value, TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)


def model_mtime(models_dir, source_model):
    if not source_model:
        return None
    candidate = Path(models_dir) / source_model
    if not candidate.is_file():
        return None
    return datetime.fromtimestamp(candidate.stat().st_mtime, tz=timezone.utc)


def check_file(path, models_dir):
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return {"file": str(path), "status": "ERROR", "detail": f"could not read/parse: {exc}"}

    metadata = data.get("metadata") if isinstance(data, dict) else None
    if not isinstance(metadata, dict) or not metadata.get("source_model") or not metadata.get("exported_at"):
        return {"file": str(path), "status": "NO_STAMP",
                "detail": "no metadata.source_model / metadata.exported_at — "
                          "not produced by exportEECSystemJSON.m (or an export from before this feature)"}

    source_model = metadata["source_model"]
    try:
        exported_at = parse_exported_at(metadata["exported_at"])
    except ValueError as exc:
        return {"file": str(path), "status": "ERROR", "detail": f"unparseable exported_at: {exc}"}

    mtime = model_mtime(models_dir, source_model)
    if mtime is None:
        return {"file": str(path), "status": "MODEL_NOT_FOUND",
                "detail": f"'{source_model}' not found under {models_dir} — cannot verify"}

    if mtime > exported_at + timedelta(seconds=STALE_TOLERANCE_SECONDS):
        return {"file": str(path), "status": "STALE",
                "detail": f"{source_model} saved {mtime.isoformat()}, "
                          f"JSON exported {exported_at.isoformat()} — re-export recommended"}

    return {"file": str(path), "status": "FRESH",
            "detail": f"{source_model} unchanged since export ({exported_at.isoformat()})"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="JSON files to check; default: library/systems/*.json under --root")
    ap.add_argument("--root", default=".", help="project root, used only for the default glob (default: .)")
    ap.add_argument("--models-dir", required=True, help="directory containing the .slx source models")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON output instead of text")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if args.paths:
        paths = [Path(p) for p in args.paths]
    else:
        paths = sorted((root / "library" / "systems").glob("*.json"))

    results = [check_file(p, args.models_dir) for p in paths]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"[{r['status']:14}] {r['file']}: {r['detail']}")
        fresh = sum(1 for r in results if r["status"] == "FRESH")
        stale = sum(1 for r in results if r["status"] == "STALE")
        unverifiable = len(results) - fresh - stale
        print(f"\n{len(results)} file(s) checked: {fresh} fresh, {stale} stale, {unverifiable} unverifiable")

    return 1 if any(r["status"] == "STALE" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
