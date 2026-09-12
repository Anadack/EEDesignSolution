/**
 * @file    EEC_verify.c
 * @brief   E/E Architect Design — Architecture verification and reporting.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#include "EEC_verify.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

static void eec_write_pin_allocation_line(FILE *report, const char *label, uint32_t total_pins, uint32_t allocated_pins)
{
    uint32_t free_pins = (allocated_pins <= total_pins) ? (total_pins - allocated_pins) : 0U;
    double allocation_percent = (total_pins > 0U)
        ? (100.0 * (double)allocated_pins) / (double)total_pins
        : 0.0;

    fprintf(report,
            "%s: total=%u allocated=%u free=%u allocation=%.1f%%\n",
            label,
            total_pins,
            allocated_pins,
            free_pins,
            allocation_percent);
}

static bool eec_is_first_connector_occurrence(const EEC_Ecu_t *ecu, uint32_t pin_index)
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

static void eec_count_connector_pins(const EEC_Ecu_t *ecu, const char *connector_name, uint32_t *total_pins, uint32_t *allocated_pins)
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

static bool eec_roles_are_compatible(EEC_PinRole_t logical_role, EEC_PinRole_t physical_role)
{
    /* Device OUTPUT (sensor) -> ECU INPUT; Device INPUT (actuator) -> ECU OUTPUT.
       INOUT reserved for communication buses. */
    switch (logical_role) {
        case EEC_PIN_ROLE_INPUT:
            return physical_role == EEC_PIN_ROLE_OUTPUT;
        case EEC_PIN_ROLE_OUTPUT:
            return physical_role == EEC_PIN_ROLE_INPUT;
        case EEC_PIN_ROLE_INOUT:
            return physical_role == EEC_PIN_ROLE_INOUT;
        case EEC_PIN_ROLE_SUPPLY:
            return physical_role == EEC_PIN_ROLE_SUPPLY;
        case EEC_PIN_ROLE_GROUND:
            return physical_role == EEC_PIN_ROLE_GROUND;
        case EEC_PIN_ROLE_UNASSIGNED:
            return true;
        default:
            return false;
    }
}

static uint32_t eec_count_signal_assignments(const EEC_Architecture_t *arch, const EEC_Signal_t *signal, const EEC_Ecu_t **matched_ecu, const EEC_EcuPin_t **matched_pin)
{
    uint32_t ecu_index;
    uint32_t pin_index;
    uint32_t count = 0U;

    if (matched_ecu) {
        *matched_ecu = NULL;
    }
    if (matched_pin) {
        *matched_pin = NULL;
    }

    if (!arch || !signal) {
        return 0U;
    }

    for (ecu_index = 0U; ecu_index < arch->ecu_count; ++ecu_index) {
        const EEC_Ecu_t *ecu = arch->ecus[ecu_index];
        if (!ecu) {
            continue;
        }
        for (pin_index = 0U; pin_index < ecu->pin_count; ++pin_index) {
            const EEC_EcuPin_t *pin = &ecu->pins[pin_index];
            if (pin->connected_signal == signal) {
                if (count == 0U) {
                    if (matched_ecu) {
                        *matched_ecu = ecu;
                    }
                    if (matched_pin) {
                        *matched_pin = pin;
                    }
                }
                ++count;
            }
        }
    }

    return count;
}

static bool eec_parse_voltage_range_volts(const char *electrical, float *out_min_v, float *out_max_v)
{
    const char *p;
    float min_v;
    float max_v;

    if (out_min_v) {
        *out_min_v = 0.0f;
    }
    if (out_max_v) {
        *out_max_v = 0.0f;
    }
    if (!electrical) {
        return false;
    }

    p = electrical;
    while (*p) {
        if (sscanf(p, "%f..%f V", &min_v, &max_v) == 2) {
            if (out_min_v) {
                *out_min_v = min_v;
            }
            if (out_max_v) {
                *out_max_v = max_v;
            }
            return true;
        }
        ++p;
    }
    return false;
}

static bool eec_parse_nominal_current_amp(const char *electrical, float *out_current_a)
{
    const char *p;
    float current;

    if (out_current_a) {
        *out_current_a = 0.0f;
    }
    if (!electrical) {
        return false;
    }

    p = electrical;
    while (*p) {
        if (sscanf(p, "%f A", &current) == 1) {
            if (out_current_a) {
                *out_current_a = current;
            }
            return true;
        }
        if (sscanf(p, "%f mA", &current) == 1) {
            if (out_current_a) {
                *out_current_a = current / 1000.0f;
            }
            return true;
        }
        ++p;
    }
    return false;
}

static bool eec_parse_frequency_range_hz(const char *electrical, float *out_min_hz, float *out_max_hz)
{
    const char *p;
    float min_hz;
    float max_hz;

    if (out_min_hz) {
        *out_min_hz = 0.0f;
    }
    if (out_max_hz) {
        *out_max_hz = 0.0f;
    }
    if (!electrical) {
        return false;
    }

    p = electrical;
    while (*p) {
        if (sscanf(p, "%f Hz .. %f Hz", &min_hz, &max_hz) == 2) {
            if (out_min_hz) {
                *out_min_hz = min_hz;
            }
            if (out_max_hz) {
                *out_max_hz = max_hz;
            }
            return true;
        }
        ++p;
    }
    return false;
}

static int eec_verify_ecu_pin_identity_uniqueness(const EEC_Ecu_t *ecu, FILE *report)
{
    uint32_t i;
    uint32_t j;
    int errors = 0;

    if (!ecu || !report) {
        return 0;
    }

    for (i = 0U; i < ecu->pin_count; ++i) {
        for (j = i + 1U; j < ecu->pin_count; ++j) {
            if (ecu->pins[i].physical_number == ecu->pins[j].physical_number &&
                strcmp(ecu->pins[i].connector_name, ecu->pins[j].connector_name) == 0) {
                fprintf(report,
                        "ERROR: duplicate physical pin identity on ECU %s: %s/%u defined multiple times\n",
                        ecu->name,
                        ecu->pins[i].connector_name,
                        ecu->pins[i].physical_number);
                ++errors;
            }
        }
    }

    return errors;
}

