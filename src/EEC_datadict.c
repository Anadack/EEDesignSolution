/**
 * @file    EEC_datadict.c
 * @brief   E/E Architect Design — Data dictionary export implementation.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */

#include "EEC_datadict.h"
#include "EEC_log.h"

#include <stdio.h>
#include <string.h>

/* ── Escaping helpers ──────────────────────────────────────────────────── */

static void dd_json_escape(FILE *f, const char *s)
{
    const unsigned char *p = (const unsigned char *)(s ? s : "");
    fputc('"', f);
    while (*p) {
        switch (*p) {
            case '\\': fputs("\\\\", f); break;
            case '"':  fputs("\\\"", f); break;
            case '\n': fputs("\\n", f); break;
            case '\r': fputs("\\r", f); break;
            case '\t': fputs("\\t", f); break;
            default:   fputc((int)*p, f); break;
        }
        ++p;
    }
    fputc('"', f);
}

static void dd_csv_field(FILE *f, const char *s)
{
    const char *p = s ? s : "";
    fputc('"', f);
    while (*p) {
        if (*p == '"') {
            fputc('"', f);
        }
        fputc(*p, f);
        ++p;
    }
    fputc('"', f);
}

static void dd_html_escape(FILE *f, const char *s)
{
    const char *p = s ? s : "";
    while (*p) {
        switch (*p) {
            case '&': fputs("&amp;", f); break;
            case '<': fputs("&lt;", f); break;
            case '>': fputs("&gt;", f); break;
            case '"': fputs("&quot;", f); break;
            default:  fputc(*p, f); break;
        }
        ++p;
    }
}

/* ── Physical-mapping lookup ───────────────────────────────────────────── */

static const EEC_EcuPin_t *dd_find_pin(const EEC_Architecture_t *arch,
                                       const EEC_Signal_t *sig,
                                       const EEC_Ecu_t **out_ecu)
{
    uint32_t i, j;
    if (out_ecu) {
        *out_ecu = NULL;
    }
    if (!arch || !sig) {
        return NULL;
    }
    for (i = 0U; i < arch->ecu_count; ++i) {
        const EEC_Ecu_t *ecu = arch->ecus[i];
        if (!ecu) {
            continue;
        }
        for (j = 0U; j < ecu->pin_count; ++j) {
            if (ecu->pins[j].connected_signal == sig) {
                if (out_ecu) {
                    *out_ecu = ecu;
                }
                return &ecu->pins[j];
            }
        }
    }
    return NULL;
}

static const char *dd_pin_iface(const EEC_EcuPin_t *pin)
{
    return EEC_Signal_InterfaceString((EEC_SignalInterface_t)pin->interface_type);
}

/* ═══════════════════════════════════════════════════════════════════════
 * JSON
 * ═══════════════════════════════════════════════════════════════════════ */

static void dd_json_logical(FILE *f, const EEC_Signal_t *sig)
{
    fprintf(f, "\"logical\": {\"type\": ");
    dd_json_escape(f, EEC_Signal_TypeString(sig->type));
    fprintf(f, ", \"interface\": ");
    dd_json_escape(f, EEC_Signal_InterfaceString(sig->interface_type));
    fprintf(f, ", \"unit\": ");
    dd_json_escape(f, EEC_Signal_UnitString(sig->unit));
    fprintf(f, ", \"min\": %g, \"max\": %g, \"resolution\": %g, \"scaling\": %g",
            (double)sig->min_value, (double)sig->max_value,
            (double)sig->resolution, (double)sig->scaling);
    fprintf(f, ", \"safety\": ");
    dd_json_escape(f, EEC_Safety_String(sig->safety));
    fprintf(f, ", \"priority\": ");
    dd_json_escape(f, EEC_Priority_String(sig->priority));
    fprintf(f, "}");
}

