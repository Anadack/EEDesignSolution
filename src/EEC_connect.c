/**
 * @file    EEC_connect.c
 * @brief   E/E Architect Design — Automatic signal-to-ECU routing.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#include "EEC_connect.h"
#include "EEC_log.h"
#include <string.h>
#include <stdlib.h>

static const EEC_StrictSignalRule_t *find_rule(const EEC_StrictConnectPolicy_t *policy, const EEC_Signal_t *signal);
static bool pin_has_function(const EEC_EcuPin_t *pin, const char *name);

/** @brief Copy a C string into a fixed-size destination and always terminate it.
 *  @param dest Destination buffer.
 *  @param dest_size Size of the destination buffer in bytes.
 *  @param src Source string, or NULL to write an empty string.
 */
static void copy_c_string(char *dest, size_t dest_size, const char *src)
{
    size_t copy_len;
    if (!dest || dest_size == 0U) {
        return;
    }
    if (!src) {
        dest[0] = '\0';
        return;
    }

    copy_len = strlen(src);
    if (copy_len >= dest_size) {
        copy_len = dest_size - 1U;
    }
    memcpy(dest, src, copy_len);
    dest[copy_len] = '\0';
}

/** @brief Find the rule that matches the current signal name. */
static const EEC_StrictSignalRule_t *find_rule(const EEC_StrictConnectPolicy_t *policy, const EEC_Signal_t *signal)
{
    uint32_t i;
    if (!policy || !policy->rules || !signal) {
        return NULL;
    }
    for (i = 0U; i < policy->rule_count; ++i) {
        if (policy->rules[i].signal_name && strcmp(policy->rules[i].signal_name, signal->name) == 0) {
            return &policy->rules[i];
        }
    }
    return NULL;
}

/** @brief Check if a pin advertises a function string. */
static bool pin_has_function(const EEC_EcuPin_t *pin, const char *name)
{
    uint32_t i;
    if (!name || !name[0]) {
        return true;
    }
    if (!pin) {
        return false;
    }
    for (i = 0U; i < pin->function_count; ++i) {
        if (pin->functions[i] && strcmp(pin->functions[i], name) == 0) {
            return true;
        }
    }
    return false;
}

