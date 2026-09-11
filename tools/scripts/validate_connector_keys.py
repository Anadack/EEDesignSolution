
#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from collections import Counter
from eec_json_common import load_contract, discover_root, expand_patterns, default_patterns_for_scope, known_keys

def collect(obj, result):
    if isinstance(obj, dict):
        if isinstance(obj.get('connectors'), list):
            for c in obj['connectors']:
                if isinstance(c, dict): result.append(sorted(c.keys()))
        if isinstance(obj.get('connector'), dict): result.append(sorted(obj['connector'].keys()))
        for v in obj.values(): collect(v, result)
    elif isinstance(obj, list):
        for it in obj: collect(it, result)

def main():
    ap=argparse.ArgumentParser(description='Report connector keys and compare them with the configurable contract')
    ap.add_argument('paths', nargs='*'); ap.add_argument('--root', default=None); ap.add_argument('--contract', default=None); ap.add_argument('--out', default='generated_doc/exports/connector_keys_report.json')
    args=ap.parse_args(); contract=load_contract(args.contract); root=discover_root(args.root)
    files=expand_patterns(args.paths or default_patterns_for_scope(contract,'library'), root)
    expected=known_keys(contract,'connector')
    by_file={}; union=set(); mismatches={}
    for p in files:
        try: data=json.loads(p.read_text(encoding='utf-8'))
        except Exception: continue
        keys=[]; collect(data, keys)
        if keys:
            rel=str(p.relative_to(root)) if p.is_relative_to(root) else str(p)
            flat=sorted(set(k for arr in keys for k in arr)); by_file[rel]=flat; union.update(flat)
            extra=sorted(set(flat)-expected); missing=sorted(expected-set(flat))
            if extra or missing: mismatches[rel]={'extra_against_contract':extra,'missing_against_contract':missing}
    report={'files_examined':len(files),'connector_files':len(by_file),'contract_connector_keys':sorted(expected),'observed_union':sorted(union),'by_file':by_file,'mismatches':mismatches}
    out=Path(args.out); out = out if out.is_absolute() else root/out; out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'out':str(out),'connector_files':len(by_file),'mismatches':len(mismatches)}, indent=2))
    return 0
if __name__ == '__main__': raise SystemExit(main())