static void dd_json_physical(FILE *f, const EEC_Architecture_t *arch,
                             const EEC_Signal_t *sig)
{
    const EEC_Ecu_t *ecu = NULL;
    const EEC_EcuPin_t *pin = dd_find_pin(arch, sig, &ecu);

    fprintf(f, "\"physical\": {");
    if (pin && ecu) {
        fprintf(f, "\"mapped\": true, \"ecu\": ");
        dd_json_escape(f, ecu->name);
        fprintf(f, ", \"connector\": ");
        dd_json_escape(f, pin->connector_name);
        fprintf(f, ", \"pin\": %u, \"pin_name\": ", pin->physical_number);
        dd_json_escape(f, pin->name);
        fprintf(f, ", \"pin_role\": ");
        dd_json_escape(f, EEC_Pin_RoleString(pin->role));
        fprintf(f, ", \"pin_interface\": ");
        dd_json_escape(f, dd_pin_iface(pin));
    } else {
        fprintf(f, "\"mapped\": false");
    }
    fprintf(f, "}");
}

static void dd_json_can(FILE *f, const EEC_Swc_t *swc, const EEC_Signal_t *sig)
{
    uint32_t m, e, t;
    int first = 1;

    fprintf(f, "\"can\": [");
    for (m = 0U; m < swc->message_count; ++m) {
        const EEC_Message_t *msg = swc->messages[m];
        if (!msg) {
            continue;
        }
        for (e = 0U; e < msg->entry_count; ++e) {
            if (msg->entries[e].signal != sig) {
                continue;
            }
            if (msg->tx_count == 0U) {
                if (!first) { fprintf(f, ", "); }
                first = 0;
                fprintf(f, "{\"message\": ");
                dd_json_escape(f, msg->name);
                fprintf(f, ", \"frame_id\": %u, \"bus\": null, \"start_bit\": %u, \"length\": %u}",
                        msg->frame_id, msg->entries[e].start_bit, msg->entries[e].length);
            }
            for (t = 0U; t < msg->tx_count; ++t) {
                const EEC_Bus_t *bus = msg->tx_ports[t].bus;
                if (!first) { fprintf(f, ", "); }
                first = 0;
                fprintf(f, "{\"message\": ");
                dd_json_escape(f, msg->name);
                fprintf(f, ", \"frame_id\": %u, \"extended\": %s, \"bus\": ",
                        msg->frame_id, msg->is_extended ? "true" : "false");
                dd_json_escape(f, bus ? bus->name : "");
                fprintf(f, ", \"start_bit\": %u, \"length\": %u}",
                        msg->entries[e].start_bit, msg->entries[e].length);
            }
        }
    }
    fprintf(f, "]");
}

