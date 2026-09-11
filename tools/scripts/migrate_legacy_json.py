
#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from eec_json_common import load_contract, discover_root, expand_patterns, write_json, backup_file, migrate_legacy_device, default_patterns_for_scope

def main():
    ap=argparse.ArgumentParser(description='Migrate legacy sensor/actuator JSON exports to explicit-pin v4-compatible JSON')
    ap.add_argument('paths', nargs='*'); ap.add_argument('--root', default=None); ap.add_argument('--contract', default=None)
    ap.add_argument('--write', action='store_true'); ap.add_argument('--outdir', default=None); ap.add_argument('--backup-suffix', default='.legacy.bak')
    args=ap.parse_args(); contract=load_contract(args.contract); root=discover_root(args.root)
    patterns=args.paths or default_patterns_for_scope(contract,'library')
    changed=0
    for p in expand_patterns(patterns, root):
        try: data=json.loads(p.read_text(encoding='utf-8'))
        except Exception as e: print(f'ERROR {p}: {e}'); continue
        new, mod=migrate_legacy_device(data, contract)
        if mod:
            changed+=1
            if args.outdir:
                out=(root/args.outdir/p.relative_to(root)) if not p.is_absolute() else (root/args.outdir/p.name)
                write_json(out, new); print('WROTE', out)
            elif args.write:
                backup_file(p,args.backup_suffix); write_json(p,new); print('UPDATED', p)
            else:
                print('WOULD_MIGRATE', p)
    print(f'done migrated={changed} write={args.write} outdir={args.outdir}')
    return 0
if __name__ == '__main__': raise SystemExit(main())