static int eec_verify_differential_pairs_on_ecu(const EEC_Ecu_t *ecu, FILE *report)
{
    uint32_t i;
    int errors = 0;

    if (!ecu || !report) {
        return 0;
    }

    for (i = 0U; i < ecu->pin_count; ++i) {
        const EEC_EcuPin_t *pin = &ecu->pins[i];
        const EEC_Signal_t *signal;
        uint32_t j;
        bool has_pair = false;

        if (!pin->is_occupied || !pin->connected_signal) {
            continue;
        }
        signal = pin->connected_signal;
        if (signal->interface_type != EEC_SIGNAL_INTERFACE_CAN &&
            signal->interface_type != EEC_SIGNAL_INTERFACE_ETHERNET) {
            continue;
        }

        for (j = 0U; j < ecu->pin_count; ++j) {
            const EEC_EcuPin_t *other = &ecu->pins[j];
            int32_t delta;
            if (j == i || !other->is_occupied || !other->connected_signal) {
                continue;
            }
            if (strcmp(pin->connector_name, other->connector_name) != 0) {
                continue;
            }
            if (other->connected_signal->interface_type != signal->interface_type) {
                continue;
            }
            delta = (int32_t)pin->physical_number - (int32_t)other->physical_number;
            if (delta == 1 || delta == -1) {
                has_pair = true;
                break;
            }
        }

        if (!has_pair) {
            fprintf(report,
                    "ERROR: differential pairing issue on ECU %s for %s signal %s at %s/%u (no adjacent same-interface pair)\n",
                    ecu->name,
                    EEC_Signal_InterfaceString(signal->interface_type),
                    signal->name,
                    pin->connector_name,
                    pin->physical_number);
            ++errors;
        }
    }

    return errors;
}

