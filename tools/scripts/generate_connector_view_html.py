#!/usr/bin/env python3
"""Generate an interactive connector view: every ECU and device that exposes
connectors, rendered as clickable pin grids with a signal/pin detail panel.
"""
from __future__ import annotations

from eec_archdoc_common import *


def device_pin_status(pin: dict[str, Any]) -> str:
    sig = pin.get('signal')
    if not isinstance(sig, dict) or not sig:
        return 'free'
    return 'valid' if sig.get('is_mapped') else 'warning'


def build_ecu_to_device_link_index(arch: dict[str, Any]) -> dict[str, str]:
    """Map signal name -> 'ECU / connector / Pin n' for cross-linking from device pins."""
    idx: dict[str, str] = {}
    for ecu in iter_ecus(arch):
        ecu_name = str(ecu.get('name', ''))
        pins = ecu.get('pins', [])
        if not isinstance(pins, list):
            continue
        for pin in pins:
            if not isinstance(pin, dict):
                continue
            sig = pin.get('signal')
            if isinstance(sig, dict) and sig.get('name'):
                idx[str(sig['name'])] = f"{ecu_name} / {pin.get('connector', '')} / Pin {pin.get('physical_number', '')}"
    return idx


def build_components(arch: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    sig_to_ecu_loc = build_ecu_to_device_link_index(arch)
    components: list[dict[str, Any]] = []

    for ecu in iter_ecus(arch):
        ecu_name = str(ecu.get('name', ''))
        pins = ecu.get('pins', [])
        if not isinstance(pins, list):
            pins = []
        conn_meta = {str(c.get('name', '')): c for c in ecu.get('connectors', []) if isinstance(c, dict)}
        by_conn: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for pin in pins:
            if isinstance(pin, dict):
                by_conn[str(pin.get('connector', ''))].append(pin)
        if not by_conn:
            continue

        connectors = []
        total_pins = 0
        for conn_name in sorted(by_conn.keys()):
            conn_pins = sorted(by_conn[conn_name], key=lambda p: p.get('physical_number', 0))
            pin_rows = []
            warnings = errors = 0
            for pin in conn_pins:
                status = str(pin.get('status') or 'free')
                if status == 'warning':
                    warnings += 1
                elif status == 'error':
                    errors += 1
                sig = pin.get('signal') if isinstance(pin.get('signal'), dict) else None
                ptype = normalize_iface(pin.get('type') or pin.get('interface_type') or '')
                device_pin = pin.get('device_pin') if isinstance(pin.get('device_pin'), dict) else None
                pin_rows.append({
                    'pin': pin.get('physical_number', pin.get('number', '')),
                    'name': str(pin.get('name', '')),
                    'group': str(pin.get('group', '')),
                    'role': str(pin.get('role', '')),
                    'type': ptype,
                    'color': iface_color(ptype),
                    'status': status,
                    'electrical': str(pin.get('electrical', '')),
                    'diagnostics': list(pin.get('diagnostics') or []),
                    'electrical_flags': list(pin.get('electrical_flags') or []),
                    'sw_config': list(pin.get('sw_config') or []),
                    'signal': sig,
                    'component': ecu_name,
                    'connector': conn_name,
                    'linked': (device_pin.get('description') if device_pin else None),
                })
            total_pins += len(pin_rows)
            meta = conn_meta.get(conn_name, {})
            alloc = meta.get('allocation_summary', {}) if isinstance(meta.get('allocation_summary'), dict) else {}
            assigned = alloc.get('allocated_pins', sum(1 for r in pin_rows if r['status'] != 'free'))
            free = alloc.get('free_pins', sum(1 for r in pin_rows if r['status'] == 'free'))
            connectors.append({
                'name': conn_name,
                'pin_count': len(pin_rows),
                'assigned': assigned,
                'free': free,
                'warnings': warnings,
                'errors': errors,
                'meta_line': '',
                'pins': pin_rows,
            })

        components.append({
            'kind': 'ECU',
            'name': ecu_name,
            'system': '',
            'variant': str(ecu.get('variant', '')),
            'part_number': str(ecu.get('part_number', '')),
            'priority': str(ecu.get('priority', '')),
            'safety': str(ecu.get('safety', '')),
            'total_pins': total_pins,
            'connectors': connectors,
        })

    for sys_obj in iter_systems(arch):
        sys_name = str(sys_obj.get('name', ''))
        for dev in flatten_components(sys_obj):
            dev_conns = dev.get('connectors', [])
            if not isinstance(dev_conns, list) or not dev_conns:
                continue
            dev_name = str(dev.get('name', ''))
            pins = dev.get('pins', [])
            if not isinstance(pins, list):
                pins = []
            conn0 = dev_conns[0] if isinstance(dev_conns[0], dict) else {}
            conn_name = str(conn0.get('name', ''))

            pin_rows = []
            warnings = errors = 0
            for pin in sorted(pins, key=lambda p: p.get('number', 0)):
                if not isinstance(pin, dict):
                    continue
                status = device_pin_status(pin)
                if status == 'warning':
                    warnings += 1
                sig = pin.get('signal') if isinstance(pin.get('signal'), dict) else None
                ptype = normalize_iface(pin.get('interface_type') or (sig.get('interface') if sig else '') or '')
                elec_flags = bitmask_labels(pin.get('electrical_requirement', 0), cfg.get('electrical_flags', {}))
                linked = sig_to_ecu_loc.get(str(sig.get('name'))) if sig and sig.get('name') else None
                pin_rows.append({
                    'pin': pin.get('number', ''),
                    'name': str(pin.get('name', '')),
                    'group': '',
                    'role': str(pin.get('role', '')),
                    'type': ptype,
                    'color': iface_color(ptype),
                    'status': status,
                    'electrical': '',
                    'diagnostics': [],
                    'electrical_flags': elec_flags,
                    'sw_config': [],
                    'signal': sig,
                    'component': dev_name,
                    'connector': conn_name,
                    'linked': linked,
                })

            meta_bits = [str(b) for b in (
                conn0.get('family'), conn0.get('gender'), conn0.get('ip_rating'),
                (f"{conn0.get('total_cavities')} cavities" if conn0.get('total_cavities') else ''),
            ) if b]
            connectors = [{
                'name': conn_name,
                'pin_count': len(pin_rows),
                'assigned': sum(1 for r in pin_rows if r['status'] != 'free'),
                'free': sum(1 for r in pin_rows if r['status'] == 'free'),
                'warnings': warnings,
                'errors': errors,
                'meta_line': ' · '.join(meta_bits),
                'pins': pin_rows,
            }]

            components.append({
                'kind': 'DEVICE',
                'name': dev_name,
                'system': sys_name,
                'variant': str(dev.get('type', '')),
                'part_number': str(dev.get('part_number', '')),
                'priority': str(dev.get('priority', '')),
                'safety': str(dev.get('safety', '')),
                'total_pins': len(pin_rows),
                'connectors': connectors,
            })

    return components


CONNECTOR_VIEW_JS = r"""
function cvEsc(s){ return String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function cvAttrSafe(obj){ return JSON.stringify(obj).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function cvStatusLabel(s){ return ({valid:'Valid', warning:'Warning', error:'Error', free:'Free'})[s] || s; }

let cvActiveComponent = 0;

function cvRenderComponentList(filterText){
  const f = (filterText || '').toLowerCase();
  const items = CV_COMPONENTS.map((c, i) => {
    if (f) {
      const hay = `${c.name} ${c.system} ${c.variant} ${c.part_number}`.toLowerCase();
      if (!hay.includes(f)) return '';
    }
    const metaBits = [c.system, c.variant, `${c.total_pins} pins`, `${c.connectors.length} connector${c.connectors.length === 1 ? '' : 's'}`].filter(Boolean);
    return `<div class="component-item${i === cvActiveComponent ? ' active' : ''}" data-index="${i}" onclick="cvSelectComponent(${i})">
      <div class="name"><span class="component-kind ${c.kind.toLowerCase()}">${cvEsc(c.kind)}</span>${cvEsc(c.name)}</div>
      <div class="meta">${cvEsc(metaBits.join(' · '))}</div>
    </div>`;
  }).join('');
  document.getElementById('cv-component-list').innerHTML = items || '<div class="component-empty">No matching component</div>';
}

function cvFilter(){ cvRenderComponentList(document.getElementById('cv-search').value); }

function cvPinTag(p){
  return `<div class="pin-tag" style="background:${p.color}22;color:${p.color}">${cvEsc(p.type || '—')}</div>`;
}

function cvRenderConnectorCards(){
  const c = CV_COMPONENTS[cvActiveComponent];
  const cards = c.connectors.map(conn => `
    <div class="connector-card">
      <div class="connector-header">
        <div>
          <h2>${cvEsc(conn.name)}</h2>
          ${conn.meta_line ? `<div class="connector-meta">${cvEsc(conn.meta_line)}</div>` : ''}
        </div>
        <div class="connector-stats">${conn.assigned}/${conn.pin_count} assigned · ${conn.free} free${conn.warnings ? ` · ${conn.warnings} warning` : ''}${conn.errors ? ` · ${conn.errors} error` : ''}</div>
      </div>
      <div class="pin-grid">
        ${conn.pins.map(p => `
          <div class="pin ${p.status}" data-pin="${cvAttrSafe(p)}" onclick="cvShowPin(this)">
            <div class="pin-num">${cvEsc(p.pin)}</div>
            <div class="pin-name">${cvEsc(p.name)}</div>
            ${cvPinTag(p)}
          </div>`).join('')}
      </div>
    </div>`).join('');
  document.getElementById('cv-connector-cards').innerHTML = cards;
}

function cvDetailRow(label, value){
  if (value === undefined || value === null || value === '') return '';
  return `<div class="detail-kv"><div class="detail-key">${cvEsc(label)}</div><div class="detail-val">${cvEsc(value)}</div></div>`;
}

function cvShowPin(el){
  let p;
  try { p = JSON.parse(el.dataset.pin); } catch (e) { return; }
  document.querySelectorAll('.pin.active').forEach(x => x.classList.remove('active'));
  el.classList.add('active');
  const sig = p.signal || {};
  let html = `<div class="detail-header"><h3>${cvEsc(p.name || ('Pin ' + p.pin))}</h3><span class="detail-kind">${cvEsc(p.component)} / ${cvEsc(p.connector)} / Pin ${cvEsc(p.pin)}</span></div><div class="detail-content">`;
  html += cvDetailRow('Status', cvStatusLabel(p.status));
  html += cvDetailRow('Role', p.role);
  html += cvDetailRow('Group', p.group);
  html += cvDetailRow('Type', p.type);
  if (sig && sig.name) {
    html += cvDetailRow('Signal', sig.name);
    html += cvDetailRow('Interface', sig.interface_type || sig.interface);
    html += cvDetailRow('Unit', sig.unit);
    html += cvDetailRow('Min', sig.min);
    html += cvDetailRow('Max', sig.max);
    html += cvDetailRow('Resolution', sig.resolution);
    html += cvDetailRow('Priority', sig.priority);
    html += cvDetailRow('Safety', sig.safety);
  }
  html += cvDetailRow('Electrical', p.electrical);
  if (p.electrical_flags && p.electrical_flags.length) html += cvDetailRow('Electrical flags', p.electrical_flags.join(', '));
  if (p.diagnostics && p.diagnostics.length) html += cvDetailRow('Diagnostics', p.diagnostics.join(', '));
  if (p.sw_config && p.sw_config.length) html += cvDetailRow('SW config', p.sw_config.join(', '));
  if (p.linked) html += cvDetailRow('Linked to', p.linked);
  html += '</div>';
  document.getElementById('cv-pin-details').innerHTML = html;
}

function cvSelectComponent(i){
  cvActiveComponent = i;
  document.querySelectorAll('.component-item').forEach(x => x.classList.remove('active'));
  const el = document.querySelector(`.component-item[data-index="${i}"]`);
  if (el) el.classList.add('active');
  cvRenderConnectorCards();
  const firstPin = document.querySelector('.pin');
  if (firstPin) cvShowPin(firstPin);
  else document.getElementById('cv-pin-details').innerHTML = '<div class="component-empty">No pins on this component.</div>';
}

cvRenderComponentList('');
cvSelectComponent(0);
"""


def main() -> int:
    parser = make_argparser(
        "Generate interactive connector/pin view from the physical architecture export.",
        input_help="Physical architecture export JSON.",
    )
    parser.set_defaults(prefer_physical=True)
    args = parser.parse_args()
    root, cfg, arch, arch_path, outdir = cli_context(args)

    components = build_components(arch, cfg)

    ecu_count = sum(1 for c in components if c['kind'] == 'ECU')
    device_count = sum(1 for c in components if c['kind'] == 'DEVICE')
    connector_count = sum(len(c['connectors']) for c in components)
    total_pins = sum(c['total_pins'] for c in components)
    assigned = sum(conn['assigned'] for c in components for conn in c['connectors'])
    free = sum(conn['free'] for c in components for conn in c['connectors'])
    issues = sum(conn['warnings'] + conn['errors'] for c in components for conn in c['connectors'])

    kpi_html = kpi_row([
        ('Components', len(components), f'{ecu_count} ECU · {device_count} device'),
        ('Connectors', connector_count, 'Across all components'),
        ('Total Pins', total_pins, 'Defined cavities'),
        ('Assigned', assigned, 'Carrying a signal'),
        ('Free', free, 'Unoccupied'),
        ('Issues', issues, 'Warning / error pins'),
    ])

    legend_html = (
        '<div class="legend-pinstatus">'
        '<span><i style="background:var(--pin-status-valid)"></i>Valid</span>'
        '<span><i style="background:var(--pin-status-warning)"></i>Warning</span>'
        '<span><i style="background:var(--pin-status-error)"></i>Error</span>'
        '<span><i style="background:var(--pin-status-free)"></i>Free</span>'
        '</div>'
    )

    sidebar_html = (
        '<input id="cv-search" class="search" placeholder="Filter components…" oninput="cvFilter()" />'
        '<div id="cv-component-list" class="component-list"></div>'
    )
    main_html = legend_html + '<div id="cv-connector-cards"></div>'
    details_html = '<div id="cv-pin-details"><div class="component-empty">Select a pin to see details.</div></div>'

    body = f"""
    <section class="section">
      <h2>Connector View Overview</h2>
      {kpi_html}
    </section>
    <section class="section">
      <h2>Pin &amp; Signal Explorer</h2>
      {main_layout(sidebar_html, main_html, details_html)}
    </section>
    <script>
    const CV_COMPONENTS = {json.dumps(components, ensure_ascii=False)};
    {CONNECTOR_VIEW_JS}
    </script>
    """

    out = outdir / 'connector_view.html'
    out.write_text(
        html_page(
            'Connector View',
            body,
            cfg,
            'Every ECU and device connector with clickable pins — select a pin to inspect its signal, electrical and diagnostic details.',
        ),
        encoding='utf-8',
    )
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
