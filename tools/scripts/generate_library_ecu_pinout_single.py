#!/usr/bin/env python3
from __future__ import annotations
from eec_report_common import *

def library_ecu_files(root: Path, cfg: dict[str, Any], only: str | None = None) -> list[Path]:
    files=[]
    for pat in cfg.get('library_ecu_globs', ['library/ecus/*.json']):
        files.extend(sorted(root.glob(pat)))
    if only:
        want=only.lower().replace('.json','')
        files=[p for p in files if p.stem.lower()==want or want in p.stem.lower()]
    return files

def rows_for_ecu(path: Path, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    data=load_json(path); rows=[]
    for pin in data.get('pins',[]) if isinstance(data.get('pins'),list) else []:
        if not isinstance(pin,dict): continue
        rows.append({'ecu':data.get('name',''),'variant':data.get('variant',''),'connector':pin.get('connector',''),'pin':pin.get('physical_number',pin.get('number','')),'name':pin.get('name',''),'role':pin.get('role',''),'type':pin.get('type',''),'group':pin.get('group',''),'electrical':decode_mask(pin.get('electrical_capability',0), cfg.get('electrical_flags',{})),'diagnostics':decode_mask(pin.get('diagnostic_flags',0), cfg.get('diagnostic_flags',{}))})
    return rows


def main() -> int:
    parser=standard_arg_parser('Generate v4 generic single library ECU pinout.'); parser.add_argument('--ecu', help='ECU file stem/name filter. If omitted, all ECUs are generated as separate files.'); args=parser.parse_args(); cfg=load_config(Path(args.config) if args.config else None); root=resolve_root(args.root)
    files=library_ecu_files(root,cfg,args.ecu); cols=[('ecu','ECU'),('variant','Variant'),('connector','Connector'),('pin','Pin'),('name','Name'),('role','Role'),('type','Type'),('group','Group'),('electrical','Electrical'),('diagnostics','Diagnostics')]
    outdir=get_output_dir(root,cfg,args.outdir); generated=[]
    for p in files:
        body=f"<div class='card'><h1>ECU Pinout: {esc(p.stem)}</h1></div><div class='card'>"+table_html(rows_for_ecu(p,cfg),cols,'ecu_pinout')+"</div>"
        out=Path(args.output) if args.output and len(files)==1 else outdir/(slug(p.stem)+'_pinout.html')
        if not out.is_absolute(): out=root/out
        write_text(out,html_page('ECU Pinout '+p.stem,body)); generated.append(out)
    if not generated: raise FileNotFoundError('No matching ECU JSON files found')
    for out in generated: print(out)
    return 0
if __name__=='__main__': raise SystemExit(main())
