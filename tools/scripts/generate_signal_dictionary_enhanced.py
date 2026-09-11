#!/usr/bin/env python3
"""Enhanced signal dictionary with advanced UI components."""
from __future__ import annotations

from eec_archdoc_common import *


def main() -> int:
    parser = make_argparser("Generate advanced signal dictionary HTML.")
    args = parser.parse_args()
    root, cfg, arch, arch_path, outdir = cli_context(args)

    idx = build_signal_index(arch)
    rows = []
    csvrows = []

    # Build data for KPIs and filters
    all_systems = set()
    all_devices = set()
    all_ecus = set()
    unmapped_count = 0

    for sn, e in sorted(idx.items(), key=lambda kv: kv[0]):
        dps = e.get('device_pins', [])
        eps = e.get('ecu_pins', [])
        systems = sorted({p['system'] for p in dps if p.get('system')})
        devices = sorted({p['device'] for p in dps if p.get('device')})
        ecus = sorted({p['ecu'] for p in eps if p.get('ecu')})
        connectors = sorted({f"{p['ecu']}:{p['connector']}:{p['physical_number']}" for p in eps})

        iface = e.get('interface', '')
        is_unmapped = len(ecus) == 0

        row = {
            'signal': esc(sn),
            'system': esc(', '.join(systems)),
            'device': esc(', '.join(devices)),
            'interface': pill(iface, iface_color(iface)),
            'unit': esc(e.get('unit', '')),
            'min': esc(e.get('min', '')),
            'max': esc(e.get('max', '')),
            'priority': esc(e.get('priority', '')),
            'safety': esc(e.get('safety', '')),
            'ecu': esc(', '.join(ecus) or 'unmapped'),
            'ecu_pin': esc(', '.join(connectors) or '—')
        }

        rows.append(row)
        csvrows.append({k: re.sub('<[^>]+>', '', str(v)) for k, v in row.items()})

        all_systems.update(systems)
        all_devices.update(devices)
        all_ecus.update(ecus)
        if is_unmapped:
            unmapped_count += 1

    write_csv(outdir / 'signal_dictionary.csv', csvrows)

    # Build KPI section with advanced tiles
    mapped_count = len(rows) - unmapped_count
    kpi_html = kpi_row([
        ('Total Signals', len(rows), 'Unique entries'),
        ('Mapped', mapped_count, 'With ECU allocation'),
        ('Unmapped', unmapped_count, 'Need assignment'),
        ('Systems', len(all_systems), 'Referenced'),
        ('Devices', len(all_devices), 'Using signals'),
    ])

    # Build table
    table_html_content = table_html('sigdict', [
        ('signal', 'Signal'),
        ('system', 'System'),
        ('device', 'Device'),
        ('interface', 'Interface'),
        ('unit', 'Unit'),
        ('min', 'Min'),
        ('max', 'Max'),
        ('priority', 'Priority'),
        ('safety', 'Safety'),
        ('ecu', 'ECU'),
        ('ecu_pin', 'Pin'),
    ], rows, 'signal_dictionary.csv')

    body = f"""
    <section class="section">
      <h2>Signal Dictionary Overview</h2>
      {kpi_html}
    </section>
    <section class="section">
      <h2>Complete Signal Catalogue</h2>
      {table_html_content}
    </section>
    """

    out = outdir / 'signal_dictionary.html'
    out.write_text(
        html_page(
            'Signal Dictionary',
            body,
            cfg,
            'Complete signal catalogue generated from framework JSON exports.'
        ),
        encoding='utf-8'
    )
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
