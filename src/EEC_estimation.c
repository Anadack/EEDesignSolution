/*
 * @file    EEC_estimation.c
 * @brief   E/E Architect Design — Architecture estimation from platform selection.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#include "EEC_estimation.h"
#include "EEC_library.h"
#include "EEC_agco.h"
#include "EEC_log.h"
#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Guard the invariant that per_iface[]/arch_io[] can be indexed by any
   EEC_SignalInterface_t value without overrunning. Fails the build if the
   interface enum ever grows past the bucket capacity. */
_Static_assert(EEC_EST_MAX_IFACE_TYPES >= (uint32_t)EEC_SIGNAL_INTERFACE_RESERVED,
               "EEC_EST_MAX_IFACE_TYPES must cover every EEC_SignalInterface_t value");

#ifdef _WIN32
#  include <windows.h>
#else
#  include <dirent.h>
#endif

/* ════════════════════════════════════════════════════════════════════════
 *  Minimal JSON helpers (reused pattern from EEC_library.c)
 * ════════════════════════════════════════════════════════════════════════ */

static char *est_read_file(const char *path, size_t *out_len)
{
    FILE *f;
    long sz;
    char *buf;
    f = fopen(path, "rb");
    if (!f) return NULL;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    sz = ftell(f);
    if (sz < 0) { fclose(f); return NULL; }
    rewind(f);
    buf = (char *)malloc((size_t)sz + 1U);
    if (!buf) { fclose(f); return NULL; }
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) { free(buf); fclose(f); return NULL; }

/*
 * ──────────────────────────────────────────────────────────────────────────────
 *  E/E Architect Design — Architecture Estimation Implementation
 *
 *  This file implements the estimation logic for the E/E Architect Design framework.
 *  It provides routines for sizing, resource estimation, and platform selection
 *  based on the constructed architecture and imported library data.
 *
 *  Major responsibilities:
 *    - Estimation of pin, signal, and device counts
 *    - Platform selection and sizing based on requirements
 *    - Integration with library import and AGCO extensions
 *    - Minimal JSON helpers for data import (pattern reused from EEC_library.c)
 *
 *  The estimation module enables early design analysis and feasibility checks.
 * ──────────────────────────────────────────────────────────────────────────────
 */

/**
 * @brief Read an entire file into memory for estimation processing.
 *
 * Opens the specified file, reads its contents into a newly allocated buffer,
 * and returns a pointer to the buffer (caller must free). Used for importing
 * JSON or data files for estimation routines.
 *
 * @param path    Path to the file to read.
 * @param out_len Output: length of the file in bytes.
 * @return Pointer to allocated buffer with file contents, or NULL on error.
 */
    buf[sz] = '\0';
    fclose(f);
    if (out_len) *out_len = (size_t)sz;
    return buf;
}

static void est_skip_ws(const char **p, const char *end)
{
    while (*p < end && isspace((unsigned char)**p)) ++(*p);
}

static int est_read_string(const char **p, const char *end, char *out, size_t out_sz)
{
    size_t n = 0;
    est_skip_ws(p, end);
    if (*p >= end || **p != '"') return -1;
    ++(*p);
    while (*p < end && **p != '"') {
        char c = *(*p)++;
        if (c == '\\' && *p < end) { c = *(*p)++; }
        if (n + 1 < out_sz) out[n] = c;
        ++n;
    }
    if (*p < end && **p == '"') ++(*p);
    if (n < out_sz) out[n] = '\0'; else if (out_sz > 0) out[out_sz - 1] = '\0';
    return (int)n;
}

/* ════════════════════════════════════════════════════════════════════════
 *  Step 1: Parse the platform file  (JSON with "systems" array)
 * ════════════════════════════════════════════════════════════════════════ */

typedef struct {
    char ref_2x[64];
} PlatformEntry;

static int parse_platform_file(const char *path, char *platform_name,
                                size_t name_sz, PlatformEntry *entries,
                                uint32_t max_entries)
{
    char *buf;
    size_t len;
    const char *p, *end;
    int count = 0;

    buf = est_read_file(path, &len);
    if (!buf) {
        EEC_Log_Printf(EEC_LOG_ERROR, "Estimation: cannot read platform file '%s'", path);
        return -1;
    }
    p = buf; end = buf + len;

    /* Find "name" */
    {
        const char *key = "\"name\"";
        const char *found = strstr(p, key);
        if (found) {
            found += strlen(key);
            while (found < end && (*found == ' ' || *found == ':')) ++found;
            est_read_string(&found, end, platform_name, name_sz);
        } else {
            snprintf(platform_name, name_sz, "Unknown Platform");
        }
    }

    /* Find "systems" array */
    {
        const char *arr = strstr(p, "\"systems\"");
        if (!arr) { free(buf); return -1; }
        arr += strlen("\"systems\"");
        while (arr < end && *arr != '[') ++arr;
        if (arr >= end) { free(buf); return -1; }
        ++arr; /* skip '[' */

        while (arr < end && *arr != ']' && (uint32_t)count < max_entries) {
            char ref[26] = "";
            est_skip_ws(&arr, end);
            if (*arr == ',') { ++arr; est_skip_ws(&arr, end); }
            if (*arr == ']') break;

            if (*arr == '"') {
                /* Simple string entry: just a Ref-2X value */
                est_read_string(&arr, end, ref, sizeof(ref));
                if (ref[0]) {
                    snprintf(entries[count].ref_2x, sizeof(entries[count].ref_2x), "%s", ref);
                    ++count;
                }
            } else if (*arr == '{') {
                /* Object entry: { "ref_2x": "..." } */
                ++arr;
                while (arr < end && *arr != '}') {
                    char key[32] = "";
                    est_skip_ws(&arr, end);
                    if (*arr == ',') { ++arr; continue; }
                    if (est_read_string(&arr, end, key, sizeof(key)) < 0) break;
                    est_skip_ws(&arr, end);
                    if (*arr == ':') ++arr;
                    est_skip_ws(&arr, end);
                    if (strcmp(key, "ref_2x") == 0 || strcmp(key, "Ref-2X") == 0) {
                        est_read_string(&arr, end, ref, sizeof(ref));
                    } else {
                        /* skip value */
                        if (*arr == '"') {
                            char tmp[128]; est_read_string(&arr, end, tmp, sizeof(tmp));
                        } else {
                            while (arr < end && *arr != ',' && *arr != '}') ++arr;
                        }
                    }
                }
                if (arr < end && *arr == '}') ++arr;
                if (ref[0]) {
                    snprintf(entries[count].ref_2x, sizeof(entries[count].ref_2x), "%s", ref);
                    ++count;
                }
            }
        }
    }

    free(buf);
    EEC_Log_Printf(EEC_LOG_INFO, "Estimation: parsed platform '%s' with %d system(s)", platform_name, count);
    return count;
}

