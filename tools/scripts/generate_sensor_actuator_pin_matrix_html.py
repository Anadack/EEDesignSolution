#!/usr/bin/env python3
from __future__ import annotations
import json, re
from eec_archdoc_common import *

SYSTEM_CODES = {
    'HYDAC_Selected_Sensor_Examples': ('HYDD', 'Hydraulics Distribution'),
    'BRAKE_SYSTEM': ('BRK', 'Brake System'),
    'Rear_Hydraulic_Hitch_System': ('RHIT', 'Rear Hitch'),
    'Example_System_with_Bosch_Rexroth_Coil_Actuators': ('BREX', 'Rexroth Coils'),
    'Example_HYDAC_Coil_Topologies_System': ('COIL', 'Hydraulic Coils'),
    'Example_System_with_selected_elobau_angle_sensors': ('ELB', 'Elobau Sensors'),
}

TYPE_CODES = {
    'POWER': ('PWR', 'Power supply rail'),
    'GROUND': ('GND', 'Ground / return'),
    'ANALOG': ('SNSR', 'Sensor'),
    'DIGITAL': ('SWT', 'Switch'),
    'CAN': ('CAN', 'CAN Bus'),
    'LIN': ('LIN', 'LIN Bus'),
    'PWM': ('CMD', 'Command signal'),
    'CURRENT': ('AI', 'Current input'),
}

def extract_pin_data(arch: dict) -> list:
    rows = []
    idx = build_signal_index(arch)

    for signal_name, sig_info in idx.items():
        device_pins = sig_info.get('device_pins', [])
        ecu_pins = sig_info.get('ecu_pins', [])
        interface = sig_info.get('interface', '')
        role = sig_info.get('role', '')

        for dp in device_pins:
            system = dp.get('system', '')
            device = dp.get('device', '')
            connector = dp.get('connector', '')
            pin_num = dp.get('pin_number', '')
            device_type = dp.get('device_type', 'SENSOR')
            part_number = dp.get('part_number', '')

            system_code, system_meaning = SYSTEM_CODES.get(system, (system[:4].upper(), system))

            signal_name_clean = parse_signal_name(signal_name)
            type_code, type_meaning = TYPE_CODES.get(interface, (interface[:3].upper(), interface))

            io_type_map = {
                'SUPPLY': 'SUP', 'GROUND': 'GND', 'INPUT': 'IN', 'OUTPUT': 'OUT', 'INOUT': 'IO'
            }
            io_type = io_type_map.get(role, role[:2].upper() if role else 'XX')

            status = validate_naming(signal_name_clean)
            status_reason = 'Compliant with SYSTEM_Function_[POSITION_]TYPE' if status == 'OK' else f'Non-compliant: {status}'
            hint = get_hint_for_interface(interface, role)

            row = {
                'system': system,
                'systemCode': system_code,
                'systemMeaning': system_meaning,
                'device': device,
                'deviceType': device_type,
                'partNumber': part_number,
                'connector': connector,
                'pin': pin_num,
                'originalSignal': signal_name,
                'signalName': signal_name_clean,
                'function': extract_function(signal_name_clean),
                'position': extract_position(signal_name_clean),
                'typeCode': type_code,
                'typeMeaning': type_meaning,
                'interface': interface,
                'role': role,
                'ioType': io_type,
                'unit': sig_info.get('unit', 'NONE'),
                'minimum': sig_info.get('min_value', 0),
                'maximum': sig_info.get('max_value', 0),
                'range': f"{sig_info.get('min_value', 0)}–{sig_info.get('max_value', 0)} {sig_info.get('unit', '')}".strip(),
                'status': status,
                'statusReason': status_reason,
                'hint': hint,
                'safety': sig_info.get('safety', 'QM'),
                'priority': sig_info.get('priority', 'MEDIUM'),
            }
            rows.append(row)

    return rows

