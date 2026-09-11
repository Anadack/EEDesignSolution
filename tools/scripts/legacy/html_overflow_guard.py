"""Shared CSS guard for generated HTML reports.

The report data contains ECU, system, device, connector and signal names that
often use long underscore-delimited identifiers. These rules keep those names
inside their visual containers without hardcoding any specific names.
"""

OVERFLOW_GUARD_CSS = """
/* Long-name guards: keep generated data labels inside their containers. */
h1, h2, h3, h4, p, a, span, strong, small, div, td, th, summary, button, label, input, select {
  overflow-wrap: anywhere;
  word-break: normal;
}
.card, .summary-card, .system-card, .device-card, .ecu-card, .connector-card,
.participant-card, .node-card, .sub-card, .route-card, .target-card, .flow-row,
.lane, .node, .chip-row, .toolbar, .filters, .table-wrap, .wrap, .diagram,
.flow-col, .bus-lane, .bus-ecu-node, .summary, .fleet, .system-section,
.participant-grid, .device-grid, .ecu-grid, .connector-grid {
  min-width: 0;
  max-width: 100%;
}
.badge, .chip, .pill, .tag, .iface-badge, .sig-badge, .filter-btn,
.prio-badge, .safety-badge, .xref, .batch-label, .group-label, .sig-name,
.dev-name, .nname, .pname, .signame, .ecu-name, .route-variant {
  white-space: normal;
  max-width: 100%;
  line-height: 1.35;
}
tbody td, thead th, th, td {
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: normal;
}
.table-wrap, .wrap, .diagram {
  max-width: 100%;
  overflow-x: auto;
}
table {
  table-layout: auto;
}
.node-head, .sub-head, .device-head, .device-card-head, .ecu-card-head,
.route-head, .target-head, .connector-card-head, .bus-lane-head {
  min-width: 0;
}
.node-head h3, .sub-head span:first-child, .device-head h3, .device-card-head h3,
.ecu-card h3, .route-head strong, .target-head strong, .connector-card-head h3,
.bus-lane-head h3, .summary-card .value, .kpi .val {
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
}
@media (max-width: 900px) {
  .toolbar, .filters {
    align-items: stretch;
  }
}
"""