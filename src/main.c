/**
 * @file    main.c
 * @brief   E/E Architect Design — Main application entry point.
 *
 * Demonstrates the full E/E Architect Design workflow:
 *
 *  ┌─────────────────────────────────────────────────────────────────────┐
 *  │  WORKFLOW OVERVIEW                                                  │
 *  │                                                                     │
 *  │  1. Create architecture container                                   │
 *  │  2. Import ECUs     from the ECU library     (JSON → runtime)      │
 *  │  3. Import systems  from the system library  (OPTION A)            │
 *  │  4. Build a system from a component template (OPTION B)  ◄ new    │
 *  │       • System    — created programmatically                       │
 *  │       • Component — loaded from eec-component-1.0 JSON             │
 *  │       • Sensors   — each imported from individual sensor JSON      │
 *  │       • Actuators — each imported from individual actuator JSON    │
 *  │  5. Map systems to ECU pins  (choose ONE strategy below)           │
 *  │  6. Configure communication buses (Tractor/Powertrain/ISOBUS/        │
 *  │       Diagnostic/Hydraulics/LIN/Ethernet — 7 buses)                  │
 *  │  7. Verify the architecture  (21 V-rules + 8 B-rules)             │
 *  │  8. Export JSON snapshots and text reports                          │
 *  │  9. Run ECU I/O sizing estimation                                  │
 *  └─────────────────────────────────────────────────────────────────────┘
 *
 * @author  Anadack Temtching Dassi
 * @date    2026
 */

#include "EEC_architecture.h"
#include "EEC_component_loader.h"
#include "EEC_connect.h"
#include "EEC_estimation.h"
#include "EEC_export.h"
#include "EEC_library.h"
#include "EEC_log.h"
#include "EEC_main_helpers.h"
#include "EEC_message.h"
#include "EEC_dbc.h"
#include "EEC_datadict.h"
#include "EEC_swc_loader.h"
#include "EEC_verify.h"
#include "EEC_zone.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef PATH_MAX
#define PATH_MAX 1024
#endif

/* =========================================================================
 * Library import tables
 *
 * Declare ECUs and systems as static const tables so adding a new device
 * or system requires only one extra line here — nothing in main() changes.
 * ========================================================================= */

/** ECU catalogue: path → instance name assigned at runtime.
 *
 * This example demonstrates a 7-ECU distributed architecture spanning
 * multiple zones (cabin, powertrain, rear, validation). Some ECU templates
 * are instantiated multiple times with different names for zone-specific
 * variants (e.g., AEC_LARGE_01 and AEC_LARGE_02 in different rear zones) —
 * import_library_ecus() automatically remaps the CAN addresses of every
 * repeated preset so no two ECUs collide (rule V1).
 */
static const LibraryEcuImport_t k_ecus[] = {
    /* Cabin/Instrument zone */
    { "library/ecus/AEC_MEDIUM_1CAN.json",   "AEC_CABIN_01"       },
    { "library/ecus/AEC_SMALL_2CAN.json",    "AEC_DISPLAY_01"     },

    /* Powertrain zone */
    { "library/ecus/AEC_LARGE_3CAN.json",    "AEC_ENGINE_01"      },
    { "library/ecus/AEC_MEDIUM_1CAN.json",   "AEC_TRANSMISSION_01" },

    /* Rear/Hydraulic zone */
    { "library/ecus/AEC_LARGE_3CAN.json",    "AEC_REAR_HITCH_01"  },
    { "library/ecus/AEC_SMALL_2CAN.json",    "AEC_TRAILER_01"     },

    /* Validation/Test fixtures — provides generic 4-20mA CURRENT-loop input
     * pins. Without it, 6 analog current-loop sensors in the demo library
     * (HYDAC HAT1200/HDA4300/ETS4100, elobau 424A/424SD11D) have no
     * CURRENT-capable ECU pin anywhere in the architecture and are reported
     * as unmapped (rule V5) — none of the AEC_* presets expose that
     * interface. Zoned under "Rear" in library/zones.json. */
    { "library/ecus/VALIDATION_IO_ECU.json", "VALIDATION_IO_ECU"  },
};
static const size_t k_ecu_count = sizeof(k_ecus) / sizeof(k_ecus[0]);

