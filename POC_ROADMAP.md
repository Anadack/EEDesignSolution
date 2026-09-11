# POC Roadmap — EE_Architect_Design v1.0.0 → v1.2.0

> **Proof of Concept priorities: Maximum user impact + feasibility within 2–3 month engineering cycles**

---

## Overview

This document proposes a phased rollout of 12 POC initiatives, grouped into **3 engineering sprints** (Q3 2026), prioritized by:
1. **User pain points** (what architects ask for most)
2. **Technical feasibility** (achievable with existing C/Python infrastructure)
3. **Time-to-value** (weeks to deliver, not months)
4. **Dependency ordering** (build POCs on top of completed features)

---

## Phase 1: Foundation (Sprint 1 — July 2026) — **4–5 weeks**

### **POC-1: DBC Export Generator** ⭐ HIGHEST PRIORITY
**Problem**: Users want to export CAN architectures to Vector CANoe format for downstream message definition.

**Scope**:
- New Python generator: `generate_can_dbc_export.py`
- Read architecture JSON signals with `interface_type == CAN`
- Auto-assign CAN message IDs (0x100–0x7FF for standard CAN)
- Group signals by ECU/bus into messages
- Export DBC format: message headers + signal definitions
- Include senders, receivers, cycle time (stub: default 100ms)

**Deliverables**:
- `exported_architecture.dbc` (Vector CANoe compatible)
- Validation: import into CANoe successfully
- Documentation: DBC generation chapter in README

**Success Criteria**:
- CANoe opens generated DBC without errors
- All CAN signals from architecture present in DBC
- Cycle time, message ID assignments logged in verify_report.txt

**Effort**: 3–4 weeks (1 dev)

**Dependencies**: None — leverages existing signal export logic

---

### **POC-2: Quick-Start Templates Library** ⭐ SECOND PRIORITY
**Problem**: New users spend 2–3 days setting up first architecture; most start from scratch.

**Scope**:
- Create 3 pre-built example architectures in `examples/templates/`:
  - `tractor_base.json` — 5 systems, 2 ECUs, basic CAN (already exists, enhance)
  - `telehandler_hydraulic.json` — Hydraulic sensors, mixed analog/CAN, 3 ECUs
  - `combine_harvester_modular.json` — Modular subsystems, 5 ECUs, multi-bus
- Add interactive `TEMPLATE_README.md` with:
  - Copy-paste instructions
  - Customization checklist (rename system, adjust IO, select ECU variant)
  - Common mistakes to avoid
- New web landing page: `examples/templates/index.html` listing all templates

**Deliverables**:
- 3 ready-to-run JSON files in `examples/templates/`
- `TEMPLATE_README.md` with step-by-step onboarding
- `examples/templates/index.html` (visual template selector)

**Success Criteria**:
- New user can fork template → 10 min to running architecture
- Templates compile & validate with zero errors
- User satisfaction survey: 80%+ "easy to start"

**Effort**: 2–3 weeks (1–2 devs)

**Dependencies**: None

---

### **POC-3: Git Hooks & CI/CD Pipeline** ⭐ OPERATIONAL VALUE
**Problem**: Teams need pre-commit validation + automated build on push to catch issues early.

**Scope**:
- Create `.githooks/pre-commit` script:
  - Validate all JSON in `library/` and `examples/`
  - Run C compiler check (no errors/warnings)
  - Auto-format DEVELOPMENT.md if changed
  - Abort commit if validation fails
- Create `.github/workflows/validate.yml` (GitHub Actions):
  - On push: compile C code
  - Run unit tests (`qa/run_tests.sh`)
  - Generate architecture exports
  - Deploy HTML to GitHub Pages (optional)
- Document in DEVELOPMENT.md: "Setting Up Git Hooks"

**Deliverables**:
- `.githooks/pre-commit` script
- `.github/workflows/validate.yml`
- GitHub Actions documentation section in DEVELOPMENT.md

