/**
 * @file    EEC_main_helpers.c
 * @brief   E/E Architect Design — Application-level setup helpers (implementation).
 *
 * @author  Anadack Temtching Dassi
 * @date    2026
 */

#include "EEC_main_helpers.h"
#include "EEC_library.h"
#include "EEC_connect.h"

#include <errno.h>
#include <stdio.h>
#include <string.h>

#ifdef _WIN32
#include <direct.h>
#else
#include <sys/stat.h>
#include <sys/types.h>
#endif

/* -------------------------------------------------------------------------
 * File-system helpers
 * ------------------------------------------------------------------------- */

int path_exists(const char *path)
{
    FILE *f;
    if (!path || !path[0]) {
        return 0;
    }
    f = fopen(path, "rb");
    if (!f) {
        return 0;
    }
    fclose(f);
    return 1;
}

void make_dir_if_missing(const char *path)
{
    if (!path || !path[0]) {
        return;
    }
#ifdef _WIN32
    if (_mkdir(path) != 0 && errno != EEXIST) {
        fprintf(stderr, "[WARN] Could not create directory '%s'\n", path);
    }
#else
    if (mkdir(path, 0775) != 0 && errno != EEXIST) {
        fprintf(stderr, "[WARN] Could not create directory '%s'\n", path);
    }
#endif
}

void join_path(char *out, size_t out_size, const char *a, const char *b)
{
    size_t len;

    if (!out || out_size == 0U) {
        return;
    }
    if (!a) a = "";
    if (!b) b = "";

    len = strlen(a);
    if (len > 0U && (a[len - 1U] == '/' || a[len - 1U] == '\\')) {
        snprintf(out, out_size, "%s%s", a, b);
    } else {
#ifdef _WIN32
        snprintf(out, out_size, "%s\\%s", a, b);
#else
        snprintf(out, out_size, "%s/%s", a, b);
#endif
    }
}

/* -------------------------------------------------------------------------
 * Bulk-import helpers
 * ------------------------------------------------------------------------- */

/* When the same ECU preset file is instantiated more than once (e.g. two
 * zone-specific AEC_LARGE_3CAN ECUs), every instance inherits the exact same
 * default CAN addresses baked into that preset's JSON. Left alone, that is a
 * genuine network conflict (rule V1: no two ECUs anywhere in the architecture
 * may share a CAN node address, since diagnostic/UDS addressing is scoped to
 * the whole vehicle network even across a gateway), not a false positive.
 *
 * For every repeat use of a preset, shift its addresses by a fixed offset per
 * repetition and, if that still collides with any ECU imported so far, keep
 * probing forward until a free byte is found. The first use of a preset is
 * left untouched so single-instance ECUs keep their documented addresses. */
static void remap_duplicate_can_addresses(EEC_Ecu_t *ecu, unsigned int repetition,
                                          EEC_Ecu_t *const *prior_ecus, unsigned int prior_count)
{
    uint8_t i;

    if (!ecu || repetition == 0U) {
        return;
    }

    for (i = 0U; i < ecu->can_address_count; ++i) {
        unsigned int offset = 0x20U * repetition;
        unsigned int candidate = ((unsigned int)ecu->can_addresses[i] + offset) & 0xFFU;
        unsigned int tries;

        for (tries = 0U; tries < 0x100U; ++tries) {
            bool taken = false;
            unsigned int p;
            for (p = 0U; p < prior_count && !taken; ++p) {
                if (EEC_Ecu_HasCanAddress(prior_ecus[p], (uint8_t)candidate)) {
                    taken = true;
                }
            }
            if (!taken) {
                break;
            }
            candidate = (candidate + 1U) & 0xFFU;
        }

        printf("[INFO]   remapped duplicate-preset CAN address 0x%02X -> 0x%02X on %s (repetition #%u of its preset)\n",
               ecu->can_addresses[i], (uint8_t)candidate, ecu->name, repetition);
        ecu->can_addresses[i] = (uint8_t)candidate;
    }
}

unsigned int import_library_ecus(EEC_Architecture_t       *arch,
                                 const LibraryEcuImport_t *ecu_imports,
                                 size_t                    ecu_import_count,
                                 EEC_Ecu_t               **ecus,
                                 size_t                    ecu_capacity)
{
    size_t       i;
    unsigned int imported = 0U;

    if (!arch || !ecu_imports || !ecus || ecu_import_count == 0U || ecu_capacity == 0U) {
        return 0U;
    }

    for (i = 0U; i < ecu_import_count && imported < ecu_capacity; ++i) {
        EEC_Ecu_t   *ecu;
        unsigned int repetition = 0U;
        size_t       j;

        if (!path_exists(ecu_imports[i].path)) {
            fprintf(stderr, "[WARN] ECU file not found: %s\n", ecu_imports[i].path);
            continue;
        }

        ecu = EEC_Library_ImportEcu(arch, ecu_imports[i].path, ecu_imports[i].instance_name);
        if (!ecu) {
            fprintf(stderr, "[WARN] Failed to import ECU: %s\n", ecu_imports[i].path);
            continue;
        }

        for (j = 0U; j < i; ++j) {
            if (strcmp(ecu_imports[j].path, ecu_imports[i].path) == 0) {
                ++repetition;
            }
        }
        remap_duplicate_can_addresses(ecu, repetition, ecus, imported);

        ecus[imported++] = ecu;
        printf("[OK] Imported ECU: %s  →  %s\n",
               ecu_imports[i].instance_name, ecu_imports[i].path);
    }

    return imported;
}