def parse_signal_name(name: str) -> str:
    name = name.replace('_', '').replace(' ', '')
    parts = re.findall(r'[A-Z][a-z]*|[0-9]+', name)
    return ''.join(parts[:3]) if parts else name

def extract_function(signal_name: str) -> str:
    parts = re.findall(r'[A-Z][a-z]*', signal_name)
    return ''.join(parts[1:-1]) if len(parts) > 1 else ''

def extract_position(signal_name: str) -> str:
    nums = re.findall(r'\d+', signal_name)
    return nums[0] if nums else ''

def validate_naming(name: str) -> str:
    if len(name) < 8: return 'Too short'
    if not name[0].isupper(): return 'Must start with uppercase'
    return 'OK'

def get_hint_for_interface(interface: str, role: str) -> str:
    hints = {
        ('POWER', 'SUPPLY'): 'Connect to protected ECU/sensor supply rail; verify voltage range and fuse/protection.',
        ('GROUND', 'GROUND'): 'Connect to ECU sensor ground, power ground, or chassis ground according to device return concept.',
        ('ANALOG', 'INPUT'): 'Verify analog input impedance, filtering and isolation requirements; check for EMC shielding.',
        ('DIGITAL', 'INPUT'): 'Confirm pull-up/pull-down configuration and logic voltage levels match ECU specs.',
        ('CAN', 'INOUT'): 'Verify CAN transceiver chipset, termination resistors and stub length compliance.',
        ('PWM', 'OUTPUT'): 'Check PWM frequency, duty-cycle limits and output impedance match device requirements.',
    }
    return hints.get((interface, role), 'Verify electrical and functional compatibility with ECU pin capabilities.')

def main() -> int:
    parser = make_argparser('Generate sensor/actuator pin naming convention matrix.')
    args = parser.parse_args()
    root, cfg, arch, arch_path, outdir = cli_context(args)

    rows = extract_pin_data(arch)
    stats = {
        'systems': len(set(r['system'] for r in rows)),
        'devices': len(set(r['device'] for r in rows)),
        'pins': len(rows),
        'sensors': len([r for r in rows if r['deviceType'] == 'SENSOR']),
        'actuators': len([r for r in rows if r['deviceType'] == 'ACTUATOR']),
        'convention_ok': len([r for r in rows if r['status'] == 'OK']),
    }

    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Sensor / Actuator Pin Matrix</title>
