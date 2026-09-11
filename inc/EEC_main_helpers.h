/**
 * @file    EEC_main_helpers.h
 * @brief   E/E Architect Design — Application-level setup helpers.
 *
 * Utility types and functions used by the main application entry point to
 * import ECUs, systems and buses from the JSON library.  Extracted here so
 * that main.c contains only high-level orchestration logic and is easy to
 * read as framework documentation.
 *
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#ifndef EEC_MAIN_HELPERS_H
#define EEC_MAIN_HELPERS_H

#include <stddef.h>
#include <stdio.h>
#include "EEC_architecture.h"

#ifdef __cplusplus
extern "C" {
#endif

/* =========================================================================
 * Descriptor types — used to declare import tables as static const arrays
 * ========================================================================= */

/**
 * @brief One row in a system-import table.
 *
 * Pass an array of these to import_library_systems() to bulk-import
 * systems from the JSON library with a single call.
 */
typedef struct LibrarySystemImport_s {
    const char *path;   /**< Relative path to the .eec-system-1.x.json file. */
    const char *label;  /**< Human-readable label used in log messages.       */
} LibrarySystemImport_t;

/**
 * @brief One row in an ECU-import table.
 *
 * Pass an array of these to import_library_ecus() to bulk-import ECUs
 * from the JSON library and assign instance names in a single call.
 */
typedef struct LibraryEcuImport_s {
    const char *path;           /**< Relative path to the .json ECU file.          */
    const char *instance_name;  /**< Unique instance name assigned at runtime.      */
} LibraryEcuImport_t;

/* =========================================================================
 * File-system helpers
 * ========================================================================= */

/**
 * @brief Return 1 if the file at @p path can be opened for reading, 0 otherwise.
 *
 * Used to give a meaningful warning before attempting an import that would
 * silently fail inside the library functions.
 *
 * @param path  File path to test (may be NULL — returns 0).
 * @return      1 if the file exists and is readable, 0 otherwise.
 */
int path_exists(const char *path);

/**
 * @brief Create @p path as a directory if it does not already exist.
 *
 * Calls _mkdir (Windows) or mkdir with mode 0775 (POSIX).  A pre-existing
 * directory is silently accepted; any other error prints a warning to stderr.
 *
 * @param path  Directory path to create (may be NULL — no-op).
 */
void make_dir_if_missing(const char *path);

/**
 * @brief Join two path components into @p out, inserting the platform separator.
 *
 * If @p a already ends with '/' or '\\' no extra separator is added.
 * Writes at most @p out_size bytes including the NUL terminator.
 *
 * @param out       Destination buffer.
 * @param out_size  Size of @p out in bytes.
 * @param a         Left path component (may be NULL — treated as "").
 * @param b         Right path component (may be NULL — treated as "").
 */
void join_path(char *out, size_t out_size, const char *a, const char *b);

/* =========================================================================
 * Bulk-import helpers
 * ========================================================================= */

/**
 * @brief Import all ECUs listed in @p ecu_imports into @p arch.
 *
 * For each entry:
 *   - Checks that the file exists (prints a warning and skips if not).
 *   - Calls EEC_Library_ImportEcu() with the given instance name.
 *   - Stores the returned pointer in @p ecus[imported].
 *   - Prints a confirmation line to stdout on success.
 *
 * Stops early if @p ecu_capacity is reached (excess entries are silently
 * skipped).
 *
 * @param arch             Target architecture.
 * @param ecu_imports      Descriptor array; each entry has a path and instance name.
 * @param ecu_import_count Number of entries in @p ecu_imports.
 * @param ecus             Caller-supplied pointer array, populated on return.
 * @param ecu_capacity     Maximum number of ECU pointers @p ecus can hold.
 * @return                 Number of ECUs successfully imported (0 on empty input).
 */
unsigned int import_library_ecus(EEC_Architecture_t        *arch,
                                 const LibraryEcuImport_t  *ecu_imports,
                                 size_t                     ecu_import_count,
                                 EEC_Ecu_t                **ecus,
                                 size_t                     ecu_capacity);

/**
 * @brief Import all systems listed in @p systems into @p arch.
 *
 * For each entry:
 *   - Checks that the file exists (prints a warning and skips if not).
 *   - Calls EEC_Library_ImportSystem() to populate the architecture.
 *   - Prints a confirmation line to stdout on success.
 *
 * @param arch         Target architecture.
 * @param systems      Descriptor array; each entry has a path and a label.
 * @param system_count Number of entries in @p systems.
 * @return             Number of systems successfully imported (0 on empty input).
 */
unsigned int import_library_systems(EEC_Architecture_t          *arch,
                                    const LibrarySystemImport_t *systems,
                                    size_t                       system_count);

/* =========================================================================
 * Bus setup helper
 * ========================================================================= */

/**
 * @brief Create the tractor's seven communication buses and wire ECUs/signals.
 *
 * Creates and connects, by ECU instance name:
 *
 *   1. Tractor_Bus           CAN      250 kbit/s  vehicle-wide backbone, all ECUs
 *   2. Powertrain_Engine_Bus CAN      500 kbit/s  AEC_ENGINE_01, AEC_TRANSMISSION_01
 *   3. ISOBUS                ISOBUS   250 kbit/s  AEC_REAR_HITCH_01, AEC_TRAILER_01
 *   4. Diagnostic_OBD_Bus    CAN      500 kbit/s  AEC_CABIN_01, AEC_ENGINE_01
 *   5. Hydraulics_Bus        CAN      250 kbit/s  AEC_REAR_HITCH_01, AEC_TRANSMISSION_01
 *   6. LIN_Bus                LIN      19.2 kbit/s AEC_CABIN_01, AEC_REAR_HITCH_01
 *   7. Ethernet_Bus           ETHERNET 100 Mbit/s  all ECUs
 *
 * Per-ECU port indices are chosen so no ECU exceeds its physical CAN port
 * count and no (ECU, port) pair is reused across buses (required because
 * EEC_Bus_ConnectEcu() tracks port occupancy per ECU across the whole
 * architecture, not per bus type). ECUs absent from @p ecus are skipped.
 *
 * System signals are routed by domain: systems whose name matches the
 * hydraulic domain (HYDAC/Hydraulic/Coil) go on Hydraulics_Bus, all other
 * systems go on Tractor_Bus; LIN_Bus and Ethernet_Bus pick up any
 * LIN/Ethernet-interface signals from every system (none exist in the
 * library yet, so this is forward-looking).
 *
 * @param arch      Target architecture.
 * @param ecus      Array of imported ECU pointers.
 * @param ecu_count Number of entries in @p ecus.
 * @return          Total number of signals connected across all buses, or -1 on error.
 */
int configure_vehicle_buses(EEC_Architecture_t *arch,
                            EEC_Ecu_t *const   *ecus,
                            unsigned int        ecu_count);

#ifdef __cplusplus
}
#endif
#endif /* EEC_MAIN_HELPERS_H */
