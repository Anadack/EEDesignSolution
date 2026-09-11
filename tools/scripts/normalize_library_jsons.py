
#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from eec_json_common import load_contract, discover_root, expand_patterns, normalize_inplace, migrate_legacy_device, write_json, backup_file, default_patterns_for_scope

def main() -> int:
    ap=argparse.ArgumentParser(description='Normalize/canonicalize E/E Architect Design JSON files using a configurable contract')
    ap.add_argument('paths', nargs='*')
    ap.add_argument('--root', default=None); ap.add_argument('--contract', default=None)
    ap.add_argument('--write', action='store_true', help='write changes in-place; default is dry-run')
    ap.add_argument('--backup-suffix', default='.normalize.bak')
    ap.add_argument('--migrate-legacy', action='store_true', help='also migrate legacy sensor/actuator exports to explicit-pin v4')
    args=ap.parse_args(); contract=load_contract(args.contract); root=discover_root(args.root)
    patterns=args.paths or default_patterns_for_scope(contract, 'library')
    changed=[]; errors=[]
    for p in expand_patterns(patterns, root):
        try: data=json.loads(p.read_text(encoding='utf-8'))
        except Exception as e: errors.append((p,str(e))); continue
        if args.migrate_legacy and isinstance(data, dict): new, mod=migrate_legacy_device(data, contract)
        else: new, mod=normalize_inplace(data, contract)
        if mod:
            changed.append(p)
            if args.write:
                backup_file(p, args.backup_suffix); write_json(p, new)
    for p in changed: print(('UPDATED ' if args.write else 'WOULD_UPDATE ') + str(p))
    for p,e in errors: print(f'ERROR {p}: {e}')
    print(f'done changed={len(changed)} errors={len(errors)} write={args.write}')
    return 1 if errors else 0
if __name__ == '__main__': raise SystemExit(main())