<style>
:root{{
  --bg:#07111f; --panel:#0d1628; --panel2:#111c32; --card:#16223a; --card2:#1b2b49;
  --ink:#e7eefb; --muted:#91a3bd; --line:rgba(148,163,184,.18); --soft:rgba(255,255,255,.06);
  --cyan:#38bdf8; --blue:#60a5fa; --violet:#a78bfa; --green:#34d399; --amber:#f59e0b; --red:#fb7185;
  --sensor:#2dd4bf; --actuator:#c084fc; --pwr:#fb923c; --gnd:#94a3b8; --can:#f43f5e;
  --shadow:0 24px 80px rgba(0,0,0,.42); --radius:18px;
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;background:radial-gradient(circle at 8% 0%,rgba(56,189,248,.18),transparent 28%),radial-gradient(circle at 84% 4%,rgba(167,139,250,.18),transparent 30%),linear-gradient(180deg,#07111f 0%,#0a1220 46%,#050914 100%);}}
header{{position:sticky;top:0;z-index:20;background:rgba(7,17,31,.76);backdrop-filter:blur(18px);border-bottom:1px solid var(--line)}}
.header-inner{{max-width:1620px;margin:auto;padding:22px 24px;display:flex;justify-content:space-between;gap:22px;align-items:flex-start;flex-wrap:wrap}}
h1{{margin:0;font-size:clamp(24px,3vw,38px);letter-spacing:-.05em;line-height:1.05}}
.subtitle{{margin:9px 0 0;color:var(--muted);font-size:13px;max-width:980px;line-height:1.55}}
.badges{{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}}
.badge{{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:999px;padding:7px 10px;font-size:11px;font-weight:800;color:#cfe9ff;background:rgba(56,189,248,.08);white-space:nowrap}}
.badge.green{{background:rgba(52,211,153,.1);color:#b7f7d8;border-color:rgba(52,211,153,.26)}}
.page{{max-width:1620px;margin:auto;padding:18px 20px 40px}}
.kpis{{display:grid;grid-template-columns:repeat(6,minmax(130px,1fr));gap:12px;margin-bottom:16px}}
.kpi{{background:linear-gradient(180deg,rgba(22,34,58,.95),rgba(14,23,42,.9));border:1px solid var(--line);border-radius:var(--radius);padding:15px 16px;box-shadow:var(--shadow);position:relative;overflow:hidden}}
.kpi:before{{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:linear-gradient(90deg,var(--cyan),var(--violet))}}
.kpi .label{{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:800}}
.kpi .value{{font-size:30px;line-height:1;margin-top:8px;font-weight:950;letter-spacing:-.06em}}
.grid{{display:grid;grid-template-columns:330px minmax(700px,1fr);gap:16px;align-items:start}}
.panel{{background:linear-gradient(180deg,rgba(17,28,50,.94),rgba(13,22,40,.91));border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden}}
.panel-title{{padding:15px 16px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:10px}}
.panel-title h2{{font-size:13px;text-transform:uppercase;letter-spacing:.08em;margin:0;color:#dbeafe}}
.panel-body{{padding:14px 16px}}
.controls{{display:grid;gap:10px}}
.control label{{display:block;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-weight:800;margin-bottom:6px}}
input,select,button{{font:inherit;color:var(--ink)}}
input,select{{width:100%;background:rgba(6,12,24,.75);border:1px solid var(--line);border-radius:12px;padding:10px 11px;outline:none}}
input:focus,select:focus{{border-color:rgba(56,189,248,.7);box-shadow:0 0 0 3px rgba(56,189,248,.12)}}
button{{background:rgba(56,189,248,.1);border:1px solid rgba(56,189,248,.3);border-radius:12px;padding:10px 12px;cursor:pointer;font-weight:800}}
button:hover{{border-color:var(--cyan);background:rgba(56,189,248,.16)}}
.action-row{{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:10px}}
.legend{{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}}
.legend span{{font-size:10px;border:1px solid var(--line);border-radius:999px;padding:5px 8px;color:#dbeafe;background:rgba(255,255,255,.05);font-weight:700}}
.rule{{background:rgba(255,255,255,.045);border:1px solid var(--line);border-radius:14px;padding:12px;margin-bottom:10px}}
.rule b{{color:#eaf6ff}}
.rule code{{font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#93c5fd;font-size:11px}}
.small{{font-size:12px;line-height:1.55;color:var(--muted)}}
.table-wrap{{overflow:auto;max-height:calc(100vh - 275px);min-height:540px}}
table{{width:100%;border-collapse:separate;border-spacing:0;font-size:12px}}
th{{position:sticky;top:0;z-index:5;background:#14203a;color:#c7dcff;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.075em;border-bottom:1px solid rgba(148,163,184,.28);padding:10px 10px;white-space:nowrap}}
td{{border-bottom:1px solid rgba(148,163,184,.11);padding:10px;vertical-align:top;color:#d8e4f5}}
tbody tr:hover td{{background:rgba(56,189,248,.055)}}
.signal{{font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-weight:800;color:#bbf7d0;white-space:nowrap;font-size:11px}}
.original{{font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#fda4af;font-size:10.5px}}
.tag{{display:inline-flex;align-items:center;border-radius:999px;padding:3px 7px;font-size:10px;font-weight:900;border:1px solid var(--line);white-space:nowrap}}
.sensor{{color:#99f6e4;background:rgba(45,212,191,.1);border-color:rgba(45,212,191,.28)}}
.actuator{{color:#e9d5ff;background:rgba(192,132,252,.1);border-color:rgba(192,132,252,.28)}}
.ok{{color:#bbf7d0;background:rgba(34,197,94,.1);border-color:rgba(34,197,94,.28)}}
.pin{{font-weight:900;color:#fff;background:rgba(255,255,255,.08);border:1px solid var(--line);border-radius:10px;padding:4px 7px;display:inline-block;min-width:34px;text-align:center}}
.device{{max-width:260px;color:#e2e8f0;font-weight:700}}
.hint{{color:#aabbd4;line-height:1.45;font-size:11.5px}}
@media(max-width:1100px){{.grid{{grid-template-columns:1fr}}.kpis{{grid-template-columns:repeat(2,1fr)}}.table-wrap{{max-height:none}}}}
@media print{{body{{background:white;color:#111827}} header,.sidebar{{display:none!important}} .page{{padding:0;max-width:none}} .grid{{display:block}} .panel{{box-shadow:none;border:0}} .table-wrap{{max-height:none;overflow:visible}} th{{background:#e5e7eb!important;color:#111827}} td{{color:#111827;border-bottom:1px solid #d1d5db}} .signal,.original{{color:#111827}}}}
</style>
</head>
<body>
<header>
  <div class="header-inner">
    <div>
      <h1>Sensor / Actuator Pin Matrix</h1>
      <p class="subtitle">Complete pin and signal matrix generated from the architecture export. Each row shows the original signal name and the cleaned signal name following <b>SYSTEM_Function_[POSITION_]TYPE</b> convention.</p>
    </div>
    <div class="badges">
      <span class="badge">Sensor/Actuator Matrix</span>
      <span class="badge green">{stats['pins']} pins validated</span>
      <span class="badge">{stats['devices']} devices</span>
    </div>
  </div>
</header>
<main class="page">
  <section class="kpis">
    <div class="kpi"><div class="label">Systems</div><div class="value">{stats['systems']}</div></div>
    <div class="kpi"><div class="label">Devices</div><div class="value">{stats['devices']}</div></div>
    <div class="kpi"><div class="label">Pins / Endpoints</div><div class="value">{stats['pins']}</div></div>
    <div class="kpi"><div class="label">Sensors</div><div class="value">{stats['sensors']}</div></div>
    <div class="kpi"><div class="label">Actuators</div><div class="value">{stats['actuators']}</div></div>
    <div class="kpi"><div class="label">Convention OK</div><div class="value">{stats['convention_ok']}</div></div>
  </section>

  <section class="grid">
    <aside class="panel sidebar">
      <div class="panel-title"><h2>Matrix Controls</h2></div>
      <div class="panel-body">
        <div class="controls">
          <div class="control"><label>Search</label><input id="q" placeholder="Search device, pin, signal, interface…" oninput="render()"></div>
          <div class="control"><label>Device Type</label><select id="deviceFilter" onchange="render()"><option value="">All devices</option><option>SENSOR</option><option>ACTUATOR</option></select></div>
          <div class="control"><label>Interface</label><select id="interfaceFilter" onchange="render()"><option value="">All interfaces</option></select></div>
          <div class="control"><label>Status</label><select id="statusFilter" onchange="render()"><option value="">All statuses</option><option>OK</option><option>Non-compliant</option></select></div>
        </div>
        <div class="action-row"><button onclick="resetFilters()">Reset</button><button onclick="downloadCsv()">Export CSV</button></div>
        <div class="legend">
          <span>🟢 Convention OK</span><span>⚙️ Signal</span><span>📌 Pin</span><span>🖨️ A4 print</span>
        </div>
      </div>
      <div class="panel-title"><h2>Naming Convention</h2></div>
      <div class="panel-body">
        <div class="rule"><b>Format</b><br><code>SYSTEM_Function_[POSITION_]TYPE</code><p class="small">Example: <code>HYDD_AnglPosn01_SNSR</code></p></div>
        <div class="rule"><b>SYSTEM</b><p class="small">System code: <code>HYDD</code> (hydraulics), <code>BRK</code> (brake), <code>RHIT</code> (rear hitch)</p></div>
        <div class="rule"><b>TYPE</b><p class="small">Last segment: <code>SNSR</code>, <code>SWT</code>, <code>PWR</code>, <code>GND</code>, <code>CAN</code>, <code>CMD</code>, etc.</p></div>
      </div>
    </aside>

    <section class="panel">
      <div class="panel-title"><h2>Pin / Signal Matrix</h2><span class="tag ok" id="resultCount">0 rows</span></div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>System</th><th>Device</th><th>Pin</th><th>Original Signal</th><th>Clean Signal</th><th>Interface</th><th>Type</th><th>Status</th></tr></thead>
          <tbody id="tbody"></tbody>
        </table>
      </div>
    </section>
  </section>
</main>

<script>
const rows = {json.dumps(rows)};

function render() {{
  const q = document.getElementById('q').value.toLowerCase();
  const device = document.getElementById('deviceFilter').value;
  const iface = document.getElementById('interfaceFilter').value;
  const status = document.getElementById('statusFilter').value;

  let filtered = rows.filter(r => {{
    if (q && !JSON.stringify(r).toLowerCase().includes(q)) return false;
    if (device && r.deviceType !== device) return false;
    if (iface && r.interface !== iface) return false;
    if (status && (status === 'OK' ? r.status !== 'OK' : r.status === 'OK')) return false;
    return true;
  }});

  const tbody = document.getElementById('tbody');
  tbody.innerHTML = filtered.map(r => `
    <tr>
      <td><span class="tag sensor">${{r.systemCode}}</span> <div class="small">${{r.system}}</div></td>
      <td><div class="device">${{r.device.split('_').slice(-1)[0]}}</div><div class="small">${{r.partNumber}}</div></td>
      <td><span class="pin">${{r.connector}}/${{r.pin}}</span></td>
      <td><div class="original">${{r.originalSignal}}</div></td>
      <td><div class="signal">${{r.signalName}}</div><div class="small">${{r.function}}</div></td>
      <td><span class="tag">${{r.interface}}</span></td>
      <td><span class="tag ok">${{r.typeCode}}</span></td>
      <td><span class="tag ${{r.status === 'OK' ? 'ok' : ''}}">${{r.status}}</span></td>
    </tr>
  `).join('');

  document.getElementById('resultCount').textContent = filtered.length + ' rows';
}}

function resetFilters() {{
  document.getElementById('q').value = '';
  document.getElementById('deviceFilter').value = '';
  document.getElementById('interfaceFilter').value = '';
  document.getElementById('statusFilter').value = '';
  render();
}}

function downloadCsv() {{
  const csv = [['System', 'Device', 'Pin', 'Original Signal', 'Clean Signal', 'Interface', 'Type', 'Status'].join(',')];
  rows.forEach(r => {{
    csv.push([r.systemCode, r.device, `${{r.connector}}/${{r.pin}}`, r.originalSignal, r.signalName, r.interface, r.typeCode, r.status].join(','));
  }});
  const blob = new Blob([csv.join('\\n')], {{type: 'text/csv'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'sensor_actuator_matrix.csv';
  a.click();
}}

// Populate interface filter
const interfaces = [...new Set(rows.map(r => r.interface))].sort();
const ifaceSelect = document.getElementById('interfaceFilter');
interfaces.forEach(i => {{
  const opt = document.createElement('option');
  opt.value = i;
  opt.textContent = i;
  ifaceSelect.appendChild(opt);
}});

render();
</script>
</body>
</html>'''

    out = outdir / 'sensor_actuator_pin_matrix.html'
    out.write_text(html, encoding='utf-8')
    print(out)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
