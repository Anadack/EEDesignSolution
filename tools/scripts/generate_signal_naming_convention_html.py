#!/usr/bin/env python3
"""Generate Signal Naming Convention reference page (HTML)."""
from __future__ import annotations
import sys
from pathlib import Path

try:
    from eec_report_common import (
        standard_arg_parser, load_config, resolve_root,
        get_output_file, html_page, write_text, esc,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from eec_report_common import (
        standard_arg_parser, load_config, resolve_root,
        get_output_file, html_page, write_text, esc,
    )

# ---------------------------------------------------------------------------
# Convention data
# ---------------------------------------------------------------------------

SYSTEMS = [
    ("SBRK",  "Service Brake (pedal, pad-wear indicator)"),
    ("PBRK",  "Park Brake (lever position, actuator pressure)"),
    ("BRK",   "Brake — generic (axle steering brake)"),
    ("AWD",   "All-Wheel Drive"),
    ("TRSM",  "Transmission"),
    ("DRVC",  "Drive Control (clutch/throttle pedal, turbo-clutch)"),
    ("DIFF",  "Differential (lock)"),
    ("EFAN",  "Electric Cooling Fan"),
    ("FHIT",  "Front Hitch"),
    ("FPTO",  "Front Power Take-Off"),
    ("HYDD",  "Hydraulics Distribution (auxiliary/remote valves)"),
    ("ISOB",  "ISOBUS power supply"),
    ("FLDR",  "Front Loader"),
    ("CLIM",  "Climate / Cab HVAC"),
    ("IMPC",  "Implement Communication / control event"),
    ("MPRT",  "Axle lubrication monitoring"),
    ("TRAC",  "Traction control (radar speed)"),
    ("RDS",   "Reversible Drive Station"),
    ("PNMD",  "Pneumatics Distribution (trailer brake air supply)"),
    ("ELCD",  "Electrical Load / Battery Disconnect"),
    ("RHIT",  "Rear Hitch"),
    ("RPTO",  "Rear Power Take-Off"),
    ("SEAT",  "Operator Seat"),
    ("STRN",  "Steering"),
    ("SPSN",  "Suspension (axle)"),
    ("TBRK",  "Trailer Brake"),
]

# "Reduced" SYSTEM codes from the CEA3 Premium tractor IO naming proposal
# (signal names capped at <=30 chars). Several original codes are merged
# into MISC when their signal count is low.
REDUCED_SYSTEMS = [
    ("DRVC", "DRV"), ("EFAN", "FAN"), ("HYDD", "HYD"), ("FLDR", "LDR"),
    ("PNMD", "PNM"), ("ELCD", "PWR"), ("STRN", "STER"), ("SPSN", "SUSP"),
    ("TBRK", "TRBR"),
    ("CLIM", "MISC"), ("IMPC", "MISC"), ("MPRT", "MISC"),
    ("TRAC", "MISC"), ("RDS", "MISC"),
]

FUNCTIONS = [
    ("ActrPresr",          "Actuator pressure"),
    ("LvrPosn1",           "Lever position (indexed: LvrPosn1, LvrPosn2)"),
    ("BrkPadWearIndcr",    "Brake-pad wear indicator"),
    ("CluPedlPosn",        "Clutch pedal position"),
    ("AxleSteerBrk",       "Axle steering brake"),
    ("Lock",               "Differential lock"),
    ("GearStg",            "Gear stage"),
    ("BevelPinionSpd",     "Bevel pinion speed"),
    ("HydMot2Engmt",       "Hydraulic motor 2 engagement"),
    ("OilFilContmsn",      "Oil filter contamination"),
    ("DwnforcePresr",      "Down-force pressure"),
    ("SngActingAV1",       "Single-acting auxiliary valve 1"),
    ("Ext_Lifting",        "Lifting, external control (compound — two CamelCase tokens)"),
    ("Ext_Lowering",       "Lowering, external control (compound — two CamelCase tokens)"),
    ("AuxOilLvl",          "Auxiliary oil level"),
    ("eLSPmp1Ctrl",        "Load-sensing pump 1 control, electronic ('e' prefix)"),
    ("PwrBeyond",          "Power-beyond hydraulic port"),
    ("PwrSupply25A",       "Power supply rail, 25 A"),
    ("3rdCirc",            "Third hydraulic circuit (leading ordinal digit allowed)"),
    ("CntrEve",            "Control event"),
    ("RvsDriveStationPosn","Reversible drive station position"),
    ("ForceMeasuringPin",  "Force-measuring pin"),
    ("eTBA",               "Trailer Brake Actuation, electronic ('e' prefix)"),
    ("WhlPosn",            "Wheel position"),
]

POSITIONS = [
    ("LE",   "Left"),
    ("RI",   "Right"),
    ("FR",   "Front"),
    ("RE",   "Rear"),
    ("FRLE", "Front-Left"),
    ("FRRI", "Front-Right"),
    ("RELE", "Rear-Left"),
    ("RERI", "Rear-Right"),
    ("CTR",  "Centre"),
]

TYPES = [
    ("SNSR",  "Sensor (generic analogue/digital input)"),
    ("SWT",   "Switch (discrete on/off)"),
    ("EVHS",  "Electrovalve High-Side drive"),
    ("EVLS",  "Electrovalve Low-Side drive"),
    ("HS",    "High-Side driver output"),
    ("LS",    "Low-Side driver output"),
    ("RELE",  "Relay output"),
    ("ACT",   "Actuator (generic)"),
    ("MTR",   "Motor"),
    ("VLV",   "Valve (hydraulic, pneumatic)"),
    ("SOL",   "Solenoid"),
    ("FUSE",  "Fuse / protection"),
    ("CMD",   "Command signal (e.g. PWM setpoint)"),
    ("CAN",   "CAN-bus interface signal"),
    ("LIN",   "LIN-bus interface signal"),
    ("PWM",   "PWM output"),
    ("PWR",   "Power supply rail"),
    ("GND",   "Ground / return"),
    ("REL",   "Relay output"),
    ("SIGN",  "Signal lamp / indicator output"),
    ("Buz",   "Buzzer / audible alarm (mixed-case exception)"),
]

COMPLIANT = [
    ("PBRK_ActrPresr_LE_SNSR",        "Park brake – left actuator pressure sensor"),
    ("BRK_AxleSteerBrk_RELE_EVHS",    "Brake – rear-left axle steering brake electrovalve (HS)"),
    ("AWD_Clu_EVHS",                  "AWD clutch electrovalve (HS) — no position needed"),
    ("DRVC_CluPedlPosn_SNSR",         "Driveline – clutch pedal position sensor"),
    ("DIFF_Lock_EVHS",                "Differential lock electrovalve (HS)"),
    ("SBRK_BrkPadWearIndcr_LE_SWT",   "Service brake – left pad wear indicator switch"),
    ("TRSM_OilTemperature_SNSR",      "Transmission oil temperature sensor"),
    ("FHIT_Ext_Lifting_SWT",          "Front hitch – external lifting switch (compound function)"),
    ("HYDD_Ext_Lifting_FR_SWT",       "Hydraulics – front external lifting switch (compound + POSITION)"),
    ("HYDD_eLSPmp1Ctrl_EVHS",         "Load-sensing pump 1 control electrovalve (HS) — 'e' prefix"),
    ("TBRK_eTBA_EVHS",                "Trailer brake actuation electrovalve (HS) — 'e' prefix"),
    ("FLDR_3rdCirc_EVHS",             "Front loader – 3rd circuit electrovalve (HS) — leading digit"),
    ("ISOB_PwrSupply25A_REL",         "ISOBUS power supply 25 A relay"),
    ("IMPC_CntrEve_SIGN",             "Implement control-event signal lamp"),
    ("RDS_RvsMtn_Buz",                "Reverse-motion buzzer — mixed-case TYPE exception"),
    ("SPSN_WhlPosn_FRLE_SNSR",        "Suspension – front-left wheel position sensor"),
    ("SEAT_OperatorPres_SWT",         "Operator-presence seat switch"),
]

NON_COMPLIANT = [
    ("HAT1200_Angle_4_20mA",   "HAT_Angle_SNSR",     "Device model in SYSTEM field; measurement spec in TYPE"),
    ("DirCoilCmd_HS",          "??_DirCoilCmd_HS",    "Missing SYSTEM prefix"),
    ("ParlockPressure",        "SYS_ParlockPresr_SNSR","No underscores; missing SYSTEM & TYPE"),
    ("elobau_424A_GND",        "ELOBAU_Functn_GND",   "Lowercase brand name; model number in name"),
    ("HYDAC_4059964_CoilCmd_HS","HYDAC_CoilCmd_HS",   "Part-number token between SYSTEM and Function"),
]

# Signals that LOOK irregular at a glance but ARE compliant — called out
# explicitly so they are not mistaken for violations.
SPECIAL_CASES = [
    ("FHIT_Ext_Lifting_SWT",  "Function spans two underscore-separated CamelCase "
                               "tokens (Ext + Lifting) treated as one compound function."),
    ("TBRK_eTBA_EVHS",        "Function starts with lowercase 'e' meaning \"electronic\" "
                               "(eTBA, eLSPmp1Ctrl) — the rest stays CamelCase."),
    ("FLDR_3rdCirc_EVHS",     "Function may start with a leading ordinal digit "
                               "(3rdCirc) before the CamelCase text."),
    ("RDS_RvsMtn_Buz",        "TYPE is normally 2-8 uppercase letters, but 'Buz' "
                               "(buzzer) is a recognised mixed-case exception."),
]

# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _row2(cells: list[str], cls: str = "") -> str:
    tds = "".join(f"<td>{c}</td>" for c in cells)
    return f"<tr class='{cls}'>{tds}</tr>" if cls else f"<tr>{tds}</tr>"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    ths = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join(_row2(r) for r in rows)
    return (f"<div style='overflow:auto;border-radius:10px;"
            f"border:1px solid rgba(255,255,255,.06);margin:12px 0'>"
            f"<table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div>")


def build_body() -> str:
    # KPI pills
    kpis = "".join(
        f"<div class='kpi'><div>{label}</div><b>{val}</b></div>"
        for label, val in [
            ("SYSTEM codes", str(len(SYSTEMS))),
            ("POSITION codes", str(len(POSITIONS))),
            ("TYPE codes", str(len(TYPES))),
            ("Parts (min)", "3"),
            ("Parts (max)", "5+"),
        ]
    )

    sys_table = _table(
        ["Code", "System / Subsystem"],
        [[f"<code class='mono' style='color:#60a5fa'>{esc(c)}</code>", esc(d)] for c, d in SYSTEMS],
    )

    reduced_sys_table = _table(
        ["Original", "Reduced (CEA3 Premium)"],
        [[f"<code class='mono' style='color:#60a5fa'>{esc(o)}</code>",
          f"<code class='mono' style='color:#93c5fd'>{esc(r)}</code>"] for o, r in REDUCED_SYSTEMS],
    )

    func_section = _table(
        ["Abbreviated token", "Meaning"],
        [[f"<code class='mono' style='color:#a78bfa'>{esc(t)}</code>", esc(m)] for t, m in FUNCTIONS],
    )

    pos_table = _table(
        ["Code", "Position"],
        [[f"<code class='mono' style='color:#f59e0b'>{esc(c)}</code>", esc(d)] for c, d in POSITIONS],
    )

    type_table = _table(
        ["Code", "Component / signal type"],
        [[f"<code class='mono' style='color:#10b981'>{esc(c)}</code>", esc(d)] for c, d in TYPES],
    )

    ok_rows = "".join(
        f"<tr>"
        f"<td><code class='mono' style='color:#86efac'>{esc(name)}</code></td>"
        f"<td style='color:#8993a8;font-size:11px'>{esc(desc)}</td>"
        f"</tr>"
        for name, desc in COMPLIANT
    )

    bad_rows = "".join(
        f"<tr>"
        f"<td><code class='mono' style='color:#fca5a5'>{esc(orig)}</code></td>"
        f"<td><code class='mono' style='color:#86efac'>{esc(prop)}</code></td>"
        f"<td style='color:#8993a8;font-size:11px'>{esc(reason)}</td>"
        f"</tr>"
        for orig, prop, reason in NON_COMPLIANT
    )

    special_rows = "".join(
        f"<tr>"
        f"<td><code class='mono' style='color:#93c5fd'>{esc(name)}</code></td>"
        f"<td style='color:#8993a8;font-size:11px'>{esc(note)}</td>"
        f"</tr>"
        for name, note in SPECIAL_CASES
    )

    ok_table = (
        f"<div style='overflow:auto;border-radius:10px;border:1px solid rgba(255,255,255,.06);margin:12px 0'>"
        f"<table><thead><tr><th>Signal name</th><th>Description</th></tr></thead>"
        f"<tbody>{ok_rows}</tbody></table></div>"
    )

    bad_table = (
        f"<div style='overflow:auto;border-radius:10px;border:1px solid rgba(255,255,255,.06);margin:12px 0'>"
        f"<table><thead><tr><th>Non-compliant</th><th>Proposed correction</th><th>Issue</th></tr></thead>"
        f"<tbody>{bad_rows}</tbody></table></div>"
    )

    special_table = (
        f"<div style='overflow:auto;border-radius:10px;border:1px solid rgba(255,255,255,.06);margin:12px 0'>"
        f"<table><thead><tr><th>Signal name</th><th>Why it's compliant</th></tr></thead>"
        f"<tbody>{special_rows}</tbody></table></div>"
    )

    return f"""
<div class="page-header">
  <h1>Signal Naming Convention</h1>
  <div class="src">Reference — <code>SYSTEM_Function_[POSITION_]TYPE</code></div>
</div>

<div class="kpis">{kpis}</div>

<!-- FORMAT -->
<div class="card">
  <h2>Convention format</h2>
  <p style="color:var(--ts);margin-bottom:16px">
    Every signal name must follow this underscore-delimited pattern.
    The POSITION segment is optional when the device has a single unambiguous mounting location.
  </p>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:20px 0">
    <div style="background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.25);border-radius:10px;padding:16px 18px;text-align:center">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#5a6278;margin-bottom:8px">① SYSTEM</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:1.3rem;font-weight:800;color:#60a5fa">PBRK</div>
      <div style="font-size:10px;color:#5a6278;margin-top:6px">2–8 uppercase letters<br>system abbreviation</div>
    </div>
    <div style="background:rgba(167,139,250,.08);border:1px solid rgba(167,139,250,.25);border-radius:10px;padding:16px 18px;text-align:center">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#5a6278;margin-bottom:8px">② Function</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:1.3rem;font-weight:800;color:#a78bfa">ActrPresr</div>
      <div style="font-size:10px;color:#5a6278;margin-top:6px">CamelCase<br>abbreviated descriptor</div>
    </div>
    <div style="background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);border-radius:10px;padding:16px 18px;text-align:center">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#5a6278;margin-bottom:8px">③ POSITION <span style="font-weight:400;color:#5a6278">(optional)</span></div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:1.3rem;font-weight:800;color:#f59e0b">LE</div>
      <div style="font-size:10px;color:#5a6278;margin-top:6px">Known position code<br>omit if unambiguous</div>
    </div>
    <div style="background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.25);border-radius:10px;padding:16px 18px;text-align:center">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#5a6278;margin-bottom:8px">④ TYPE</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:1.3rem;font-weight:800;color:#10b981">SNSR</div>
      <div style="font-size:10px;color:#5a6278;margin-top:6px">2–8 uppercase letters<br>component/signal type</div>
    </div>
  </div>

  <!-- assembled example -->
  <div style="background:var(--raised);border:1px solid var(--b1);border-radius:10px;padding:18px 22px;margin-top:8px;text-align:center">
    <span style="font-family:'JetBrains Mono',monospace;font-size:1.4rem;font-weight:800">
      <span style="color:#60a5fa">PBRK</span><span style="color:#5a6278">_</span><span style="color:#a78bfa">ActrPresr</span><span style="color:#5a6278">_</span><span style="color:#f59e0b">LE</span><span style="color:#5a6278">_</span><span style="color:#10b981">SNSR</span>
    </span>
    <div style="font-size:11px;color:#5a6278;margin-top:8px">Park Brake — Left Actuator Pressure Sensor</div>
  </div>
</div>

<!-- RULES -->
<div class="card">
  <h2>Naming rules</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
    <div style="background:var(--raised);border-radius:var(--rm);padding:14px 16px;border:1px solid var(--b1)">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#60a5fa;margin-bottom:8px">SYSTEM</div>
      <ul style="padding-left:16px;color:var(--ts);font-size:12px;line-height:2">
        <li>2–8 uppercase letters only (no digits)</li>
        <li>Chosen once per functional sub-system</li>
        <li>Stable across architecture releases</li>
        <li>Examples: <code class="mono" style="color:#60a5fa">PBRK, AWD, DRVC, EFAN</code></li>
      </ul>
    </div>
    <div style="background:var(--raised);border-radius:var(--rm);padding:14px 16px;border:1px solid var(--b1)">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#a78bfa;margin-bottom:8px">Function</div>
      <ul style="padding-left:16px;color:var(--ts);font-size:12px;line-height:2">
        <li>CamelCase: first letter uppercase</li>
        <li>Abbreviated but self-explanatory</li>
        <li>Avoid device brand / model numbers</li>
        <li>May be <strong>compound</strong>: several underscore-separated
            CamelCase tokens count as one Function (<code class="mono" style="color:#a78bfa">Ext_Lifting</code>)</li>
        <li>May start with lowercase <code class="mono" style="color:#a78bfa">e</code> for
            "electronic" (<code class="mono" style="color:#a78bfa">eTBA</code>) or a
            leading ordinal digit (<code class="mono" style="color:#a78bfa">3rdCirc</code>)</li>
        <li>Examples: <code class="mono" style="color:#a78bfa">ActrPresr, CluPedlPosn, eTBA</code></li>
      </ul>
    </div>
    <div style="background:var(--raised);border-radius:var(--rm);padding:14px 16px;border:1px solid var(--b1)">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#f59e0b;margin-bottom:8px">POSITION (optional)</div>
      <ul style="padding-left:16px;color:var(--ts);font-size:12px;line-height:2">
        <li>Omit when there is only one instance</li>
        <li>Must be from the approved position list</li>
        <li>Examples: <code class="mono" style="color:#f59e0b">LE, RI, RELE, FR</code></li>
      </ul>
    </div>
    <div style="background:var(--raised);border-radius:var(--rm);padding:14px 16px;border:1px solid var(--b1)">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#10b981;margin-bottom:8px">TYPE</div>
      <ul style="padding-left:16px;color:var(--ts);font-size:12px;line-height:2">
        <li>2–8 uppercase letters only</li>
        <li>Describes component or signal interface</li>
        <li>Must be from the approved type list</li>
        <li>One mixed-case exception: <code class="mono" style="color:#10b981">Buz</code> (buzzer)</li>
        <li>Examples: <code class="mono" style="color:#10b981">SNSR, EVHS, HS, LS, REL, SIGN</code></li>
      </ul>
    </div>
  </div>
</div>

<!-- REFERENCE TABLES -->
<div class="card">
  <h2>① SYSTEM codes</h2>
  <p style="color:var(--ts);font-size:12px;margin-bottom:4px">Add project-specific codes to this list and keep it under version control.</p>
  {sys_table}
  <h3 style="font-size:12px;color:var(--ts);margin:18px 0 4px">Reduced SYSTEM codes — CEA3 Premium IO naming proposal (≤30-char signal names)</h3>
  {reduced_sys_table}
</div>

<div class="card">
  <h2>② Function abbreviation guide</h2>
  <p style="color:var(--ts);font-size:12px;margin-bottom:4px">
    Construct the Function token by concatenating abbreviated CamelCase words.
    Use at most ~20 characters. Avoid articles, prepositions, and conjunctions.
  </p>
  {func_section}
</div>

<div class="card">
  <h2>③ POSITION codes</h2>
  {pos_table}
</div>

<div class="card">
  <h2>④ TYPE codes</h2>
  {type_table}
</div>

<!-- EXAMPLES -->
<div class="card">
  <h2>Compliant signal names</h2>
  <p style="color:var(--ts);font-size:12px;margin-bottom:4px">Real examples from the CEA3 naming reference.</p>
  {ok_table}
</div>

<div class="card">
  <h2>Special cases — still compliant</h2>
  <p style="color:var(--ts);font-size:12px;margin-bottom:8px">
    These signal names look irregular at first glance but satisfy the convention.
  </p>
  {special_table}
</div>

<div class="card">
  <h2>Non-compliant examples with proposed corrections</h2>
  <p style="color:var(--ts);font-size:12px;margin-bottom:8px">
    These are automatically detected by <code class="mono">validate_signal_naming.py</code>.
    Proposals are best-effort — the engineer must verify the SYSTEM code and Function token.
  </p>
  {bad_table}
</div>

<!-- VALIDATION -->
<div class="card">
  <h2>Automated validation</h2>
  <p style="color:var(--ts);font-size:12px;margin-bottom:14px">
    The validator runs automatically as <strong>Step 3</strong> of the build pipeline
    (<code class="mono">run.sh</code>). It can also be invoked standalone:
  </p>
  <div style="background:var(--raised);border:1px solid var(--b1);border-radius:var(--rm);padding:14px 18px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#e8ecf4">
    <span style="color:#5a6278"># Validate against auto-detected architecture JSON</span><br>
    python3 tools/scripts/validate_signal_naming.py --root .<br><br>
    <span style="color:#5a6278"># Exit with code 1 when violations found (CI gate)</span><br>
    python3 tools/scripts/validate_signal_naming.py --root . --fail-on-warn
  </div>
  <div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
    <div style="background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.2);border-radius:8px;padding:12px 14px">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#22c55e;margin-bottom:4px">One warning per signal</div>
      <div style="font-size:11px;color:var(--ts)">Duplicate uses of the same non-compliant name are grouped into a single warning</div>
    </div>
    <div style="background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.2);border-radius:8px;padding:12px 14px">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#60a5fa;margin-bottom:4px">Proposal included</div>
      <div style="font-size:11px;color:var(--ts)">Each warning includes a best-effort proposed name following the convention</div>
    </div>
    <div style="background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);border-radius:8px;padding:12px 14px">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#f59e0b;margin-bottom:4px">Infra signals exempt</div>
      <div style="font-size:11px;color:var(--ts)">CAN_H, CAN_L, CAN_GND, SUPPLY_*, GND_* are not subject to this rule</div>
    </div>
  </div>
</div>
"""


def main() -> int:
    p = standard_arg_parser("Generate signal naming convention reference page")
    args = p.parse_args()
    root = resolve_root(args.root)
    cfg  = load_config(None)

    out = get_output_file(root, cfg, "signal_naming_convention",
                          explicit=args.output, outdir=args.outdir)
    # Default to generated_doc/architecture_html/
    if not args.output and not args.outdir:
        out = root / "generated_doc" / "architecture_html" / "signal_naming_convention.html"

    body = build_body()
    page = html_page("Signal Naming Convention — E/E Architect Design", body)
    write_text(out, page)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