int EEC_Export_data_dictionary_json(const EEC_Architecture_t *arch, const char *filename)
{
    FILE *f;
    uint32_t i, c, d, p, s, v;
    int rows = 0;
    int sys_first = 1;

    if (!arch || !filename) {
        return -1;
    }
    f = fopen(filename, "w");
    if (!f) {
        return -1;
    }

    fprintf(f, "{\n  \"schema\": \"eec-data-dictionary-1.0\",\n  \"architecture\": ");
    dd_json_escape(f, arch->name);
    fprintf(f, ",\n  \"systems\": [");

    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *sys = arch->systems[i];
        int ds_first = 1;
        int sw_first = 1;
        if (!sys) {
            continue;
        }
        if (!sys_first) { fprintf(f, ","); }
        sys_first = 0;

        fprintf(f, "\n    {\n      \"name\": ");
        dd_json_escape(f, sys->name);
        fprintf(f, ", \"safety\": ");
        dd_json_escape(f, EEC_Safety_String(sys->safety));
        fprintf(f, ", \"location\": ");
        dd_json_escape(f, sys->location);
        fprintf(f, ",\n      \"device_signals\": [");

        for (c = 0U; c < sys->component_count; ++c) {
            const EEC_Component_t *comp = sys->components[c];
            if (!comp) {
                continue;
            }
            for (d = 0U; d < comp->sensor_count; ++d) {
                const EEC_Sensor_t *dev = comp->sensors[d];
                if (!dev) { continue; }
                for (p = 0U; p < dev->pin_count; ++p) {
                    const EEC_Signal_t *sig = dev->pins[p].signal;
                    if (!sig) { continue; }
                    if (!ds_first) { fprintf(f, ","); }
                    ds_first = 0;
                    fprintf(f, "\n        {\"signal\": ");
                    dd_json_escape(f, sig->name);
                    fprintf(f, ", \"clean_name\": ");
                    dd_json_escape(f, sig->clean_signal_name);
                    fprintf(f, ", \"device\": ");
                    dd_json_escape(f, dev->name);
                    fprintf(f, ", \"device_type\": \"sensor\", ");
                    dd_json_logical(f, sig);
                    fprintf(f, ", ");
                    dd_json_physical(f, arch, sig);
                    fprintf(f, "}");
                    ++rows;
                }
            }
            for (d = 0U; d < comp->actuator_count; ++d) {
                const EEC_Actuator_t *dev = comp->actuators[d];
                if (!dev) { continue; }
                for (p = 0U; p < dev->pin_count; ++p) {
                    const EEC_Signal_t *sig = dev->pins[p].signal;
                    if (!sig) { continue; }
                    if (!ds_first) { fprintf(f, ","); }
                    ds_first = 0;
                    fprintf(f, "\n        {\"signal\": ");
                    dd_json_escape(f, sig->name);
                    fprintf(f, ", \"clean_name\": ");
                    dd_json_escape(f, sig->clean_signal_name);
                    fprintf(f, ", \"device\": ");
                    dd_json_escape(f, dev->name);
                    fprintf(f, ", \"device_type\": \"actuator\", ");
                    dd_json_logical(f, sig);
                    fprintf(f, ", ");
                    dd_json_physical(f, arch, sig);
                    fprintf(f, "}");
                    ++rows;
                }
            }
        }
        fprintf(f, ds_first ? "]," : "\n      ],");

        fprintf(f, "\n      \"software_signals\": [");
        for (s = 0U; s < sys->swc_count; ++s) {
            const EEC_Swc_t *swc = sys->swcs[s];
            if (!swc) { continue; }
            for (v = 0U; v < swc->variable_count; ++v) {
                const EEC_Signal_t *sig = swc->variables[v];
                if (!sig) { continue; }
                if (!sw_first) { fprintf(f, ","); }
                sw_first = 0;
                fprintf(f, "\n        {\"signal\": ");
                dd_json_escape(f, sig->name);
                fprintf(f, ", \"swc\": ");
                dd_json_escape(f, swc->name);
                fprintf(f, ", \"allocated_ecu\": ");
                dd_json_escape(f, swc->allocated_ecu ? swc->allocated_ecu->name : "");
                fprintf(f, ", ");
                dd_json_logical(f, sig);
                fprintf(f, ", ");
                dd_json_can(f, swc, sig);
                fprintf(f, "}");
                ++rows;
            }
        }
        fprintf(f, sw_first ? "]" : "\n      ]");
        fprintf(f, "\n    }");
    }

    fprintf(f, "\n  ]\n}\n");
    fclose(f);
    EEC_Log_Printf(EEC_LOG_INFO, "Data dictionary JSON: %d row(s) → %s", rows, filename);
    return rows;
}

/* ═══════════════════════════════════════════════════════════════════════
 * CSV
 * ═══════════════════════════════════════════════════════════════════════ */

