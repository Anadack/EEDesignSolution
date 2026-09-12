# Vendored HTML templates

Two generators consume a base HTML template that must live here (portable,
relative to the scripts) instead of an absolute author-machine path:

- `Network_BUS_Backbone_Template.html`      → generate_network_bus_backbone_html.py
- `ECU_Pinout_MultiECU_Config_Validation_Template.html` → generate_ecu_v3_config_validation_html.py

If a template is absent the generator prints `[SKIP] ...` and exits 0 so the
documentation suite still completes. Add the template here (or pass
`--template <path>`) to enable that document. Do NOT reference paths outside
the repository.
