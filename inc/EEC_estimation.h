/**
 * @file    EEC_estimation.h
 * @brief   E/E Architect Design — Architecture estimation from a platform selection file.
 * @author  Anadack Temtching Dassi
 * @date    2026
 *
 * Reads a platform JSON listing system Ref-2X identifiers, resolves each
 * against the component library, tallies IO requirements per signal
 * interface, and computes ECU sizing proposals (SMALL / MEDIUM / LARGE
 * only, and an optimised mixed proposition).
 */
#ifndef EEC_ESTIMATION_H
#define EEC_ESTIMATION_H

#include "EEC_architecture.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @brief Maximum number of systems that a platform file can reference. */
#define EEC_EST_MAX_SYSTEMS     64U

/** @brief Maximum number of distinct signal-interface buckets tracked.
 *
 *  MUST be >= EEC_SIGNAL_INTERFACE_RESERVED, because per_iface[] is indexed
 *  directly by the EEC_SignalInterface_t enum value (see EEC_estimation.c).
 *  Previously this was 10 while the enum has 13 usable values (DIGITAL..GROUND),
 *  causing out-of-bounds writes for FLEXRAY/POWER/GROUND pins. A compile-time
 *  assertion in EEC_estimation.c guards this invariant. */
#define EEC_EST_MAX_IFACE_TYPES 16U

/** @brief Number of AGCO ECU variants (SMALL, MEDIUM, LARGE). */
#define EEC_EST_VARIANT_COUNT   3U

/* ── Design-rule thresholds (used by the mixed-proposition algorithm) ── */

/** @brief Signal threshold above which a safety-critical system gets a LARGE ECU. */
#define EEC_EST_SAFETY_THRESHOLD_SIGNALS   100U

/** @brief Signal threshold above which a high-priority system gets a LARGE ECU. */
#define EEC_EST_HIGHPRI_THRESHOLD_SIGNALS   80U

/** @brief Maximum fill-percentage for shared SMALL ECUs (R4: 40-70%). */
#define EEC_EST_SHARE_FILL_PCT              70U

/** @brief IO demand for one signal interface type. */
typedef struct EEC_IoCount_s {
    EEC_SignalInterface_t interface_type;  /**< Interface enum value. */
    uint32_t input_count;                 /**< Signals with role INPUT. */
    uint32_t output_count;                /**< Signals with role OUTPUT. */
    uint32_t inout_count;                 /**< Signals with role INOUT. */
    uint32_t total;                       /**< input + output + inout. */
} EEC_IoCount_t;

/** @brief IO summary for one system. */
typedef struct EEC_SystemIo_s {
    char name[64];                            /**< System name from library. */
    char ref_2x[64];                          /**< Ref-2X identifier. */
    bool found_in_library;                    /**< True if resolved successfully. */
    EEC_IoCount_t per_iface[EEC_EST_MAX_IFACE_TYPES]; /**< IO count per interface. */
    uint32_t iface_count;                     /**< Number of used interface buckets. */
    uint32_t total_signals;                   /**< Grand total signal count. */
} EEC_SystemIo_t;

/** @brief Pin capacity of one ECU variant per interface type. */
typedef struct EEC_EcuCapacity_s {
    char variant[16];                         /**< "SMALL", "MEDIUM", "LARGE". */
    uint32_t per_iface[EEC_EST_MAX_IFACE_TYPES]; /**< Available pins per interface. */
    uint32_t total_pins;                      /**< Grand total usable pins. */
} EEC_EcuCapacity_t;

/** @brief ECU count estimation for one variant used exclusively. */
typedef struct EEC_EcuEstimate_s {
    char variant[16];                         /**< Variant label. */
    uint32_t ecu_count;                       /**< Number of ECUs required. */
    uint32_t total_pins_available;            /**< Total pin capacity. */
    uint32_t total_pins_used;                 /**< Pins consumed by signals. */
    float    utilisation_pct;                 /**< Utilisation percentage. */
} EEC_EcuEstimate_t;

/** @brief One ECU in the optimised mixed proposition. */
typedef struct EEC_ProposedEcu_s {
    char variant[16];                         /**< SMALL / MEDIUM / LARGE. */
    char assigned_systems[256];               /**< Comma-separated system names. */
    uint32_t pins_used;                       /**< Pins consumed. */
    uint32_t pins_total;                      /**< Total pins on this ECU. */
    float    utilisation_pct;                 /**< Utilisation percentage. */
} EEC_ProposedEcu_t;

/** @brief Maximum ECUs in a mixed proposition. */
#define EEC_EST_MAX_PROPOSED_ECUS 16U

/** @brief Full estimation result. */
typedef struct EEC_EstimationResult_s {
    char platform_name[128];                  /**< Platform file identifier. */

    /* System IO demand */
    EEC_SystemIo_t systems[EEC_EST_MAX_SYSTEMS]; /**< Per-system IO breakdown. */
    uint32_t system_count;                    /**< Total systems requested. */
    uint32_t systems_found;                   /**< Systems resolved from library. */
    uint32_t systems_missing;                 /**< Systems not found. */

    /* Architecture-level IO totals */
    EEC_IoCount_t arch_io[EEC_EST_MAX_IFACE_TYPES]; /**< Aggregate IO per interface. */
    uint32_t arch_iface_count;                /**< Used interface buckets. */
    uint32_t arch_total_signals;              /**< Grand total signals. */

    /* ECU variant capacities (for reference) */
    EEC_EcuCapacity_t capacities[EEC_EST_VARIANT_COUNT]; /**< SMALL, MEDIUM, LARGE. */

    /* Homogeneous ECU estimates (one per variant, same order as capacities[]) */
    EEC_EcuEstimate_t estimates[EEC_EST_VARIANT_COUNT];  /**< All-SMALL, All-MEDIUM, All-LARGE. */

    /* Optimised mixed proposition */
    EEC_ProposedEcu_t proposed[EEC_EST_MAX_PROPOSED_ECUS]; /**< Mixed ECU list. */
    uint32_t proposed_count;                  /**< Number of proposed ECUs. */
    char proposition_notes[512];              /**< Design rationale summary. */
} EEC_EstimationResult_t;

/** @brief Run the full estimation pipeline.
 *
 *  Reads the platform file, scans the library folder for matching systems,
 *  counts IO demand, computes ECU sizing, and writes a JSON result file.
 *
 *  @param platform_path  Path to the platform JSON file.
 *  @param library_dir    Path to the library root folder (e.g. "library").
 *  @param output_json    Path for the estimation result JSON output.
 *  @return 0 on success, negative on error.
 */
int EEC_Estimation_Run(const char *platform_path,
                       const char *library_dir,
                       const char *output_json);

#ifdef __cplusplus
}
#endif
#endif
