#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
from eec_report_common import *

def main() -> int:
    p=argparse.ArgumentParser(description='Build/run framework and generate wiring report generically.')
    p.add_argument('--root'); p.add_argument('--config'); p.add_argument('--compiler'); p.add_argument('--python'); p.add_argument('--app-name'); p.add_argument('--skip-build', action='store_true'); p.add_argument('--skip-run', action='store_true'); p.add_argument('--input'); p.add_argument('--output'); p.add_argument('--outdir')
    args=p.parse_args(); cfg=load_config(Path(args.config) if args.config else None); root=resolve_root(args.root)
    compiler=args.compiler or default_compiler(cfg); py=args.python or default_python(cfg); app_name=args.app_name or default_app_name(cfg); app_path=root/app_name
    if not args.skip_build: app_path=build_demo(root,compiler,app_name)
    if not args.skip_run: run_demo(root,app_path)
    gen=root/'tools'/'scripts'/'generate_architecture_wiring_html.py'
    cmd=[py, str(gen), '--root', str(root)]
    if args.config: cmd += ['--config', args.config]
    if args.input: cmd += ['--input', args.input]
    if args.output: cmd += ['--output', args.output]
    if args.outdir: cmd += ['--outdir', args.outdir]
    run_command(cmd, root, 'Generate wiring HTML')
    return 0
if __name__=='__main__': raise SystemExit(main())