static void dd_csv_row(FILE *f, const EEC_Architecture_t *arch,
                       const char *system, const char *scope,
                       const char *owner, const char *device_type,
                       const EEC_Signal_t *sig,
                       const EEC_Swc_t *swc)
{
    const EEC_Ecu_t *ecu = NULL;
    const EEC_EcuPin_t *pin = dd_find_pin(arch, sig, &ecu);
    char range[64];
    char can[200];

    (void)snprintf(range, sizeof(range), "%g..%g",
                   (double)sig->min_value, (double)sig->max_value);

    can[0] = '\0';
    if (swc) {
        uint32_t m, e;
        for (m = 0U; m < swc->message_count && can[0] == '\0'; ++m) {
            const EEC_Message_t *msg = swc->messages[m];
            if (!msg) { continue; }
            for (e = 0U; e < msg->entry_count; ++e) {
                if (msg->entries[e].signal == sig) {
                    const EEC_Bus_t *bus = (msg->tx_count > 0U) ? msg->tx_ports[0].bus : NULL;
                    (void)snprintf(can, sizeof(can), "%s@0x%X on %s [%u|%u]",
                                   msg->name, msg->frame_id,
                                   bus ? bus->name : "(no bus)",
                                   msg->entries[e].start_bit, msg->entries[e].length);
                    break;
                }
            }
        }
    }

    dd_csv_field(f, system);          fputc(',', f);
    dd_csv_field(f, scope);           fputc(',', f);
    dd_csv_field(f, owner);           fputc(',', f);
    dd_csv_field(f, device_type);     fputc(',', f);
    dd_csv_field(f, sig->name);       fputc(',', f);
    dd_csv_field(f, sig->clean_signal_name); fputc(',', f);
    dd_csv_field(f, EEC_Signal_TypeString(sig->type)); fputc(',', f);
    dd_csv_field(f, EEC_Signal_InterfaceString(sig->interface_type)); fputc(',', f);
    dd_csv_field(f, EEC_Signal_UnitString(sig->unit)); fputc(',', f);
    dd_csv_field(f, range);           fputc(',', f);
    dd_csv_field(f, EEC_Safety_String(sig->safety));   fputc(',', f);
    dd_csv_field(f, EEC_Priority_String(sig->priority)); fputc(',', f);
    dd_csv_field(f, (pin && ecu) ? ecu->name : "");    fputc(',', f);
    dd_csv_field(f, pin ? pin->connector_name : "");   fputc(',', f);
    if (pin) { fprintf(f, "%u", pin->physical_number); }
    fputc(',', f);
    dd_csv_field(f, pin ? EEC_Pin_RoleString(pin->role) : "");    fputc(',', f);
    dd_csv_field(f, pin ? dd_pin_iface(pin) : "");     fputc(',', f);
    dd_csv_field(f, can);
    fputc('\n', f);
}

int EEC_Export_data_dictionary_csv(const EEC_Architecture_t *arch, const char *filename)
{
    FILE *f;
    uint32_t i, c, d, p, s, v;
    int rows = 0;

    if (!arch || !filename) {
        return -1;
    }
    f = fopen(filename, "w");
    if (!f) {
        return -1;
    }

    fprintf(f, "System,Scope,Owner,DeviceType,Signal,CleanName,Type,Interface,Unit,"
               "Range,Safety,Priority,ECU,Connector,Pin,PinRole,PinInterface,CAN\n");

    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *sys = arch->systems[i];
        if (!sys) { continue; }

        for (c = 0U; c < sys->component_count; ++c) {
            const EEC_Component_t *comp = sys->components[c];
            if (!comp) { continue; }
            for (d = 0U; d < comp->sensor_count; ++d) {
                const EEC_Sensor_t *dev = comp->sensors[d];
                if (!dev) { continue; }
                for (p = 0U; p < dev->pin_count; ++p) {
                    if (!dev->pins[p].signal) { continue; }
                    dd_csv_row(f, arch, sys->name, "device", dev->name, "sensor",
                               dev->pins[p].signal, NULL);
                    ++rows;
                }
            }
            for (d = 0U; d < comp->actuator_count; ++d) {
                const EEC_Actuator_t *dev = comp->actuators[d];
                if (!dev) { continue; }
                for (p = 0U; p < dev->pin_count; ++p) {
                    if (!dev->pins[p].signal) { continue; }
                    dd_csv_row(f, arch, sys->name, "device", dev->name, "actuator",
                               dev->pins[p].signal, NULL);
                    ++rows;
                }
            }
        }
        for (s = 0U; s < sys->swc_count; ++s) {
            const EEC_Swc_t *swc = sys->swcs[s];
            if (!swc) { continue; }
            for (v = 0U; v < swc->variable_count; ++v) {
                if (!swc->variables[v]) { continue; }
                dd_csv_row(f, arch, sys->name, "software", swc->name, "swc_variable",
                           swc->variables[v], swc);
                ++rows;
            }
        }
    }

    fclose(f);
    EEC_Log_Printf(EEC_LOG_INFO, "Data dictionary CSV: %d row(s) → %s", rows, filename);
    return rows;
}

/* ═══════════════════════════════════════════════════════════════════════
 * HTML
 * ═══════════════════════════════════════════════════════════════════════ */