/* ════════════════════════════════════════════════════════════════════════
 *  Step 2: Scan library/systems/ for matching Ref-2X
 * ════════════════════════════════════════════════════════════════════════ */

/** Try to find a system JSON in library_dir/systems/ whose Ref-2X matches.
 *  Returns the filepath in out_path, or empty string if not found. */
static bool find_system_by_ref2x(const char *library_dir, const char *ref_2x,
                                  char *out_path, size_t out_sz)
{
    /* Scan known system files.  We iterate through potential filenames
       by reading each .json in library_dir/systems/ and checking Ref-2X. */
    char dir_path[512];
    snprintf(dir_path, sizeof(dir_path), "%s/systems", library_dir);

#ifdef _WIN32
    {
        WIN32_FIND_DATAA fd;
        HANDLE hFind;
        char scan_pattern[560];
        snprintf(scan_pattern, sizeof(scan_pattern), "%s/*.json", dir_path);
        hFind = FindFirstFileA(scan_pattern, &fd);
        if (hFind == INVALID_HANDLE_VALUE) return false;
        do {
            char filepath[800];
            char *buf;
            size_t len;
            const char *key;
            snprintf(filepath, sizeof(filepath), "%s/%s", dir_path, fd.cFileName);
            buf = est_read_file(filepath, &len);
            if (!buf) continue;
            key = strstr(buf, "\"Ref-2X\"");
            if (key) {
                char found_ref[26] = "";
                key += strlen("\"Ref-2X\"");
                while (*key && (*key == ' ' || *key == ':')) ++key;
                {
                    const char *kp = key;
                    const char *kend = buf + len;
                    est_read_string(&kp, kend, found_ref, sizeof(found_ref));
                }
                if (strcmp(found_ref, ref_2x) == 0) {
                    snprintf(out_path, out_sz, "%s", filepath);
                    free(buf);
                    FindClose(hFind);
                    return true;
                }
            }
            free(buf);
        } while (FindNextFileA(hFind, &fd));
        FindClose(hFind);
    }
#else
    /* POSIX fallback */
    {
        DIR *d = opendir(dir_path);
        struct dirent *ent;
        if (!d) return false;
        while ((ent = readdir(d)) != NULL) {
            char filepath[600];
            char *buf;
            size_t len;
            const char *key;
            size_t nlen = strlen(ent->d_name);
            if (nlen < 6 || strcmp(ent->d_name + nlen - 5, ".json") != 0) continue;
            snprintf(filepath, sizeof(filepath), "%s/%s", dir_path, ent->d_name);
            buf = est_read_file(filepath, &len);
            if (!buf) continue;
            key = strstr(buf, "\"Ref-2X\"");
            if (key) {
                char found_ref[26] = "";
                key += strlen("\"Ref-2X\"");
                while (*key && (*key == ' ' || *key == ':')) ++key;
                {
                    const char *kp = key;
                    const char *kend = buf + len;
                    est_read_string(&kp, kend, found_ref, sizeof(found_ref));
                }
                if (strcmp(found_ref, ref_2x) == 0) {
                    snprintf(out_path, out_sz, "%s", filepath);
                    free(buf);
                    closedir(d);
                    return true;
                }
            }
            free(buf);
        }
        closedir(d);
    }
#endif
    return false;
}

/* ════════════════════════════════════════════════════════════════════════
 *  Step 3: Count IO per interface on an imported system
 * ════════════════════════════════════════════════════════════════════════ */

static uint32_t iface_bucket(EEC_IoCount_t *buckets, uint32_t *count,
                              EEC_SignalInterface_t iface)
{
    uint32_t i;
    for (i = 0; i < *count; ++i) {
        if (buckets[i].interface_type == iface) return i;
    }
    if (*count < EEC_EST_MAX_IFACE_TYPES) {
        memset(&buckets[*count], 0, sizeof(buckets[0]));
        buckets[*count].interface_type = iface;
        return (*count)++;
    }
    return 0; /* fallback */
}

static void count_device_pins(const EEC_DevicePin_t *pins, uint32_t pin_count,
                               EEC_IoCount_t *buckets, uint32_t *bucket_count)
{
    uint32_t i;
    for (i = 0; i < pin_count; ++i) {
        const EEC_Signal_t *sig = pins[i].signal;
        uint32_t bi;
        if (!sig) continue;
        bi = iface_bucket(buckets, bucket_count, sig->interface_type);
        switch (pins[i].role) {
            case EEC_PIN_ROLE_OUTPUT:  buckets[bi].output_count++; break;
            case EEC_PIN_ROLE_INOUT:   buckets[bi].inout_count++;  break;
            default:                   buckets[bi].input_count++;  break;
        }
        buckets[bi].total++;
    }
}

static void count_system_io(const EEC_System_t *sys, EEC_SystemIo_t *sio)
{
    uint32_t c, d;
    sio->iface_count = 0;
    sio->total_signals = 0;

    for (c = 0; c < sys->component_count; ++c) {
        const EEC_Component_t *comp = sys->components[c];
        if (!comp) continue;
        for (d = 0; d < comp->sensor_count; ++d) {
            if (comp->sensors[d])
                count_device_pins(comp->sensors[d]->pins, comp->sensors[d]->pin_count,
                                  sio->per_iface, &sio->iface_count);
        }
        for (d = 0; d < comp->actuator_count; ++d) {
            if (comp->actuators[d])
                count_device_pins(comp->actuators[d]->pins, comp->actuators[d]->pin_count,
                                  sio->per_iface, &sio->iface_count);
        }
    }

    /* Sum totals */
    {
        uint32_t i;
        for (i = 0; i < sio->iface_count; ++i)
            sio->total_signals += sio->per_iface[i].total;
    }
}

