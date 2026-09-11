/**
 * @file    EEC_connect.h
 * @brief   E/E Architect Design — Automatic signal-to-ECU routing helpers.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#ifndef EEC_CONNECT_H
#define EEC_CONNECT_H

#include "EEC_architecture.h"
#include <stdio.h>

#ifdef __cplusplus
extern "C" {
#endif

/** @brief Optional strict routing rule for one signal name. */
typedef struct EEC_StrictSignalRule_s {
    const char *signal_name;             /**< Target signal name. */
    const char *preferred_connector;     /**< Preferred connector name or NULL. */
    const char *required_pin_function;   /**< Required pin function or NULL. */
    uint32_t required_diagnostic_flags;  /**< Required diagnostic bits or zero. */
} EEC_StrictSignalRule_t;

/** @brief Strict connection policy shared by all rules. */
typedef struct EEC_StrictConnectPolicy_s {
    const EEC_StrictSignalRule_t *rules;  /**< Array of per-signal rules. */
    uint32_t rule_count;                 /**< Number of rules. */
    bool prefer_same_ecu;                /**< Prefer first successful ECU afterwards. */
    bool require_all_signals;            /**< Return -1 if one signal cannot be connected. */
    bool verbose_trace;                  /**< Emit verbose trace lines. */
} EEC_StrictConnectPolicy_t;

/** @brief Connect each signal in one system to the first compatible free ECU pin.
 *  @param system System whose device pins provide the logical signals to route.
 *  @param ecus Array of ECU pointers that offer routing resources.
 *  @param ecu_count Number of entries in @p ecus.
 *  @param trace Optional trace stream receiving one line per successful mapping.
 *  @return Number of connected signals, or -1 on invalid input.
 */
int EEC_System_connect_to_ecus(EEC_System_t *system, EEC_Ecu_t *const *ecus, uint32_t ecu_count, FILE *trace);

/** @brief Connect each signal in one system using rule-based scoring and filtering.
 *  @param system System whose device pins provide the logical signals to route.
 *  @param ecus Array of ECU pointers that offer routing resources.
 *  @param ecu_count Number of entries in @p ecus.
 *  @param policy Optional strict-routing policy controlling scoring and mandatory constraints.
 *  @param trace Optional trace stream receiving success and failure lines.
 *  @return Number of connected signals, or -1 when input is invalid or a mandatory signal fails.
 */
int EEC_System_connect_to_ecus_strict(EEC_System_t *system, EEC_Ecu_t *const *ecus, uint32_t ecu_count, const EEC_StrictConnectPolicy_t *policy, FILE *trace);

/** @brief Map all signals of a system to a single specified ECU.
 *
 *  Iterates over all sensor and actuator device pins in the system's active
 *  variant and options.  For each signal, finds a free ECU pin that matches
 *  the required interface, role, and electrical capability.
 *
 *  @param system System whose device pins provide the logical signals to route.
 *  @param ecu    Target ECU to map signals onto.
 *  @param trace  Optional trace stream receiving one line per mapping attempt.
 *  @return Number of successfully mapped signals, or -1 on invalid input.
 *          Signals that cannot be mapped (no compatible free pin) are skipped
 *          and reported in the trace stream.
 */
int EEC_System_MapToEcu(EEC_System_t *system, EEC_Ecu_t *ecu, FILE *trace);

/** @brief Auto-map all unmapped systems in the architecture to available ECUs.
 *
 *  Iterates every system in the architecture. For each system that still has
 *  unmapped signals, calls EEC_System_connect_to_ecus to route them to the
 *  first compatible free pin across the given ECU array.
 *  Systems that are already fully mapped are skipped.
 *
 *  @param arch      Architecture containing the systems to map.
 *  @param ecus      Array of ECU pointers offering pin resources.
 *  @param ecu_count Number of entries in @p ecus.
 *  @param trace     Optional trace stream for per-system logging.
 *  @return Total number of newly mapped signals, or -1 on invalid input.
 */
