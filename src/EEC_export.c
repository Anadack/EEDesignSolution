/*
 * @file    EEC_export.c
 * @brief   E/E Architect Design — JSON and HTML export implementation.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#include "EEC_export.h"
#include "EEC_log.h"
#include "EEC_agco.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/** @brief Convert a capability mask into one representative interface type for display. */
static EEC_SignalInterface_t signal_interface_from_capability_mask(uint32_t supported_capability_mask)
{
    if (supported_capability_mask & (1U << 3)) return EEC_SIGNAL_INTERFACE_CAN;
    if (supported_capability_mask & (1U << 6)) return EEC_SIGNAL_INTERFACE_ETHERNET;
    if (supported_capability_mask & (1U << 11)) return EEC_SIGNAL_INTERFACE_FLEXRAY;
    if (supported_capability_mask & (1U << 5)) return EEC_SIGNAL_INTERFACE_SENT;
    if (supported_capability_mask & (1U << 4)) return EEC_SIGNAL_INTERFACE_LIN;
    if (supported_capability_mask & (1U << 12)) return EEC_SIGNAL_INTERFACE_CURRENT;
    if (supported_capability_mask & (1U << 10)) return EEC_SIGNAL_INTERFACE_FREQUENCY;
    if (supported_capability_mask & (1U << 9)) return EEC_SIGNAL_INTERFACE_RESISTANCE;
    if (supported_capability_mask & (1U << 2)) return EEC_SIGNAL_INTERFACE_PWM;
    if (supported_capability_mask & (1U << 1)) return EEC_SIGNAL_INTERFACE_ANALOG;
    if (supported_capability_mask & (1U << 0)) return EEC_SIGNAL_INTERFACE_DIGITAL;
    if (supported_capability_mask & (1U << 7)) return EEC_SIGNAL_INTERFACE_POWER;
    if (supported_capability_mask & (1U << 8)) return EEC_SIGNAL_INTERFACE_GROUND;
    return EEC_SIGNAL_INTERFACE_RESERVED;
}

/** @brief Escape a JSON string into a file. */
static void json_escape(FILE *f, const char *s)
{
    const unsigned char *p = (const unsigned char *)(s ? s : "");
    fputc('"', f);
    while (*p) {
        switch (*p) {
            case '\\': fputs("\\\\", f); break;

/*
 * ──────────────────────────────────────────────────────────────────────────────
 *  E/E Architect Design — JSON and HTML Export Implementation
 *
 *  This file implements the export logic for the E/E Architect Design framework,
 *  supporting both JSON and HTML output formats. It provides routines for
 *  serializing architecture, device, signal, and mapping data, as well as
 *  helpers for capability mask conversion and AGCO-specific export features.
 *
 *  Major responsibilities:
 *    - Export of architecture and library objects to JSON and HTML
 *    - Capability mask to interface type conversion for display
 *    - String escaping and formatting for safe output
 *    - AGCO extensions for custom export requirements
 *
 *  The export module ensures that all output is standards-compliant and
 *  suitable for downstream tools and documentation.
 * ──────────────────────────────────────────────────────────────────────────────
 */

/**
 * @brief Convert a capability mask into one representative interface type for display.
 *
 * Examines the bitmask of supported capabilities and returns the most
 * representative EEC_SignalInterface_t for display or export purposes.
 *
 * @param supported_capability_mask Bitmask of supported capabilities.
 * @return Representative interface type for display.
 */
            case '"': fputs("\\\"", f); break;
            case '\n': fputs("\\n", f); break;
            case '\r': fputs("\\r", f); break;
            case '\t': fputs("\\t", f); break;
            default: fputc(*p, f); break;
        }
        ++p;
    }
    fputc('"', f);
}

/** @brief Write one pipe-separated string as a JSON array. */
static void write_pipe_text_as_array(FILE *f, const char *text)
{
    char buffer[256];
    char *token;
    char *next;
    int first = 1;
    if (!text || !text[0]) {
        fprintf(f, "[]");
        return;
    }

    strncpy(buffer, text, sizeof(buffer) - 1U);
    buffer[sizeof(buffer) - 1U] = '\0';
    fprintf(f, "[");
    token = buffer;
    while (token && token[0] != '\0') {
        next = strchr(token, '|');
        if (next) {
            *next = '\0';
        }
        if (!first) {
            fprintf(f, ", ");
        }
        json_escape(f, token);
        first = 0;
        token = next ? (next + 1) : NULL;
    }
    fprintf(f, "]");
}

