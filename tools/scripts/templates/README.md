# Vendored HTML templates

Base HTML templates consumed by documentation generators, kept here
(portable, relative to the scripts) instead of an absolute author-machine
path:

- `Network_BUS_Backbone_Template.html` → `generate_network_bus_backbone_html.py`
- `ECU_Pinout_MultiECU_Config_Validation_Template.html` → `generate_ecu_v3_config_validation_html.py`
- `ecu_dataflow_from_json_template.html` → `generate_ecu_dataflow_from_json_html.py`

The first two are first-cut (v1) implementations written to close a gap
where these generators always printed `[SKIP] ... vendored template not
found` (the originals referenced were never committed to the repo, only an
absolute path on one author's machine). They satisfy the exact contract each
generator script expects — including, for the ECU pinout template, an
in-template comment-boundary marker that the generator itself needed a
matching one-line fix for (see `generate_ecu_v3_config_validation_html.py`,
the `zone_end` marker) — and render a genuinely working, if visually simpler,
view. They are not a recreation of any prior/original template.

If a template is absent the generator prints `[SKIP] ...` and exits 0 so the
documentation suite still completes; pass `--template <path>` to point a
generator at a different file. Do NOT reference paths outside the repository.
