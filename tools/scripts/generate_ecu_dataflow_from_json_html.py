#!/usr/bin/env python3
"""ECU Dataflow Architecture Template — exact reference template, real export data.

This page is the hand-authored "ECU Dataflow Architecture Template" reference
file (templates/ecu_dataflow_from_json_template.html) reproduced byte-for-byte:
same CSS, same DOM, same client-side JS (search, bus/interface filters, click-
to-inspect ECU/bus drawer, free-port toggle, Load JSON / Export JSON / Print).
Nothing about the design is reskinned or ported — unlike the other dataflow
report, this one is not adapted to the site theme.

The only part regenerated is the embedded `<script id="default-data">`
payload: instead of the template's own bundled sample, it ships the real
physical architecture export (ECUs with full pin/connector detail, buses,
systems/devices), so opening the file immediately renders this architecture.
The template's own "Load JSON" button still works unmodified, so a viewer can
swap in any other exported_physical_architecture.json by hand.
"""
from __future__ import annotations
from eec_archdoc_common import *

_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "ecu_dataflow_from_json_template.html"
_DEFAULT_DATA_RE = re.compile(
    r'(<script type="application/json" id="default-data">)(.*?)(</script>)',
    re.DOTALL,
)
_FILE_NAME_HINT_RE = re.compile(
    r'(<div class="file-name" id="fileName">)[^<]*(</div>)'
)


def main() -> int:
    parser = make_argparser(
        "Generate the ECU Dataflow Architecture Template page (exact reference template) "
        "populated with the real physical architecture export.",
        input_help="Physical architecture export JSON.",
    )
    parser.set_defaults(prefer_physical=True)
    args = parser.parse_args()
    root, cfg, arch, arch_path, outdir = cli_context(args)

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    payload = json.dumps({"architecture": arch}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page, n = _DEFAULT_DATA_RE.subn(lambda m: m.group(1) + payload + m.group(3), template, count=1)
    if n != 1:
        raise RuntimeError(f"{_TEMPLATE_PATH}: <script id=\"default-data\"> tag not found, template may have changed")

    n_ecus, n_buses = len(arch.get("ecus", [])), len(arch.get("buses", []))
    hint = f"Generated from {arch_path.name} — {n_ecus} ECU{'s' if n_ecus != 1 else ''}, {n_buses} bus{'es' if n_buses != 1 else ''}."
    page, _ = _FILE_NAME_HINT_RE.subn(lambda m: m.group(1) + html.escape(hint) + m.group(2), page, count=1)

    out = outdir / "ecu_dataflow_from_json.html"
    out.write_text(page, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