/** System catalogue: pre-built system JSON files from the library.
 *
 * This example uses all 5 available systems, demonstrating a complete
 * tractor E/E architecture with multiple sensor and actuator networks.
 *
 * System composition:
 *   1. HYDAC_Example_Sensors       — Hydraulic pressure/position sensors
 *   2. Elobau_Example_Angle_Sensors— Steering wheel angle sensors
 *   3. HYDAC_Example_Coils         — Solenoid coils for valve control
 *   4. Bosch_Rexroth_Example_Coils — Proportional valve electronics
 *   5. BRAKE_SYSTEM                — Brake control and feedback
 */
static const LibrarySystemImport_t k_systems[] = {
    { "library/systems/HYDAC_Example_Sensors.eec-system-1.4.json",
      "HYDAC_Selected_Sensor_Examples"                                     },
    { "library/systems/Elobau_Example_Angle_Sensors.eec-system-1.4.json",
      "Example_System_with_selected_elobau_angle_sensors"                  },
    { "library/systems/HYDAC_Example_Coils.eec-system-1.4.json",
      "Hydraulic_Valve_Coil_System"                                        },
    { "library/systems/Bosch_Rexroth_Example_Coils.eec-system-1.4.json",
      "Proportional_Valve_Control_System"                                  },
    { "library/systems/BRAKE_SYSTEM.json",
      "Brake_Control_and_Monitoring_System"                                },
};
static const size_t k_system_count = sizeof(k_systems) / sizeof(k_systems[0]);

/** SWC / CAN data files: software components, variables and CAN messages are
 *  defined as data (edit the JSON to change the CAN topology). Bit layout and
 *  DLC are auto-derived; ECUs and buses are resolved by name at load time. */
static const char *const k_swc_files[] = {
    "library/swc/engine_control.swc.json",
    "library/swc/vehicle_swcs.swc.json",
};
static const size_t k_swc_file_count = sizeof(k_swc_files) / sizeof(k_swc_files[0]);

/* =========================================================================
 * main
 * ========================================================================= */

