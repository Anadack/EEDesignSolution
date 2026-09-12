/**
 * @file    EEC_zone.c
 * @brief   E/E Architect Design — Zonal/Central distribution implementation.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#include "EEC_zone.h"
#include "EEC_log.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── small helpers ──────────────────────────────────────────────────────── */

static bool zone_str_ieq(const char *a, const char *b)
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

/* ── mode ───────────────────────────────────────────────────────────────── */

void EEC_Architecture_SetMode(EEC_Architecture_t *arch, EEC_ArchMode_t mode)
{
    if (arch) {
        arch->mode = mode;
    }
}

const char *EEC_ArchMode_ToString(EEC_ArchMode_t mode)
{
    return (mode == EEC_ARCH_MODE_ZONAL) ? "ZONAL" : "CENTRAL";
}

EEC_ArchMode_t EEC_ArchMode_FromString(const char *name)
{
    return zone_str_ieq(name, "zonal") ? EEC_ARCH_MODE_ZONAL : EEC_ARCH_MODE_CENTRAL;
}

/* ── lookups ────────────────────────────────────────────────────────────── */

EEC_Ecu_t *EEC_Architecture_FindEcu(EEC_Architecture_t *arch, const char *name)
{
    uint32_t i;
    if (!arch || !name) {
        return NULL;
    }
    for (i = 0U; i < arch->ecu_count; ++i) {
        if (arch->ecus[i] && strcmp(arch->ecus[i]->name, name) == 0) {
            return arch->ecus[i];
        }
    }
    return NULL;
}

EEC_System_t *EEC_Architecture_FindSystem(EEC_Architecture_t *arch, const char *name)
{
    uint32_t i;
    if (!arch || !name) {
        return NULL;
    }
    for (i = 0U; i < arch->system_count; ++i) {
        if (arch->systems[i] && strcmp(arch->systems[i]->name, name) == 0) {
            return arch->systems[i];
        }
    }
    return NULL;
}

EEC_Zone_t *EEC_Architecture_FindZone(EEC_Architecture_t *arch, const char *name)
{
    uint32_t i;
    if (!arch || !name) {
        return NULL;
    }
    for (i = 0U; i < arch->zone_count; ++i) {
        if (arch->zones[i] && strcmp(arch->zones[i]->name, name) == 0) {
            return arch->zones[i];
        }
    }
    return NULL;
}

/* ── zone construction ──────────────────────────────────────────────────── */

EEC_Zone_t *EEC_Architecture_CreateZone(EEC_Architecture_t *arch, const char *name)
{
    EEC_Zone_t *zone;
    EEC_Zone_t **grown;

    if (!arch || !name || !name[0]) {
        return NULL;
    }
    zone = EEC_Architecture_FindZone(arch, name);
    if (zone) {
        return zone;
    }

    zone = (EEC_Zone_t *)calloc(1U, sizeof(EEC_Zone_t));
    if (!zone) {
        return NULL;
    }
    zone->id = arch->zone_count + 1U;
    strncpy(zone->name, name, sizeof(zone->name) - 1U);
    zone->owner_architecture = arch;

    grown = (EEC_Zone_t **)realloc(arch->zones, (arch->zone_count + 1U) * sizeof(*grown));
    if (!grown) {
        free(zone);
        return NULL;
    }
    arch->zones = grown;
    arch->zones[arch->zone_count++] = zone;
    EEC_Log_Printf(EEC_LOG_INFO, "Created zone '%s'", zone->name);
    return zone;
}

int EEC_Zone_AddEcu(EEC_Zone_t *zone, EEC_Ecu_t *ecu)
{
    uint32_t i;
    EEC_Ecu_t **grown;

    if (!zone || !ecu) {
        return -1;
    }
    for (i = 0U; i < zone->ecu_count; ++i) {
        if (zone->ecus[i] == ecu) {
            return 0;
        }
    }
    grown = (EEC_Ecu_t **)realloc(zone->ecus, (zone->ecu_count + 1U) * sizeof(*grown));
    if (!grown) {
        return -1;
    }
    zone->ecus = grown;
    zone->ecus[zone->ecu_count++] = ecu;
    return 0;
}

int EEC_Architecture_AssignSystemToZone(EEC_System_t *system, EEC_Zone_t *zone)
{
    if (!system || !zone) {
        return -1;
    }
    system->zone = zone;
    return 0;
}