static int eec_verify_logical_pins(const EEC_Architecture_t *arch, const char *owner_kind, const char *owner_name, const EEC_DevicePin_t *pins, uint32_t pin_count, FILE *report)
{
    uint32_t index;
    int errors = 0;

    for (index = 0U; index < pin_count; ++index) {
        const EEC_DevicePin_t *logical_pin = &pins[index];
        const EEC_Ecu_t *matched_ecu = NULL;
        const EEC_EcuPin_t *matched_pin = NULL;
        uint32_t assignment_count;

        if (!logical_pin->signal) {
            continue;
        }

        assignment_count = eec_count_signal_assignments(arch, logical_pin->signal, &matched_ecu, &matched_pin);
        if (assignment_count == 0U) {
            fprintf(report, "ERROR: unmapped signal %s referenced by %s %s pin %u\n",
                    logical_pin->signal->name, owner_kind, owner_name, logical_pin->number);
            ++errors;
            continue;
        }
        if (assignment_count > 1U) {
            fprintf(report, "ERROR: signal %s is assigned to %u ECU pins\n",
                    logical_pin->signal->name, assignment_count);
            ++errors;
            continue;
        }
        if (!matched_ecu || !matched_pin) {
            fprintf(report, "ERROR: internal verification failure while resolving signal %s\n",
                    logical_pin->signal->name);
            ++errors;
            continue;
        }
        if (!matched_pin->is_occupied) {
            fprintf(report, "ERROR: signal %s is connected on %s %s/%u but pin is not marked occupied\n",
                    logical_pin->signal->name, matched_ecu->name, matched_pin->connector_name, matched_pin->physical_number);
            ++errors;
        }
        if (!eec_roles_are_compatible(logical_pin->role, matched_pin->role)) {
            fprintf(report, "ERROR: role mismatch for signal %s between logical pin %s %s/%u and ECU pin %s %s/%u\n",
                    logical_pin->signal->name,
                    owner_kind,
                    owner_name,
                    logical_pin->number,
                    matched_ecu->name,
                    matched_pin->connector_name,
                    matched_pin->physical_number);
            ++errors;
        }
        /* Electrical compatibility: every requirement bit on the device pin
           must be satisfied by a corresponding capability bit on the ECU pin. */
        {
            uint32_t missing = logical_pin->electrical_requirement & ~matched_pin->electrical_capability;
            if (missing != 0U) {
                uint32_t blocking_missing = missing & (EEC_ELEC_PULLUP | EEC_ELEC_PULLDOWN);
                fprintf(report, "WARNING: electrical mismatch for signal %s on %s %s/%u: device requires 0x%02X, ECU provides 0x%02X (missing 0x%02X",
                        logical_pin->signal->name,
                        matched_ecu->name,
                        matched_pin->connector_name,
                        matched_pin->physical_number,
                        logical_pin->electrical_requirement,
                        matched_pin->electrical_capability,
                        missing);
                if (missing & EEC_ELEC_PULLUP)        fprintf(report, " PULLUP");
                if (missing & EEC_ELEC_PULLDOWN)      fprintf(report, " PULLDOWN");
                if (missing & EEC_ELEC_HIGH_SIDE)     fprintf(report, " HIGH_SIDE");
                if (missing & EEC_ELEC_LOW_SIDE)      fprintf(report, " LOW_SIDE");
                if (missing & EEC_ELEC_PUSH_PULL)     fprintf(report, " PUSH_PULL");
                if (missing & EEC_ELEC_CURRENT_SENSE) fprintf(report, " CURRENT_SENSE");
                if (missing & EEC_ELEC_VOLTAGE_IN)    fprintf(report, " VOLTAGE_IN");
                if (missing & EEC_ELEC_DIFFERENTIAL)  fprintf(report, " DIFFERENTIAL");
                fprintf(report, ")\n");

                if (blocking_missing != 0U) {
                    fprintf(report,
                            "ERROR: missing mandatory pull resistor capability for signal %s on %s %s/%u (missing 0x%02X)\n",
                            logical_pin->signal->name,
                            matched_ecu->name,
                            matched_pin->connector_name,
                            matched_pin->physical_number,
                            blocking_missing);
                    ++errors;
                }
            }
        }

        /* D1: if ECU pin declares a voltage envelope, signal range must fit it.
         *     Only compare when the signal's own unit is volts so that analog
         *     sensors measuring temperature, pressure, etc. are not rejected
         *     by a voltage-envelope check they cannot satisfy.            */
        if (logical_pin->signal->unit == EEC_SIGNAL_UNIT_VOLT &&
            matched_pin->electrical[0] != '\0') {
            float pin_min_v;
            float pin_max_v;
            if (eec_parse_voltage_range_volts(matched_pin->electrical, &pin_min_v, &pin_max_v)) {
                if (logical_pin->signal->min_value < pin_min_v || logical_pin->signal->max_value > pin_max_v) {
                    fprintf(report,
                            "ERROR: voltage range mismatch for signal %s on %s %s/%u: signal range=[%.3f..%.3f] V, pin range=[%.3f..%.3f] V\n",
                            logical_pin->signal->name,
                            matched_ecu->name,
                            matched_pin->connector_name,
                            matched_pin->physical_number,
                            (double)logical_pin->signal->min_value,
                            (double)logical_pin->signal->max_value,
                            (double)pin_min_v,
                            (double)pin_max_v);
                    ++errors;
                }
            }
        }

        /* D2: when signal is in amperes and pin exposes nominal current, enforce it. */
        if ((logical_pin->signal->unit == EEC_SIGNAL_UNIT_AMPERE) &&
            (logical_pin->role == EEC_PIN_ROLE_OUTPUT || logical_pin->role == EEC_PIN_ROLE_INOUT) &&
            matched_pin->electrical[0] != '\0') {
            float pin_nominal_a;
            if (eec_parse_nominal_current_amp(matched_pin->electrical, &pin_nominal_a)) {
                float signal_demand_a = fmaxf(fabsf(logical_pin->signal->min_value), fabsf(logical_pin->signal->max_value));
                if (signal_demand_a > pin_nominal_a) {
                    fprintf(report,
                            "ERROR: output current mismatch for signal %s on %s %s/%u: signal demand=%.3f A, pin nominal=%.3f A\n",
                            logical_pin->signal->name,
                            matched_ecu->name,
                            matched_pin->connector_name,
                            matched_pin->physical_number,
                            (double)signal_demand_a,
                            (double)pin_nominal_a);
                    ++errors;
                }
            }
        }

        /* F: PWM constraints. */
        if (logical_pin->signal->interface_type == EEC_SIGNAL_INTERFACE_PWM) {
            if (logical_pin->signal->unit == EEC_SIGNAL_UNIT_PERCENT) {
                if (logical_pin->signal->min_value < 0.0f || logical_pin->signal->max_value > 100.0f ||
                    logical_pin->signal->min_value > logical_pin->signal->max_value) {
                    fprintf(report,
                            "ERROR: PWM duty-cycle range invalid for signal %s: [%.3f..%.3f] %% (expected 0..100 %%)\n",
                            logical_pin->signal->name,
                            (double)logical_pin->signal->min_value,
                            (double)logical_pin->signal->max_value);
                    ++errors;
                }
            }

            if (logical_pin->signal->unit == EEC_SIGNAL_UNIT_HERTZ && matched_pin->electrical[0] != '\0') {
                float pin_min_hz;
                float pin_max_hz;
                if (eec_parse_frequency_range_hz(matched_pin->electrical, &pin_min_hz, &pin_max_hz)) {
                    if (logical_pin->signal->min_value < pin_min_hz || logical_pin->signal->max_value > pin_max_hz) {
                        fprintf(report,
                                "ERROR: PWM frequency range mismatch for signal %s on %s %s/%u: signal=[%.3f..%.3f] Hz, pin=[%.3f..%.3f] Hz\n",
                                logical_pin->signal->name,
                                matched_ecu->name,
                                matched_pin->connector_name,
                                matched_pin->physical_number,
                                (double)logical_pin->signal->min_value,
                                (double)logical_pin->signal->max_value,
                                (double)pin_min_hz,
                                (double)pin_max_hz);
                        ++errors;
                    }
                }
            }
        }

        /* V10: Diagnostics requirement — device required ⊆ ECU pin provides */
        if (logical_pin->diagnostics_required != 0U) {
            uint32_t missing_diag = logical_pin->diagnostics_required & ~matched_pin->diagnostic_flags;
            if (missing_diag != 0U) {
                fprintf(report,
                        "ERROR: diagnostics gap for signal %s on %s %s/%u: device requires 0x%02X, ECU provides 0x%02X (missing 0x%02X",
                        logical_pin->signal->name,
                        matched_ecu->name,
                        matched_pin->connector_name,
                        matched_pin->physical_number,
                        logical_pin->diagnostics_required,
                        matched_pin->diagnostic_flags,
                        missing_diag);
                if (missing_diag & EEC_DIAG_OPEN_LOAD)    fprintf(report, " OPEN_LOAD");
                if (missing_diag & EEC_DIAG_SHORT_GND)    fprintf(report, " SHORT_GND");
                if (missing_diag & EEC_DIAG_SHORT_BAT)    fprintf(report, " SHORT_BAT");
                if (missing_diag & EEC_DIAG_OVERCURRENT)  fprintf(report, " OVERCURRENT");
                if (missing_diag & EEC_DIAG_THERMAL_WARN) fprintf(report, " THERMAL");
                fprintf(report, ")\n");
                ++errors;
            }
        }

        /* V11: Current overload — device nominal/inrush vs ECU pin current_max */
        if (logical_pin->nominal_current > 0.0f && matched_pin->current_max > 0.0f) {
            if (logical_pin->nominal_current > matched_pin->current_max) {
                fprintf(report,
                        "ERROR: current overload for signal %s on %s %s/%u: device draws %.3f A, pin max %.3f A\n",
                        logical_pin->signal->name,
                        matched_ecu->name,
                        matched_pin->connector_name,
                        matched_pin->physical_number,
                        (double)logical_pin->nominal_current,
                        (double)matched_pin->current_max);
                ++errors;
            }
            if (logical_pin->inrush_current > 0.0f && logical_pin->inrush_current > matched_pin->current_max * 2.0f) {
                fprintf(report,
                        "WARNING: inrush current for signal %s on %s %s/%u: peak %.3f A exceeds 2x pin max (%.3f A)\n",
                        logical_pin->signal->name,
                        matched_ecu->name,
                        matched_pin->connector_name,
                        matched_pin->physical_number,
                        (double)logical_pin->inrush_current,
                        (double)matched_pin->current_max);
            }
        }

        /* V12: Ground class mixing — power device on logic ground is forbidden */
        if (logical_pin->ground_class != EEC_GND_UNCLASSIFIED &&
            matched_pin->ground_class != EEC_GND_UNCLASSIFIED) {
            if (logical_pin->ground_class != matched_pin->ground_class) {
                fprintf(report,
                        "ERROR: ground class mismatch for signal %s on %s %s/%u: device requires %s, ECU provides %s\n",
                        logical_pin->signal->name,
                        matched_ecu->name,
                        matched_pin->connector_name,
                        matched_pin->physical_number,
                        (logical_pin->ground_class == EEC_GND_POWER) ? "GND_POWER" : "GND_LOGIC",
                        (matched_pin->ground_class == EEC_GND_POWER) ? "GND_POWER" : "GND_LOGIC");
                ++errors;
            }
        }

        /* V13: Safety-relevant device on non-diagnostic pin.
           POWER and GROUND supply lines are monitored at the system rail level,
           not through individual ECU pin diagnostics — exclude them from this check. */
        if (logical_pin->safety_relevant && matched_pin->diagnostic_flags == EEC_DIAG_NONE &&
            logical_pin->interface_type != (EEC_PinInterface_t)EEC_SIGNAL_INTERFACE_POWER &&
            logical_pin->interface_type != (EEC_PinInterface_t)EEC_SIGNAL_INTERFACE_GROUND) {
            fprintf(report,
                    "ERROR: safety-relevant signal %s on %s %s/%u has no diagnostic capability (ISO 26262 violation)\n",
                    logical_pin->signal->name,
                    matched_ecu->name,
                    matched_pin->connector_name,
                    matched_pin->physical_number);
            ++errors;
        }
    }

    return errors;
}