/** @brief Write diagnostics bits as JSON text labels. */
static void write_diag_array(FILE *f, uint32_t diag)
{
    int first = 1;
    struct { uint32_t bit; const char *label; } map[] = {
        { EEC_DIAG_OPEN_LOAD, "Open Load" },
        { EEC_DIAG_SHORT_GND, "Short GND" },
        { EEC_DIAG_SHORT_BAT, "Short BAT" },
        { EEC_DIAG_RANGE_CHECK, "Range Check" },
        { EEC_DIAG_OVERCURRENT, "Overcurrent" },
        { EEC_DIAG_THERMAL_WARN, "Thermal Warn" },
        { EEC_DIAG_LINE_BREAK, "Line Break" },
        { EEC_DIAG_PLAUSIBILITY, "Plausibility" }
    };
    size_t i;
    fprintf(f, "[");
    for (i = 0U; i < sizeof(map) / sizeof(map[0]); ++i) {
        if (diag & map[i].bit) {
            if (!first) {
                fprintf(f, ", ");
            }
            json_escape(f, map[i].label);
            first = 0;
        }
    }
    fprintf(f, "]");
}

/** @brief Write electrical capability/requirement flags as a JSON array. */
static void write_elec_array(FILE *f, uint32_t flags)
{
    int first = 1;
    struct { uint32_t bit; const char *label; } map[] = {
        { EEC_ELEC_PULLUP, "PULLUP" },
        { EEC_ELEC_PULLDOWN, "PULLDOWN" },
        { EEC_ELEC_HIGH_SIDE, "HIGH_SIDE" },
        { EEC_ELEC_LOW_SIDE, "LOW_SIDE" },
        { EEC_ELEC_PUSH_PULL, "PUSH_PULL" },
        { EEC_ELEC_CURRENT_SENSE, "CURRENT_SENSE" },
        { EEC_ELEC_VOLTAGE_IN, "VOLTAGE_IN" },
        { EEC_ELEC_DIFFERENTIAL, "DIFFERENTIAL" }
    };
    size_t i;
    fprintf(f, "[");
    for (i = 0U; i < sizeof(map) / sizeof(map[0]); ++i) {
        if (flags & map[i].bit) {
            if (!first) fprintf(f, ", ");
            json_escape(f, map[i].label);
            first = 0;
        }
    }
    fprintf(f, "]");
}

static bool is_first_connector_occurrence(const EEC_Ecu_t *ecu, uint32_t pin_index)
{
    uint32_t previous_index;
    const char *connector_name;

    if (!ecu || pin_index >= ecu->pin_count) {
        return false;
    }

    connector_name = ecu->pins[pin_index].connector_name;
    for (previous_index = 0U; previous_index < pin_index; ++previous_index) {
        if (strcmp(ecu->pins[previous_index].connector_name, connector_name) == 0) {
            return false;
        }
    }
    return true;
}

static void count_connector_pins(const EEC_Ecu_t *ecu, const char *connector_name, uint32_t *total_pins, uint32_t *allocated_pins)
{
    uint32_t pin_index;

    if (total_pins) {
        *total_pins = 0U;
    }
    if (allocated_pins) {
        *allocated_pins = 0U;
    }
    if (!ecu || !connector_name) {
        return;
    }

    for (pin_index = 0U; pin_index < ecu->pin_count; ++pin_index) {
        const EEC_EcuPin_t *pin = &ecu->pins[pin_index];
        if (strcmp(pin->connector_name, connector_name) != 0) {
            continue;
        }
        if (total_pins) {
            ++(*total_pins);
        }
        if (allocated_pins && pin->is_occupied) {
            ++(*allocated_pins);
        }
    }
}

static void write_allocation_summary(FILE *f, uint32_t total_pins, uint32_t allocated_pins, int indent)
{
    uint32_t free_pins = (allocated_pins <= total_pins) ? (total_pins - allocated_pins) : 0U;
    double allocation_percent = (total_pins > 0U)
        ? (100.0 * (double)allocated_pins) / (double)total_pins
        : 0.0;

    fprintf(f,
            "%*s\"allocation_summary\": { \"total_pins\": %u, \"allocated_pins\": %u, \"free_pins\": %u, \"allocation_percent\": %.1f }",
            indent,
            "",
            total_pins,
            allocated_pins,
            free_pins,
            allocation_percent);
}

static void write_connector_summary(FILE *f, const EEC_Ecu_t *ecu)
{
    uint32_t pin_index;
    bool first_connector = true;

    fprintf(f, "        \"connectors\": [\n");
    for (pin_index = 0U; pin_index < ecu->pin_count; ++pin_index) {
        uint32_t connector_total_pins;
        uint32_t connector_allocated_pins;

        if (!is_first_connector_occurrence(ecu, pin_index)) {
            continue;
        }

        count_connector_pins(
            ecu,
            ecu->pins[pin_index].connector_name,
            &connector_total_pins,
            &connector_allocated_pins
        );

        if (!first_connector) {
            fprintf(f, ",\n");
        }
        fprintf(f, "          { \"name\": ");
        json_escape(f, ecu->pins[pin_index].connector_name);
        fprintf(f, ", ");
        write_allocation_summary(f, connector_total_pins, connector_allocated_pins, 0);
        fprintf(f, " }");
        first_connector = false;
    }
    fprintf(f, "\n        ]");
}