unsigned int import_library_systems(EEC_Architecture_t          *arch,
                                    const LibrarySystemImport_t *systems,
                                    size_t                       system_count)
{
    size_t       i;
    unsigned int imported = 0U;

    if (!arch || !systems || system_count == 0U) {
        return 0U;
    }

    for (i = 0U; i < system_count; ++i) {
        EEC_System_t *sys;

        if (!path_exists(systems[i].path)) {
            fprintf(stderr, "[WARN] %s not found: %s\n",
                    systems[i].label ? systems[i].label : "System",
                    systems[i].path);
            continue;
        }

        sys = EEC_Library_ImportSystem(arch, systems[i].path);
        if (!sys) {
            fprintf(stderr, "[WARN] Failed to import %s: %s\n",
                    systems[i].label ? systems[i].label : "system",
                    systems[i].path);
            continue;
        }

        printf("[OK] Imported %s: %s\n",
               systems[i].label ? systems[i].label : "system",
               systems[i].path);
        ++imported;
    }

    return imported;
}

/* -------------------------------------------------------------------------
 * Bus setup helper
 * ------------------------------------------------------------------------- */

/** @brief Find an imported ECU by its instance name (NULL if not present). */
static EEC_Ecu_t *find_ecu_by_name(EEC_Ecu_t *const *ecus, unsigned int ecu_count, const char *name)
{
    unsigned int i;
    for (i = 0U; i < ecu_count; ++i) {
        if (ecus[i] && strcmp(ecus[i]->name, name) == 0) {
            return ecus[i];
        }
    }
    return NULL;
}

/** @brief Look up an ECU by name and connect it to @p bus at @p port_index (no-op if absent). */
static void connect_named_ecu(EEC_Bus_t *bus, EEC_Ecu_t *const *ecus, unsigned int ecu_count,
                              const char *name, uint8_t port_index)
{
    EEC_Ecu_t *ecu = find_ecu_by_name(ecus, ecu_count, name);
    if (ecu) {
        (void)EEC_Bus_ConnectEcu(bus, ecu, port_index);
    }
}

/** @brief True when a system's name marks it as part of the hydraulic domain. */
static bool is_hydraulic_system(const EEC_System_t *sys)
{
    return sys != NULL &&
           (strstr(sys->name, "HYDAC") != NULL ||
            strstr(sys->name, "Hydraulic") != NULL ||
            strstr(sys->name, "Coil") != NULL);
}

/** @brief Print one summary line for a successfully created bus. */
static void print_bus_summary(const EEC_Bus_t *bus)
{
    if (!bus) return;
    printf("[INFO]   %-22s : %u node(s), %u signal(s)\n",
           bus->name, bus->node_count, bus->signal_count);
}