/** @brief Write per-ECU and global pin allocation statistics. */
int EEC_Report_pin_allocation(const EEC_Architecture_t *arch, FILE *report)
{
    uint32_t ecu_index;
    uint32_t total_pins = 0U;
    uint32_t allocated_pins = 0U;

    if (!arch || !report) {
        return -1;
    }

    fprintf(report, "========================================================================\n");
    fprintf(report, "  E/E Architect Design — Pin Allocation Report\n");
    fprintf(report, "========================================================================\n");
    fprintf(report, "What:   Per-ECU and per-connector physical pin usage statistics.\n");
    fprintf(report, "How:    Iterates all ECU pins, counts occupied vs total per connector\n");
    fprintf(report, "        and per ECU, then computes allocation percentages.\n");
    fprintf(report, "------------------------------------------------------------------------\n");
    fprintf(report, "Name:     %s\n", arch->name);
    fprintf(report, "Priority: %s\n", EEC_Priority_String(arch->priority));
    fprintf(report, "Safety:   %s\n\n", EEC_Safety_String(arch->safety));

    for (ecu_index = 0U; ecu_index < arch->ecu_count; ++ecu_index) {
        const EEC_Ecu_t *ecu = arch->ecus[ecu_index];
        uint32_t pin_index;
        uint32_t ecu_allocated_pins = 0U;

        if (!ecu) {
            continue;
        }

        for (pin_index = 0U; pin_index < ecu->pin_count; ++pin_index) {
            if (ecu->pins[pin_index].is_occupied) {
                ++ecu_allocated_pins;
            }
        }

        total_pins += ecu->pin_count;
        allocated_pins += ecu_allocated_pins;
        eec_write_pin_allocation_line(report, ecu->name, ecu->pin_count, ecu_allocated_pins);
        fprintf(report, "  Priority: %s  Safety: %s\n", EEC_Priority_String(ecu->priority), EEC_Safety_String(ecu->safety));

        for (pin_index = 0U; pin_index < ecu->pin_count; ++pin_index) {
            uint32_t connector_total_pins;
            uint32_t connector_allocated_pins;

            if (!eec_is_first_connector_occurrence(ecu, pin_index)) {
                continue;
            }

            eec_count_connector_pins(
                ecu,
                ecu->pins[pin_index].connector_name,
                &connector_total_pins,
                &connector_allocated_pins
            );
            fprintf(report, "  ");
            eec_write_pin_allocation_line(report, ecu->pins[pin_index].connector_name, connector_total_pins, connector_allocated_pins);
        }

        fprintf(report, "\n");
    }

    eec_write_pin_allocation_line(report, "TOTAL", total_pins, allocated_pins);

    /* System-level summary showing safety/priority metadata per system. */
    if (arch->system_count > 0U) {
        fprintf(report, "\nSystems:\n");
        for (ecu_index = 0U; ecu_index < arch->system_count; ++ecu_index) {
            const EEC_System_t *sys = arch->systems[ecu_index];
            uint32_t sig_count = 0U;
            uint32_t c, d;
            if (!sys) {
                continue;
            }
            for (c = 0U; c < sys->component_count; ++c) {
                const EEC_Component_t *comp = sys->components[c];
                if (!comp) continue;
                for (d = 0U; d < comp->sensor_count; ++d) {
                    if (comp->sensors[d]) {
                        sig_count += comp->sensors[d]->pin_count;
                    }
                }
                for (d = 0U; d < comp->actuator_count; ++d) {
                    if (comp->actuators[d]) {
                        sig_count += comp->actuators[d]->pin_count;
                    }
                }
            }
            fprintf(report, "  %s: level=%s  priority=%s  safety=%s  signals=%u\n",
                    sys->name,
                    EEC_System_LevelString(sys->system_level),
                    EEC_Priority_String(sys->priority),
                    EEC_Safety_String(sys->safety),
                    sig_count);
        }
    }

    fprintf(report, "\n========================================================================\n");
    fprintf(report, "RESULT: %u ECU(s), %u total pin(s), %u allocated, %u free (%.1f%% used)\n",
            arch->ecu_count, total_pins, allocated_pins,
            total_pins - allocated_pins,
            total_pins > 0U ? 100.0 * (double)allocated_pins / (double)total_pins : 0.0);
    fprintf(report, "========================================================================\n");

    return 0;
}

