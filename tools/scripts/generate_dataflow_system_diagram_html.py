#!/usr/bin/env python3
from __future__ import annotations
from collections import Counter, defaultdict
from eec_archdoc_common import *

def main() -> int:
    parser = make_argparser("Generate DFD Level 1 diagrams per tractor system.")
    args = parser.parse_args()
    root, cfg, arch, arch_path, outdir = cli_context(args)
    sigidx = build_signal_index(arch)
    sections = []
    summary_rows = []
    for sys_obj in iter_systems(arch):
        sys_name = str(sys_obj.get('name','System'))
        devs = flatten_components(sys_obj)
        pins = list(iter_device_pins({'systems':[sys_obj]}))
        ecu_targets = Counter()
        for p in pins:
            for ep in sigidx.get(p['signal_name'], {}).get('ecu_pins', []):
                ecu_targets[ep['ecu']] += 1
        sensors = [d for d in devs if str(d.get('device_type', d.get('type',''))).upper() == 'SENSOR']
        acts = [d for d in devs if str(d.get('device_type', d.get('type',''))).upper() == 'ACTUATOR']
        buses = Counter(p['interface'] for p in pins if p['interface'] in cfg.get('bus_interfaces', []))
        ios = Counter(p['interface'] for p in pins if p['interface'] not in cfg.get('bus_interfaces', []))
        summary_rows.append({'system': esc(sys_name), 'sensors': len(sensors), 'actuators': len(acts), 'pins': len(pins), 'primary_ecu': esc(ecu_targets.most_common(1)[0][0] if ecu_targets else '-'), 'interfaces': ''.join(pill(k, iface_color(k)) for k,_ in (ios+buses).most_common(6))})
        sensor_nodes = ''.join(f'<div class="node"><div class="name">{icon("sensor","#2ee6a0",14)} {esc(d.get("name","Sensor"))}</div><div class="small">{len(d.get("pins",[]) if isinstance(d.get("pins"),list) else [])} pins</div></div>' for d in sensors[:20]) or '<div class="node muted">No sensors</div>'
        actuator_nodes = ''.join(f'<div class="node"><div class="name">{icon("actuator","#ffb43d",14)} {esc(d.get("name","Actuator"))}</div><div class="small">{len(d.get("pins",[]) if isinstance(d.get("pins"),list) else [])} pins</div></div>' for d in acts[:20]) or '<div class="node muted">No actuators</div>'
        ecu_nodes = ''.join(f'<div class="node"><div class="name">{icon("ecu","#2ee6ff",14)} {esc(name)}</div><div class="small">{cnt} mapped flows</div></div>' for name,cnt in ecu_targets.most_common(8)) or '<div class="node muted">No ECU mapping</div>'
        sections.append(f'''<section class="section"><h2>{esc(sys_name)}</h2>
        <div class="flow-row"><div class="flow-col"><div class="flow-title">Sensors / inputs</div>{sensor_nodes}</div><div class="arrow"></div><div class="flow-col"><div class="flow-title">System logic</div><div class="node" style="border-color:#1d4ed8"><div class="name">{esc(sys_name)}</div><div class="small">{len(pins)} signal pins · {len(devs)} devices</div>{''.join(pill(k, iface_color(k)) for k,_ in ios.most_common(6))}</div></div><div class="arrow"></div><div class="flow-col"><div class="flow-title">ECU / buses</div>{ecu_nodes}{''.join(pill(k, iface_color(k)) for k,_ in buses.items())}</div><div class="arrow"></div><div class="flow-col"><div class="flow-title">Actuators / outputs</div>{actuator_nodes}</div></div></section>''')
    body = kpi_row([('Systems', len(summary_rows), 'DFD Level 1 diagrams'), ('Signals', len(sigidx), 'Unique signal flows'), ('ECUs', len(list(iter_ecus(arch))), 'Mapping targets'), ('Source', arch_path.name, 'Architecture JSON')])
    body += '<section class="section"><h2>System dataflow summary</h2>' + table_html('system_dfd_summary', [('system','System'),('sensors','Sensors'),('actuators','Actuators'),('pins','Signal pins'),('primary_ecu','Primary ECU'),('interfaces','Interfaces')], summary_rows, 'system_dataflow_summary.csv') + '</section>'
    body += ''.join(sections)
    out = outdir / 'dataflow_system_diagram.html'
    out.write_text(html_page('Dataflow System Diagrams', body, cfg, 'DFD Level 1 per system, derived from exported systems/devices/pins/signals.'), encoding='utf-8')
    print(out)
    return 0
if __name__ == '__main__': raise SystemExit(main())