/* ════════════════════════════════════════════════════════════════════════
 *  Step 4: Compute ECU variant capacities
 * ════════════════════════════════════════════════════════════════════════ */

/** @brief Return true if this interface is a shared-bus protocol (CAN/LIN/ETH/SENT).
 *  Bus signals are multiplexed — one port carries many signals. */
static bool is_bus_interface(EEC_SignalInterface_t iface)
{
    return iface == EEC_SIGNAL_INTERFACE_CAN
        || iface == EEC_SIGNAL_INTERFACE_ETHERNET
        || iface == EEC_SIGNAL_INTERFACE_LIN
        || iface == EEC_SIGNAL_INTERFACE_SENT;
}

/** @brief ECU factory variant table — name + index. */
static const char *ecu_variant_names[EEC_EST_VARIANT_COUNT] = {
    "SMALL", "MEDIUM", "LARGE"
};

/** @brief Create an AGCO ECU by variant index. */
static EEC_Ecu_t *create_ecu_by_variant(EEC_Architecture_t *arch,
                                         uint32_t variant_idx,
                                         const char *label)
{
    switch (variant_idx) {
        case 0: return EEC_Agco_CreateEcuSmall(arch, label, 0);
        case 1: return EEC_Agco_CreateEcuMedium(arch, label, 0);
        case 2: return EEC_Agco_CreateEcuLarge(arch, label, 0);
        default: return NULL;
    }
}

static void compute_capacity_from_ecu(const EEC_Ecu_t *ecu,
                                      const char *capacity_name,
                                      EEC_EcuCapacity_t *cap)
{
    uint32_t p;

    snprintf(cap->variant, sizeof(cap->variant), "%s", capacity_name ? capacity_name : "ECU");
    memset(cap->per_iface, 0, sizeof(cap->per_iface));
    cap->total_pins = 0;
    if (!ecu) return;

    /* Count available pins per interface type using the canonical mapping */
    for (p = 0; p < ecu->pin_count; ++p) {
        const EEC_EcuPin_t *pin = &ecu->pins[p];
        uint32_t mask = pin->supported_capability_mask;
        EEC_SignalInterface_t iface;
        bool usable = false;

        /* Try each interface — use EEC_Signal_InterfaceToCapability() */
        for (iface = EEC_SIGNAL_INTERFACE_DIGITAL;
             iface < EEC_SIGNAL_INTERFACE_RESERVED; ++iface) {
            if (mask & EEC_Signal_InterfaceToCapability(iface)) {
                cap->per_iface[iface]++;
                usable = true;
            }
        }
        /* A multifunction pin contributes to every interface it supports, but
         * remains one physical pin in the total capacity. The estimator takes
         * the maximum per-interface ECU count, so this avoids falsely declaring
         * supplier multifunction inputs unsupported without double-counting
         * physical pins in utilisation. */
        if (usable) cap->total_pins++;
    }
}

static void compute_ecu_capacity(EEC_Architecture_t *scratch,
                                  uint32_t variant_idx,
                                  EEC_EcuCapacity_t *cap)
{
    EEC_Ecu_t *ecu;
    char label[32];

    snprintf(label, sizeof(label), "_cap_%s", ecu_variant_names[variant_idx]);
    ecu = create_ecu_by_variant(scratch, variant_idx, label);
    compute_capacity_from_ecu(ecu, ecu_variant_names[variant_idx], cap);
}

/* ════════════════════════════════════════════════════════════════════════
 *  Step 5: Compute homogeneous ECU estimates
 * ════════════════════════════════════════════════════════════════════════ */

static void compute_homogeneous_estimate(const EEC_IoCount_t *arch_io,
                                          uint32_t iface_count,
                                          uint32_t total_signals,
                                          const EEC_EcuCapacity_t *cap,
                                          EEC_EcuEstimate_t *est)
{
    uint32_t max_ecus = 1;
    uint32_t i;

    snprintf(est->variant, sizeof(est->variant), "%s", cap->variant);

    /* For each interface type, compute how many ECUs are needed to cover demand */
    for (i = 0; i < iface_count; ++i) {
        uint32_t demand = arch_io[i].total;
        EEC_SignalInterface_t iface = arch_io[i].interface_type;
        uint32_t available = cap->per_iface[iface];
        uint32_t needed;

        if (demand == 0) continue;

        /* Bus-type protocols (CAN/LIN/ETH/SENT) multiplex signals on a shared
           bus — each ECU port can carry all signals, so we only need 1 ECU
           as long as it has at least 1 port for that bus type. */
        if (is_bus_interface(iface)) {
            needed = (available > 0) ? 1 : 0;
        } else if (available == 0) {
            needed = demand; /* worst case: 1 per missing pin */
        } else {
            needed = (demand + available - 1U) / available;
        }
        if (needed > max_ecus) max_ecus = needed;
    }

    est->ecu_count = max_ecus;
    est->total_pins_available = max_ecus * cap->total_pins;
    est->total_pins_used = total_signals;
    est->utilisation_pct = est->total_pins_available > 0
        ? 100.0f * (float)total_signals / (float)est->total_pins_available
        : 0.0f;
}

/* ════════════════════════════════════════════════════════════════════════
 *  Step 6: Compute optimised mixed proposition
 *
 *  Rules applied:
 *   R1  Safety-critical systems (SL3+) must have a dedicated ECU (no mixing).
 *   R2  High-priority systems prefer MEDIUM or LARGE for headroom.
 *   R3  Low-IO systems can share a SMALL ECU to reduce cost/wiring.
 *   R4  Target 40-70% ECU utilisation for maintainability & evolution.
 *   R5  Minimise total ECU count for wiring / weight.
 *   R6  Each ECU must physically support all required interface types.
 * ════════════════════════════════════════════════════════════════════════ */

typedef struct {
    uint32_t sys_idx;           /* index into result->systems[] */
    bool     is_safety;         /* SL3 or SL4 */
    bool     is_high_priority;  /* CRITICAL or HIGH */
    uint32_t total_signals;
} SysClassification;