/* ══════════════════════════════════════════════════════════════════════════
 *  Bus verification rules B1–B8
 * ══════════════════════════════════════════════════════════════════════════ */

/* Worst-case on-wire bit length of a classic-CAN frame including bit stuffing,
 * per ISO 11898-1. Fixed framing/overhead + 8*DLC data bits + worst-case stuff
 * bits (one per 4 bits of the stuffable field). Standard = 11-bit ID, extended
 * = 29-bit ID (J1939). Used by the B9 busload estimate. */
static uint32_t eec_can_frame_bits(uint8_t dlc, bool extended)
{
    uint32_t data = 8U * (uint32_t)dlc;
    if (extended) {
        return 67U + data + ((54U + data) / 4U);
    }
    return 47U + data + ((34U + data) / 4U);
}

static int eec_verify_buses(const EEC_Architecture_t *arch, FILE *report)
{
    uint32_t b, n, s, b2, n2;
    int errors = 0;

    for (b = 0; b < arch->bus_count; ++b) {
        const EEC_Bus_t *bus = arch->buses[b];
        if (!bus) continue;

        for (n = 0; n < bus->node_count; ++n) {
            const EEC_BusNode_t *node = &bus->nodes[n];
            if (!node->ecu) continue;

            /* B1: port index valid for ECU variant */
            {
                uint8_t max_ports = 0;
                if (bus->type == EEC_BUS_TYPE_ETHERNET) {
                    max_ports = EEC_Ecu_CountEthernetPorts(node->ecu);
                } else {
                    max_ports = EEC_Ecu_CountCanPorts(node->ecu);
                }
                if (node->port_index > max_ports) {
                    fprintf(report,
                            "ERROR: bus '%s': ECU '%s' port %u exceeds available %s ports (%u)\n",
                            bus->name, node->ecu->name, node->port_index,
                            (bus->type == EEC_BUS_TYPE_ETHERNET) ? "ETH" : "CAN",
                            max_ports);
                    ++errors;
                }
            }

            /* B2: same ECU+port not on multiple buses */
            for (b2 = b + 1; b2 < arch->bus_count; ++b2) {
                const EEC_Bus_t *other = arch->buses[b2];
                if (!other) continue;
                for (n2 = 0; n2 < other->node_count; ++n2) {
                    if (other->nodes[n2].ecu == node->ecu &&
                        other->nodes[n2].port_index == node->port_index) {
                        fprintf(report,
                                "ERROR: ECU '%s' port %u connected to both bus '%s' and bus '%s'\n",
                                node->ecu->name, node->port_index,
                                bus->name, other->name);
                        ++errors;
                    }
                }
            }

            /* B4: no duplicate ECU+port on same bus */
            for (n2 = n + 1; n2 < bus->node_count; ++n2) {
                if (bus->nodes[n2].ecu == node->ecu &&
                    bus->nodes[n2].port_index == node->port_index) {
                    fprintf(report,
                            "ERROR: bus '%s': duplicate ECU '%s' port %u\n",
                            bus->name, node->ecu->name, node->port_index);
                    ++errors;
                }
            }
        }

        /* B3: signal interface matches bus type */
        for (s = 0; s < bus->signal_count; ++s) {
            const EEC_Signal_t *sig = bus->signals[s];
            if (!sig) continue;
            if (!EEC_Bus_InterfaceCompatible(bus->type, sig->interface_type)) {
                fprintf(report,
                        "ERROR: bus '%s' (%s): signal '%s' has incompatible interface %s\n",
                        bus->name, EEC_Bus_TypeString(bus->type),
                        sig->name, EEC_Signal_InterfaceString(sig->interface_type));
                ++errors;
            }
        }

        /* B5: CAN/ISOBUS bus ≤ 32 nodes */
        if ((bus->type == EEC_BUS_TYPE_CAN || bus->type == EEC_BUS_TYPE_ISOBUS) &&
            bus->node_count > 32U) {
            fprintf(report,
                    "WARNING: bus '%s' (%s): %u nodes exceeds CAN limit of 32\n",
                    bus->name, EEC_Bus_TypeString(bus->type), bus->node_count);
        }

        /* B6: unique CAN node addresses per bus */
        if (bus->type == EEC_BUS_TYPE_CAN || bus->type == EEC_BUS_TYPE_ISOBUS) {
            for (n = 0; n < bus->node_count; ++n) {
                const EEC_Ecu_t *ecu_a = bus->nodes[n].ecu;
                if (!ecu_a) continue;
                for (n2 = n + 1; n2 < bus->node_count; ++n2) {
                    const EEC_Ecu_t *ecu_b = bus->nodes[n2].ecu;
                    uint8_t a_idx, b_idx;
                    if (!ecu_b) continue;
                    for (a_idx = 0; a_idx < ecu_a->can_address_count; ++a_idx) {
                        for (b_idx = 0; b_idx < ecu_b->can_address_count; ++b_idx) {
                            if (ecu_a->can_addresses[a_idx] == ecu_b->can_addresses[b_idx]) {
                                fprintf(report,
                                        "ERROR: bus '%s': duplicate CAN address 0x%02X between '%s' and '%s'\n",
                                        bus->name, ecu_a->can_addresses[a_idx],
                                        ecu_a->name, ecu_b->name);
                                ++errors;
                            }
                        }
                    }
                }
            }
        }

        /* B8: bitrate > 0 when nodes connected */
        if (bus->node_count > 0U && bus->bitrate == 0U) {
            fprintf(report,
                    "WARNING: bus '%s': bitrate is 0 but %u nodes are connected\n",
                    bus->name, bus->node_count);
        }

        /* B9: CAN busload estimate must stay within safe utilization.
         * Sums worst-case periodic traffic (cycle_time_ms > 0) on CAN/ISOBUS
         * buses; event-driven frames (cycle 0) are reported, not summed.
         * WARNING >= 50% (leave headroom; safety buses lower still),
         * ERROR > 80% (classic-CAN practical ceiling). Uses existing model
         * fields only: bus->bitrate, msg->dlc/is_extended, tx cycle_time_ms. */
        if ((bus->type == EEC_BUS_TYPE_CAN || bus->type == EEC_BUS_TYPE_ISOBUS) &&
            bus->bitrate > 0U && bus->message_count > 0U) {
            double load_bps = 0.0;
            uint32_t event_driven = 0U, m;
            for (m = 0; m < bus->message_count; ++m) {
                const EEC_Message_t *msg = bus->messages[m];
                uint32_t cycle_ms = 0U, t;
                if (!msg) continue;
                for (t = 0; t < msg->tx_count; ++t) {
                    if (msg->tx_ports[t].bus == bus) {
                        cycle_ms = msg->tx_ports[t].cycle_time_ms;
                        break;
                    }
                }
                if (cycle_ms == 0U) { ++event_driven; continue; }
                load_bps += (double)eec_can_frame_bits(msg->dlc, msg->is_extended)
                            * (1000.0 / (double)cycle_ms);
            }
            {
                double pct = 100.0 * load_bps / (double)bus->bitrate;
                if (pct > 80.0) {
                    ++errors;
                    fprintf(report,
                            "ERROR: bus '%s': B9 busload %.1f%% exceeds 80%% ceiling "
                            "(%.0f bps periodic of %u bps)\n",
                            bus->name, pct, load_bps, bus->bitrate);
                } else if (pct >= 50.0) {
                    fprintf(report,
                            "WARNING: bus '%s': B9 busload %.1f%% is high (target <50%% for headroom)\n",
                            bus->name, pct);
                }
                if (event_driven > 0U) {
                    fprintf(report,
                            "  [INFO] bus '%s': %u event-driven frame(s) excluded from busload (cycle=0)\n",
                            bus->name, event_driven);
                }
            }
        }
    }

    /* B7: every bus-type signal should be on a bus */
    {
        uint32_t si;
        for (si = 0; si < arch->signal_count; ++si) {
            const EEC_Signal_t *sig = arch->signals[si];
            bool on_bus = false;
            if (!sig) continue;
            if (sig->interface_type != EEC_SIGNAL_INTERFACE_CAN &&
                sig->interface_type != EEC_SIGNAL_INTERFACE_LIN &&
                sig->interface_type != EEC_SIGNAL_INTERFACE_ETHERNET) {
                continue;
            }
            for (b = 0; b < arch->bus_count && !on_bus; ++b) {
                const EEC_Bus_t *bus = arch->buses[b];
                if (!bus) continue;
                for (s = 0; s < bus->signal_count; ++s) {
                    if (bus->signals[s] == sig) { on_bus = true; break; }
                }
            }
            if (!on_bus) {
                fprintf(report,
                        "WARNING: signal '%s' (%s) is not assigned to any bus\n",
                        sig->name, EEC_Signal_InterfaceString(sig->interface_type));
            }
        }
    }

    return errors;
}