int EEC_Architecture_AutoMapAll(EEC_Architecture_t *arch, EEC_Ecu_t *const *ecus, uint32_t ecu_count, FILE *trace);

/** @brief Smart auto-map: maps all unmapped systems sorted by priority score.
 *
 *  System priority scoring (highest mapped first):
 *    1. Mandatory systems (is_mandatory = true)
 *    2. Highest take rate (% of vehicles needing this system)
 *    3. Highest priority (CRITICAL > HIGH > MEDIUM > LOW)
 *    4. Highest required AgPL level (safety integrity — ISO 25119)
 *    5. Highest system level (SL4 > SL3 > SL2 > SL1)
 *    6. Interface diversity (more distinct interface types = harder to fit later)
 *    7. Most physical interfaces (pin count)
 *
 *  ECU list is used in the order provided by the caller. The caller is
 *  responsible for choosing and ordering ECUs (e.g. zone-specific ECU for
 *  cabin systems, safety-rated ECU for critical systems, etc.).
 *
 *  @param arch      Architecture containing the systems to map.
 *  @param ecus      Array of ECU pointers offering pin resources (order matters).
 *  @param ecu_count Number of entries in @p ecus.
 *  @param trace     Optional trace stream for detailed per-system logging.
 *  @return Total number of newly mapped signals, or -1 on invalid input.
 */
int EEC_Architecture_AutoMapSmart(EEC_Architecture_t *arch, EEC_Ecu_t *const *ecus, uint32_t ecu_count, FILE *trace);

/** @brief Enable or disable automatic signal mapping for a system.
 *  When enabled, the system is eligible for auto-mapping by
 *  EEC_Architecture_AutoMapAll and EEC_Architecture_AutoMapSmart.
 *  @param system The target system.
 *  @param enable True to enable, false to disable.
 */
void EEC_System_EnableAutoMapping(EEC_System_t *system, bool enable);

/** @brief Runtime-selectable IO mapping strategy. */
typedef enum EEC_MapStrategy_e {
    EEC_MAP_STRATEGY_SMART = 0, /**< Score-sorted 7-tier mapping (default). */
    EEC_MAP_STRATEGY_ORDER,     /**< Registration-order, no scoring. */
    EEC_MAP_STRATEGY_ZONE,      /**< Per-system relaxed first-fit routing. */
    EEC_MAP_STRATEGY_STRICT     /**< Per-signal scored/strict routing. */
} EEC_MapStrategy_t;

/** @brief Canonical name of a strategy ("SMART"|"ORDER"|"ZONE"|"STRICT"). */
const char *EEC_MapStrategy_ToString(EEC_MapStrategy_t strategy);

/** @brief Parse a strategy name (case-insensitive).
 *  @param name "smart"|"order"|"zone"|"strict", or NULL/unknown.
 *  @return Matching strategy, or EEC_MAP_STRATEGY_SMART when NULL/unrecognised.
 */
EEC_MapStrategy_t EEC_MapStrategy_FromString(const char *name);

/** @brief Auto-map the whole architecture using a runtime-selected strategy.
 *  Dispatches to the existing mapping routines without changing their behaviour.
 *  @param arch      Architecture containing the systems to map.
 *  @param ecus      Array of ECU pointers offering pin resources (order matters).
 *  @param ecu_count Number of entries in @p ecus.
 *  @param strategy  Strategy to apply.
 *  @param trace     Optional trace stream for detailed per-system logging.
 *  @return Total number of newly mapped signals, or -1 on invalid input.
 */
int EEC_Architecture_AutoMap(EEC_Architecture_t *arch, EEC_Ecu_t *const *ecus,
                             uint32_t ecu_count, EEC_MapStrategy_t strategy, FILE *trace);

#ifdef __cplusplus
}
#endif
#endif