static void write_system_member_json(FILE *f,
                                     const char *name,
                                     const char *part_number,
                                     EEC_DeviceType_t type,
                                     EEC_ObjectPriority_t priority,
                                     EEC_SafetyClass_t safety,
                                     const EEC_DevicePin_t *pins,
                                     uint32_t pin_count,
                                     const EEC_Connector_t *connectors,
                                     uint32_t connector_count,
                                     bool trailing_comma)
{
    uint32_t k;
    fprintf(f, "          {\n            \"name\": ");
    json_escape(f, name);
    fprintf(f, ",\n            \"part_number\": ");
    json_escape(f, part_number);
    fprintf(f, ",\n            \"type\": ");
    json_escape(f, EEC_Device_TypeString(type));
    fprintf(f, ",\n            \"priority\": ");
    json_escape(f, EEC_Priority_String(priority));
    fprintf(f, ",\n            \"safety\": ");
    json_escape(f, EEC_Safety_String(safety));
    fprintf(f, ",\n            \"pins\": [\n");
    for (k = 0U; k < pin_count; ++k) {
        const EEC_DevicePin_t *pin = &pins[k];
        fprintf(f, "              { \"number\": %u, \"name\": ", pin->number);
        json_escape(f, pin->name);
        fprintf(f, ", \"role\": ");
        json_escape(f, EEC_Pin_RoleString(pin->role));
        fprintf(f, ", \"electrical_requirement\": %u", pin->electrical_requirement);
            fprintf(f, ", \"interface_type\": ");
            json_escape(f, EEC_Signal_InterfaceString((EEC_SignalInterface_t)pin->interface_type));
        fprintf(f, ", \"signal\": ");
        if (pin->signal) {
            fprintf(f, "{ \"name\": ");
            json_escape(f, pin->signal->name);
            fprintf(f, ", \"type\": ");
            json_escape(f, EEC_Signal_TypeString(pin->signal->type));
            fprintf(f, ", \"interface\": ");
            json_escape(f, EEC_Signal_InterfaceString(pin->signal->interface_type));
            fprintf(f, ", \"unit\": ");
            json_escape(f, EEC_Signal_UnitString(pin->signal->unit));
            fprintf(f, ", \"priority\": ");
            json_escape(f, EEC_Priority_String(pin->signal->priority));
            fprintf(f, ", \"safety\": ");
            json_escape(f, EEC_Safety_String(pin->signal->safety));
            fprintf(f, ", \"min\": %g, \"max\": %g, \"resolution\": %g, \"scaling\": %g",
                    (double)pin->signal->min_value,
                    (double)pin->signal->max_value,
                    (double)pin->signal->resolution,
                    (double)pin->signal->scaling);
            fprintf(f, ", \"is_mapped\": %s", pin->signal->is_mapped ? "true" : "false");
            if (pin->signal->clean_signal_name[0] != '\0') {
                fprintf(f, ", \"clean_name\": ");
                json_escape(f, pin->signal->clean_signal_name);
                fprintf(f, ", \"naming_convention\": { \"system_code\": ");
                json_escape(f, pin->signal->system_code);
                fprintf(f, ", \"function_name\": ");
                json_escape(f, pin->signal->function_name);
                fprintf(f, ", \"position_index\": ");
                json_escape(f, pin->signal->position_index);
                fprintf(f, ", \"type_code\": ");
                json_escape(f, pin->signal->type_code);
                fprintf(f, ", \"is_auto_named\": %s }", pin->signal->is_auto_named ? "true" : "false");
            }
            fprintf(f, " }");
        } else {
            fprintf(f, "null");
        }
        fprintf(f, " }%s\n", (k + 1U < pin_count) ? "," : "");
    }
    fprintf(f, "            ]");
    if (connector_count > 0U) {
        fprintf(f, ",\n            \"connectors\": [\n");
        for (k = 0U; k < connector_count; ++k) {
            const EEC_Connector_t *con = &connectors[k];
            fprintf(f, "              { \"name\": ");
            json_escape(f, con->name);
            fprintf(f, ", \"part_number\": ");
            json_escape(f, con->part_number);
            fprintf(f, ", \"family\": ");
            json_escape(f, EEC_Connector_FamilyString(con->family));
            fprintf(f, ", \"gender\": ");
            json_escape(f, EEC_Connector_GenderString(con->gender));
            fprintf(f, ", \"total_cavities\": %u", con->total_cavities);
            fprintf(f, ", \"max_pin_number\": %u", con->max_pin_number);
            fprintf(f, ", \"sealed\": %s", con->sealed ? "true" : "false");
            if (con->ip_rating[0]) { fprintf(f, ", \"ip_rating\": "); json_escape(f, con->ip_rating); }
            if (con->color[0]) { fprintf(f, ", \"color\": "); json_escape(f, con->color); }
            if (con->mounting[0]) { fprintf(f, ", \"mounting\": "); json_escape(f, con->mounting); }
            if (con->rated_voltage > 0.0f) fprintf(f, ", \"rated_voltage\": %.1f", (double)con->rated_voltage);
            if (con->rated_current > 0.0f) fprintf(f, ", \"rated_current\": %.1f", (double)con->rated_current);
            fprintf(f, ", \"temperature_min\": %.1f, \"temperature_max\": %.1f", (double)con->temperature_min, (double)con->temperature_max);
            fprintf(f, " }%s\n", (k + 1U < connector_count) ? "," : "");
        }
        fprintf(f, "            ]");
    }
    fprintf(f, "\n          }%s\n", trailing_comma ? "," : "");
}

