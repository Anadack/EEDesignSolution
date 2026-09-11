#!/usr/bin/env python3
from __future__ import annotations
from eec_archdoc_common import *

DOCS=[
('Sensor/Actuator Pin Matrix','sensor_actuator_pin_matrix.html','Pin naming convention matrix with signal validation — device pins matched to cleaned signal names per SYSTEM_Function_TYPE standard.'),
('Dataflow System Diagrams','dataflow_system_diagram.html','DFD Level 1 by system.'),
('Network Schematic Diagram','network_schematic_diagram.html','Freeform IC-chip canvas with ECUs, networked devices, variant clustering and optional manual annotations.'),
('Network Bus Backbone','network_bus_backbone.html','System-level ECU/bus topology view with protocol details, load targets and connection heirarchy.'),
('ECU Network Dataflow Diagram','ecu_dataflow_diagram.html','Interactive bus-deck canvas — pan/zoom, search and click-a-bus-to-highlight, auto-laid-out from the real export.'),
('ECU Dataflow Architecture Template','ecu_dataflow_from_json.html','Exact reference template — ECU/bus cards, pin-level inspect drawer, search/filter and JSON load/export — pre-loaded with the real physical architecture export.'),
('Connection Schematic','connection_schematic.html','Pin-level connection diagram — circuit symbols, electrical zones and real device wiring per ECU connector.'),
('Multi-ECU Wiring Viewer','professional_multi_ecu_wiring.html','Interactive per-ECU pinout & wiring viewer — search/zoom/inspect/print-to-PDF, sensors/actuators wired left-to-right against every pin, including unconnected spares.'),
('ECU Pinout v3 Config/Validation','ecu_v3_config_validation.html','Production v3 interactive multi-ECU pinout with tabs, dataflow diagram, signal validation panel and print modes.'),
('Completeness Report','architecture_completeness_report.html','v4 explicit-pin documentation completeness checklist.'),
]

def main()->int:
    parser=make_argparser('Generate architecture documentation index.'); args=parser.parse_args(); root,cfg,arch,arch_path,outdir=cli_context(args)
    idx=build_signal_index(arch); docs=[]
    for title,fn,desc in DOCS:
        exists=(outdir/fn).exists()
        docs.append((title,fn,desc + (' ✅' if exists else ' ⚠ not generated yet')))
    body=kpi_row([('Architecture',arch.get('name','Architecture'),'Framework export'),('Systems',len(list(iter_systems(arch))),'Functional domains'),('ECUs',len(list(iter_ecus(arch))),'Controllers'),('Signals',len(idx),'Unique flows')])
    body+='<section class="section"><h2>Documentation set</h2>'+linked_index(docs)+'</section>'
    body+='<section class="section"><h2>How to regenerate</h2><pre class="mono">python tools/generate_all_architecture_docs.py --root .</pre></section>'
    out=outdir/'architecture_documentation_index.html'; out.write_text(html_page('Architecture Documentation Index',body,cfg,'Single entry point for tractor E/E architecture documentation.'),encoding='utf-8'); print(out); return 0
if __name__=='__main__': raise SystemExit(main())
