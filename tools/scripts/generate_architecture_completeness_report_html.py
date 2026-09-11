#!/usr/bin/env python3
from __future__ import annotations
from eec_archdoc_common import *

def check(cond: bool, item: str, severity: str, location: str, message: str) -> dict[str, str]:
    return {'status': pill('PASS' if cond else severity, '#15803d' if cond else ('#b45309' if severity=='WARN' else '#b91c1c')), 'item': esc(item), 'location': esc(location), 'message': esc('OK' if cond else message)}

def main()->int:
    parser=make_argparser('Generate architecture completeness checklist.'); args=parser.parse_args(); root,cfg,arch,arch_path,outdir=cli_context(args)
    rows=[]
    idx=build_signal_index(arch)
    rows.append(check(bool(list(iter_systems(arch))), 'Architecture has systems', 'ERROR', arch.get('name','architecture'), 'No systems exported'))
    rows.append(check(bool(list(iter_ecus(arch))), 'Architecture has ECUs', 'ERROR', arch.get('name','architecture'), 'No ECUs exported'))
    for sys_obj in iter_systems(arch):
        sys_name=str(sys_obj.get('name','System'))
        devs=flatten_components(sys_obj)
        rows.append(check(bool(devs),'System has devices','WARN',sys_name,'No devices/components found'))
        for dev in devs:
            loc=f"{sys_name}/{dev.get('name','Device')}"
            rows.append(check(isinstance(dev.get('connectors'),list) and len(dev.get('connectors'))>0,'Device connectors[] present','WARN',loc,'Missing connectors[]'))
            pins=dev.get('pins',[]); sigs=dev.get('signals',[]); conns=dev.get('connectors',[])
            rows.append(check(isinstance(pins,list) and len(pins)>0,'Device pins[] present','ERROR',loc,'Missing pins[] for v4 explicit-pin documentation'))
            rows.append(check(isinstance(sigs,list) and len(sigs)>0,'Device signals[] present','WARN',loc,'Missing signals[]'))
            used=sum(int(c.get('used_cavities',c.get('total_cavities',0)) or 0) for c in conns) if isinstance(conns,list) else 0
            total=sum(int(c.get('total_cavities',0) or 0) for c in conns) if isinstance(conns,list) else 0
            rows.append(check((not conns) or (len(pins)==len(sigs)==used==total),'v4 pin/signal/cavity equality','ERROR',loc,f'pins={len(pins)} signals={len(sigs)} used_cavities={used} total_cavities={total}'))
            for p in pins if isinstance(pins,list) else []:
                rows.append(check(bool(signal_name(p.get('signal'))),'Pin has signal reference','ERROR',f"{loc}/pin {p.get('number','?')}",'Missing signal'))
    for sn,e in idx.items():
        rows.append(check(bool(e.get('ecu_pins')),'Signal mapped to ECU pin','WARN',sn,'Signal has no ECU allocation'))
    fails=sum(1 for r in rows if 'ERROR' in r['status']); warns=sum(1 for r in rows if 'WARN' in r['status']); passes=sum(1 for r in rows if 'PASS' in r['status'])
    body=kpi_row([('Checks',len(rows),'Completeness assertions'),('Pass',passes,'OK'),('Warnings',warns,'Improve'),('Errors',fails,'Fix required')])
    body+='<section class="section"><h2>Completeness checklist</h2>'+table_html('complete',[('status','Status'),('item','Item'),('location','Location'),('message','Message')],rows,'architecture_completeness.csv')+'</section>'
    out=outdir/'architecture_completeness_report.html'; out.write_text(html_page('Architecture Completeness Report',body,cfg,'Quality gate for v4 explicit-pin architecture documentation completeness.'),encoding='utf-8'); print(out); return 0
if __name__=='__main__': raise SystemExit(main())