/* ── minimal JSON scanner (objects/arrays/strings only) ─────────────────── */

static void json_skip_ws(const char **p)
{
    while (**p == ' ' || **p == '\t' || **p == '\n' || **p == '\r') {
        ++(*p);
    }
}

/** Read a "..."-quoted string into out (no escape handling needed here). */
static bool json_string(const char **p, char *out, size_t out_size)
{
    size_t n = 0U;
    json_skip_ws(p);
    if (**p != '"') {
        return false;
    }
    ++(*p);
    while (**p && **p != '"') {
        if (n + 1U < out_size) {
            out[n++] = **p;
        }
        ++(*p);
    }
    if (**p != '"') {
        return false;
    }
    ++(*p);
    out[n] = '\0';
    return true;
}

/** Skip one JSON value (string/number/bool/null/object/array). */
static void json_skip_value(const char **p)
{
    json_skip_ws(p);
    if (**p == '"') {
        char tmp[8];
        (void)json_string(p, tmp, 1U); /* reuse scanner; content discarded */
        return;
    }
    if (**p == '{' || **p == '[') {
        char open = **p;
        char close = (open == '{') ? '}' : ']';
        int depth = 0;
        while (**p) {
            if (**p == '"') {
                char tmp[8];
                (void)json_string(p, tmp, 1U);
                continue;
            }
            if (**p == open) { ++depth; }
            else if (**p == close) { --depth; if (depth == 0) { ++(*p); return; } }
            ++(*p);
        }
        return;
    }
    /* primitive: advance to next delimiter */
    while (**p && **p != ',' && **p != '}' && **p != ']') {
        ++(*p);
    }
}

/** Parse an array of strings, invoking cb(ctx, value) for each element. */
static void json_string_array(const char **p, void (*cb)(void *, const char *), void *ctx)
{
    json_skip_ws(p);
    if (**p != '[') {
        json_skip_value(p);
        return;
    }
    ++(*p);
    json_skip_ws(p);
    if (**p == ']') { ++(*p); return; }
    for (;;) {
        char val[64];
        if (json_string(p, val, sizeof(val))) {
            cb(ctx, val);
        }
        json_skip_ws(p);
        if (**p == ',') { ++(*p); continue; }
        if (**p == ']') { ++(*p); break; }
        break;
    }
}

typedef struct {
    EEC_Architecture_t *arch;
    EEC_Zone_t         *zone;
} zone_ctx_t;

static void cb_add_ecu(void *ctx, const char *name)
{
    zone_ctx_t *z = (zone_ctx_t *)ctx;
    EEC_Ecu_t *ecu = EEC_Architecture_FindEcu(z->arch, name);
    if (ecu) {
        (void)EEC_Zone_AddEcu(z->zone, ecu);
    } else {
        EEC_Log_Printf(EEC_LOG_WARN, "LoadZones: unknown ECU '%s' in zone '%s'", name, z->zone->name);
    }
}

static void cb_assign_system(void *ctx, const char *name)
{
    zone_ctx_t *z = (zone_ctx_t *)ctx;
    EEC_System_t *sys = EEC_Architecture_FindSystem(z->arch, name);
    if (sys) {
        (void)EEC_Architecture_AssignSystemToZone(sys, z->zone);
    } else {
        EEC_Log_Printf(EEC_LOG_WARN, "LoadZones: unknown system '%s' in zone '%s'", name, z->zone->name);
    }
}

/** Parse one zone object: { "name":..., "ecus":[...], "systems":[...] }. */
static void parse_zone_object(const char **p, EEC_Architecture_t *arch)
{
    char zone_name[64] = {0};
    zone_ctx_t ctx;

    json_skip_ws(p);
    if (**p != '{') { json_skip_value(p); return; }
    ++(*p);

    ctx.arch = arch;
    ctx.zone = NULL;

    for (;;) {
        char key[32];
        json_skip_ws(p);
        if (**p == '}') { ++(*p); break; }
        if (!json_string(p, key, sizeof(key))) { break; }
        json_skip_ws(p);
        if (**p == ':') { ++(*p); }

        if (strcmp(key, "name") == 0) {
            (void)json_string(p, zone_name, sizeof(zone_name));
            ctx.zone = EEC_Architecture_CreateZone(arch, zone_name);
        } else if (strcmp(key, "ecus") == 0) {
            if (!ctx.zone) { ctx.zone = EEC_Architecture_CreateZone(arch, zone_name); }
            json_string_array(p, cb_add_ecu, &ctx);
        } else if (strcmp(key, "systems") == 0) {
            if (!ctx.zone) { ctx.zone = EEC_Architecture_CreateZone(arch, zone_name); }
            json_string_array(p, cb_assign_system, &ctx);
        } else {
            json_skip_value(p);
        }

        json_skip_ws(p);
        if (**p == ',') { ++(*p); continue; }
        if (**p == '}') { ++(*p); break; }
    }
}