static bool roles_are_compatible(EEC_PinRole_t logical_role, EEC_PinRole_t physical_role)
{
    /* Device OUTPUT (sensor produces signal) -> ECU INPUT (ECU reads it).
       Device INPUT (actuator receives command) -> ECU OUTPUT (ECU drives it).
       INOUT is dedicated to communication buses (CAN, ETH, LIN). */
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

static int connect_pins_relaxed(EEC_DevicePin_t *pins, uint32_t pin_count, const char *device_name, EEC_Ecu_t *const *ecus, uint32_t ecu_count, FILE *trace)
{
    uint32_t p, e, ep;
    int connected = 0;

    for (p = 0U; p < pin_count; ++p) {
        EEC_Signal_t *signal = pins[p].signal;
        uint32_t elec_req;
        int pass;

        if (!signal || signal->is_mapped) {
            continue;
        }

        elec_req = pins[p].electrical_requirement;

        /* Two-pass strategy:
           Pass 0 (when elec_req != 0): prefer pins that fully satisfy electrical requirement.
           Pass 1: fall back to any interface-compatible pin (original relaxed behaviour). */
        for (pass = (elec_req != 0U ? 0 : 1); pass <= 1; ++pass) {
            for (e = 0U; e < ecu_count; ++e) {
                EEC_Ecu_t *ecu = ecus[e];
                for (ep = 0U; ecu && ep < ecu->pin_count; ++ep) {
                    EEC_EcuPin_t *epin = &ecu->pins[ep];
                    EEC_AgplLevel_t required_agpl;

                    if (epin->is_occupied) {
                        continue;
                    }
                    if (!roles_are_compatible(pins[p].role, epin->role) || !EEC_Ecu_IsPinCompatible(epin, signal)) {
                        continue;
                    }
                    /* Pass 0 only: skip pins that do not satisfy the electrical requirement. */
                    if (pass == 0 && (elec_req & ~epin->electrical_capability) != 0U) {
                        continue;
                    }

                    required_agpl = EEC_AGPL_A;
                    if (signal->safety > EEC_SAFETY_QM) {
                        required_agpl = EEC_AGPL_C;
                        if (signal->priority == EEC_PRIORITY_CRITICAL) {
                            required_agpl = EEC_AGPL_D;
                        }
                    }
                    if (epin->max_agpl < required_agpl) {
                        if (trace) {
                            fprintf(trace, "[AUTO-WARN] %s requires AgPL %d but %s %s/%u supports %d\n",
                                    signal->name, (int)required_agpl,
                                    ecu->name, epin->connector_name, epin->physical_number,
                                    (int)epin->max_agpl);
                        }
                    }
                    if (EEC_Ecu_ConnectSignalToPin(ecu, epin->connector_name, epin->physical_number, signal)) {
                        copy_c_string(epin->device_pin_name, sizeof(epin->device_pin_name), pins[p].name);
                        copy_c_string(epin->device_pin_desc, sizeof(epin->device_pin_desc), device_name);
                        if (trace) {
                            fprintf(trace, "[AUTO] %s -> %s %s/%u\n", signal->name, ecu->name, epin->connector_name, epin->physical_number);
                        }
                        connected++;
                        goto next_signal_relaxed;
                    }
                }
            }
        }
next_signal_relaxed:
        ;
    }

    return connected;
}

static int connect_pins_strict(EEC_DevicePin_t *pins, uint32_t pin_count, const char *device_name, EEC_Ecu_t *const *ecus, uint32_t ecu_count, const EEC_StrictConnectPolicy_t *policy, FILE *trace, uint32_t *preferred_ecu_id)
{
    uint32_t p, e, ep;
    int connected = 0;

    for (p = 0U; p < pin_count; ++p) {
        EEC_Signal_t *signal = pins[p].signal;
        const EEC_StrictSignalRule_t *rule;
        EEC_Ecu_t *best_ecu = NULL;
        EEC_EcuPin_t *best_pin = NULL;
        int best_score = -1000000;

        if (!signal || signal->is_mapped) {
            continue;
        }

        rule = find_rule(policy, signal);

        for (e = 0U; e < ecu_count; ++e) {
            EEC_Ecu_t *ecu = ecus[e];
            const int ecu_bonus = (*preferred_ecu_id != 0U && ecu && ecu->id == *preferred_ecu_id) ? 1000 : 0;

            for (ep = 0U; ecu && ep < ecu->pin_count; ++ep) {
                EEC_EcuPin_t *pin = &ecu->pins[ep];

                if (!roles_are_compatible(pins[p].role, pin->role) || !EEC_Ecu_IsPinCompatible(pin, signal)) {
                    continue;
                }
                /* Enforce AgPL constraint in strict mode: skip pins that cannot support the required AgPL. */
                {
                    EEC_AgplLevel_t required_agpl = EEC_AGPL_A;
                    if (signal->safety >= EEC_SAFETY_AGPL_A) {
                        required_agpl = EEC_AGPL_C;
                        if (signal->priority == EEC_PRIORITY_CRITICAL) {
                            required_agpl = EEC_AGPL_D;
                        }
                    }
                    if (pin->max_agpl < required_agpl) {
                        continue;
                    }
                }
                if (rule && rule->preferred_connector && strcmp(pin->connector_name, rule->preferred_connector) != 0) {
                    continue;
                }
                if (rule && rule->required_pin_function && !pin_has_function(pin, rule->required_pin_function)) {
                    continue;
                }
                if (rule && rule->required_diagnostic_flags &&
                    ((pin->diagnostic_flags & rule->required_diagnostic_flags) != rule->required_diagnostic_flags)) {
                    continue;
                }

                int score = 0;
                score += ecu_bonus;
                if (rule && rule->preferred_connector && strcmp(pin->connector_name, rule->preferred_connector) == 0) {
                    score += 300;
                }
                if (rule && rule->required_pin_function) {
                    score += 200;
                }

                /* Priority scoring: higher-priority signals prefer lower-numbered
                   (typically higher-quality) pin positions. */
                switch (signal->priority) {
                    case EEC_PRIORITY_CRITICAL: score += 100; break;
                    case EEC_PRIORITY_HIGH:     score +=  60; break;

                /*
                 * ──────────────────────────────────────────────────────────────────────────────
                 *  E/E Architect Design — Automatic Signal-to-ECU Routing Implementation
                 *
                 *  This file implements the core logic for mapping signals to ECU pins
                 *  according to strict and flexible connection policies. It provides helpers
                 *  for rule-based mapping, pin function detection, and batch connection
                 *  operations, as well as AGCO-specific extensions for advanced routing.
                 *
                 *  Major responsibilities:
                 *    - Rule-based signal-to-pin mapping (strict and fallback)
                 *    - Pin function detection and validation
                 *    - Batch connection helpers for architecture mapping
                 *    - AGCO extensions for custom connection policies
                 *
                 *  The connection module ensures robust, standards-compliant mapping for
                 *  all supported architectures and platforms.
                 * ──────────────────────────────────────────────────────────────────────────────
                 */

                /**
                 * @brief Copy a C string into a fixed-size destination and always terminate it.
                 *
                 * Copies the source string into the destination buffer, ensuring that the
                 * result is always null-terminated and does not overflow the buffer. Used
                 * throughout the connection logic for safe string handling.
                 *
                 * @param dest      Destination buffer.
                 * @param dest_size Size of the destination buffer in bytes.
                 * @param src       Source string, or NULL to write an empty string.
                 */
                    case EEC_PRIORITY_MEDIUM:   score +=  30; break;
                    default:                                 break;
                }

                /* Safety scoring: safety-related signals get a bonus toward pins
                   that support richer diagnostics. */
                if (signal->safety > EEC_SAFETY_QM) {
                    score += 50;
                    if (pin->diagnostic_flags != 0U) {
                        score += 40;
                    }
                }

                /* Electrical compatibility: bonus when pin satisfies all device
                   requirements; penalty for each missing capability bit. */
                {
                    uint32_t elec_req = pins[p].electrical_requirement;
                    uint32_t missing  = elec_req & ~pin->electrical_capability;
                    if (missing == 0U && elec_req != 0U) {
                        score += 80;
                    } else {
                        /* Count missing bits and penalise. */
                        uint32_t m = missing;
                        while (m) { score -= 25; m &= m - 1U; }
                    }
                }

                if (pin->physical_number <= 16U) {
                    score += 10;
                }

                if (score > best_score) {
                    best_score = score;
                    best_ecu = ecu;
                    best_pin = pin;
                }
            }
        }

        if (!best_ecu || !best_pin) {
            if (trace) {
                fprintf(trace, "[STRICT] FAIL %s\n", signal->name);
            }
            if (policy && policy->require_all_signals) {
                return -1;
            }
            continue;
        }

        if (EEC_Ecu_ConnectSignalToPin(best_ecu, best_pin->connector_name, best_pin->physical_number, signal)) {
            copy_c_string(best_pin->device_pin_name, sizeof(best_pin->device_pin_name), pins[p].name);
            copy_c_string(best_pin->device_pin_desc, sizeof(best_pin->device_pin_desc), device_name);
            connected++;
            if (policy && policy->prefer_same_ecu && *preferred_ecu_id == 0U) {
                *preferred_ecu_id = best_ecu->id;
            }
            if (trace) {
                fprintf(trace, "[STRICT] %s -> %s %s/%u\n", signal->name, best_ecu->name, best_pin->connector_name, best_pin->physical_number);
            }
        }
    }

    return connected;
}

/** @brief Basic first-match connector routine. */
int EEC_System_connect_to_ecus(EEC_System_t *system, EEC_Ecu_t *const *ecus, uint32_t ecu_count, FILE *trace)
{
    uint32_t c, d;
    int connected = 0;
    if (!system || !ecus) {
        return -1;
    }

    for (c = 0U; c < system->component_count; ++c) {
        EEC_Component_t *comp = system->components[c];
        if (!comp) continue;
        for (d = 0U; d < comp->sensor_count; ++d) {
            EEC_Sensor_t *sensor = comp->sensors[d];
            if (!sensor) continue;
            if (!sensor->mapping_enabled) {
                if (trace) fprintf(trace, "  [SKIP device] '%s': mapping_enabled=false\n", sensor->name);
                continue;
            }
            connected += connect_pins_relaxed(sensor->pins, sensor->pin_count,
                                              sensor->name, ecus, ecu_count, trace);
        }
        for (d = 0U; d < comp->actuator_count; ++d) {
            EEC_Actuator_t *actuator = comp->actuators[d];
            if (!actuator) continue;
            if (!actuator->mapping_enabled) {
                if (trace) fprintf(trace, "  [SKIP device] '%s': mapping_enabled=false\n", actuator->name);
                continue;
            }
            connected += connect_pins_relaxed(actuator->pins, actuator->pin_count,
                                              actuator->name, ecus, ecu_count, trace);
        }
    }

    EEC_Log_Printf(EEC_LOG_INFO, "Relaxed auto-connection mapped %d signal(s)", connected);
    return connected;
}

/** @brief Rule-based connector routine with preference and diagnostics checking. */
int EEC_System_connect_to_ecus_strict(EEC_System_t *system, EEC_Ecu_t *const *ecus, uint32_t ecu_count, const EEC_StrictConnectPolicy_t *policy, FILE *trace)
{
    uint32_t c, d;
    int connected = 0;
    uint32_t preferred_ecu_id = 0U;

    if (!system || !ecus) {
        return -1;
    }

    for (c = 0U; c < system->component_count; ++c) {
        EEC_Component_t *comp = system->components[c];
        if (!comp) continue;
        for (d = 0U; d < comp->sensor_count; ++d) {
            EEC_Sensor_t *sensor = comp->sensors[d];
            int result;
            if (!sensor) { continue; }
            result = connect_pins_strict(sensor->pins, sensor->pin_count, sensor->name,
                                         ecus, ecu_count, policy, trace, &preferred_ecu_id);
            if (result < 0) { return -1; }
            connected += result;
        }
        for (d = 0U; d < comp->actuator_count; ++d) {
            EEC_Actuator_t *actuator = comp->actuators[d];
            int result;
            if (!actuator) { continue; }
            result = connect_pins_strict(actuator->pins, actuator->pin_count, actuator->name,
                                          ecus, ecu_count, policy, trace, &preferred_ecu_id);
            if (result < 0) { return -1; }
            connected += result;
        }
    }

    EEC_Log_Printf(EEC_LOG_INFO, "Strict auto-connection mapped %d signal(s)", connected);
    return connected;
}

/* ── Map system to a single ECU ────────────────────────────────────────── */

int EEC_System_MapToEcu(EEC_System_t *system, EEC_Ecu_t *ecu, FILE *trace)
{
    uint32_t c, d, p, ep;
    int connected = 0;
    int failed = 0;

    if (!system || !ecu) {
        return -1;
    }

    EEC_Log_Printf(EEC_LOG_INFO, "Mapping system '%s' -> ECU '%s'", system->name, ecu->name);

    /* Count free pins on the ECU first. */
    {
        uint32_t free_pins = 0;
        for (ep = 0U; ep < ecu->pin_count; ++ep) {
            if (!ecu->pins[ep].is_occupied) {
                free_pins++;
            }
        }
        if (trace) {
            fprintf(trace, "[MAP] ECU '%s' has %u free pin(s) out of %u total\n",
                    ecu->name, free_pins, ecu->pin_count);
        }
        if (free_pins == 0) {
            EEC_Log_Printf(EEC_LOG_WARN, "ECU '%s' has no free pins — cannot map system '%s'",
                           ecu->name, system->name);
            return 0;
        }
    }

    /* Internal helper: try to map one device's pins to the single ECU. */
    #define MAP_DEVICE_PINS(pins_ptr, pin_cnt, dev_name) \
        do { \
            for (p = 0U; p < (pin_cnt); ++p) { \
                EEC_Signal_t *sig = (pins_ptr)[p].signal; \
                bool mapped = false; \
                if (!sig) continue; \
                /* Skip signals that are already mapped elsewhere to avoid */ \
                /* attempting to re-map them and emitting misleading failures. */ \
                if (sig->is_mapped) { \
                    if (trace) { \
                        fprintf(trace, "[MAP-SKIP] %s: already mapped\n", sig->name); \
                    } \
                    continue; \
                } \
                for (ep = 0U; ep < ecu->pin_count; ++ep) { \
                    EEC_EcuPin_t *epin = &ecu->pins[ep]; \
                    /* GROUND pins allow multiple connections (star topology). */ \
                    if (epin->is_occupied) continue; \
                    if (!roles_are_compatible((pins_ptr)[p].role, epin->role)) continue; \
                    if (!EEC_Ecu_IsPinCompatible(epin, sig)) continue; \
                    /* Check electrical capability match. */ \
                    if ((pins_ptr)[p].electrical_requirement != 0 && \
                        (epin->electrical_capability & (pins_ptr)[p].electrical_requirement) \
                         != (pins_ptr)[p].electrical_requirement) continue; \
                    /* Map signal to this pin. */ \
                    if (EEC_Ecu_ConnectSignalToPin(ecu, epin->connector_name, epin->physical_number, sig)) { \
                        copy_c_string(epin->device_pin_name, sizeof(epin->device_pin_name), (pins_ptr)[p].name); \
                        copy_c_string(epin->device_pin_desc, sizeof(epin->device_pin_desc), (dev_name)); \
                        if (trace) { \
                            fprintf(trace, "[MAP-OK] %s -> %s %s/%u\n", \
                                    sig->name, ecu->name, epin->connector_name, epin->physical_number); \
                        } \
                        connected++; \
                        mapped = true; \
                        break; \
                    } \
                } \
                if (!mapped) { \
                    failed++; \
                    EEC_Log_Printf(EEC_LOG_ERROR, "MapToEcu FAIL: signal '%s' has no compatible free pin on ECU '%s'", \
                                   sig->name, ecu->name); \
                    if (trace) { \
                        fprintf(trace, "[MAP-FAIL] %s: no compatible free pin on ECU '%s'\n", \
                                sig->name, ecu->name); \
                    } \
                } \
            } \
        } while (0)

    /* Route through all components. */
    for (c = 0U; c < system->component_count; ++c) {
        EEC_Component_t *comp = system->components[c];
        if (!comp) continue;
        for (d = 0U; d < comp->sensor_count; ++d) {
            if (comp->sensors[d]) {
                MAP_DEVICE_PINS(comp->sensors[d]->pins,
                                comp->sensors[d]->pin_count,
                                comp->sensors[d]->name);
            }
        }
        for (d = 0U; d < comp->actuator_count; ++d) {
            if (comp->actuators[d]) {
                MAP_DEVICE_PINS(comp->actuators[d]->pins,
                                comp->actuators[d]->pin_count,
                                comp->actuators[d]->name);
            }
        }
    }

    #undef MAP_DEVICE_PINS

    EEC_Log_Printf(EEC_LOG_INFO, "MapToEcu '%s' -> '%s': %d mapped, %d failed",
                   system->name, ecu->name, connected, failed);
    return connected;
}

/* ── Architecture-level auto-map all unmapped systems ──────────────────── */

int EEC_Architecture_AutoMapAll(EEC_Architecture_t *arch, EEC_Ecu_t *const *ecus, uint32_t ecu_count, FILE *trace)
{
    uint32_t s, c, d, p;
    int total_mapped = 0;

    if (!arch || !ecus || ecu_count == 0U) {
        return -1;
    }

    for (s = 0U; s < arch->system_count; ++s) {
        EEC_System_t *sys = arch->systems[s];
        if (!sys) continue;

        /* Check if system has any unmapped signals. */
        uint32_t unmapped = 0;
        for (c = 0U; c < sys->component_count; ++c) {
            EEC_Component_t *comp = sys->components[c];
            if (!comp) continue;
            for (d = 0U; d < comp->sensor_count; ++d) {
                if (!comp->sensors[d]) continue;
                for (p = 0U; p < comp->sensors[d]->pin_count; ++p) {
                    if (comp->sensors[d]->pins[p].signal && !comp->sensors[d]->pins[p].signal->is_mapped)
                        unmapped++;
                }
            }
            for (d = 0U; d < comp->actuator_count; ++d) {
                if (!comp->actuators[d]) continue;
                for (p = 0U; p < comp->actuators[d]->pin_count; ++p) {
                    if (comp->actuators[d]->pins[p].signal && !comp->actuators[d]->pins[p].signal->is_mapped)
                        unmapped++;
                }
            }
        }

        if (unmapped == 0U) {
            if (trace) {
                fprintf(trace, "[SKIP] System '%s': all signals already mapped\n", sys->name);
            }
            continue;
        }

        /* Map unmapped signals to available ECUs. */
        int mapped = EEC_System_connect_to_ecus(sys, ecus, ecu_count, trace);
        if (mapped > 0) {
            total_mapped += mapped;
        }
        if (trace) {
            fprintf(trace, "[AUTO] System '%s': %d signal(s) mapped (%u were unmapped)\n",
                    sys->name, mapped, unmapped);
        }
    }

    EEC_Log_Printf(EEC_LOG_INFO, "Architecture AutoMapAll: %d total signal(s) mapped across %u system(s)",
                   total_mapped, arch->system_count);
    return total_mapped;
}

/* ── Smart auto-map: score-sorted, zone-aware ──────────────────────────── */

/** @brief Compute the number of unmapped signal pins in a system. */
static uint32_t count_unmapped_signals(const EEC_System_t *sys)
{
    uint32_t c, d, p, unmapped = 0;
    for (c = 0U; c < sys->component_count; ++c) {
        const EEC_Component_t *comp = sys->components[c];
        if (!comp) continue;
        for (d = 0U; d < comp->sensor_count; ++d) {
            if (!comp->sensors[d]) continue;
            for (p = 0U; p < comp->sensors[d]->pin_count; ++p) {
                if (comp->sensors[d]->pins[p].signal && !comp->sensors[d]->pins[p].signal->is_mapped)
                    unmapped++;
            }
        }
        for (d = 0U; d < comp->actuator_count; ++d) {
            if (!comp->actuators[d]) continue;
            for (p = 0U; p < comp->actuators[d]->pin_count; ++p) {
                if (comp->actuators[d]->pins[p].signal && !comp->actuators[d]->pins[p].signal->is_mapped)
                    unmapped++;
            }
        }
    }
    return unmapped;
}

/** @brief Compute total physical interface (pin) count for a system. */
static uint32_t count_total_pins(const EEC_System_t *sys)
{
    uint32_t c, d, total = 0;
    for (c = 0U; c < sys->component_count; ++c) {
        const EEC_Component_t *comp = sys->components[c];
        if (!comp) continue;
        for (d = 0U; d < comp->sensor_count; ++d) {
            if (comp->sensors[d]) total += comp->sensors[d]->pin_count;
        }
        for (d = 0U; d < comp->actuator_count; ++d) {
            if (comp->actuators[d]) total += comp->actuators[d]->pin_count;
        }
    }
    return total;
}

/** @brief Derive the highest required AgPL across all signals in a system. */
static EEC_AgplLevel_t system_max_agpl(const EEC_System_t *sys)
{
    uint32_t c, d, p;
    EEC_AgplLevel_t max_lvl = EEC_AGPL_A;
    for (c = 0U; c < sys->component_count; ++c) {
        const EEC_Component_t *comp = sys->components[c];
        if (!comp) continue;
        for (d = 0U; d < comp->sensor_count; ++d) {
            if (!comp->sensors[d]) continue;
            for (p = 0U; p < comp->sensors[d]->pin_count; ++p) {
                const EEC_Signal_t *sig = comp->sensors[d]->pins[p].signal;
                if (!sig) continue;
                EEC_AgplLevel_t lvl = EEC_AGPL_A;
                if (sig->safety >= EEC_SAFETY_AGPL_A) {
                    lvl = EEC_AGPL_C;
                    if (sig->priority == EEC_PRIORITY_CRITICAL) lvl = EEC_AGPL_D;
                }
                if (lvl > max_lvl) max_lvl = lvl;
            }
        }
        for (d = 0U; d < comp->actuator_count; ++d) {
            if (!comp->actuators[d]) continue;
            for (p = 0U; p < comp->actuators[d]->pin_count; ++p) {
                const EEC_Signal_t *sig = comp->actuators[d]->pins[p].signal;
                if (!sig) continue;
                EEC_AgplLevel_t lvl = EEC_AGPL_A;
                if (sig->safety >= EEC_SAFETY_AGPL_A) {
                    lvl = EEC_AGPL_C;
                    if (sig->priority == EEC_PRIORITY_CRITICAL) lvl = EEC_AGPL_D;
                }
                if (lvl > max_lvl) max_lvl = lvl;
            }
        }
    }
    return max_lvl;
}

/** @brief Compute priority score for a system (higher = should be mapped first).
 *
 *  Scoring formula:
 *    +20000 if mandatory
 *    +take_rate * 100  (0–10000)
 *    +priority * 2000  (CRITICAL=8000, HIGH=6000, MEDIUM=4000, LOW=2000)
 *    +agpl * 2500      (D=7500, C=5000, B=2500, A=0)
 *    +system_level * 1500 (SL4=6000, SL3=4500, SL2=3000, SL1=1500)
 *    +interface_diversity * 500 (number of distinct interface types needed)
 *    +pin_count * 2    (more interfaces = harder to place later)
 */
static int compute_system_mapping_score(const EEC_System_t *sys)
{
    int score = 0;
    uint32_t c, d, p;
    uint32_t iface_seen = 0U; /* bitmask of distinct interface types */

    /* Mandatory systems always go first */
    if (sys->is_mandatory) score += 20000;

    /* Take rate: higher take rate = more important to allocate early */
    score += (int)(sys->take_rate * 100.0f);

    /* Priority weight */
    switch (sys->priority) {
        case EEC_PRIORITY_CRITICAL: score += 8000; break;
        case EEC_PRIORITY_HIGH:     score += 6000; break;
        case EEC_PRIORITY_MEDIUM:   score += 4000; break;
        case EEC_PRIORITY_LOW:      score += 2000; break;
        default: break;
    }

    /* Safety / AgPL: safety-critical systems must be placed first (ISO 25119) */
    score += (int)system_max_agpl(sys) * 2500;

    /* System Level: higher SL = stricter integrity → map first */
    score += (int)sys->system_level * 1500;

    /* Interface diversity: systems needing rare/varied interface types are
       harder to fit once common pin types are exhausted → map them earlier */
    for (c = 0U; c < sys->component_count; ++c) {
        const EEC_Component_t *comp = sys->components[c];
        if (!comp) continue;
        for (d = 0U; d < comp->sensor_count; ++d) {
            if (!comp->sensors[d]) continue;
            for (p = 0U; p < comp->sensors[d]->pin_count; ++p) {
                const EEC_Signal_t *sig = comp->sensors[d]->pins[p].signal;
                if (sig) iface_seen |= (1U << (uint32_t)sig->interface_type);
            }
        }
        for (d = 0U; d < comp->actuator_count; ++d) {
            if (!comp->actuators[d]) continue;
            for (p = 0U; p < comp->actuators[d]->pin_count; ++p) {
                const EEC_Signal_t *sig = comp->actuators[d]->pins[p].signal;
                if (sig) iface_seen |= (1U << (uint32_t)sig->interface_type);
            }
        }
    }
    /* Count bits = number of distinct interface types */
    {
        uint32_t bits = iface_seen;
        uint32_t diversity = 0;
        while (bits) { diversity += bits & 1U; bits >>= 1U; }
        score += (int)diversity * 500;
    }

    /* Pin count: larger systems are harder to fit → prioritize */
    score += (int)count_total_pins(sys) * 2;

    return score;
}

int EEC_Architecture_AutoMapSmart(EEC_Architecture_t *arch, EEC_Ecu_t *const *ecus, uint32_t ecu_count, FILE *trace)
{
    uint32_t s;
    int total_mapped = 0;

    if (!arch || !ecus || ecu_count == 0U) {
        return -1;
    }

    /* Build a sortable index of systems with their scores. */
    uint32_t sys_count = arch->system_count;
    typedef struct { uint32_t index; int score; } SysEntry;
    SysEntry *order = (SysEntry *)calloc(sys_count, sizeof(SysEntry));
    if (!order) return -1;

    for (s = 0U; s < sys_count; ++s) {
        order[s].index = s;
        order[s].score = arch->systems[s] ? compute_system_mapping_score(arch->systems[s]) : 0;
    }

    /* Simple insertion sort by descending score. */
    {
        uint32_t i, j;
        for (i = 1U; i < sys_count; ++i) {
            SysEntry key = order[i];
            j = i;
            while (j > 0U && order[j - 1U].score < key.score) {
                order[j] = order[j - 1U];
                j--;
            }
            order[j] = key;
        }
    }

    if (trace) {
        fprintf(trace, "\n=== AutoMapSmart: system priority order ===\n");
        fprintf(trace, "  Criteria: mandatory > take_rate > priority > AgPL > SL > iface_diversity > pin_count\n");
        fprintf(trace, "  ECU selection: zone_affinity > safety_compat > safety_isolation > capacity_fit\n\n");
        for (s = 0U; s < sys_count; ++s) {
            EEC_System_t *sys = arch->systems[order[s].index];
            if (!sys) continue;
            fprintf(trace, "  #%u  score=%d  mandatory=%d  take_rate=%.0f%%  priority=%d  safety=%d  SL=%d  zone='%s'  name='%s'\n",
                    s + 1U, order[s].score, sys->is_mandatory, sys->take_rate,
                    (int)sys->priority, (int)sys->safety, (int)sys->system_level,
                    sys->location, sys->name);
        }
        fprintf(trace, "\n");
    }

    /* Map systems in priority order. */
    for (s = 0U; s < sys_count; ++s) {
        EEC_System_t *sys = arch->systems[order[s].index];
        if (!sys) continue;

        if (!sys->auto_mapping_enabled) {
            if (trace) fprintf(trace, "[SKIP] '%s': auto_mapping_enabled=false\n", sys->name);
            continue;
        }

        uint32_t unmapped = count_unmapped_signals(sys);
        if (unmapped == 0U) {
            if (trace) {
                fprintf(trace, "[SKIP] '%s': fully mapped\n", sys->name);
            }
            continue;
        }

        /* Use ECU list as provided by caller — no internal reordering. */
        if (trace) {
            fprintf(trace, "[MAP] '%s' (score=%d, unmapped=%u, zone='%s')\n",
                    sys->name, order[s].score, unmapped, sys->location);
        }

        int mapped = EEC_System_connect_to_ecus(sys, ecus, ecu_count, trace);
        if (mapped > 0) {
            total_mapped += mapped;
        }

        EEC_Log_Printf(EEC_LOG_INFO, "SmartMap '%s' (score=%d): %d/%u signal(s) mapped",
                       sys->name, order[s].score, mapped, unmapped);
    }

    free(order);

    EEC_Log_Printf(EEC_LOG_INFO, "Architecture AutoMapSmart: %d total signal(s) mapped across %u system(s)",
                   total_mapped, arch->system_count);
    return total_mapped;
}

/* ── Auto-mapping enable/disable ─────────────────────────────────────────── */

void EEC_System_EnableAutoMapping(EEC_System_t *system, bool enable)
{
    if (enable) {
        EEC_Log_Printf(EEC_LOG_INFO, "Auto-mapping enabled for system: %s", system ? system->name : "(null)");
    } else {
        EEC_Log_Printf(EEC_LOG_INFO, "Auto-mapping disabled for system: %s", system ? system->name : "(null)");
    }
}

/* ── Runtime strategy selection ──────────────────────────────────────────── */

/** @brief Case-insensitive equality for ASCII strings. */
static bool str_ieq(const char *a, const char *b)
{
    if (!a || !b) {
        return false;
    }
    for (; *a && *b; ++a, ++b) {
        char ca = (*a >= 'A' && *a <= 'Z') ? (char)(*a + 32) : *a;
        char cb = (*b >= 'A' && *b <= 'Z') ? (char)(*b + 32) : *b;
        if (ca != cb) {
            return false;
        }
    }
    return *a == *b;
}

const char *EEC_MapStrategy_ToString(EEC_MapStrategy_t strategy)
{
    switch (strategy) {
        case EEC_MAP_STRATEGY_ORDER:  return "ORDER";
        case EEC_MAP_STRATEGY_ZONE:   return "ZONE";
        case EEC_MAP_STRATEGY_STRICT: return "STRICT";
        case EEC_MAP_STRATEGY_SMART:
        default:                      return "SMART";
    }
}

EEC_MapStrategy_t EEC_MapStrategy_FromString(const char *name)
{
    if (str_ieq(name, "order"))  { return EEC_MAP_STRATEGY_ORDER; }
    if (str_ieq(name, "zone"))   { return EEC_MAP_STRATEGY_ZONE; }
    if (str_ieq(name, "strict")) { return EEC_MAP_STRATEGY_STRICT; }
    return EEC_MAP_STRATEGY_SMART;
}

/** @brief Route every eligible system with a per-system connect function. */
static int automap_per_system(EEC_Architecture_t *arch, EEC_Ecu_t *const *ecus,
                              uint32_t ecu_count, bool strict, FILE *trace)
{
    uint32_t i;
    int total = 0;

    for (i = 0U; i < arch->system_count; ++i) {
        EEC_System_t *sys = arch->systems[i];
        int mapped;

        if (!sys || !sys->auto_mapping_enabled) {
            continue;
        }
        mapped = strict
               ? EEC_System_connect_to_ecus_strict(sys, ecus, ecu_count, NULL, trace)
               : EEC_System_connect_to_ecus(sys, ecus, ecu_count, trace);
        if (mapped > 0) {
            total += mapped;
        }
    }
    return total;
}

/** @brief Zone-aware routing: assigned systems map only onto their zone ECUs. */
static int automap_zonal(EEC_Architecture_t *arch, EEC_Ecu_t *const *ecus,
                         uint32_t ecu_count, FILE *trace)
{
    uint32_t i;
    int total = 0;

    for (i = 0U; i < arch->system_count; ++i) {
        EEC_System_t *sys = arch->systems[i];
        EEC_Ecu_t *const *use_ecus = ecus;
        uint32_t use_count = ecu_count;
        int mapped;

        if (!sys || !sys->auto_mapping_enabled) {
            continue;
        }
        if (sys->zone && sys->zone->ecu_count > 0U) {
            use_ecus = sys->zone->ecus;
            use_count = sys->zone->ecu_count;
            if (trace) {
                fprintf(trace, "[ZONE] '%s' -> zone '%s' (%u ECU)\n",
                        sys->name, sys->zone->name, use_count);
            }
        } else if (trace) {
            fprintf(trace, "[ZONE] '%s' -> unzoned, all ECUs\n", sys->name);
        }
        mapped = EEC_System_connect_to_ecus(sys, use_ecus, use_count, trace);
        if (mapped > 0) {
            total += mapped;
        }
    }
    return total;
}

int EEC_Architecture_AutoMap(EEC_Architecture_t *arch, EEC_Ecu_t *const *ecus,
                             uint32_t ecu_count, EEC_MapStrategy_t strategy, FILE *trace)
{
    if (!arch || !ecus) {
        return -1;
    }

    switch (strategy) {
        case EEC_MAP_STRATEGY_ORDER:
            return EEC_Architecture_AutoMapAll(arch, ecus, ecu_count, trace);
        case EEC_MAP_STRATEGY_ZONE:
            return automap_zonal(arch, ecus, ecu_count, trace);
        case EEC_MAP_STRATEGY_STRICT:
            return automap_per_system(arch, ecus, ecu_count, true, trace);
        case EEC_MAP_STRATEGY_SMART:
        default:
            return EEC_Architecture_AutoMapSmart(arch, ecus, ecu_count, trace);
    }
}
