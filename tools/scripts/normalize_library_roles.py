
#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from eec_json_common import load_contract, discover_root, expand_patterns, write_json, backup_file, default_patterns_for_scope, canon_token

def fix_roles(obj, contract) -> bool:
    modified=False
    def walk(o):
        nonlocal modified
        if isinstance(o, dict):
            dtype=o.get('device_type')
            if dtype in ('SENSOR','ACTUATOR') and isinstance(o.get('signals'), list):
                for sig in o['signals']:
                    if not isinstance(sig, dict): continue
                    iface=canon_token(contract,'interfaces',sig.get('interface'))
                    old=sig.get('role')
                    if iface == 'POWER': new='SUPPLY'
                    elif iface == 'GROUND': new='GROUND'
                    elif iface in set(contract.get('rules',{}).get('bus_interfaces', [])): new=old or 'INOUT'
                    elif dtype == 'SENSOR': new=contract.get('rules',{}).get('sensor_default_signal_role','OUTPUT')
                    else: new=contract.get('rules',{}).get('actuator_default_signal_role','INPUT')
                    if new and old != new: sig['role']=new; modified=True
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for it in o: walk(it)
    walk(obj); return modified

def main():
    ap=argparse.ArgumentParser(description='Normalize device-centric signal roles without hard-coded role policy')
    ap.add_argument('paths', nargs='*'); ap.add_argument('--root', default=None); ap.add_argument('--contract', default=None)
    ap.add_argument('--write', action='store_true'); ap.add_argument('--backup-suffix', default='.rolefix.bak')
    args=ap.parse_args(); contract=load_contract(args.contract); root=discover_root(args.root)
    patterns=args.paths or default_patterns_for_scope(contract,'library')
    changed=[]
    for p in expand_patterns(patterns, root):
        try: data=json.loads(p.read_text(encoding='utf-8'))
        except Exception: continue
        if fix_roles(data, contract):
            changed.append(p)
            if args.write: backup_file(p,args.backup_suffix); write_json(p,data)
    for p in changed: print(('UPDATED ' if args.write else 'WOULD_UPDATE ') + str(p))
    print(f'done changed={len(changed)} write={args.write}')
    return 0
if __name__ == '__main__': raise SystemExit(main())
