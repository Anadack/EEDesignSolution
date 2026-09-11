#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def find_base() -> Path:
    script_dir = Path(__file__).resolve().parent
    if (script_dir.parent / "src").exists() and (script_dir.parent / "tools").exists():
        return script_dir.parent
    return script_dir


def run_command(command: list[str], cwd: Path, label: str) -> None:
    print(f"[STEP] {label}")
    print(" ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def build_demo(base: Path, compiler: str, app_name: str) -> Path:
    sources = sorted((base / "src").glob("*.c"))
    if not sources:
        raise FileNotFoundError("No C source files found in src/")
    app_path = base / app_name
    run_command([
        compiler, "-std=c11", "-Wall", "-Wextra", "-pedantic", "-O2", "-Iinc",
        *[str(path.relative_to(base)) for path in sources], "-o", str(app_path.relative_to(base))
    ], base, "Build demo executable from src/main.c")
    return app_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the AM demo, run it, and generate the bus communication HTML view.")
    parser.add_argument("--compiler", default="C:/mingw64/bin/gcc.exe")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--app-name", default="app.exe" if sys.platform.startswith("win") else "app")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-run", action="store_true")
    args = parser.parse_args()

    base = find_base()
    generator_script = base / "tools" / "generate_architecture_bus_diagram_html.py"
    app_path = base / args.app_name
    json_path = base / "exports" / "example_physical_architecture.json"
    html_path = base / "exports" / "architecture_bus_diagram.html"

    if not generator_script.exists():
        raise FileNotFoundError(f"Missing generator script: {generator_script}")
    if not args.skip_build:
        app_path = build_demo(base, args.compiler, args.app_name)
    elif not app_path.exists():
        raise FileNotFoundError(f"Missing executable: {app_path}")
    if not args.skip_run:
        run_command([str(app_path)], base, "Run demo executable to refresh physical architecture JSON")
    elif not json_path.exists():
        raise FileNotFoundError(f"Missing exported JSON: {json_path}")

    run_command([args.python, str(generator_script.relative_to(base))], base, "Generate bus diagram HTML from exported JSON")
    print(f"[OK] JSON: {json_path}")
    print(f"[OK] HTML: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())