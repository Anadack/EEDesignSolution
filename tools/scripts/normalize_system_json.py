
#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from eec_json_common import load_contract, discover_root, expand_patterns, write_json, migrate_legacy_device

def normalize_system(data, contract):
    modified=False
    if not isinstance(data, dict): return data, False
    if data.get('type') != 'system': return data, False
    # Preserve both v4 components[] and legacy devices[]. If only devices[] exists,
    # create a generic component wrapper without deleting original information.
    if 'components' not in data and isinstance(data.get('devices'), list):
        data['components']=[{'type':'component','schema_version':'eec-component-1.0','name': data.get('name','System') + '_Component','is_mandatory': True,'mapping_enabled': True,'sensors': [],'actuators': []}]
        for d in data.get('devices', []):
            if not isinstance(d, dict): continue
            nd, _=migrate_legacy_device(d, contract)
            if nd.get('device_type') == 'ACTUATOR': data['components'][0]['actuators'].append(nd)
            else: data['components'][0]['sensors'].append(nd)
        modified=True
    return data, modified

def main():
    ap=argparse.ArgumentParser(description='Normalize system JSON to v4 component/sensor/actuator hierarchy')
    ap.add_argument('paths', nargs='*'); ap.add_argument('--root', default=None); ap.add_argument('--contract', default=None); ap.add_argument('--outdir', required=True)
    args=ap.parse_args(); contract=load_contract(args.contract); root=discover_root(args.root)
    patterns=args.paths or contract.get('default_paths',{}).get('system_globs',['library/systems/**/*.json'])
    count=0
    for p in expand_patterns(patterns, root):
        try: data=json.loads(p.read_text(encoding='utf-8'))
        except Exception as e: print('ERROR', p, e); continue
        new, mod=normalize_system(data, contract)
        out=Path(args.outdir) / p.name
        if not out.is_absolute(): out=root/out
        write_json(out, new); count+=1; print(('NORMALIZED ' if mod else 'COPIED ') + str(out))
    print('done files=', count)
    return 0
if __name__ == '__main__': raise SystemExit(main())