static void compute_mixed_proposition(EEC_EstimationResult_t *result,
                                       const EEC_System_t *const *imported_systems,
                                       uint32_t imported_count,
                                       const EEC_EcuCapacity_t *cap_small,
                                       const EEC_EcuCapacity_t *cap_medium,
                                       const EEC_EcuCapacity_t *cap_large)
{
    SysClassification cls[EEC_EST_MAX_SYSTEMS];
    uint32_t i, assigned = 0;
    uint32_t ecu_idx = 0;

    memset(cls, 0, sizeof(cls));

    /* Classify each imported system */
    for (i = 0; i < result->system_count; ++i) {
        if (!result->systems[i].found_in_library) continue;
        cls[assigned].sys_idx = i;
        cls[assigned].total_signals = result->systems[i].total_signals;

        /* Check safety level from imported system */
        if (assigned < imported_count && imported_systems[assigned]) {
            EEC_SystemLevel_t lvl = imported_systems[assigned]->system_level;
            EEC_ObjectPriority_t pri = imported_systems[assigned]->priority;
            cls[assigned].is_safety = (lvl >= EEC_SYSTEM_LEVEL_SL3);
            cls[assigned].is_high_priority = (pri >= EEC_PRIORITY_HIGH);
        }
        ++assigned;
    }

    /* Pass 1: Safety-critical systems get their own ECU (R1) */
    for (i = 0; i < assigned && ecu_idx < EEC_EST_MAX_PROPOSED_ECUS; ++i) {
        if (!cls[i].is_safety) continue;

        EEC_ProposedEcu_t *pe = &result->proposed[ecu_idx];
        uint32_t sig = cls[i].total_signals;

        /* Choose variant based on signal count vs threshold */
        if (sig > EEC_EST_SAFETY_THRESHOLD_SIGNALS) {
            snprintf(pe->variant, sizeof(pe->variant), "LARGE");
            pe->pins_total = cap_large->total_pins;
        } else {
            snprintf(pe->variant, sizeof(pe->variant), "MEDIUM");
            pe->pins_total = cap_medium->total_pins;
        }
        { char tmp[64]; memcpy(tmp, result->systems[cls[i].sys_idx].name, sizeof(tmp));
          snprintf(pe->assigned_systems, sizeof(pe->assigned_systems), "%s", tmp); }
        pe->pins_used = sig;
        pe->utilisation_pct = pe->pins_total > 0
            ? 100.0f * (float)sig / (float)pe->pins_total : 0.0f;

        cls[i].sys_idx = UINT32_MAX; /* mark as placed */
        ++ecu_idx;
    }

    /* Pass 2: High-priority non-safety systems → MEDIUM ECU (R2) */
    for (i = 0; i < assigned && ecu_idx < EEC_EST_MAX_PROPOSED_ECUS; ++i) {
        if (cls[i].sys_idx == UINT32_MAX) continue;
        if (!cls[i].is_high_priority) continue;

        EEC_ProposedEcu_t *pe = &result->proposed[ecu_idx];
        uint32_t sig = cls[i].total_signals;

        if (sig > EEC_EST_HIGHPRI_THRESHOLD_SIGNALS) {
            snprintf(pe->variant, sizeof(pe->variant), "LARGE");
            pe->pins_total = cap_large->total_pins;
        } else {
            snprintf(pe->variant, sizeof(pe->variant), "MEDIUM");
            pe->pins_total = cap_medium->total_pins;
        }
        { char tmp[64]; memcpy(tmp, result->systems[cls[i].sys_idx].name, sizeof(tmp));
          snprintf(pe->assigned_systems, sizeof(pe->assigned_systems), "%s", tmp); }
        pe->pins_used = sig;
        pe->utilisation_pct = pe->pins_total > 0
            ? 100.0f * (float)sig / (float)pe->pins_total : 0.0f;

        cls[i].sys_idx = UINT32_MAX;
        ++ecu_idx;
    }

    /* Pass 3: Remaining low-priority systems → share SMALL ECUs (R3, R5) */
    {
        uint32_t shared_signals = 0;
        char shared_names[256] = "";
        for (i = 0; i < assigned; ++i) {
            if (cls[i].sys_idx == UINT32_MAX) continue;
            if (shared_signals + cls[i].total_signals > cap_small->total_pins * EEC_EST_SHARE_FILL_PCT / 100) {
                /* Flush current shared ECU */
                if (shared_signals > 0 && ecu_idx < EEC_EST_MAX_PROPOSED_ECUS) {
                    EEC_ProposedEcu_t *pe = &result->proposed[ecu_idx];
                    snprintf(pe->variant, sizeof(pe->variant), "SMALL");
                    snprintf(pe->assigned_systems, sizeof(pe->assigned_systems), "%s", shared_names);
                    pe->pins_used = shared_signals;
                    pe->pins_total = cap_small->total_pins;
                    pe->utilisation_pct = pe->pins_total > 0
                        ? 100.0f * (float)shared_signals / (float)pe->pins_total : 0.0f;
                    ++ecu_idx;
                }
                shared_signals = 0;
                shared_names[0] = '\0';
            }
            if (shared_names[0]) {
                size_t l = strlen(shared_names);
                snprintf(shared_names + l, sizeof(shared_names) - l, ", %s",
                        result->systems[cls[i].sys_idx].name);
            } else {
                snprintf(shared_names, sizeof(shared_names), "%s",
                        result->systems[cls[i].sys_idx].name);
            }
            shared_signals += cls[i].total_signals;
            cls[i].sys_idx = UINT32_MAX;
        }
        /* Flush remaining */
        if (shared_signals > 0 && ecu_idx < EEC_EST_MAX_PROPOSED_ECUS) {
            EEC_ProposedEcu_t *pe = &result->proposed[ecu_idx];
            /* Choose SMALL if utilisation fits, else MEDIUM */
            if (shared_signals <= cap_small->total_pins * EEC_EST_SHARE_FILL_PCT / 100) {
                snprintf(pe->variant, sizeof(pe->variant), "SMALL");
                pe->pins_total = cap_small->total_pins;
            } else {
                snprintf(pe->variant, sizeof(pe->variant), "MEDIUM");
                pe->pins_total = cap_medium->total_pins;
            }
            snprintf(pe->assigned_systems, sizeof(pe->assigned_systems), "%s", shared_names);
            pe->pins_used = shared_signals;
            pe->utilisation_pct = pe->pins_total > 0
                ? 100.0f * (float)shared_signals / (float)pe->pins_total : 0.0f;
            ++ecu_idx;
        }
    }

    result->proposed_count = ecu_idx;

    snprintf(result->proposition_notes, sizeof(result->proposition_notes),
        "R1: Safety-critical systems (SL3+) on dedicated ECU. "
        "R2: High-priority systems prefer MEDIUM/LARGE for headroom. "
        "R3: Low-IO systems share SMALL ECUs (cost/wiring). "
        "R4: Target 40-70%% utilisation for evolution margin. "
        "R5: Minimise total ECU count. "
        "R6: Interface compatibility enforced.");
}