static void dd_html_signal_row(FILE *f, const EEC_Architecture_t *arch,
                               const char *scope, const char *owner,
                               const EEC_Signal_t *sig, const EEC_Swc_t *swc)
{
    const EEC_Ecu_t *ecu = NULL;
    const EEC_EcuPin_t *pin = dd_find_pin(arch, sig, &ecu);

    fprintf(f, "<tr><td class=\"sig\">");
    dd_html_escape(f, sig->name);
    if (sig->clean_signal_name[0] != '\0') {
        fprintf(f, "<span class=\"clean\">");
        dd_html_escape(f, sig->clean_signal_name);
        fprintf(f, "</span>");
    }
    fprintf(f, "</td><td><span class=\"tag %s\">%s</span></td><td>",
            (strcmp(scope, "software") == 0) ? "sw" : "hw", scope);
    dd_html_escape(f, owner);
    fprintf(f, "</td><td>");
    dd_html_escape(f, EEC_Signal_InterfaceString(sig->interface_type));
    fprintf(f, "</td><td>");
    dd_html_escape(f, EEC_Signal_TypeString(sig->type));
    fprintf(f, "</td><td>");
    dd_html_escape(f, EEC_Signal_UnitString(sig->unit));
    fprintf(f, "</td><td>%g..%g</td><td>",
            (double)sig->min_value, (double)sig->max_value);
    dd_html_escape(f, EEC_Safety_String(sig->safety));
    fprintf(f, "</td><td class=\"phys\">");
    if (pin && ecu) {
        dd_html_escape(f, ecu->name);
        fprintf(f, " · ");
        dd_html_escape(f, pin->connector_name);
        fprintf(f, " pin %u (", pin->physical_number);
        dd_html_escape(f, EEC_Pin_RoleString(pin->role));
        fprintf(f, ")");
    } else {
        fprintf(f, "<span class=\"muted\">—</span>");
    }
    fprintf(f, "</td><td class=\"can\">");
    if (swc) {
        uint32_t m, e;
        int printed = 0;
        for (m = 0U; m < swc->message_count; ++m) {
            const EEC_Message_t *msg = swc->messages[m];
            if (!msg) { continue; }
            for (e = 0U; e < msg->entry_count; ++e) {
                if (msg->entries[e].signal == sig) {
                    const EEC_Bus_t *bus = (msg->tx_count > 0U) ? msg->tx_ports[0].bus : NULL;
                    dd_html_escape(f, msg->name);
                    fprintf(f, " <span class=\"muted\">0x%X @ ", msg->frame_id);
                    dd_html_escape(f, bus ? bus->name : "(no bus)");
                    fprintf(f, " [%u|%u]</span>",
                            msg->entries[e].start_bit, msg->entries[e].length);
                    printed = 1;
                }
            }
        }
        if (!printed) {
            fprintf(f, "<span class=\"muted\">—</span>");
        }
    } else {
        fprintf(f, "<span class=\"muted\">—</span>");
    }
    fprintf(f, "</td></tr>\n");
}