**Success Criteria**:
- All commits pass pre-commit validation
- CI/CD completes in <2 min (compile + tests)
- 100% of merged PRs have passed CI

**Effort**: 2 weeks (1 dev)

**Dependencies**: None

---

## Phase 2: Capability (Sprint 2 — August 2026) — **4–5 weeks**

### **POC-4: CAN Message Packing & Payload Layout**
**Problem**: DBC export alone doesn't show signal byte order / start-bit; users need full message structure.

**Scope**:
- Extend `EEC_Signal_t` struct (in C headers) with:
  - `uint16_t can_message_id` — CAN message identifier
  - `uint8_t start_bit` — Signal byte position in payload
  - `uint8_t length` — Number of bits
  - `bool big_endian` — Byte order (Motorola vs. Intel)
  - `float scale, offset` — Encoding parameters
- Implement `EEC_Signal_PackMessage()` — groups signals by message ID, calculates layout
- Update DBC exporter to include start-bit, length, byte order per signal
- Add interactive HTML viewer: `message_layout_viewer.html`
  - Shows signal bit packing visually
  - Detects overlaps / gaps

**Deliverables**:
- C header updates (EEC_architecture.h)
- Message packing C implementation (src/EEC_pack.c)
- Enhanced DBC exporter with signal layout
- `message_layout_viewer.html` with bit-grid visualization

**Success Criteria**:
- All CAN signals have assigned start-bit & length
- DBC format includes signal encoding (scale, offset, byte order)
- message_layout_viewer shows zero overlaps for valid architectures
- CANoe imports updated DBC with correct signal encoding

**Effort**: 3–4 weeks (1–2 devs)

**Dependencies**: POC-1 (DBC Export)

---

### **POC-5: Bandwidth & Load Analysis**
**Problem**: Architects guess if a CAN bus can handle 50+ signals; no framework calculates actual load.

**Scope**:
- New Python generator: `generate_can_bus_load_analysis.py`
- For each CAN bus:
  - Count signals per message
  - Calculate payload bytes (sum of signal bit-lengths)
  - Estimate message cycle time (default 100ms, or from metadata)
  - **Bus load = (total_bytes_per_cycle / 8) / (bitrate in Mbps) × 100%**
  - Warn if load > 70% (yellow) or > 90% (red)
- Generate HTML report:
  - Bar chart: load per bus
  - Table: message-by-message breakdown
  - Recommendations: "Split CAN_FT into CAN_LO (priority signals)"
- Add rule **B9**: "Bus load ≤ 80% under worst-case timing"

**Deliverables**:
- `generate_can_bus_load_analysis.py` generator
- `bus_load_report.html`
- New verification rule B9
- Documentation: CAN bus sizing best practices in README

**Success Criteria**:
- Load calculations match CANoe analysis (±5%)
- High-load buses flagged with recommendations
- Report helps architects decide: 1 CAN vs. 2 CAN buses

**Effort**: 2–3 weeks (1 dev)

**Dependencies**: POC-4 (CAN Message Packing) — needed for payload size calc

---

### **POC-6: LIN Schedule Generator**
**Problem**: LIN buses exist in library but framework doesn't generate schedules; users do it manually.

**Scope**:
- New Python generator: `generate_lin_schedule.py`
- For each LIN bus in architecture:
  - List all signals (interface_type == LIN)
  - Auto-assign LIN frame IDs (0x00–0x3F)
  - Assign to ECUs (one master = frame publisher, slaves = subscribers)
  - Generate LIN database file (.ldf format) stub
  - HTML viewer: LIN frame timing diagram
- Add rule **B9a**: "LIN bus has single master"

**Deliverables**:
- `generate_lin_schedule.py`
- `.ldf` file export (LIN database format)
- `lin_schedule_viewer.html` (timing diagram)
- LIN configuration section in generated documentation