/* ════════════════════════════════════════════════════════════════════════
 *  Step 7: Write estimation result to JSON
 * ════════════════════════════════════════════════════════════════════════ */

static void json_escape_str(FILE *f, const char *s)
{
    const unsigned char *p = (const unsigned char *)(s ? s : "");
    fputc('"', f);
    while (*p) {
        switch (*p) {
            case '\\': fputs("\\\\", f); break;
            case '"':  fputs("\\\"", f); break;
            case '\n': fputs("\\n", f);  break;
            default:   fputc(*p, f);     break;
        }
        ++p;
    }
    fputc('"', f);
}

static const char *iface_label(EEC_SignalInterface_t iface)
{
    switch (iface) {
        case EEC_SIGNAL_INTERFACE_DIGITAL:  return "DIGITAL";
        case EEC_SIGNAL_INTERFACE_ANALOG:   return "ANALOG";
        case EEC_SIGNAL_INTERFACE_PWM:      return "PWM";
        case EEC_SIGNAL_INTERFACE_CAN:      return "CAN";
        case EEC_SIGNAL_INTERFACE_LIN:      return "LIN";
        case EEC_SIGNAL_INTERFACE_SENT:     return "SENT";
        case EEC_SIGNAL_INTERFACE_ETHERNET: return "ETHERNET";
        case EEC_SIGNAL_INTERFACE_RESISTANCE: return "RESISTANCE";
        case EEC_SIGNAL_INTERFACE_FREQUENCY: return "FREQUENCY";
        case EEC_SIGNAL_INTERFACE_CURRENT: return "CURRENT";
        case EEC_SIGNAL_INTERFACE_FLEXRAY: return "FLEXRAY";
        case EEC_SIGNAL_INTERFACE_POWER:    return "POWER";
        case EEC_SIGNAL_INTERFACE_GROUND:   return "GROUND";
        default: return "UNKNOWN";
    }
}

static void write_io_array(FILE *f, const EEC_IoCount_t *io, uint32_t count, int indent)
{
    uint32_t i;
    char pad[32];
    memset(pad, ' ', sizeof(pad));
    if ((size_t)indent >= sizeof(pad)) indent = (int)sizeof(pad) - 1;
    pad[indent] = '\0';

    fprintf(f, "[\n");
    for (i = 0; i < count; ++i) {
        fprintf(f, "%s  {\"interface\": \"%s\", \"input\": %u, \"output\": %u, \"inout\": %u, \"total\": %u}%s\n",
                pad, iface_label(io[i].interface_type),
                io[i].input_count, io[i].output_count, io[i].inout_count, io[i].total,
                (i + 1 < count) ? "," : "");
    }
    fprintf(f, "%s]", pad);
}

