#!/usr/bin/env python3
"""E/E Architect Design — Bundle all generated documents into a dated release package.

Includes generated_doc/exports/, generated_doc/architecture_html/, and
generated_doc/system_viewer/ in a single zip with manifest.json listing all
included files.

Usage:
  python tools/scripts/package_release.py                  # auto timestamp
  python tools/scripts/package_release.py --tag v1.2.0     # custom tag
  python tools/scripts/package_release.py --outdir releases # explicit output dir
"""
from __future__ import annotations

import argparse
import json
import zipfile
from datetime import datetime
from pathlib import Path


INCLUDE_GLOBS = ["*.html", "*.json", "*.txt", "*.csv"]
EXCLUDE_NAMES = {"automap_trace.txt"}


def collect_files(directory: Path, prefix: str = "") -> list[tuple[Path, str]]:
    """Collect files from directory, returning (file_path, archive_name) tuples."""
    found: list[tuple[Path, str]] = []
    if not directory.exists():
        return found
    for pattern in INCLUDE_GLOBS:
        for f in sorted(directory.glob(pattern)):
            if f.is_file() and f.name not in EXCLUDE_NAMES:
                arcname = f"{prefix}/{f.name}".lstrip("/")
                found.append((f, arcname))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description="Package E/E Architect Design all generated documents into a release zip.")
    ap.add_argument("--root", default=".", help="Framework workspace root.")
    ap.add_argument("--tag", default=None, help="Release tag, e.g. v1.0.0. Defaults to timestamp.")
    ap.add_argument("--outdir", default="releases", help="Output directory for the release zip.")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.outdir) if Path(args.outdir).is_absolute() else root / args.outdir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Define source directories and their archive prefixes
    gendir = root / "generated_doc"
    sources = [
        (gendir, ""),                                      # generated_doc/architecture_console.html → root of zip
        (gendir / "exports", ""),                          # generated_doc/exports → root of zip
        (gendir / "architecture_html", "docs"),   # generated_doc/architecture_html → docs/ in zip
        (gendir / "system_viewer", "system_viewer"),  # generated_doc/system_viewer → system_viewer/ in zip
    ]

    tag = args.tag or datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"EE_Architect_Design_release_{tag}.zip"
    zip_path = out_dir / zip_name

    # Collect all files
    all_files: list[tuple[Path, str]] = []
    for src_dir, prefix in sources:
        all_files.extend(collect_files(src_dir, prefix))

    if not all_files:
        print(f"[WARN] No files found in any source directories")
        return 0

    manifest: list[dict] = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for src_path, arcname in all_files:
            zf.write(src_path, arcname)
            size = src_path.stat().st_size
            manifest.append({"file": arcname, "size": size})
            print(f"  + {arcname}  ({size:,} B)")

        manifest_data = {
            "release": tag,
            "generated": datetime.now().isoformat(timespec="seconds"),
            "sources": [str(src) for src, _ in sources],
            "files": manifest,
            "total_files": len(manifest),
        }
        zf.writestr("manifest.json", json.dumps(manifest_data, indent=2))
        print(f"  + manifest.json  ({len(json.dumps(manifest_data, indent=2)):,} B)")

    size_kb = zip_path.stat().st_size // 1024
    print(f"\n[OK] {zip_path.name}  ({size_kb} KB)  — {len(all_files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
