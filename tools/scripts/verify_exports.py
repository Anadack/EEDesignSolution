#!/usr/bin/env python3
from __future__ import annotations
import json
from eec_report_common import *

def summarize(arch: dict[str, Any]) -> dict[str, Any]:
    rows=collect_allocation_rows(arch,{})
    return {
        'architecture_name': arch.get('name',''),
        'ecu_count': len(arch.get('ecus',[]) if isinstance(arch.get('ecus'),list) else []),
        'system_count': len(arch.get('systems',[]) if isinstance(arch.get('systems'),list) else []),
        'bus_count': len(arch.get('buses',[]) if isinstance(arch.get('buses'),list) else []),
        'allocation_rows': len(rows),
        'mapped_rows': sum(1 for r in rows if r.get('status')=='MAPPED'),
        'unmapped_rows': sum(1 for r in rows if r.get('status')!='MAPPED'),
    }

def main() -> int:
    parser=standard_arg_parser('Verify architecture JSON exports generically.'); args=parser.parse_args(); cfg=load_config(Path(args.config) if args.config else None); root=resolve_root(args.root)
    src,arch=load_architecture_from_args(args,cfg,physical=False)
    result={'source':str(src), 'summary':summarize(arch), 'status':'OK'}
    # Optional physical export comparison
    phys=first_existing(root,cfg.get('physical_architecture_json_candidates',[]))
    if phys and phys != src:
        result['physical_source']=str(phys); result['physical_summary']=summarize(get_architecture(load_json(phys)))
    out=get_output_file(root,cfg,'verify_exports',args.output,args.outdir)
    write_text(out,json.dumps(result,indent=2)); print(json.dumps(result,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