int EEC_Architecture_LoadZones(EEC_Architecture_t *arch, const char *path)
{
    FILE *f;
    long size;
    char *buf;
    const char *p;
    uint32_t start_zone_count;

    if (!arch || !path) {
        return -1;
    }
    f = fopen(path, "rb");
    if (!f) {
        return -1;
    }
    fseek(f, 0L, SEEK_END);
    size = ftell(f);
    fseek(f, 0L, SEEK_SET);
    if (size <= 0L) {
        fclose(f);
        return -1;
    }
    buf = (char *)malloc((size_t)size + 1U);
    if (!buf) {
        fclose(f);
        return -1;
    }
    if (fread(buf, 1U, (size_t)size, f) != (size_t)size) {
        free(buf);
        fclose(f);
        return -1;
    }
    buf[size] = '\0';
    fclose(f);

    start_zone_count = arch->zone_count;
    p = buf;
    json_skip_ws(&p);
    if (*p != '{') { free(buf); return -1; }
    ++p;

    for (;;) {
        char key[32];
        json_skip_ws(&p);
        if (*p == '}' || *p == '\0') { break; }
        if (!json_string(&p, key, sizeof(key))) { break; }
        json_skip_ws(&p);
        if (*p == ':') { ++p; }

        if (strcmp(key, "mode") == 0) {
            char mode_s[16];
            if (json_string(&p, mode_s, sizeof(mode_s))) {
                EEC_Architecture_SetMode(arch, EEC_ArchMode_FromString(mode_s));
            }
        } else if (strcmp(key, "zones") == 0) {
            json_skip_ws(&p);
            if (*p == '[') {
                ++p;
                json_skip_ws(&p);
                if (*p == ']') { ++p; }
                else {
                    for (;;) {
                        parse_zone_object(&p, arch);
                        json_skip_ws(&p);
                        if (*p == ',') { ++p; continue; }
                        if (*p == ']') { ++p; break; }
                        break;
                    }
                }
            } else {
                json_skip_value(&p);
            }
        } else {
            json_skip_value(&p);
        }

        json_skip_ws(&p);
        if (*p == ',') { ++p; continue; }
        if (*p == '}') { break; }
    }

    free(buf);
    EEC_Log_Printf(EEC_LOG_INFO, "LoadZones: %u zone(s) from %s (mode=%s)",
                   arch->zone_count - start_zone_count, path,
                   EEC_ArchMode_ToString(arch->mode));
    return (int)(arch->zone_count - start_zone_count);
}

/* ── export ─────────────────────────────────────────────────────────────── */

int EEC_Export_zones_json(const EEC_Architecture_t *arch, const char *path)
{
    FILE *f;
    uint32_t z, e, s;

    if (!arch || !path) {
        return -1;
    }
    f = fopen(path, "w");
    if (!f) {
        return -1;
    }

    fprintf(f, "{\n");
    fprintf(f, "  \"mode\": \"%s\",\n", EEC_ArchMode_ToString(arch->mode));
    fprintf(f, "  \"zones\": [\n");
    for (z = 0U; z < arch->zone_count; ++z) {
        const EEC_Zone_t *zone = arch->zones[z];
        if (!zone) {
            continue;
        }
        fprintf(f, "    {\n");
        fprintf(f, "      \"name\": \"%s\",\n", zone->name);

        fprintf(f, "      \"ecus\": [");
        for (e = 0U; e < zone->ecu_count; ++e) {
            fprintf(f, "%s\"%s\"", (e ? ", " : ""),
                    zone->ecus[e] ? zone->ecus[e]->name : "");
        }
        fprintf(f, "],\n");

        fprintf(f, "      \"systems\": [");
        {
            bool first = true;
            for (s = 0U; s < arch->system_count; ++s) {
                if (arch->systems[s] && arch->systems[s]->zone == zone) {
                    fprintf(f, "%s\"%s\"", (first ? "" : ", "), arch->systems[s]->name);
                    first = false;
                }
            }
        }
        fprintf(f, "]\n");
        fprintf(f, "    }%s\n", (z + 1U < arch->zone_count) ? "," : "");
    }
    fprintf(f, "  ]\n");
    fprintf(f, "}\n");

    fclose(f);
    EEC_Log_Printf(EEC_LOG_INFO, "Zones export: %u zone(s) -> %s", arch->zone_count, path);
    return 0;
}