int EEC_Export_data_dictionary_html(const EEC_Architecture_t *arch, const char *filename)
{
    FILE *f;
    uint32_t i, c, d, p, s, v;
    int rows = 0;

    if (!arch || !filename) {
        return -1;
    }
    f = fopen(filename, "w");
    if (!f) {
        return -1;
    }

    fprintf(f,
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>EE Architect Design — Data Dictionary</title>\n<style>\n"
        ":root{--bg:#0d1117;--surface:#161b22;--surface2:#1c2333;--border:#30363d;"
        "--text:#e6edf3;--muted:#8b949e;--accent:#2ee6ff;--sw:#bc8cff;--hw:#3fb950}\n"
        "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);"
        "font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}\n"
        "header{padding:22px 28px;border-bottom:1px solid var(--border);"
        "background:linear-gradient(180deg,#111722,#0d1117)}\n"
        "h1{margin:0;font-size:1.35rem}.sub{color:var(--muted);font-size:.82rem;margin-top:4px}\n"
        ".wrap{padding:20px 28px}section{margin-bottom:26px}\n"
        "h2{font-size:1rem;margin:0 0 8px;padding:8px 12px;background:var(--surface2);"
        "border:1px solid var(--border);border-radius:8px}\n"
        "h2 .meta{color:var(--muted);font-weight:400;font-size:.78rem;margin-left:8px}\n"
        "table{width:100%%;border-collapse:collapse;font-size:.82rem}\n"
        "th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--border);vertical-align:top}\n"
        "th{color:var(--muted);font-weight:600;text-transform:uppercase;font-size:.68rem;letter-spacing:.04em}\n"
        "tr:hover td{background:var(--surface)}\n"
        ".sig{font-weight:600}.sig .clean{display:block;color:var(--muted);font-size:.72rem;"
        "font-family:ui-monospace,Consolas,monospace}\n"
        ".tag{display:inline-block;padding:1px 7px;border-radius:20px;font-size:.68rem;font-weight:700}\n"
        ".tag.hw{background:rgba(63,185,80,.16);color:var(--hw)}\n"
        ".tag.sw{background:rgba(188,140,255,.16);color:var(--sw)}\n"
        ".phys{font-family:ui-monospace,Consolas,monospace;font-size:.76rem}\n"
        ".can{font-size:.76rem}.muted{color:var(--muted)}\n"
        "</style></head>\n<body>\n<header><h1>Data Dictionary</h1>"
        "<div class=\"sub\">Logical &amp; physical signals grouped by module / system — ");
    dd_html_escape(f, arch->name);
    fprintf(f, "</div></header>\n<div class=\"wrap\">\n");

    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *sys = arch->systems[i];
        int sys_rows = 0;
        if (!sys) { continue; }

        fprintf(f, "<section><h2>");
        dd_html_escape(f, sys->name);
        fprintf(f, "<span class=\"meta\">safety ");
        dd_html_escape(f, EEC_Safety_String(sys->safety));
        if (sys->location[0] != '\0') {
            fprintf(f, " · ");
            dd_html_escape(f, sys->location);
        }
        fprintf(f, "</span></h2>\n<table><thead><tr>"
                   "<th>Signal</th><th>Scope</th><th>Owner</th><th>Interface</th>"
                   "<th>Type</th><th>Unit</th><th>Range</th><th>Safety</th>"
                   "<th>Physical (ECU · pin)</th><th>CAN (msg @ bus)</th>"
                   "</tr></thead><tbody>\n");

        for (c = 0U; c < sys->component_count; ++c) {
            const EEC_Component_t *comp = sys->components[c];
            if (!comp) { continue; }
            for (d = 0U; d < comp->sensor_count; ++d) {
                const EEC_Sensor_t *dev = comp->sensors[d];
                if (!dev) { continue; }
                for (p = 0U; p < dev->pin_count; ++p) {
                    if (!dev->pins[p].signal) { continue; }
                    dd_html_signal_row(f, arch, "device", dev->name,
                                       dev->pins[p].signal, NULL);
                    ++rows; ++sys_rows;
                }
            }
            for (d = 0U; d < comp->actuator_count; ++d) {
                const EEC_Actuator_t *dev = comp->actuators[d];
                if (!dev) { continue; }
                for (p = 0U; p < dev->pin_count; ++p) {
                    if (!dev->pins[p].signal) { continue; }
                    dd_html_signal_row(f, arch, "device", dev->name,
                                       dev->pins[p].signal, NULL);
                    ++rows; ++sys_rows;
                }
            }
        }
        for (s = 0U; s < sys->swc_count; ++s) {
            const EEC_Swc_t *swc = sys->swcs[s];
            if (!swc) { continue; }
            for (v = 0U; v < swc->variable_count; ++v) {
                if (!swc->variables[v]) { continue; }
                dd_html_signal_row(f, arch, "software", swc->name,
                                   swc->variables[v], swc);
                ++rows; ++sys_rows;
            }
        }

        if (sys_rows == 0) {
            fprintf(f, "<tr><td colspan=\"10\" class=\"muted\">No signals</td></tr>\n");
        }
        fprintf(f, "</tbody></table></section>\n");
    }

    fprintf(f, "</div>\n</body></html>\n");
    fclose(f);
    EEC_Log_Printf(EEC_LOG_INFO, "Data dictionary HTML: %d row(s) → %s", rows, filename);
    return rows;
}