int main(void)
{
    const char *generated_doc_dir = "generated_doc";
    const char *exports_dir = "generated_doc/exports";
    const char *dbc_dir = "generated_doc/DBC";

    char arch_json_path[PATH_MAX];
    char phys_json_path[PATH_MAX];
    char automap_trace_path[PATH_MAX];
    char verify_report_path[PATH_MAX];
    char allocation_report_path[PATH_MAX];
    char estimation_json_path[PATH_MAX];

    EEC_Architecture_t *arch  = NULL;
    EEC_Ecu_t          *ecus[7];  /* Support 7 ECU instances (multi-zone) */
    unsigned int        ecu_count    = 0U;
    unsigned int        system_count = 0U;
    int                 mapped_total = 0;
    int                 verify_errors = 0;
    FILE               *trace = NULL;
    FILE               *rpt   = NULL;
    FILE               *alloc = NULL;

    /* ------------------------------------------------------------------
     * 1. Create the architecture container
     * ------------------------------------------------------------------ */
    printf("[INFO] Creating architecture...\n");
    arch = EEC_Architecture_Create("Imported Architecture");
    if (!arch) {
        fprintf(stderr, "[ERROR] EEC_Architecture_Create failed\n");
        return 1;
    }
    make_dir_if_missing(generated_doc_dir);
    make_dir_if_missing(exports_dir);
    make_dir_if_missing(dbc_dir);

    /* ------------------------------------------------------------------
     * 2. Import ECUs from the library
     * ------------------------------------------------------------------ */
    ecu_count = import_library_ecus(arch,
                                    k_ecus, k_ecu_count,
                                    ecus, sizeof(ecus) / sizeof(ecus[0]));
    if (ecu_count == 0U) {
        fprintf(stderr, "[ERROR] No ECU imported from library/ecus\n");
        EEC_Architecture_Destroy(arch);
        return 2;
    }
    printf("[OK] Imported %u ECU(s)\n", ecu_count);

    /* ------------------------------------------------------------------
     * 3. OPTION A — Import systems from pre-built system JSON files
     *
     * Each system JSON contains all sensors, actuators, connectors and
     * signal definitions in a single flat file.  Use this approach for
     * well-known, fully specified system configurations.
     * ------------------------------------------------------------------ */
    system_count = import_library_systems(arch, k_systems, k_system_count);
    if (system_count == 0U) {
        fprintf(stderr, "[ERROR] No system imported from library/systems\n");
        EEC_Architecture_Destroy(arch);
        return 3;
    }
    printf("[OK] Imported %u system(s)\n", system_count);

    /* ------------------------------------------------------------------
     * 4. OPTION B — Build systems from component templates
     *
     * The eec-component-1.0 schema groups individual sensor and actuator
     * catalogue files under a single component record. This example creates
     * two programmatic systems to augment the five pre-built systems from
     * the library, demonstrating a complete 7-ECU, 7-system architecture.
     *
     * Object hierarchy produced per system:
     *
     *   EEC_Architecture_t
     *    └── EEC_System_t          (created here with CreateSystem)
     *         └── EEC_Component_t  (loaded from JSON template)
     *              ├── EEC_Sensor_t    (multiple sensors)
     *              └── EEC_Actuator_t  (multiple actuators)
     * ------------------------------------------------------------------ */

    /* System 1: Rear Hydraulic Hitch System
     * Priority: Mandatory + High (safety-critical, high take-rate)
     * Zone: Rear/Hydraulic (AEC_REAR_HITCH_01 primary)
     */
    {
        EEC_System_t *hitch_sys = EEC_Architecture_CreateSystem(
            arch, "Rear_Hydraulic_Hitch_System");

        if (!hitch_sys) {
            fprintf(stderr, "[WARN] Could not create Rear Hitch system\n");
        } else {
            hitch_sys->is_mandatory         = true;
            hitch_sys->auto_mapping_enabled = true;
            hitch_sys->take_rate            = 100.0f;
            hitch_sys->priority             = EEC_PRIORITY_HIGH;
            hitch_sys->safety               = EEC_SAFETY_AGPL_B;
            hitch_sys->system_level         = EEC_SYSTEM_LEVEL_SL2;

            (void)EEC_System_AddPlatform(hitch_sys, "MF8S");
            (void)EEC_System_AddPlatform(hitch_sys, "Fendt900");
            (void)EEC_System_AddBrand(hitch_sys, EEC_BRAND_MASSEY_FERGUSON);
            (void)EEC_System_AddBrand(hitch_sys, EEC_BRAND_FENDT);

            printf("[OK] Created system '%s' (mandatory, high priority, safety AgPL_B)\n",
                   hitch_sys->name);

            EEC_Component_t *hitch_comp = EEC_ComponentLoader_Load(
                arch,
                hitch_sys,
                "library/components/"
                "Hydraulic_Rear_Hitch_Control.eec-component-1.0.json");

            if (!hitch_comp) {
                fprintf(stderr, "[WARN] Component template load failed\n");
            } else {
                EEC_ComponentLoader_PrintSummary(hitch_comp, stdout);
                printf("[INFO] Hitch system ready: %u sensor(s), %u actuator(s)\n",
                       hitch_comp->sensor_count, hitch_comp->actuator_count);
            }
        }
    }

    /* System 2: Cabin HVAC & Comfort System
     * Priority: Optional + Medium (convenience, moderate take-rate)
     * Zone: Cabin (AEC_CABIN_01 primary, AEC_DISPLAY_01 secondary)
     */
    {
        EEC_System_t *cabin_sys = EEC_Architecture_CreateSystem(
            arch, "Cabin_HVAC_and_Comfort_System");

        if (!cabin_sys) {
            fprintf(stderr, "[WARN] Could not create Cabin system\n");
        } else {
            cabin_sys->is_mandatory         = false;
            cabin_sys->auto_mapping_enabled = true;
            cabin_sys->take_rate            = 60.0f;
            cabin_sys->priority             = EEC_PRIORITY_MEDIUM;
            cabin_sys->safety               = EEC_SAFETY_QM;
            cabin_sys->system_level         = EEC_SYSTEM_LEVEL_SL1;

            (void)EEC_System_AddPlatform(cabin_sys, "MF8S");
            (void)EEC_System_AddPlatform(cabin_sys, "Fendt900");
            (void)EEC_System_AddBrand(cabin_sys, EEC_BRAND_MASSEY_FERGUSON);

            printf("[OK] Created system '%s' (optional, medium priority, comfort)\n",
                   cabin_sys->name);
        }
    }

    /* ------------------------------------------------------------------
     * 4b. Optional zonal distribution — enabled via EEC_ZONES=<file>.
     * Loads the architecture mode (CENTRAL/ZONAL), zone→ECU membership and
     * system→zone assignments from JSON. Default (unset) = CENTRAL.
     * ------------------------------------------------------------------ */
    {
        const char *zones_file = getenv("EEC_ZONES");
        if (zones_file && zones_file[0] != '\0') {
            int nz = EEC_Architecture_LoadZones(arch, zones_file);
            if (nz >= 0) {
                printf("[INFO] Zones loaded → %d zone(s), mode=%s\n",
                       nz, EEC_ArchMode_ToString(arch->mode));
            } else {
                fprintf(stderr, "[WARN] Failed to load zones: %s\n", zones_file);
            }
        }
    }

    /* ==================================================================
     * 5. MAPPING STRATEGY
     *
     * Enable exactly ONE strategy block below.  To switch strategy:
     *   - Comment the active block
     *   - Uncomment the desired one
     *   - Rebuild and compare generated_doc/exports/automap_trace.txt
     *
     * All strategies write to the same trace file; the only difference
     * is the order and constraints applied when choosing which ECU pin
     * receives each logical signal.
     * ================================================================== */

    join_path(automap_trace_path, sizeof(automap_trace_path),
              exports_dir, "automap_trace.txt");
    trace = fopen(automap_trace_path, "w");
    if (!trace) {
        fprintf(stderr, "[WARN] Cannot open trace file: %s\n", automap_trace_path);
        trace = stdout;
    }

    /* ------------------------------------------------------------------
     * Strategy is selected at runtime via the EEC_MAP_STRATEGY environment
     * variable (case-insensitive); no recompile needed. Default = SMART.
     *
     *   smart   Score-sorted 7-tier mapping (mandatory/take-rate/priority/…).
     *   order   Registration-order, no scoring.
     *   zone    Per-system relaxed first-fit routing.
     *   strict  Per-signal scored/strict routing.
     *
     * All strategies write to the same automap_trace.txt; only the order and
     * constraints applied when choosing pins differ.
     * ------------------------------------------------------------------ */
    {
        const char *strategy_env = getenv("EEC_MAP_STRATEGY");
        EEC_MapStrategy_t strategy = EEC_MapStrategy_FromString(strategy_env);
        const char *strategy_src = strategy_env ? "env EEC_MAP_STRATEGY" : "default";

        /* In ZONAL mode, default to zone-aware routing unless overridden. */
        if (!strategy_env && arch->mode == EEC_ARCH_MODE_ZONAL) {
            strategy = EEC_MAP_STRATEGY_ZONE;
            strategy_src = "auto (ZONAL mode)";
        }

        if (trace) {
            fprintf(trace, "[STRATEGY] selected = %s (source: %s)\n\n",
                    EEC_MapStrategy_ToString(strategy), strategy_src);
        }
        printf("[INFO] Mapping strategy: %s (%s)\n",
               EEC_MapStrategy_ToString(strategy), strategy_src);

        mapped_total = EEC_Architecture_AutoMap(arch, ecus, ecu_count, strategy, trace);
    }

    if (trace && trace != stdout) {
        fclose(trace);
        trace = NULL;
        printf("[INFO] Auto-map trace  → %s\n", automap_trace_path);
    }
    if (mapped_total < 0) {
        fprintf(stderr, "[ERROR] Mapping failed\n");
        EEC_Architecture_Destroy(arch);
        return 5;
    }
    printf("[INFO] Total signals mapped: %d\n", mapped_total);

    /* ------------------------------------------------------------------
     * 6. Configure communication buses
     *
     * Creates the tractor's seven networks: Tractor_Bus (vehicle-wide CAN
     * backbone), Powertrain_Engine_Bus, ISOBUS (implement interface),
     * Diagnostic_OBD_Bus, Hydraulics_Bus, LIN_Bus and Ethernet_Bus.
     * ------------------------------------------------------------------ */
    (void)configure_vehicle_buses(arch, ecus, ecu_count);

    /* ------------------------------------------------------------------
     * 6b. Import SWC / CAN definitions from data files (fully data-driven).
     *     Bit layout and DLC are auto-derived; ECUs and buses are resolved
     *     by name. Editing library/swc/ JSON files changes every CAN output.
     * ------------------------------------------------------------------ */
    {
        size_t si;
        int swc_total = 0;
        for (si = 0U; si < k_swc_file_count; ++si) {
            int n = EEC_Import_swc_json(arch, k_swc_files[si]);
            if (n > 0) {
                swc_total += n;
            }
        }
        if (swc_total > 0) {
            EEC_Architecture_RebuildHostedSwcs(arch);
            EEC_Architecture_RebuildBusMessages(arch);
            printf("[OK] Imported %d SWC(s) from data files\n", swc_total);
        }
    }

    /* Zone distribution snapshot + consistency check. Runs AFTER buses are
     * configured so the inter-zone connectivity rule (Z3) sees real topology. */
    if (arch->zone_count > 0U) {
        char zones_json_path[PATH_MAX];
        int zone_errors;
        join_path(zones_json_path, sizeof(zones_json_path), exports_dir, "zones.json");
        if (EEC_Export_zones_json(arch, zones_json_path) == 0) {
            printf("[INFO] Zones JSON → %s\n", zones_json_path);
        }
        zone_errors = EEC_Verify_zones(arch, stdout);
        if (zone_errors > 0) {
            printf("[WARN] Zone verification: %d issue(s)\n", zone_errors);
        }
    }

    /* ------------------------------------------------------------------
     * 7. Verification
     * ------------------------------------------------------------------ */
    join_path(verify_report_path, sizeof(verify_report_path),
              exports_dir, "verify_report.txt");
    rpt = fopen(verify_report_path, "w");
    if (!rpt) {
        fprintf(stderr, "[WARN] Cannot open verify report: %s\n", verify_report_path);
    } else {
        verify_errors = EEC_Verify_architecture(arch, rpt);
        fclose(rpt);
        rpt = NULL;
        printf("[INFO] Verification → %s  (errors=%d)\n",
               verify_report_path, verify_errors);
    }

    join_path(allocation_report_path, sizeof(allocation_report_path),
              exports_dir, "pin_allocation_report.txt");
    alloc = fopen(allocation_report_path, "w");
    if (!alloc) {
        fprintf(stderr, "[WARN] Cannot open allocation report: %s\n", allocation_report_path);
    } else {
        (void)EEC_Report_pin_allocation(arch, alloc);
        fclose(alloc);
        alloc = NULL;
        printf("[INFO] Pin allocation → %s\n", allocation_report_path);
    }

    /* ------------------------------------------------------------------
     * 8. Export architecture snapshots
     * ------------------------------------------------------------------ */
    join_path(arch_json_path, sizeof(arch_json_path),
              exports_dir, "exported_architecture.json");
    join_path(phys_json_path, sizeof(phys_json_path),
              exports_dir, "exported_physical_architecture.json");

    if (EEC_Export_architecture_json(arch, arch_json_path) == 0) {
        printf("[INFO] Architecture JSON → %s\n", arch_json_path);
    } else {
        fprintf(stderr, "[WARN] Failed to export architecture JSON\n");
    }

    if (EEC_Export_physical_architecture_json(arch, phys_json_path) == 0) {
        printf("[INFO] Physical arch JSON → %s\n", phys_json_path);
    } else {
        fprintf(stderr, "[WARN] Failed to export physical architecture JSON\n");
    }

    /* Per-bus CAN database (DBC) export into the dedicated DBC/ folder. */
    {
        int dbc_files = EEC_Export_dbc_all(arch, dbc_dir);
        if (dbc_files > 0) {
            printf("[INFO] DBC export → %d file(s) in %s\n", dbc_files, dbc_dir);
        }
        /* Report DBC-level errors (frame overflow, overlap, dup id, etc.). */
        {
            int dbc_errors = EEC_Dbc_Validate_all(arch, stdout);
            if (dbc_errors > 0) {
                printf("[WARN] DBC validation: %d error(s) — see [DBC:*] lines above\n", dbc_errors);
            } else {
                printf("[OK] DBC validation: no errors\n");
            }
        }
    }

    /* Optional CAN database (DBC) import — enabled via EEC_IMPORT_DBC=<file>. */
    {
        const char *dbc_in = getenv("EEC_IMPORT_DBC");
        if (dbc_in && dbc_in[0] != '\0') {
            EEC_System_t *imp_sys = EEC_Architecture_CreateSystem(arch, "Imported_DBC");
            EEC_Swc_t    *imp_swc = imp_sys ? EEC_System_CreateSwc(imp_sys, "Imported_DBC_SWC") : NULL;
            if (imp_swc) {
                int n = EEC_Import_dbc(arch, imp_swc, dbc_in);
                if (n >= 0) {
                    printf("[INFO] DBC import ← %d message(s) from %s\n", n, dbc_in);
                } else {
                    fprintf(stderr, "[WARN] DBC import failed: %s\n", dbc_in);
                }
            } else {
                fprintf(stderr, "[WARN] DBC import: could not create owner SWC\n");
            }
        }
    }

    /* Data dictionary — logical + physical signals grouped per module/system. */
    {
        char dd_json[PATH_MAX];
        char dd_csv[PATH_MAX];
        char dd_html[PATH_MAX];
        join_path(dd_json, sizeof(dd_json), exports_dir, "data_dictionary.json");
        join_path(dd_csv,  sizeof(dd_csv),  exports_dir, "data_dictionary.csv");
        join_path(dd_html, sizeof(dd_html), generated_doc_dir, "data_dictionary.html");
        (void)EEC_Export_data_dictionary_json(arch, dd_json);
        (void)EEC_Export_data_dictionary_csv(arch, dd_csv);
        if (EEC_Export_data_dictionary_html(arch, dd_html) >= 0) {
            printf("[INFO] Data dictionary → %s (+ .json/.csv in exports/)\n", dd_html);
        }
    }

    /* ------------------------------------------------------------------
     * 9. ECU I/O sizing estimation
     * ------------------------------------------------------------------ */
    join_path(estimation_json_path, sizeof(estimation_json_path),
              exports_dir, "estimation_result.json");
    {
        const char *estimation_ecu = getenv("EEC_ESTIMATION_ECU");
        if (estimation_ecu && estimation_ecu[0] != '\0') {
            printf("[INFO] Estimation ECU selected: %s\n", estimation_ecu);
        }
        if (EEC_Estimation_RunWithEcu("library/platform.json", "library",
                                     estimation_ecu, estimation_json_path) == 0) {
            printf("[INFO] Estimation JSON → %s\n", estimation_json_path);
        } else {
            fprintf(stderr, "[WARN] Estimation failed — check platform and selected ECU JSON\n");
        }
    }

    /* ------------------------------------------------------------------
     * Cleanup
     * ------------------------------------------------------------------ */
    EEC_Architecture_Destroy(arch);

    if (verify_errors > 0) {
        printf("[WARN] Completed with %d verification error(s)\n", verify_errors);
    } else {
        printf("[OK] Completed successfully\n");
    }

    return 0;
}