/* ── verification ───────────────────────────────────────────────────────── */

int EEC_Verify_zones(const EEC_Architecture_t *arch, FILE *report)
{
    int errors = 0;
    uint32_t i;

    if (!arch) {
        return 0;
    }
    if (arch->mode != EEC_ARCH_MODE_ZONAL) {
        if (report) {
            fprintf(report, "[ZONES] mode=CENTRAL — zone assignment not required.\n");
        }
        return 0;
    }

    if (report) {
        fprintf(report, "[ZONES] mode=ZONAL — checking zone assignments.\n");
    }

    /* Every zone must have at least one ECU. */
    for (i = 0U; i < arch->zone_count; ++i) {
        const EEC_Zone_t *zone = arch->zones[i];
        if (zone && zone->ecu_count == 0U) {
            ++errors;
            if (report) {
                fprintf(report, "  [FAIL] zone '%s' has no ECU.\n", zone->name);
            }
        }
    }

    /* Every auto-mappable system must be assigned to exactly one zone. */
    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *sys = arch->systems[i];
        if (!sys || !sys->auto_mapping_enabled) {
            continue;
        }
        if (!sys->zone) {
            ++errors;
            if (report) {
                fprintf(report, "  [FAIL] system '%s' is not assigned to any zone.\n", sys->name);
            }
        }
    }

    /* Z1: each ECU must belong to at most one zone (no ECU in two zones). */
    for (i = 0U; i < arch->ecu_count; ++i) {
        const EEC_Ecu_t *ecu = arch->ecus[i];
        uint32_t z, in = 0U;
        if (!ecu) continue;
        for (z = 0U; z < arch->zone_count; ++z) {
            const EEC_Zone_t *zone = arch->zones[z];
            uint32_t e;
            if (!zone) continue;
            for (e = 0U; e < zone->ecu_count; ++e) {
                if (zone->ecus[e] == ecu) { ++in; break; }
            }
        }
        if (in > 1U) {
            ++errors;
            if (report) fprintf(report, "  [FAIL] Z1 ECU '%s' assigned to %u zones (must be exactly one).\n", ecu->name, in);
        }
        /* Z2: every ECU must belong to some zone in ZONAL mode. */
        if (in == 0U) {
            ++errors;
            if (report) fprintf(report, "  [FAIL] Z2 ECU '%s' is not assigned to any zone.\n", ecu->name);
        }
    }

    /* Z3: inter-zone connectivity. With more than one zone, each zone must have
       at least one ECU that sits on a bus shared with an ECU from another zone
       (a backbone). A zone with no inter-zone bus link is islanded — cross-zone
       signals from it cannot be routed. */
    if (arch->zone_count > 1U && arch->bus_count > 0U) {
        for (i = 0U; i < arch->zone_count; ++i) {
            const EEC_Zone_t *zone = arch->zones[i];
            bool linked = false;
            uint32_t b;
            if (!zone || zone->ecu_count == 0U) continue;
            for (b = 0U; b < arch->bus_count && !linked; ++b) {
                const EEC_Bus_t *bus = arch->buses[b];
                bool has_self = false, has_other = false;
                uint32_t n, e;
                if (!bus) continue;
                for (n = 0U; n < bus->node_count; ++n) {
                    const EEC_Ecu_t *necu = bus->nodes[n].ecu;
                    bool in_zone = false;
                    if (!necu) continue;
                    for (e = 0U; e < zone->ecu_count; ++e) {
                        if (zone->ecus[e] == necu) { in_zone = true; break; }
                    }
                    if (in_zone) has_self = true; else has_other = true;
                }
                if (has_self && has_other) linked = true;
            }
            if (!linked) {
                ++errors;
                if (report) fprintf(report, "  [FAIL] Z3 zone '%s' has no inter-zone bus link (islanded — cross-zone signals cannot be routed).\n", zone->name);
            }
        }
    }

    if (report) {
        fprintf(report, "[ZONES] %d error(s).\n", errors);
    }
    return errors;
}