int configure_vehicle_buses(EEC_Architecture_t *arch,
                            EEC_Ecu_t *const   *ecus,
                            unsigned int        ecu_count)
{
    EEC_Bus_t *tractor, *powertrain, *isobus, *diagnostic, *hydraulics, *lin, *ethernet;
    uint32_t   i;
    int        total_signals = 0;

    if (!arch || !ecus || ecu_count == 0U) {
        return 0;
    }

    /* 1. Tractor_Bus — vehicle-wide CAN backbone, every CAN-capable ECU on port 1 */
    tractor = EEC_Architecture_CreateBus(arch, "Tractor_Bus", EEC_BUS_TYPE_CAN);
    if (!tractor) {
        fprintf(stderr, "[WARN] Could not create Tractor_Bus\n");
        return -1;
    }
    tractor->bitrate = 250000U;
    for (i = 0U; i < ecu_count; ++i) {
        if (ecus[i] && EEC_Ecu_CountCanPorts(ecus[i]) > 0U) {
            (void)EEC_Bus_ConnectEcu(tractor, ecus[i], 1U);
        }
    }

    /* 2. Powertrain_Engine_Bus — fast engine/transmission control loop */
    powertrain = EEC_Architecture_CreateBus(arch, "Powertrain_Engine_Bus", EEC_BUS_TYPE_CAN);
    if (powertrain) {
        powertrain->bitrate = 500000U;
        connect_named_ecu(powertrain, ecus, ecu_count, "AEC_ENGINE_01", 2U);
        connect_named_ecu(powertrain, ecus, ecu_count, "AEC_TRANSMISSION_01", 2U);
    } else {
        fprintf(stderr, "[WARN] Could not create Powertrain_Engine_Bus\n");
    }

    /* 3. ISOBUS — ISO 11783 implement interface (rear hitch + trailer) */
    isobus = EEC_Architecture_CreateBus(arch, "ISOBUS", EEC_BUS_TYPE_ISOBUS);
    if (isobus) {
        isobus->bitrate = 250000U;
        connect_named_ecu(isobus, ecus, ecu_count, "AEC_REAR_HITCH_01", 2U);
        connect_named_ecu(isobus, ecus, ecu_count, "AEC_TRAILER_01", 2U);
    } else {
        fprintf(stderr, "[WARN] Could not create ISOBUS\n");
    }

    /* 4. Diagnostic_OBD_Bus — service-tool / UDS diagnostics via zone gateways */
    diagnostic = EEC_Architecture_CreateBus(arch, "Diagnostic_OBD_Bus", EEC_BUS_TYPE_CAN);
    if (diagnostic) {
        diagnostic->bitrate = 500000U;
        connect_named_ecu(diagnostic, ecus, ecu_count, "AEC_CABIN_01", 2U);
        connect_named_ecu(diagnostic, ecus, ecu_count, "AEC_ENGINE_01", 3U);
    } else {
        fprintf(stderr, "[WARN] Could not create Diagnostic_OBD_Bus\n");
    }

    /* 5. Hydraulics_Bus — hydraulic sensor / valve-coil network */
    hydraulics = EEC_Architecture_CreateBus(arch, "Hydraulics_Bus", EEC_BUS_TYPE_CAN);
    if (hydraulics) {
        hydraulics->bitrate = 250000U;
        connect_named_ecu(hydraulics, ecus, ecu_count, "AEC_REAR_HITCH_01", 3U);
        connect_named_ecu(hydraulics, ecus, ecu_count, "AEC_TRANSMISSION_01", 3U);
    } else {
        fprintf(stderr, "[WARN] Could not create Hydraulics_Bus\n");
    }

    /* 6. LIN_Bus — low-cost cabin switches and rear hitch indicator lamps */
    lin = EEC_Architecture_CreateBus(arch, "LIN_Bus", EEC_BUS_TYPE_LIN);
    if (lin) {
        lin->bitrate = 19200U;
        connect_named_ecu(lin, ecus, ecu_count, "AEC_CABIN_01", 3U);
        connect_named_ecu(lin, ecus, ecu_count, "AEC_REAR_HITCH_01", 4U);
    } else {
        fprintf(stderr, "[WARN] Could not create LIN_Bus\n");
    }

    /* 7. Ethernet_Bus — high-bandwidth backbone (telematics/camera-ready) */
    ethernet = EEC_Architecture_CreateBus(arch, "Ethernet_Bus", EEC_BUS_TYPE_ETHERNET);
    if (ethernet) {
        ethernet->bitrate = 100000000U;
        for (i = 0U; i < ecu_count; ++i) {
            if (ecus[i] && EEC_Ecu_CountEthernetPorts(ecus[i]) > 0U) {
                (void)EEC_Bus_ConnectEcu(ethernet, ecus[i], 5U);
            }
        }
    } else {
        fprintf(stderr, "[WARN] Could not create Ethernet_Bus\n");
    }

    /* Route system signals: hydraulic-domain systems → Hydraulics_Bus,
     * everything else → Tractor_Bus. LIN_Bus/Ethernet_Bus scan every
     * system so they automatically pick up future LIN/Ethernet signals. */
    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *sys = arch->systems[i];
        int added;

        added = is_hydraulic_system(sys)
                    ? EEC_Bus_ConnectSystemSignals(hydraulics, sys)
                    : EEC_Bus_ConnectSystemSignals(tractor, sys);
        if (added > 0) total_signals += added;

        added = EEC_Bus_ConnectSystemSignals(lin, sys);
        if (added > 0) total_signals += added;

        added = EEC_Bus_ConnectSystemSignals(ethernet, sys);
        if (added > 0) total_signals += added;
    }

    printf("[INFO] Bus topology configured: %u bus(es), %d signal(s) routed\n",
           arch->bus_count, total_signals);
    print_bus_summary(tractor);
    print_bus_summary(powertrain);
    print_bus_summary(isobus);
    print_bus_summary(diagnostic);
    print_bus_summary(hydraulics);
    print_bus_summary(lin);
    print_bus_summary(ethernet);

    return total_signals;
}
