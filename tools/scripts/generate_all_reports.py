#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from eec_report_common import *

REPORTS = [
 'generate_architecture_allocation_matrix_html.py',
 'generate_architecture_bus_backbone_html.py',
 'generate_architecture_bus_diagram_html.py',
 'generate_architecture_html_pinout.py',
 'generate_architecture_signal_flow_html.py',
 'generate_architecture_signal_flow_v2_html.py',
 'generate_architecture_topology_html.py',
 'generate_architecture_tree_html.py',
 'generate_architecture_wiring_html.py',
 'generate_logical_architecture_html.py',
 'generate_library_ecu_pinout_html.py',
]

def main() -> int:
    p=argparse.ArgumentParser(description='Generate all E/E Architect Design v4 HTML reports without building.'); p.add_argument('--root'); p.add_argument('--config'); p.add_argument('--outdir'); p.add_argument('--continue-on-error', action='store_true')
    args=p.parse_args(); root=resolve_root(args.root); py=default_python(load_config(Path(args.config) if args.config else None)); ok=True
    for script in REPORTS:
        cmd=[py, str(root/'tools'/'scripts'/script), '--root', str(root)]
        if args.config: cmd += ['--config', args.config]
        if args.outdir: cmd += ['--outdir', args.outdir]
        try: run_command(cmd, root, script)
        except Exception as exc:
            ok=False; print(f'[ERROR] {script}: {exc}', file=sys.stderr)
            if not args.continue_on_error: raise
    return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
