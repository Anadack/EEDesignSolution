#!/usr/bin/env python3
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
from eec_archdoc_common import *

SCRIPTS=[
'generate_architecture_allocation_matrix_html.py',
'generate_sensor_actuator_pin_matrix_html.py',
'generate_dataflow_system_diagram_html.py',
'generate_network_schematic_diagram_html.py',
'generate_ecu_dataflow_diagram_html.py',
'generate_ecu_dataflow_from_json_html.py',
'generate_network_bus_backbone_html.py',
'generate_connection_schematic_html.py',
'generate_professional_multi_ecu_wiring_html.py',
'generate_logical_architecture_html.py',
'generate_ecu_pinouts_stacked_html.py',
'generate_signal_flow_html.py',
'generate_architecture_tree_html.py',
'generate_architecture_wiring_html.py',
'generate_ecu_v3_config_validation_html.py',
'generate_architecture_completeness_report_html.py',
'generate_full_architecture_documentation_index.py',
]

ARCHITECTURE_HTML_SCRIPTS={
'generate_architecture_allocation_matrix_html.py',
'generate_logical_architecture_html.py',
'generate_ecu_pinouts_stacked_html.py',
'generate_signal_flow_html.py',
'generate_architecture_tree_html.py',
'generate_architecture_wiring_html.py',
}

def main()->int:
    parser=argparse.ArgumentParser(description='Generate the full tractor E/E HTML documentation suite from framework JSON exports.')
    parser.add_argument('--root',default='.') ; parser.add_argument('--input',default=None); parser.add_argument('--outdir',default=None); parser.add_argument('--config',default=None)
    parser.add_argument('--build-run',action='store_true',help='Build and run the C framework before generating docs.')
    parser.add_argument('--compiler',default=None); parser.add_argument('--app-name',default=None); parser.add_argument('--skip-build',action='store_true'); parser.add_argument('--skip-run',action='store_true')
    parser.add_argument('--strict',action='store_true',help='Exit non-zero if ANY generator fails (for CI gating). Default: run all, report at end.')
    args=parser.parse_args(); root=resolve_root(args.root)
    if args.build_run: build_and_run(root,args.compiler,args.app_name,args.skip_build,args.skip_run)
    tools=Path(__file__).resolve().parent
    results=[]  # (script, status, seconds, message)
    import time
    for script in SCRIPTS:
        cmd=[sys.executable,str(tools/script),'--root',str(root)]
        if args.input: cmd += ['--input',args.input]
        if script in ARCHITECTURE_HTML_SCRIPTS:
            cmd += ['--outdir', 'generated_doc/architecture_html']
        elif args.outdir:
            cmd += ['--outdir',args.outdir]
        if args.config: cmd += ['--config',args.config]
        print('[DOC]',script)
        t0=time.time()
        # Fault-tolerant: never let one broken generator abort the whole suite.
        proc=subprocess.run(cmd,capture_output=True,text=True)
        dt=time.time()-t0
        out=(proc.stdout or '')+(proc.stderr or '')
        if proc.returncode==0:
            status='SKIP' if '[SKIP]' in out else 'OK'
        else:
            status='FAIL'
        msg=''
        for line in out.splitlines():
            if any(k in line for k in ('[SKIP]','Error','error','Traceback','Exception')):
                msg=line.strip()[:120]; break
        results.append((script,status,dt,msg))
        if status!='OK':
            print(f'   -> {status}: {msg}')
    # Summary
    ok=sum(1 for _,s,_,_ in results if s=='OK')
    skip=sum(1 for _,s,_,_ in results if s=='SKIP')
    fail=sum(1 for _,s,_,_ in results if s=='FAIL')
    print('\n================ DOC SUITE SUMMARY ================')
    for script,status,dt,msg in results:
        tag={'OK':'  OK ','SKIP':' SKIP','FAIL':'FAIL '}[status]
        print(f'[{tag}] {script:<52} {dt:5.1f}s  {msg}')
    print('--------------------------------------------------')
    print(f'{ok} ok, {skip} skipped, {fail} failed, {len(results)} total')
    print('==================================================')
    # Default: succeed if nothing hard-failed (skips are tolerated).
    # --strict: any non-OK is a failure (CI gate).
    if args.strict:
        return 1 if (fail or skip) else 0
    return 1 if fail else 0
if __name__=='__main__': raise SystemExit(main())