static int write_estimation_json(const EEC_EstimationResult_t *r, const char *path)
{
    FILE *f;
    uint32_t i;

    f = fopen(path, "w");
    if (!f) return -1;

    fprintf(f, "{\n");
    fprintf(f, "  \"platform\": "); json_escape_str(f, r->platform_name); fprintf(f, ",\n");

    /* Systems */
    fprintf(f, "  \"systems\": [\n");
    for (i = 0; i < r->system_count; ++i) {
        const EEC_SystemIo_t *s = &r->systems[i];
        fprintf(f, "    {\n");
        fprintf(f, "      \"ref_2x\": "); json_escape_str(f, s->ref_2x); fprintf(f, ",\n");
        fprintf(f, "      \"name\": "); json_escape_str(f, s->name); fprintf(f, ",\n");
        fprintf(f, "      \"found\": %s,\n", s->found_in_library ? "true" : "false");
        fprintf(f, "      \"total_signals\": %u,\n", s->total_signals);
        fprintf(f, "      \"io\": ");
        write_io_array(f, s->per_iface, s->iface_count, 6);
        fprintf(f, "\n    }%s\n", (i + 1 < r->system_count) ? "," : "");
    }
    fprintf(f, "  ],\n");

    /* Architecture totals */
    fprintf(f, "  \"architecture_io\": {\n");
    fprintf(f, "    \"total_signals\": %u,\n", r->arch_total_signals);
    fprintf(f, "    \"systems_found\": %u,\n", r->systems_found);
    fprintf(f, "    \"systems_missing\": %u,\n", r->systems_missing);
    fprintf(f, "    \"per_interface\": ");
    write_io_array(f, r->arch_io, r->arch_iface_count, 4);
    fprintf(f, "\n  },\n");

    /* ECU capacities */
    fprintf(f, "  \"ecu_capacities\": [\n");
    for (i = 0; i < EEC_EST_VARIANT_COUNT; ++i) {
        const EEC_EcuCapacity_t *c = &r->capacities[i];
        uint32_t j;
        fprintf(f, "    {\"variant\": \"%s\", \"total_pins\": %u, \"per_interface\": {",
                c->variant, c->total_pins);
        {
            bool first = true;
            for (j = 0; j < EEC_EST_MAX_IFACE_TYPES; ++j) {
                if (c->per_iface[j] == 0) continue;
                if (!first) fprintf(f, ", ");
                fprintf(f, "\"%s\": %u", iface_label((EEC_SignalInterface_t)j), c->per_iface[j]);
                first = false;
            }
        }
        fprintf(f, "}}%s\n", (i + 1 < EEC_EST_VARIANT_COUNT) ? "," : "");
    }
    fprintf(f, "  ],\n");

    /* Homogeneous estimates — iterate the generic array */
    fprintf(f, "  \"estimates\": [\n");
    for (i = 0; i < EEC_EST_VARIANT_COUNT; ++i) {
        const EEC_EcuEstimate_t *e = &r->estimates[i];
        fprintf(f, "    {\"variant\": \"%s\", \"ecu_count\": %u, \"pins_available\": %u, \"pins_used\": %u, \"utilisation_pct\": %.1f}%s\n",
                e->variant, e->ecu_count, e->total_pins_available,
                e->total_pins_used, (double)e->utilisation_pct,
                (i + 1 < EEC_EST_VARIANT_COUNT) ? "," : "");
    }
    fprintf(f, "  ],\n");

    /* Optional supplier/product ECU selected from the JSON library. */
    fprintf(f, "  \"selected_ecu\": ");
    if (r->selected_ecu.selected) {
        const EEC_SelectedEcuEstimate_t *s = &r->selected_ecu;
        uint32_t j;
        bool first = true;
        fprintf(f, "{\n    \"source\": "); json_escape_str(f, s->source_path);
        fprintf(f, ",\n    \"name\": "); json_escape_str(f, s->name);
        fprintf(f, ",\n    \"variant\": "); json_escape_str(f, s->variant);
        fprintf(f, ",\n    \"compatible\": %s", s->compatible ? "true" : "false");
        fprintf(f, ",\n    \"unsupported_interface_count\": %u",
                s->unsupported_interface_count);
        fprintf(f, ",\n    \"capacity\": {\"total_pins\": %u, \"per_interface\": {",
                s->capacity.total_pins);
        for (j = 0; j < EEC_EST_MAX_IFACE_TYPES; ++j) {
            if (s->capacity.per_iface[j] == 0) continue;
            if (!first) fprintf(f, ", ");
            fprintf(f, "\"%s\": %u", iface_label((EEC_SignalInterface_t)j),
                    s->capacity.per_iface[j]);
            first = false;
        }
        fprintf(f, "}},\n    \"estimate\": {\"ecu_count\": %u, \"pins_available\": %u, "
                   "\"pins_used\": %u, \"utilisation_pct\": %.1f}\n  },\n",
                s->estimate.ecu_count, s->estimate.total_pins_available,
                s->estimate.total_pins_used, (double)s->estimate.utilisation_pct);
    } else {
        fprintf(f, "null,\n");
    }

    /* Mixed proposition */
    fprintf(f, "  \"proposition\": {\n");
    fprintf(f, "    \"ecu_count\": %u,\n", r->proposed_count);
    fprintf(f, "    \"notes\": "); json_escape_str(f, r->proposition_notes); fprintf(f, ",\n");
    fprintf(f, "    \"ecus\": [\n");
    for (i = 0; i < r->proposed_count; ++i) {
        const EEC_ProposedEcu_t *pe = &r->proposed[i];
        fprintf(f, "      {\"variant\": \"%s\", \"systems\": ", pe->variant);
        json_escape_str(f, pe->assigned_systems);
        fprintf(f, ", \"pins_used\": %u, \"pins_total\": %u, \"utilisation_pct\": %.1f}%s\n",
                pe->pins_used, pe->pins_total, (double)pe->utilisation_pct,
                (i + 1 < r->proposed_count) ? "," : "");
    }
    fprintf(f, "    ]\n");
    fprintf(f, "  },\n");

    /* Design rules (structured, data-driven) */
    fprintf(f, "  \"design_rules\": [\n");
    fprintf(f, "    {\"id\": \"R1\", \"title\": \"Safety isolation\",       \"description\": \"Safety-critical systems (SL3+) must have a dedicated ECU — no mixing with other systems.\"},\n");
    fprintf(f, "    {\"id\": \"R2\", \"title\": \"High-priority headroom\", \"description\": \"High-priority systems (CRITICAL/HIGH) prefer MEDIUM or LARGE ECU to allow evolution headroom.\"},\n");
    fprintf(f, "    {\"id\": \"R3\", \"title\": \"Low-IO consolidation\",   \"description\": \"Low-IO or low-priority systems can share a SMALL ECU to reduce cost and wiring.\"},\n");
    fprintf(f, "    {\"id\": \"R4\", \"title\": \"Utilisation target\",     \"description\": \"Target 40-70%% ECU utilisation for maintainability and future evolution margin.\"},\n");
    fprintf(f, "    {\"id\": \"R5\", \"title\": \"ECU count minimisation\", \"description\": \"Minimise total ECU count to reduce wiring, weight and integration cost.\"},\n");
    fprintf(f, "    {\"id\": \"R6\", \"title\": \"Interface compatibility\", \"description\": \"Each ECU must physically support all required signal interface types for its assigned systems.\"}\n");
    fprintf(f, "  ],\n");

    /* Design thresholds (so the report can display them without hardcoding) */
    fprintf(f, "  \"thresholds\": {\n");
    fprintf(f, "    \"safety_signal_threshold\": %u,\n", (unsigned)EEC_EST_SAFETY_THRESHOLD_SIGNALS);
    fprintf(f, "    \"highpri_signal_threshold\": %u,\n", (unsigned)EEC_EST_HIGHPRI_THRESHOLD_SIGNALS);
    fprintf(f, "    \"shared_fill_percent\": %u\n", (unsigned)EEC_EST_SHARE_FILL_PCT);
    fprintf(f, "  }\n");
    fprintf(f, "}\n");

    fclose(f);
    return 0;
}

/* ════════════════════════════════════════════════════════════════════════
 *  Public entry point
 * ════════════════════════════════════════════════════════════════════════ */