/** @brief Verify duplicate CAN addresses, mapping consistency, and logical-to-physical compatibility. */
/* ── CAN message / SWC coherence (C1-C5) ───────────────────────────────── */
static int eec_verify_can(const EEC_Architecture_t *arch, FILE *report)
{
    int errors = 0;
    uint32_t i, s, m, e, t;
    uint32_t bi, bs, bm, bt, om;

    if (!arch) {
        return 0;
    }

    /* Per-message structural checks. */
    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *sys = arch->systems[i];
        if (!sys) {
            continue;
        }
        for (s = 0U; s < sys->swc_count; ++s) {
            const EEC_Swc_t *swc = sys->swcs[s];
            if (!swc) {
                continue;
            }
            for (m = 0U; m < swc->message_count; ++m) {
                const EEC_Message_t *msg = swc->messages[m];
                unsigned char bitmap[64];   /* up to 512 bits (64 bytes, CAN-FD). */
                uint32_t frame_bits;
                if (!msg) {
                    continue;
                }
                frame_bits = (uint32_t)msg->dlc * 8U;
                if (frame_bits > 512U) {
                    frame_bits = 512U;
                }
                memset(bitmap, 0, sizeof(bitmap));

                /* C1: a message must be transmitted at least once. */
                if (msg->tx_count == 0U) {
                    fprintf(report, "  [FAIL] C1  Message '%s' (0x%X) has no tx port\n",
                            msg->name, msg->frame_id);
                    ++errors;
                }

                /* C2: tx port ECU must match the SWC allocation and have a bus. */
                for (t = 0U; t < msg->tx_count; ++t) {
                    const EEC_MessageTx_t *tx = &msg->tx_ports[t];
                    if (!tx->bus) {
                        fprintf(report, "  [FAIL] C2  Message '%s' tx port %u has no bus\n",
                                msg->name, t);
                        ++errors;
                    }
                    if (tx->ecu != swc->allocated_ecu) {
                        fprintf(report,
                                "  [FAIL] C2  Message '%s' tx ecu '%s' != SWC '%s' allocation '%s'\n",
                                msg->name,
                                tx->ecu ? tx->ecu->name : "(null)",
                                swc->name,
                                swc->allocated_ecu ? swc->allocated_ecu->name : "(unallocated)");
                        ++errors;
                    }
                }

                /* C3-C4: signal presence, frame overflow, bit overlap. */
                for (e = 0U; e < msg->entry_count; ++e) {
                    const EEC_MessageSignal_t *ms = &msg->entries[e];
                    uint32_t start = ms->start_bit;
                    uint32_t len = ms->length;
                    uint32_t bit;

                    if (!ms->signal) {
                        fprintf(report, "  [FAIL] C3  Message '%s' entry %u has no signal\n",
                                msg->name, e);
                        ++errors;
                        continue;
                    }
                    if (len == 0U || (start + len) > frame_bits) {
                        fprintf(report,
                                "  [FAIL] C4  Message '%s' signal '%s' [%u..%u) exceeds %u-bit frame\n",
                                msg->name, ms->signal->name, start, start + len, frame_bits);
                        ++errors;
                        continue;
                    }
                    for (bit = start; bit < start + len; ++bit) {
                        unsigned char mask = (unsigned char)(1U << (bit & 7U));
                        if (bitmap[bit >> 3] & mask) {
                            fprintf(report,
                                    "  [FAIL] C4  Message '%s' signal '%s' overlaps bit %u\n",
                                    msg->name, ms->signal->name, bit);
                            ++errors;
                            break;
                        }
                        bitmap[bit >> 3] |= mask;
                    }
                }
            }
        }
    }

    /* C5: frame_id must be unique per bus (same id on different buses is OK). */
    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *sys = arch->systems[i];
        if (!sys) {
            continue;
        }
        for (s = 0U; s < sys->swc_count; ++s) {
            const EEC_Swc_t *swc = sys->swcs[s];
            if (!swc) {
                continue;
            }
            for (m = 0U; m < swc->message_count; ++m) {
                const EEC_Message_t *a = swc->messages[m];
                if (!a) {
                    continue;
                }
                for (bi = 0U; bi < arch->system_count; ++bi) {
                    const EEC_System_t *osys = arch->systems[bi];
                    if (!osys) {
                        continue;
                    }
                    for (bs = 0U; bs < osys->swc_count; ++bs) {
                        const EEC_Swc_t *oswc = osys->swcs[bs];
                        if (!oswc) {
                            continue;
                        }
                        for (bm = 0U; bm < oswc->message_count; ++bm) {
                            const EEC_Message_t *b = oswc->messages[bm];
                            if (!b || b <= a || b->frame_id != a->frame_id) {
                                continue;   /* b<=a avoids double reporting. */
                            }
                            for (bt = 0U; bt < a->tx_count; ++bt) {
                                for (om = 0U; om < b->tx_count; ++om) {
                                    if (a->tx_ports[bt].bus &&
                                        a->tx_ports[bt].bus == b->tx_ports[om].bus) {
                                        fprintf(report,
                                                "  [FAIL] C5  Duplicate frame_id 0x%X on bus '%s' ('%s' vs '%s')\n",
                                                a->frame_id,
                                                a->tx_ports[bt].bus->name,
                                                a->name, b->name);
                                        ++errors;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    return errors;
}

int EEC_Verify_can(const EEC_Architecture_t *arch, FILE *report)
{
    int errors;
    if (!arch || !report) {
        return -1;
    }
    fprintf(report, "\n=== CAN / SWC coherence (C1-C5) ===\n");
    errors = eec_verify_can(arch, report);
    if (errors == 0) {
        fprintf(report, "  [PASS] C1-C5  All CAN message rules passed\n");
    } else {
        fprintf(report, "  [FAIL] C1-C5  %d CAN coherence error(s)\n", errors);
    }
    return errors;
}

int EEC_Verify_architecture(const EEC_Architecture_t *arch, FILE *report)
{
    uint32_t i, j, k;
    int errors = 0;
    int check_errors;
    int warnings = 0;
    int checks_passed = 0;
    int checks_failed = 0;
    if (!arch || !report) {
        return -1;
    }

    fprintf(report, "========================================================================\n");
    fprintf(report, "  E/E Architect Design — Architecture Verification Report\n");
    fprintf(report, "========================================================================\n");
    fprintf(report, "Name:     %s\n", arch->name);
    fprintf(report, "ECUs:     %u\n", arch->ecu_count);
    fprintf(report, "Systems:  %u\n", arch->system_count);
    fprintf(report, "Signals:  %u\n", arch->signal_count);
    fprintf(report, "Buses:    %u\n", arch->bus_count);
    fprintf(report, "\n");
    fprintf(report, "Checks performed:\n");
    fprintf(report, "  V1  Global duplicate CAN address detection\n");
    fprintf(report, "  V2  ECU pin occupied/signal consistency\n");
    fprintf(report, "  V3  ECU pin identity uniqueness (connector+number)\n");
    fprintf(report, "  V4  Differential pair validation (CAN/ETH/LIN)\n");
    fprintf(report, "  V5  Signal-to-ECU mapping completeness\n");
    fprintf(report, "  V6  Duplicate signal assignment detection\n");
    fprintf(report, "  V7  Role compatibility (device pin vs ECU pin)\n");
    fprintf(report, "  V8  Electrical capability matching\n");
    fprintf(report, "  V9  Pull resistor requirement check\n");
    fprintf(report, "  V10 Diagnostics requirement coverage\n");
    fprintf(report, "  V11 Current overload detection (nominal + inrush)\n");
    fprintf(report, "  V12 Ground class mixing prevention\n");
    fprintf(report, "  V13 Safety-relevant signal diagnostic coverage\n");
    fprintf(report, "  B1  Bus port index within ECU capacity\n");
    fprintf(report, "  B2  ECU port not shared across buses\n");
    fprintf(report, "  B3  Signal interface matches bus type\n");
    fprintf(report, "  B4  No duplicate ECU port on same bus\n");
    fprintf(report, "  B5  CAN/ISOBUS node count <= 32\n");
    fprintf(report, "  B6  Unique CAN addresses per bus\n");
    fprintf(report, "  B7  Bus-type signals assigned to a bus\n");
    fprintf(report, "  B8  Bus bitrate > 0 when nodes connected\n");
    fprintf(report, "  B9  CAN busload within safe utilization (<80%%)\n");
    fprintf(report, "\n------------------------------------------------------------------------\n");
    fprintf(report, "Results:\n");
    fprintf(report, "------------------------------------------------------------------------\n");

    /* V1: Global duplicate CAN addresses */
    check_errors = 0;
    for (i = 0U; i < arch->ecu_count; ++i) {
        const EEC_Ecu_t *a = arch->ecus[i];
        for (j = 0U; a && j < a->can_address_count; ++j) {
            for (k = i + 1U; k < arch->ecu_count; ++k) {
                const EEC_Ecu_t *b = arch->ecus[k];
                if (b && EEC_Ecu_HasCanAddress(b, a->can_addresses[j])) {
                    fprintf(report, "ERROR: duplicate CAN address 0x%02X between %s and %s\n",
                            a->can_addresses[j], a->name, b->name);
                    check_errors++;
                }
            }
        }
    }
    errors += check_errors;
    if (check_errors == 0) { fprintf(report, "  [PASS] V1  No duplicate CAN addresses across ECUs\n"); checks_passed++; }
    else { fprintf(report, "  [FAIL] V1  %d duplicate CAN address(es) found\n", check_errors); checks_failed++; }

    /* V2-V4: ECU pin consistency, uniqueness, differential pairs */
    check_errors = 0;
    for (i = 0U; i < arch->ecu_count; ++i) {
        const EEC_Ecu_t *ecu = arch->ecus[i];
        for (j = 0U; ecu && j < ecu->pin_count; ++j) {
            const EEC_EcuPin_t *pin = &ecu->pins[j];
            if (pin->is_occupied && !pin->connected_signal) {
                fprintf(report, "ERROR: occupied pin without signal: %s %s/%u\n",
                        ecu->name, pin->connector_name, pin->physical_number);
                check_errors++;
            } else if (!pin->is_occupied && pin->connected_signal) {
                fprintf(report, "ERROR: signal attached on non-occupied pin: %s %s/%u\n",
                        ecu->name, pin->connector_name, pin->physical_number);
                check_errors++;
            }
        }
        check_errors += eec_verify_ecu_pin_identity_uniqueness(ecu, report);
        check_errors += eec_verify_differential_pairs_on_ecu(ecu, report);
    }
    errors += check_errors;
    if (check_errors == 0) { fprintf(report, "  [PASS] V2  All occupied pins have signals, all signals on occupied pins\n"); checks_passed++; }
    else { fprintf(report, "  [FAIL] V2  %d ECU pin consistency error(s)\n", check_errors); checks_failed++; }

    /* V5-V9: Logical pin verification (mapping, duplicates, role, electrical, pull) */
    check_errors = 0;
    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *system = arch->systems[i];
        uint32_t c;
        if (!system) {
            continue;
        }
        for (c = 0U; c < system->component_count; ++c) {
            const EEC_Component_t *comp = system->components[c];
            if (!comp) continue;
            for (j = 0U; j < comp->sensor_count; ++j) {
                const EEC_Sensor_t *sensor = comp->sensors[j];
                if (!sensor) {
                    continue;
                }
                check_errors += eec_verify_logical_pins(arch, "sensor", sensor->name, sensor->pins, sensor->pin_count, report);
            }
            for (j = 0U; j < comp->actuator_count; ++j) {
                const EEC_Actuator_t *actuator = comp->actuators[j];
                if (!actuator) {
                    continue;
                }
                check_errors += eec_verify_logical_pins(arch, "actuator", actuator->name, actuator->pins, actuator->pin_count, report);
            }
        }
    }
    errors += check_errors;
    if (check_errors == 0) { fprintf(report, "  [PASS] V5-V9  All signal mappings valid (role, electrical, pull resistor)\n"); checks_passed++; }
    else { fprintf(report, "  [FAIL] V5-V9  %d logical pin error(s)\n", check_errors); checks_failed++; }

    /* B1-B9: Bus verification (incl. busload) */
    check_errors = eec_verify_buses(arch, report);
    errors += check_errors;
    if (check_errors == 0) { fprintf(report, "  [PASS] B1-B9  All bus rules passed\n"); checks_passed++; }
    else { fprintf(report, "  [FAIL] B1-B9  %d bus verification error(s)\n", check_errors); checks_failed++; }

    /* C1-C5: CAN message / SWC coherence */
    check_errors = eec_verify_can(arch, report);
    errors += check_errors;
    if (check_errors == 0) { fprintf(report, "  [PASS] C1-C5  All CAN message rules passed\n"); checks_passed++; }
    else { fprintf(report, "  [FAIL] C1-C5  %d CAN coherence error(s)\n", check_errors); checks_failed++; }

    fprintf(report, "\n========================================================================\n");
    fprintf(report, "SUMMARY:  %d check group(s) passed, %d failed, %d total error(s), %d warning(s)\n",
            checks_passed, checks_failed, errors, warnings);
    if (errors == 0) {
        fprintf(report, "STATUS: OK\n");
    } else {
        fprintf(report, "STATUS: FAIL with %d error(s)\n", errors);
    }
    fprintf(report, "========================================================================\n");
    return errors;
}