**Success Criteria**:
- LIN schedule generated for all LIN buses
- .ldf file imports into Vector toolchain
- Timing diagram shows no frame collisions
- Master/slave assignments validated per rule B9a

**Effort**: 2–3 weeks (1 dev)

**Dependencies**: None (independent from CAN)

---

### **POC-7: Functional Safety Traceability (ISO 26262 Evidence)**
**Problem**: Safety-critical vehicle platforms need automated ISO 26262 compliance evidence.

**Scope**:
- Extend `EEC_Signal_t` with:
  - `uint8_t asil_level` — ASIL A/B/C/D (0 = QM)
  - `bool is_monitored` — has on-board diagnostics
  - `uint16_t diagnostic_latency_ms` — time to detect & react
- New rule **V14**: "Safety-critical signal on ECU pin has diagnostic coverage"
- Generator: `generate_iso26262_evidence.html`
  - Traceability table: Signal → ASIL → Diagnostic Method → Coverage (%) → Evidence
  - Failure Mode & Effects Analysis (FMEA) summary
  - Diagnostic Strategy matrix
- Add CSV export for feeding into ISO 26262 FMEA tools

**Deliverables**:
- C struct updates (EEC_architecture.h)
- Verification rule V14
- `generate_iso26262_evidence.html`
- Safety traceability CSV export
- ISO 26262 compliance documentation

**Success Criteria**:
- All ASIL_B+ signals have assigned diagnostic method
- Evidence table correlates architecture → safety strategy
- Can be submitted to safety auditor as compliance evidence
- FMEA CSV imports into FTA tools

**Effort**: 3–4 weeks (1–2 devs)

**Dependencies**: POC-2 (templates should include safety examples)

---

## Phase 3: Polish & Consolidation (Sprint 3 — September 2026) — **3–4 weeks**

### **POC-8: Incremental Build System**
**Problem**: Rebuild takes 30s even after 1-signal change; developers want <5s feedback loop.

**Scope**:
- Implement `.eec-cache` directory:
  - Hash of each source file (library JSONs, C code)
  - Timestamp of last export
- C code change detection:
  - Only re-link if src/ or inc/ changed
  - Skip exports if library/ unchanged
- Python generator orchestration:
  - Skip generator if input architecture unchanged
  - Cache HTML output
- New CLI flag: `./app --incremental` or `./run.sh --fast`

**Deliverables**:
- Incremental build cache mechanism
- `--incremental` / `--fast` CLI flag
- Performance metrics: before/after rebuild times
- Documentation: "Fast Development Loop" in DEVELOPMENT.md

**Success Criteria**:
- Single-signal edit → rebuild in <5 sec (vs. 30s baseline)
- Full build still takes <30s (no regression)
- Cache invalidation works correctly on file changes
- Team adopts fast loop for daily iteration

**Effort**: 2–3 weeks (1 dev)

**Dependencies**: None (pure infrastructure)

---

### **POC-9: Multilingual Report Generation**
**Problem**: Global OEM customers need documentation in German, French, Japanese.

**Scope**:
- Create i18n system:
  - Central `tools/scripts/i18n_strings.json` with language keys
  - Supported languages: EN, DE, FR, JA, ZH
- Update all HTML generators to use i18n keys:
  - Before: `<h2>Communication Matrix</h2>`
  - After: `<h2>{{ i18n('comm_matrix_title') }}</h2>`
- Python template system: substitute language-specific strings at generation time
- Add CLI flag: `./app --language de` or environment var `EEC_LANGUAGE=FR`
- Default: English, with config fallback

**Deliverables**:
- `tools/scripts/i18n_strings.json` (EN, DE, FR, JA, ZH)
- Generator updates (sample 5 generators for POC)
- `--language` CLI flag
- Multilingual documentation section in README

**Success Criteria**:
- All 5 sample generators produce correct German output
- Team validates translations with native speakers
- 80%+ of framework content translatable (some custom text stays in EN)
- Users can generate full suite in any language