int EEC_Estimation_RunWithEcu(const char *platform_path,
                              const char *library_dir,
                              const char *ecu_json_path,
                              const char *output_json)
{
    EEC_EstimationResult_t result;
    EEC_Architecture_t *arch = NULL;
    EEC_Architecture_t *scratch = NULL;
    PlatformEntry entries[EEC_EST_MAX_SYSTEMS];
    const EEC_System_t *imported_systems[EEC_EST_MAX_SYSTEMS];
    int entry_count;
    uint32_t i, v, imported_idx = 0;

    memset(&result, 0, sizeof(result));
    memset(imported_systems, 0, sizeof(imported_systems));

    EEC_Log_Printf(EEC_LOG_INFO, "════════════════════════════════════════════════════════════");
    EEC_Log_Printf(EEC_LOG_INFO, "=== E/E Architect Design Estimation Pipeline ===");
    EEC_Log_Printf(EEC_LOG_INFO, "════════════════════════════════════════════════════════════");

    /* ── Step 1/7: Parse platform file ─────────────────────────────────── */
    EEC_Log_Printf(EEC_LOG_INFO, "[Step 1/7] Parsing platform file: %s", platform_path);
    entry_count = parse_platform_file(platform_path, result.platform_name,
                                       sizeof(result.platform_name),
                                       entries, EEC_EST_MAX_SYSTEMS);
    if (entry_count < 0) {
        EEC_Log_Printf(EEC_LOG_ERROR, "  FAILED — could not parse platform file");
        return -1;
    }
    result.system_count = (uint32_t)entry_count;
    EEC_Log_Printf(EEC_LOG_INFO, "  Platform: '%s' — %d system(s) listed", result.platform_name, entry_count);

    /* ── Step 2/7: Resolve systems from library ────────────────────────── */
    EEC_Log_Printf(EEC_LOG_INFO, "[Step 2/7] Resolving systems from library: %s/systems/", library_dir);
    arch = EEC_Architecture_Create("Estimation_Workspace");
    if (!arch) return -1;

    for (i = 0; i < (uint32_t)entry_count; ++i) {
        char sys_path[800] = "";
        EEC_SystemIo_t *sio = &result.systems[i];

        memcpy(sio->ref_2x, entries[i].ref_2x, sizeof(sio->ref_2x));
        sio->ref_2x[sizeof(sio->ref_2x) - 1] = '\0';

        if (find_system_by_ref2x(library_dir, entries[i].ref_2x, sys_path, sizeof(sys_path))) {
            EEC_System_t *sys = EEC_Library_ImportSystem(arch, sys_path);
            if (sys) {
                snprintf(sio->name, sizeof(sio->name), "%s", sys->name);
                sio->found_in_library = true;
                count_system_io(sys, sio);
                imported_systems[imported_idx++] = sys;
                result.systems_found++;
                EEC_Log_Printf(EEC_LOG_INFO, "  [%u/%u] '%s' -> %s  (%u signals, %u iface types)",
                              i + 1, result.system_count, entries[i].ref_2x,
                              sys->name, sio->total_signals, sio->iface_count);
            } else {
                snprintf(sio->name, sizeof(sio->name), "(import failed)");
                sio->found_in_library = false;
                result.systems_missing++;
                EEC_Log_Printf(EEC_LOG_ERROR, "  [%u/%u] '%s' -> import FAILED",
                              i + 1, result.system_count, entries[i].ref_2x);
            }
        } else {
            snprintf(sio->name, sizeof(sio->name), "(not found)");
            sio->found_in_library = false;
            result.systems_missing++;
            EEC_Log_Printf(EEC_LOG_WARN, "  [%u/%u] '%s' -> NOT FOUND in library",
                          i + 1, result.system_count, entries[i].ref_2x);
        }
    }
    EEC_Log_Printf(EEC_LOG_INFO, "  Result: %u found, %u missing", result.systems_found, result.systems_missing);

    /* ── Step 3/7: Aggregate architecture-level IO ─────────────────────── */
    EEC_Log_Printf(EEC_LOG_INFO, "[Step 3/7] Aggregating architecture IO demand");
    for (i = 0; i < result.system_count; ++i) {
        uint32_t j;
        if (!result.systems[i].found_in_library) continue;
        for (j = 0; j < result.systems[i].iface_count; ++j) {
            uint32_t bi = iface_bucket(result.arch_io, &result.arch_iface_count,
                                        result.systems[i].per_iface[j].interface_type);
            result.arch_io[bi].input_count  += result.systems[i].per_iface[j].input_count;
            result.arch_io[bi].output_count += result.systems[i].per_iface[j].output_count;
            result.arch_io[bi].inout_count  += result.systems[i].per_iface[j].inout_count;
            result.arch_io[bi].total        += result.systems[i].per_iface[j].total;
        }
        result.arch_total_signals += result.systems[i].total_signals;
    }
    EEC_Log_Printf(EEC_LOG_INFO, "  Total: %u signals across %u interface types",
                  result.arch_total_signals, result.arch_iface_count);
    for (i = 0; i < result.arch_iface_count; ++i) {
        EEC_Log_Printf(EEC_LOG_INFO, "    %-10s : %u IN, %u OUT, %u INOUT = %u total",
                      iface_label(result.arch_io[i].interface_type),
                      result.arch_io[i].input_count, result.arch_io[i].output_count,
                      result.arch_io[i].inout_count, result.arch_io[i].total);
    }

    /* ── Step 4/7: Compute ECU variant capacities ──────────────────────── */
    EEC_Log_Printf(EEC_LOG_INFO, "[Step 4/7] Computing ECU variant pin capacities");
    scratch = EEC_Architecture_Create("_scratch_caps");
    if (scratch) {
        for (v = 0; v < EEC_EST_VARIANT_COUNT; ++v) {
            compute_ecu_capacity(scratch, v, &result.capacities[v]);
            EEC_Log_Printf(EEC_LOG_INFO, "  AEC %-6s : %u usable pins",
                          result.capacities[v].variant, result.capacities[v].total_pins);
        }
        if (ecu_json_path && ecu_json_path[0] != '\0') {
            EEC_Ecu_t *selected = EEC_Library_ImportEcu(
                    scratch, ecu_json_path, NULL);
            if (!selected) {
                EEC_Log_Printf(EEC_LOG_ERROR,
                               "  FAILED — could not import selected ECU '%s'", ecu_json_path);
                EEC_Architecture_Destroy(scratch);
                EEC_Architecture_Destroy(arch);
                return -1;
            }
            result.selected_ecu.selected = true;
            snprintf(result.selected_ecu.source_path, sizeof(result.selected_ecu.source_path),
                     "%s", ecu_json_path);
            snprintf(result.selected_ecu.name, sizeof(result.selected_ecu.name),
                     "%s", selected->name);
            snprintf(result.selected_ecu.variant, sizeof(result.selected_ecu.variant),
                     "%s", selected->variant);
            compute_capacity_from_ecu(selected, selected->name,
                                      &result.selected_ecu.capacity);
            compute_homogeneous_estimate(result.arch_io, result.arch_iface_count,
                                         result.arch_total_signals,
                                         &result.selected_ecu.capacity,
                                         &result.selected_ecu.estimate);
            result.selected_ecu.compatible = true;
            for (i = 0; i < result.arch_iface_count; ++i) {
                EEC_SignalInterface_t iface = result.arch_io[i].interface_type;
                if (result.arch_io[i].total > 0U
                    && result.selected_ecu.capacity.per_iface[iface] == 0U) {
                    result.selected_ecu.compatible = false;
                    result.selected_ecu.unsupported_interface_count++;
                    EEC_Log_Printf(EEC_LOG_WARN,
                                   "  Selected ECU has no %s capacity (%u required)",
                                   iface_label(iface), result.arch_io[i].total);
                }
            }
            EEC_Log_Printf(EEC_LOG_INFO,
                           "  Selected %-20s : %u ECU(s), %u/%u pins, %.1f%% utilisation",
                           result.selected_ecu.name, result.selected_ecu.estimate.ecu_count,
                           result.selected_ecu.estimate.total_pins_used,
                           result.selected_ecu.estimate.total_pins_available,
                           (double)result.selected_ecu.estimate.utilisation_pct);
        }
        EEC_Architecture_Destroy(scratch);
    }

    /* ── Step 5/7: Homogeneous ECU estimates ───────────────────────────── */
    EEC_Log_Printf(EEC_LOG_INFO, "[Step 5/7] Computing homogeneous ECU estimates");
    for (v = 0; v < EEC_EST_VARIANT_COUNT; ++v) {
        compute_homogeneous_estimate(result.arch_io, result.arch_iface_count,
                                      result.arch_total_signals,
                                      &result.capacities[v], &result.estimates[v]);
        EEC_Log_Printf(EEC_LOG_INFO, "  All-%-6s : %u ECU(s), %u/%u pins, %.1f%% utilisation",
                      result.estimates[v].variant,
                      result.estimates[v].ecu_count,
                      result.estimates[v].total_pins_used,
                      result.estimates[v].total_pins_available,
                      (double)result.estimates[v].utilisation_pct);
    }

    /* ── Step 6/7: Optimised mixed proposition ─────────────────────────── */
    EEC_Log_Printf(EEC_LOG_INFO, "[Step 6/7] Computing optimised mixed proposition");
    EEC_Log_Printf(EEC_LOG_INFO, "  Thresholds: safety=%u, highpri=%u, share_fill=%u%%",
                  (unsigned)EEC_EST_SAFETY_THRESHOLD_SIGNALS,
                  (unsigned)EEC_EST_HIGHPRI_THRESHOLD_SIGNALS,
                  (unsigned)EEC_EST_SHARE_FILL_PCT);
    compute_mixed_proposition(&result, imported_systems, imported_idx,
                               &result.capacities[0], &result.capacities[1],
                               &result.capacities[2]);
    EEC_Log_Printf(EEC_LOG_INFO, "  Proposition: %u ECU(s)", result.proposed_count);
    for (i = 0; i < result.proposed_count; ++i) {
        const EEC_ProposedEcu_t *pe = &result.proposed[i];
        EEC_Log_Printf(EEC_LOG_INFO, "    ECU #%u: AEC %-6s | %u/%u pins (%.1f%%) | Systems: %s",
                      i + 1, pe->variant, pe->pins_used, pe->pins_total,
                      (double)pe->utilisation_pct, pe->assigned_systems);
    }

    /* ── Step 7/7: Write JSON result ──────────────────────────────────── */
    EEC_Log_Printf(EEC_LOG_INFO, "[Step 7/7] Writing estimation result to: %s", output_json);
    if (write_estimation_json(&result, output_json) != 0) {
        EEC_Log_Printf(EEC_LOG_ERROR, "  FAILED — could not write '%s'", output_json);
        EEC_Architecture_Destroy(arch);
        return -1;
    }

    /* ── Summary ───────────────────────────────────────────────────────── */
    EEC_Log_Printf(EEC_LOG_INFO, "════════════════════════════════════════════════════════════");
    EEC_Log_Printf(EEC_LOG_INFO, "  ESTIMATION SUMMARY");
    EEC_Log_Printf(EEC_LOG_INFO, "  Platform     : %s", result.platform_name);
    EEC_Log_Printf(EEC_LOG_INFO, "  Systems      : %u found, %u missing, %u total",
                  result.systems_found, result.systems_missing, result.system_count);
    EEC_Log_Printf(EEC_LOG_INFO, "  Total signals: %u", result.arch_total_signals);
    for (v = 0; v < EEC_EST_VARIANT_COUNT; ++v) {
        EEC_Log_Printf(EEC_LOG_INFO, "  All-%-6s   : %u ECU(s)  (%.1f%% util)",
                      result.estimates[v].variant,
                      result.estimates[v].ecu_count,
                      (double)result.estimates[v].utilisation_pct);
    }
    EEC_Log_Printf(EEC_LOG_INFO, "  Best mix     : %u ECU(s)", result.proposed_count);
    EEC_Log_Printf(EEC_LOG_INFO, "  Output       : %s", output_json);
    EEC_Log_Printf(EEC_LOG_INFO, "════════════════════════════════════════════════════════════");
    EEC_Log_Printf(EEC_LOG_INFO, "=== E/E Architect Design Estimation end ===");

    EEC_Architecture_Destroy(arch);
    return 0;
}

int EEC_Estimation_Run(const char *platform_path,
                       const char *library_dir,
                       const char *output_json)
{
    return EEC_Estimation_RunWithEcu(platform_path, library_dir, NULL, output_json);
}