int EEC_Export_architecture_json(const EEC_Architecture_t *arch, const char *filename)
{
    uint32_t i, j, k;
    uint32_t total_pins = 0U;
    uint32_t allocated_pins = 0U;
    FILE *f;
    if (!arch || !filename) {
        return -1;
    }
    f = fopen(filename, "w");
    if (!f) {
        return -1;
    }

    fprintf(f, "{\n  \"architecture\": {\n    \"name\": ");
    json_escape(f, arch->name);
    fprintf(f, ",\n    \"part_number\": ");
    json_escape(f, arch->part_number);
    fprintf(f, ",\n    \"priority\": ");
    json_escape(f, EEC_Priority_String(arch->priority));
    fprintf(f, ",\n    \"safety\": ");
    json_escape(f, EEC_Safety_String(arch->safety));
    fprintf(f, ",\n    \"ecus\": [\n");

    for (i = 0U; i < arch->ecu_count; ++i) {
        const EEC_Ecu_t *ecu = arch->ecus[i];
        uint32_t ecu_allocated_pins = 0U;

        for (j = 0U; j < ecu->pin_count; ++j) {
            if (ecu->pins[j].is_occupied) {
                ++ecu_allocated_pins;
            }
        }
        total_pins += ecu->pin_count;
        allocated_pins += ecu_allocated_pins;

        fprintf(f, "      {\n        \"name\": ");
        json_escape(f, ecu->name);
        fprintf(f, ",\n        \"part_number\": ");
        json_escape(f, ecu->part_number);
        fprintf(f, ",\n        \"variant\": ");
        json_escape(f, ecu->variant);
        fprintf(f, ",\n        \"priority\": ");
        json_escape(f, EEC_Priority_String(ecu->priority));
        fprintf(f, ",\n        \"safety\": ");
        json_escape(f, EEC_Safety_String(ecu->safety));
        fprintf(f, ",\n        \"location\": ");
        json_escape(f, ecu->location);
        fprintf(f, ",\n        \"can_addresses\": [");
        for (j = 0U; j < ecu->can_address_count; ++j) {
            if (j) fprintf(f, ", ");
            fprintf(f, "\"0x%02X\"", ecu->can_addresses[j]);
        }
        fprintf(f, "],\n        \"pins\": [\n");

        for (j = 0U; j < ecu->pin_count; ++j) {
            const EEC_EcuPin_t *pin = &ecu->pins[j];
            fprintf(f, "          {\n            \"connector\": ");
            json_escape(f, pin->connector_name);
            fprintf(f, ",\n            \"physical_number\": %u,\n            \"name\": ", pin->physical_number);
            json_escape(f, pin->name);
            fprintf(f, ",\n            \"group\": ");
            json_escape(f, pin->main_group);
            fprintf(f, ",\n            \"functions\": [");
            for (k = 0U; k < pin->function_count; ++k) {
                if (k) fprintf(f, ", ");
                json_escape(f, pin->functions[k]);
            }
            fprintf(f, "],\n            \"role\": ");
            json_escape(f, EEC_Pin_RoleString(pin->role));
            fprintf(f, ",\n            \"interface_type\": ");
            json_escape(f, EEC_Signal_InterfaceString((EEC_SignalInterface_t)pin->interface_type));
            fprintf(f, ",\n            \"type\": ");
            json_escape(f, pin->connected_signal ? EEC_Signal_InterfaceString(pin->connected_signal->interface_type)
                                               : EEC_Signal_InterfaceString(signal_interface_from_capability_mask(pin->supported_capability_mask)));
            fprintf(f, ",\n            \"electrical\": ");
            json_escape(f, pin->electrical);
            fprintf(f, ",\n            \"diagnostic_flags\": %u,\n            \"diagnostics\": ", pin->diagnostic_flags);
            write_diag_array(f, pin->diagnostic_flags);
            fprintf(f, ",\n            \"electrical_capability\": %u,\n            \"electrical_flags\": ", pin->electrical_capability);
            write_elec_array(f, pin->electrical_capability);
            fprintf(f, ",\n            \"sw_config\": ");
            write_pipe_text_as_array(f, pin->sw_config);
            fprintf(f, ",\n            \"status\": ");
            json_escape(f, pin->connected_signal ? "valid" : "free");
            fprintf(f, ",\n            \"is_occupied\": %s,\n            \"signal\": ", pin->is_occupied ? "true" : "false");
            if (pin->connected_signal) {
                fprintf(f, "{ \"name\": ");
                json_escape(f, pin->connected_signal->name);
                fprintf(f, ", \"type\": ");
                json_escape(f, EEC_Signal_TypeString(pin->connected_signal->type));
                fprintf(f, ", \"bit_width\": %u", EEC_Signal_TypeBitWidth(pin->connected_signal->type));
                fprintf(f, ", \"is_signed\": %s", EEC_Signal_TypeIsSigned(pin->connected_signal->type) ? "true" : "false");
                fprintf(f, ", \"interface_type\": ");
                json_escape(f, EEC_Signal_InterfaceString(pin->connected_signal->interface_type));
                fprintf(f, ", \"unit\": ");
                json_escape(f, EEC_Signal_UnitString(pin->connected_signal->unit));
                fprintf(f, ", \"priority\": ");
                json_escape(f, EEC_Priority_String(pin->connected_signal->priority));
                fprintf(f, ", \"safety\": ");
                json_escape(f, EEC_Safety_String(pin->connected_signal->safety));
                fprintf(f, ", \"min\": %.3f, \"max\": %.3f, \"resolution\": %.3f",
                        pin->connected_signal->min_value,
                        pin->connected_signal->max_value,
                        pin->connected_signal->resolution);
                fprintf(f, ", \"is_mapped\": %s", pin->connected_signal->is_mapped ? "true" : "false");
                if (pin->connected_signal->clean_signal_name[0] != '\0') {
                    fprintf(f, ", \"clean_name\": ");
                    json_escape(f, pin->connected_signal->clean_signal_name);
                    fprintf(f, ", \"naming_convention\": { \"system_code\": ");
                    json_escape(f, pin->connected_signal->system_code);
                    fprintf(f, ", \"function_name\": ");
                    json_escape(f, pin->connected_signal->function_name);
                    fprintf(f, ", \"position_index\": ");
                    json_escape(f, pin->connected_signal->position_index);
                    fprintf(f, ", \"type_code\": ");
                    json_escape(f, pin->connected_signal->type_code);
                    fprintf(f, ", \"is_auto_named\": %s }", pin->connected_signal->is_auto_named ? "true" : "false");
                }
                fprintf(f, " }");
            } else {
                fprintf(f, "null");
            }
            fprintf(f, ",\n            \"device_pin\": ");
            if (pin->device_pin_name[0] != '\0') {
                fprintf(f, "{ \"name\": ");
                json_escape(f, pin->device_pin_name);
                fprintf(f, ", \"description\": ");
                json_escape(f, pin->device_pin_desc);
                fprintf(f, " }");
            } else {
                fprintf(f, "null");
            }
            fprintf(f, "\n          }%s\n", (j + 1U < ecu->pin_count) ? "," : "");
        }

        fprintf(f, "        ],\n");
        write_allocation_summary(f, ecu->pin_count, ecu_allocated_pins, 8);
        fprintf(f, ",\n");
        write_connector_summary(f, ecu);
        fprintf(f, "\n      }%s\n", (i + 1U < arch->ecu_count) ? "," : "");
    }

    fprintf(f, "    ],\n");
    write_allocation_summary(f, total_pins, allocated_pins, 4);
    fprintf(f, ",\n    \"systems\": [\n");
    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *system = arch->systems[i];
        fprintf(f, "      {\n        \"name\": ");
        json_escape(f, system->name);
        fprintf(f, ",\n        \"part_number\": ");
        json_escape(f, system->part_number);
        fprintf(f, ",\n        \"system_level\": ");
        json_escape(f, EEC_System_LevelString(system->system_level));
        fprintf(f, ",\n        \"Ref-2X\": ");
        json_escape(f, system->ref_2x);
        fprintf(f, ",\n        \"priority\": ");
        json_escape(f, EEC_Priority_String(system->priority));
        fprintf(f, ",\n        \"safety\": ");
        json_escape(f, EEC_Safety_String(system->safety));
        fprintf(f, ",\n        \"location\": ");
        json_escape(f, system->location);
        fprintf(f, ",\n        \"take_rate\": %.1f", (double)system->take_rate);
        fprintf(f, ",\n        \"is_mandatory\": %s", system->is_mandatory ? "true" : "false");
        fprintf(f, ",\n        \"devices\": [\n");

        /* Emit all devices from components */
        {
            uint32_t c_idx;
            bool first_device = true;
            for (c_idx = 0U; c_idx < system->component_count; ++c_idx) {
                const EEC_Component_t *comp = system->components[c_idx];
                if (!comp) continue;
                for (j = 0U; j < comp->sensor_count; ++j) {
                    const EEC_Sensor_t *sensor = comp->sensors[j];
                    if (sensor) {
                        if (!first_device) { fprintf(f, ",\n"); }
                        write_system_member_json(f, sensor->name, sensor->part_number, EEC_DEVICE_SENSOR, sensor->priority, sensor->safety, sensor->pins, sensor->pin_count, sensor->connectors, sensor->connector_count, false);
                        first_device = false;
                    }
                }
                for (j = 0U; j < comp->actuator_count; ++j) {
                    const EEC_Actuator_t *actuator = comp->actuators[j];
                    if (actuator) {
                        if (!first_device) { fprintf(f, ",\n"); }
                        write_system_member_json(f, actuator->name, actuator->part_number, EEC_DEVICE_ACTUATOR, actuator->priority, actuator->safety, actuator->pins, actuator->pin_count, actuator->connectors, actuator->connector_count, false);
                        first_device = false;
                    }
                }
            }
        }

        fprintf(f, "        ]\n      }%s\n", (i + 1U < arch->system_count) ? "," : "");
    }
    fprintf(f, "    ],\n");

    /* ── Buses ── */
    fprintf(f, "    \"buses\": [\n");
    for (i = 0U; i < arch->bus_count; ++i) {
        const EEC_Bus_t *bus = arch->buses[i];
        uint32_t n;
        fprintf(f, "      {\n        \"name\": ");
        json_escape(f, bus->name);
        fprintf(f, ",\n        \"part_number\": ");
        json_escape(f, bus->part_number);
        fprintf(f, ",\n        \"type\": ");
        json_escape(f, EEC_Bus_TypeString(bus->type));
        fprintf(f, ",\n        \"Ref-2X\": ");
        json_escape(f, bus->ref_2x);
        fprintf(f, ",\n        \"bitrate\": %u", bus->bitrate);
        fprintf(f, ",\n        \"priority\": ");
        json_escape(f, EEC_Priority_String(bus->priority));
        fprintf(f, ",\n        \"safety\": ");
        json_escape(f, EEC_Safety_String(bus->safety));
        fprintf(f, ",\n        \"nodes\": [");
        for (n = 0U; n < bus->node_count; ++n) {
            fprintf(f, "\n          { \"ecu\": ");
            json_escape(f, bus->nodes[n].ecu ? bus->nodes[n].ecu->name : "");
            fprintf(f, ", \"port_index\": %u }", bus->nodes[n].port_index);
            if (n + 1U < bus->node_count) fprintf(f, ",");
        }
        if (bus->node_count > 0U) fprintf(f, "\n        ");
        fprintf(f, "],\n        \"signals\": [");
        for (n = 0U; n < bus->signal_count; ++n) {
            fprintf(f, "\n          ");
            json_escape(f, bus->signals[n] ? bus->signals[n]->name : "");
            if (n + 1U < bus->signal_count) fprintf(f, ",");
        }
        if (bus->signal_count > 0U) fprintf(f, "\n        ");
        fprintf(f, "]\n      }%s\n", (i + 1U < arch->bus_count) ? "," : "");
    }
    fprintf(f, "    ]\n");

    fprintf(f, "  }\n}\n");
    fclose(f);

    EEC_Log_Printf(EEC_LOG_INFO, "Exported architecture JSON to '%s'", filename);
    return 0;
}