**Effort**: 2–3 weeks (1 dev + translation support)

**Dependencies**: None (optional feature)

---

### **POC-10: Interactive Web UI for Architecture Authoring**
**Problem**: Non-technical stakeholders (procurement, product) can't edit JSON; need drag-and-drop UI.

**Scope**:
- New directory: `webui/architect/` (Vue.js / React app)
- Features (Phase 1):
  - Load existing architecture JSON from file/workspace
  - Visual system browser (tree of systems, components, signals)
  - Add/remove signals with form validation (real-time errors)
  - Estimate ECU sizing (call backend `/estimate` endpoint)
  - Export updated JSON or run full build
- Backend: Simple Node.js/Python HTTP server:
  - `/api/load-architecture` → read JSON
  - `/api/validate-signal` → check uniqueness, type, unit
  - `/api/estimate` → call C estimation engine
  - `/api/build` → trigger full build pipeline
- Deployment: `webui/architect/index.html` (standalone HTML + JS, no build step)

**Deliverables**:
- `webui/architect/` directory with HTML/CSS/JS
- Simple HTTP server (can run on localhost:8080)
- API documentation
- "Web UI Quick Start" in DEVELOPMENT.md

**Success Criteria**:
- Non-technical user can add 5 signals via UI in <5 min
- Validation catches naming conflicts in real-time
- Export JSON matches manual editing exactly
- UI responsive on desktop + tablet

**Effort**: 4–5 weeks (1–2 devs)

**Dependencies**: None (optional, can be done in parallel)

---

### **POC-11: Cybersecurity Threat Model (ISO 21434 Evidence)**
**Problem**: Automotive OEMs need ISO 21434 cyber risk assessment; manual process takes weeks.

**Scope**:
- Extend architecture with "cyber context" metadata:
  - ECU: `threat_level` (LOW, MEDIUM, HIGH, CRITICAL)
  - Bus: `is_external` (true if exposed to external networks)
  - Signal: `is_authentication_required` bool
- Generator: `generate_iso21434_threat_model.html`
  - Auto-enumerate attack paths (e.g., "CAN node 0x70 → ECU_X → Brake Signal")
  - Risk matrix: Likelihood × Impact
  - Recommended mitigations (encryption, authentication, timeout)
  - Attack tree visualization
- CSV export for feeding into risk management tools

**Deliverables**:
- C struct extensions (threat_level, is_external fields)
- `generate_iso21434_threat_model.html` generator
- Attack tree visualization (HTML/SVG)
- Threat model CSV export
- ISO 21434 documentation section in README

**Success Criteria**:
- All external-facing signals flagged for review
- Risk matrix aligns with OEM threat assessment
- Threat model can be submitted to cyber auditor
- CSV imports into risk management systems

**Effort**: 3–4 weeks (1–2 devs)

**Dependencies**: POC-7 (safety foundation helps cyber too)

---

### **POC-12: Architecture Diff / Version Comparison Report**
**Problem**: Users release v2.0 architecture; need to show stakeholders what changed from v1.0.

**Scope**:
- Enhance existing `generate_change_impact_report_html.py`:
  - Compare two JSON architecture snapshots (file A vs. file B)
  - Detect added/removed/modified signals, systems, ECUs, buses
  - Calculate impact scores: signal count delta, ECU count delta, bus topology change
  - Highlight risky changes (e.g., safety signal moved to different ECU)
  - Generate before/after pin allocation chart
  - Recommend verification focus: "Re-verify V5 (signal mapping) and B1 (ECU capacity)"
- Add interactive HTML mode:
  - Side-by-side view (v1 signals vs. v2 signals)
  - Filter by change type (added, removed, modified)
  - Traceability: which requirement changed triggered which architecture change

**Deliverables**:
- Enhanced `generate_change_impact_report_html.py`
- Side-by-side comparison viewer
- Impact assessment scoring
- Change traceability CSV export

