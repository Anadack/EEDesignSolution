#!/usr/bin/env python3
from __future__ import annotations
from eec_report_common import *

def flatten(obj: Any, prefix: str='') -> list[dict[str, Any]]:
    rows=[]
    if isinstance(obj,dict):
        for k,v in obj.items(): rows += flatten(v, f'{prefix}.{k}' if prefix else str(k))
    elif isinstance(obj,list):
        for i,v in enumerate(obj): rows += flatten(v, f'{prefix}[{i}]')
    else:
        rows.append({'path':prefix,'value':obj})
    return rows

def main() -> int:
    parser=standard_arg_parser('Generate v4 generic estimation HTML.'); args=parser.parse_args(); cfg=load_config(Path(args.config) if args.config else None); root=resolve_root(args.root)
    if args.input: src=Path(args.input); src=src if src.is_absolute() else root/src
    else: src=first_existing(root,cfg.get('estimation_json_candidates',[]))
    if not src: raise FileNotFoundError('No estimation JSON found')
    data=load_json(src); rows=flatten(data)
    body=f"<div class='card'><h1>Architecture Estimation</h1><p class='muted'>Source: {esc(src.relative_to(root) if src.is_relative_to(root) else src)}</p></div><div class='card'>"+table_html(rows,[('path','Field'),('value','Value')],'estimation')+"</div>"
    out=get_output_file(root,cfg,'estimation',args.output,args.outdir); write_text(out,html_page('Architecture Estimation',body)); print(out); return 0
if __name__=='__main__': raise SystemExit(main())