/** @brief Pin-only physical projection: ECU -> connector -> pin -> wire.
 *  Unlike EEC_Export_architecture_json(), this drops the logical device tree
 *  (systems/components/sensors/actuators) entirely and adds a flat "wires"
 *  netlist (one entry per occupied pin: which device pin lands on which ECU
 *  connector/pin, via which signal) — the harness-relevant view a wiring
 *  team or connector/pinout tool consumes, as opposed to the requirements-
 *  relevant view (which system/component a signal belongs to) the logical
 *  export serves.
 */
int EEC_Export_physical_architecture_json(const EEC_Architecture_t *arch, const char *filename)
{
    uint32_t i, j, k;
    uint32_t total_pins = 0U;
    uint32_t allocated_pins = 0U;
    FILE *f;
    if (!arch || !filename) {
        return -1;
    }
    f = fopen(filename, "w");
    if (!f) {
        return -1;
    }

    fprintf(f, "{\n  \"architecture\": {\n    \"name\": ");
    json_escape(f, arch->name);
    fprintf(f, ",\n    \"part_number\": ");
    json_escape(f, arch->part_number);
    fprintf(f, ",\n    \"priority\": ");
    json_escape(f, EEC_Priority_String(arch->priority));
    fprintf(f, ",\n    \"safety\": ");
    json_escape(f, EEC_Safety_String(arch->safety));
    fprintf(f, ",\n    \"view\": \"physical\",\n    \"ecus\": [\n");

    for (i = 0U; i < arch->ecu_count; ++i) {
        const EEC_Ecu_t *ecu = arch->ecus[i];
        uint32_t ecu_allocated_pins = 0U;

        for (j = 0U; j < ecu->pin_count; ++j) {
            if (ecu->pins[j].is_occupied) {
                ++ecu_allocated_pins;
            }
        }
        total_pins += ecu->pin_count;
        allocated_pins += ecu_allocated_pins;

        fprintf(f, "      {\n        \"name\": ");
        json_escape(f, ecu->name);
        fprintf(f, ",\n        \"part_number\": ");
        json_escape(f, ecu->part_number);
        fprintf(f, ",\n        \"variant\": ");
        json_escape(f, ecu->variant);
        fprintf(f, ",\n        \"priority\": ");
        json_escape(f, EEC_Priority_String(ecu->priority));
        fprintf(f, ",\n        \"safety\": ");
        json_escape(f, EEC_Safety_String(ecu->safety));
        fprintf(f, ",\n        \"location\": ");
        json_escape(f, ecu->location);
        fprintf(f, ",\n        \"can_addresses\": [");
        for (j = 0U; j < ecu->can_address_count; ++j) {
            if (j) fprintf(f, ", ");
            fprintf(f, "\"0x%02X\"", ecu->can_addresses[j]);
        }
        fprintf(f, "],\n        \"pins\": [\n");

        /* Pin objects use the exact same schema as EEC_Export_architecture_json()
         * (connector/physical_number/.../signal/device_pin): several Python doc
         * generators (e.g. generate_network_bus_backbone_html.py,
         * generate_ecu_v3_config_validation_html.py) read fields like pin["type"]
         * or pin["device_pin"] straight off whichever export prefer_physical
         * resolves to, with no fallback for a physical-only pin schema. Only the
         * top-level shape (dropping "systems", adding "wires") differs here. */
        for (j = 0U; j < ecu->pin_count; ++j) {
            const EEC_EcuPin_t *pin = &ecu->pins[j];
            fprintf(f, "          {\n            \"connector\": ");
            json_escape(f, pin->connector_name);
            fprintf(f, ",\n            \"physical_number\": %u,\n            \"name\": ", pin->physical_number);
            json_escape(f, pin->name);
            fprintf(f, ",\n            \"group\": ");
            json_escape(f, pin->main_group);
            fprintf(f, ",\n            \"functions\": [");
            for (k = 0U; k < pin->function_count; ++k) {
                if (k) fprintf(f, ", ");
                json_escape(f, pin->functions[k]);
            }
            fprintf(f, "],\n            \"role\": ");
            json_escape(f, EEC_Pin_RoleString(pin->role));
            fprintf(f, ",\n            \"interface_type\": ");
            json_escape(f, EEC_Signal_InterfaceString((EEC_SignalInterface_t)pin->interface_type));
            fprintf(f, ",\n            \"type\": ");
            json_escape(f, pin->connected_signal ? EEC_Signal_InterfaceString(pin->connected_signal->interface_type)
                                               : EEC_Signal_InterfaceString(signal_interface_from_capability_mask(pin->supported_capability_mask)));
            fprintf(f, ",\n            \"electrical\": ");
            json_escape(f, pin->electrical);
            fprintf(f, ",\n            \"diagnostic_flags\": %u,\n            \"diagnostics\": ", pin->diagnostic_flags);
            write_diag_array(f, pin->diagnostic_flags);
            fprintf(f, ",\n            \"electrical_capability\": %u,\n            \"electrical_flags\": ", pin->electrical_capability);
            write_elec_array(f, pin->electrical_capability);
            fprintf(f, ",\n            \"current_max\": %.3f", (double)pin->current_max);
            fprintf(f, ",\n            \"sw_config\": ");
            write_pipe_text_as_array(f, pin->sw_config);
            fprintf(f, ",\n            \"status\": ");
            json_escape(f, pin->connected_signal ? "valid" : "free");
            fprintf(f, ",\n            \"is_occupied\": %s,\n            \"signal\": ", pin->is_occupied ? "true" : "false");
            if (pin->connected_signal) {
                fprintf(f, "{ \"name\": ");
                json_escape(f, pin->connected_signal->name);
                fprintf(f, ", \"interface_type\": ");
                json_escape(f, EEC_Signal_InterfaceString(pin->connected_signal->interface_type));
                fprintf(f, ", \"unit\": ");
                json_escape(f, EEC_Signal_UnitString(pin->connected_signal->unit));
                fprintf(f, ", \"min\": %.3f, \"max\": %.3f",
                        pin->connected_signal->min_value, pin->connected_signal->max_value);
                fprintf(f, " }");
            } else {
                fprintf(f, "null");
            }
            fprintf(f, ",\n            \"device_pin\": ");
            if (pin->device_pin_name[0] != '\0') {
                fprintf(f, "{ \"name\": ");
                json_escape(f, pin->device_pin_name);
                fprintf(f, ", \"description\": ");
                json_escape(f, pin->device_pin_desc);
                fprintf(f, " }");
            } else {
                fprintf(f, "null");
            }
            fprintf(f, "\n          }%s\n", (j + 1U < ecu->pin_count) ? "," : "");
        }

        fprintf(f, "        ],\n");
        write_allocation_summary(f, ecu->pin_count, ecu_allocated_pins, 8);
        fprintf(f, ",\n");
        write_connector_summary(f, ecu);
        fprintf(f, "\n      }%s\n", (i + 1U < arch->ecu_count) ? "," : "");
    }

    fprintf(f, "    ],\n");
    write_allocation_summary(f, total_pins, allocated_pins, 4);

    /* ── Wires: flat netlist, one entry per occupied pin ──
     * (device pin) --[signal]--> (ECU connector/pin). This is the piece of
     * information the logical export leaves implicit (spread across the
     * systems tree); here it is the primary artefact. */
    fprintf(f, ",\n    \"wires\": [");
    {
        bool first_wire = true;
        for (i = 0U; i < arch->ecu_count; ++i) {
            const EEC_Ecu_t *ecu = arch->ecus[i];
            for (j = 0U; j < ecu->pin_count; ++j) {
                const EEC_EcuPin_t *pin = &ecu->pins[j];
                if (!pin->is_occupied || !pin->connected_signal) {
                    continue;
                }
                fprintf(f, "%s\n      {\n        \"signal\": ", first_wire ? "" : ",");
                json_escape(f, pin->connected_signal->name);
                fprintf(f, ",\n        \"device_pin\": ");
                if (pin->device_pin_name[0] != '\0') {
                    fprintf(f, "{ \"name\": ");
                    json_escape(f, pin->device_pin_name);
                    fprintf(f, ", \"description\": ");
                    json_escape(f, pin->device_pin_desc);
                    fprintf(f, " }");
                } else {
                    fprintf(f, "null");
                }
                fprintf(f, ",\n        \"ecu\": ");
                json_escape(f, ecu->name);
                fprintf(f, ",\n        \"connector\": ");
                json_escape(f, pin->connector_name);
                fprintf(f, ",\n        \"pin\": %u\n      }", pin->physical_number);
                first_wire = false;
            }
        }
        if (!first_wire) {
            fprintf(f, "\n    ");
        }
    }
    fprintf(f, "],\n");

    /* ── Buses: physical topology (unchanged from the logical export — bus
     * membership and bitrate are physical-layer facts, not logical-tree
     * data). ── */
    fprintf(f, "    \"buses\": [\n");
    for (i = 0U; i < arch->bus_count; ++i) {
        const EEC_Bus_t *bus = arch->buses[i];
        uint32_t n;
        fprintf(f, "      {\n        \"name\": ");
        json_escape(f, bus->name);
        fprintf(f, ",\n        \"part_number\": ");
        json_escape(f, bus->part_number);
        fprintf(f, ",\n        \"type\": ");
        json_escape(f, EEC_Bus_TypeString(bus->type));
        fprintf(f, ",\n        \"Ref-2X\": ");
        json_escape(f, bus->ref_2x);
        fprintf(f, ",\n        \"bitrate\": %u", bus->bitrate);
        fprintf(f, ",\n        \"priority\": ");
        json_escape(f, EEC_Priority_String(bus->priority));
        fprintf(f, ",\n        \"safety\": ");
        json_escape(f, EEC_Safety_String(bus->safety));
        fprintf(f, ",\n        \"nodes\": [");
        for (n = 0U; n < bus->node_count; ++n) {
            fprintf(f, "\n          { \"ecu\": ");
            json_escape(f, bus->nodes[n].ecu ? bus->nodes[n].ecu->name : "");
            fprintf(f, ", \"port_index\": %u }", bus->nodes[n].port_index);
            if (n + 1U < bus->node_count) fprintf(f, ",");
        }
        if (bus->node_count > 0U) fprintf(f, "\n        ");
        fprintf(f, "],\n        \"signals\": [");
        for (n = 0U; n < bus->signal_count; ++n) {
            fprintf(f, "\n          ");
            json_escape(f, bus->signals[n] ? bus->signals[n]->name : "");
            if (n + 1U < bus->signal_count) fprintf(f, ",");
        }
        if (bus->signal_count > 0U) fprintf(f, "\n        ");
        fprintf(f, "]\n      }%s\n", (i + 1U < arch->bus_count) ? "," : "");
    }
    fprintf(f, "    ]\n");

    fprintf(f, "  }\n}\n");
    fclose(f);

    EEC_Log_Printf(EEC_LOG_INFO, "Exported physical architecture JSON to '%s'", filename);
    return 0;
}

int EEC_Export_full_pinout_template_html(const char *filename, const char *ecu_name, const char *variant)
{
    FILE *f;
    const char *title = ecu_name ? ecu_name : "ECU";
    const char *var = variant ? variant : "SMALL";
    if (!filename) {
        return -1;
    }
    f = fopen(filename, "w");
    if (!f) {
        return -1;
    }

    /* The actual full templates are shipped as static template files in templates/.
       This helper only creates a minimal documented marker file when used directly. */
    fprintf(f,
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>ECU Pinout - %s</title></head>"
        "<body><h1>ECU Pinout - %s</h1><p>Variant: %s</p><p>Use templates/AEC_%s_full_pinout.html for the full physical template.</p></body></html>",
        title, title, var, var);
    fclose(f);
    return 0;
}