**Success Criteria**:
- All added/removed signals detected with 100% accuracy
- Impact score helps prioritize re-verification (80% agree)
- Executive summary shows delta in <30 seconds
- CSV traceability matches change logs from requirements tool

**Effort**: 2–3 weeks (1 dev)

**Dependencies**: None

---

## Summary Table

| POC # | Title | Phase | Effort | Priority | Owner | Blockers |
|-------|-------|-------|--------|----------|-------|----------|
| 1 | DBC Export | Ph1 | 3–4w | ⭐⭐⭐ | Dev1 | None |
| 2 | Templates | Ph1 | 2–3w | ⭐⭐⭐ | Dev1–2 | None |
| 3 | Git Hooks/CI | Ph1 | 2w | ⭐⭐ | DevOps | None |
| 4 | Message Packing | Ph2 | 3–4w | ⭐⭐⭐ | Dev2 | POC-1 |
| 5 | Bandwidth Analysis | Ph2 | 2–3w | ⭐⭐⭐ | Dev1 | POC-4 |
| 6 | LIN Scheduler | Ph2 | 2–3w | ⭐⭐ | Dev2 | None |
| 7 | Safety Traceability | Ph2 | 3–4w | ⭐⭐⭐ | Dev3 | POC-2 |
| 8 | Incremental Build | Ph3 | 2–3w | ⭐⭐ | DevOps | None |
| 9 | Multilingual | Ph3 | 2–3w | ⭐ | Dev2 | None |
| 10 | Web UI | Ph3 | 4–5w | ⭐⭐ | Dev1–2 | None |
| 11 | Cyber Threat Model | Ph3 | 3–4w | ⭐⭐ | Dev3 | POC-7 |
| 12 | Version Compare | Ph3 | 2–3w | ⭐⭐ | Dev1 | None |

---

## Resource & Timeline

**Total Effort**: 35–45 weeks of dev (3–4 devs across 3 months)

**Recommended Team**:
- **Dev1** (Lead): POC-1, 2, 5, 10, 12 — Generator/feature expertise
- **Dev2** (Backend): POC-4, 6, 9 — C/data structure expertise
- **Dev3** (Systems): POC-7, 11 — Safety/security domain knowledge
- **DevOps** (1 engineer, part-time): POC-3, 8 — CI/CD + build infrastructure

**Timeline**:
- **Sprint 1 (Jul 1–Aug 1)**: POC-1, 2, 3 (Foundation complete, templates live)
- **Sprint 2 (Aug 1–Sep 1)**: POC-4, 5, 6, 7 (CAN + safety matured)
- **Sprint 3 (Sep 1–Oct 1)**: POC-8, 9, 10, 11, 12 (Polish, optimize, compliance)

---

## Success Criteria (Overall)

✅ **Phase 1 Complete** (Aug 1):
- Users can export CAN to CANoe format
- New users onboard in <1 hour using templates
- All commits validated automatically

✅ **Phase 2 Complete** (Sep 1):
- CAN message structures fully defined (payload layout)
- Bus load analysis guides ECU selection
- Safety & cyber compliance evidence auto-generated

✅ **Phase 3 Complete** (Oct 1):
- Fast iteration loop (<5s rebuild)
- Global teams work in native languages
- Non-technical stakeholders can edit architectures
- Threat models & version diffs auto-generated

---

## Post-POC Roadmap (v1.3+)

Once core POCs validate product-market fit:
- **CANoe integration**: Auto-launch CANoe with generated .dbc
- **Simulink export**: Generate bus objects + message structures for Model-Based Design
- **Cloud deployment**: SaaS version with team collaboration + workspace
- **AI anomaly detection**: Highlight risky architecture patterns (e.g., "Signal routed to wrong ECU variant")

---

**Document Owner**: Solution Architect  
**Last Updated**: June 29, 2026  
**Status**: Ready for team review & planning
