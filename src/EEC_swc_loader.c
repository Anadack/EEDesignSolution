/**
 * @file    EEC_swc_loader.c
 * @brief   E/E Architect Design — Data-driven SWC / CAN message importer.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */

#include "EEC_swc_loader.h"
#include "EEC_message.h"
#include "EEC_log.h"

#include <ctype.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

/* ── Minimal self-contained JSON reader ────────────────────────────────── */

typedef struct {
    const char *buf;
    const char *cur;
    size_t      len;
} Jr;

static char *jr_read_file(const char *path, size_t *out_len)
{
    FILE *f = fopen(path, "rb");
    long sz;
    char *buf;
    if (!f) { return NULL; }
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    sz = ftell(f);
    if (sz < 0) { fclose(f); return NULL; }
    rewind(f);
    buf = (char *)malloc((size_t)sz + 1U);
    if (!buf) { fclose(f); return NULL; }
    if (fread(buf, 1U, (size_t)sz, f) != (size_t)sz) { free(buf); fclose(f); return NULL; }
    buf[sz] = '\0';
    fclose(f);
    if (out_len) { *out_len = (size_t)sz; }
    return buf;
}

static void jr_ws(Jr *r)
{
    while (r->cur < r->buf + r->len && isspace((unsigned char)*r->cur)) {
        ++r->cur;
    }
}

static bool jr_char(Jr *r, char c)
{
    jr_ws(r);
    if (r->cur < r->buf + r->len && *r->cur == c) { ++r->cur; return true; }
    return false;
}

static int jr_string(Jr *r, char *out, size_t out_sz)
{
    size_t n = 0U;
    jr_ws(r);
    if (r->cur >= r->buf + r->len || *r->cur != '"') { return -1; }
    ++r->cur;
    while (r->cur < r->buf + r->len && *r->cur != '"') {
        char c = *r->cur++;
        if (c == '\\' && r->cur < r->buf + r->len) {
            char esc = *r->cur++;
            switch (esc) {
                case 'n':  c = '\n'; break;
                case 'r':  c = '\r'; break;
                case 't':  c = '\t'; break;
                default:   c = esc;  break;
            }
        }
        if (n + 1U < out_sz) { out[n] = c; }
        ++n;
    }
    if (r->cur < r->buf + r->len && *r->cur == '"') { ++r->cur; }
    if (n < out_sz) { out[n] = '\0'; } else if (out_sz > 0U) { out[out_sz - 1U] = '\0'; }
    return (int)n;
}

static double jr_number(Jr *r)
{
    char *end = NULL;
    double v;
    jr_ws(r);
    v = strtod(r->cur, &end);
    if (end > r->cur) { r->cur = end; }
    return v;
}

static bool jr_bool(Jr *r)
{
    jr_ws(r);
    if (r->cur < r->buf + r->len && (*r->cur == 't' || *r->cur == 'T')) {
        while (r->cur < r->buf + r->len && isalpha((unsigned char)*r->cur)) { ++r->cur; }
        return true;
    }
    while (r->cur < r->buf + r->len && isalpha((unsigned char)*r->cur)) { ++r->cur; }
    return false;
}

/* Skip one value; cursor left just after it. */
static void jr_skip(Jr *r)
{
    jr_ws(r);
    if (r->cur >= r->buf + r->len) { return; }
    if (*r->cur == '"') { char t[8]; jr_string(r, t, sizeof(t)); return; }
    if (*r->cur == '{' || *r->cur == '[') {
        int depth = 0;
        do {
            if (*r->cur == '"') { char t[8]; jr_string(r, t, sizeof(t)); continue; }
            if (*r->cur == '{' || *r->cur == '[') { ++depth; }
            else if (*r->cur == '}' || *r->cur == ']') { --depth; }
            ++r->cur;
        } while (depth > 0 && r->cur < r->buf + r->len);
        return;
    }
    while (r->cur < r->buf + r->len &&
           *r->cur != ',' && *r->cur != '}' && *r->cur != ']') {
        ++r->cur;
    }
}

/* Seek a key within the object whose body starts at @p obj_start (just after
 * '{'). On success the cursor is right after ':'. Returns false otherwise. */
static bool jr_seek(Jr *r, const char *obj_start, const char *key)
{
    char k[128];
    r->cur = obj_start;
    jr_ws(r);
    while (r->cur < r->buf + r->len && *r->cur != '}') {
        jr_ws(r);
        if (*r->cur == ',') { ++r->cur; jr_ws(r); }
        if (*r->cur == '}') { break; }
        if (jr_string(r, k, sizeof(k)) < 0) { break; }
        if (!jr_char(r, ':')) { break; }
        if (strcmp(k, key) == 0) { return true; }
        jr_skip(r);
    }
    return false;
}

/* Advance the cursor from just after '{' to just after the matching '}'. */
static void jr_skip_object_body(Jr *r)
{
    int depth = 1;
    while (r->cur < r->buf + r->len && depth > 0) {
        if (*r->cur == '"') { char t[8]; jr_string(r, t, sizeof(t)); continue; }
        if (*r->cur == '{' || *r->cur == '[') { ++depth; }
        else if (*r->cur == '}' || *r->cur == ']') { --depth; }
        ++r->cur;
    }
}

/* ── String → enum maps ────────────────────────────────────────────────── */

static EEC_SignalType_t map_type(const char *s)
{
    if (!strcmp(s, "U1"))  { return EEC_SIGNAL_TYPE_UNSIGNED_1BIT; }
    if (!strcmp(s, "U8"))  { return EEC_SIGNAL_TYPE_UNSIGNED_8BIT; }
    if (!strcmp(s, "S8"))  { return EEC_SIGNAL_TYPE_SIGNED_8BIT; }
    if (!strcmp(s, "U16")) { return EEC_SIGNAL_TYPE_UNSIGNED_16BIT; }
    if (!strcmp(s, "S16")) { return EEC_SIGNAL_TYPE_SIGNED_16BIT; }
    if (!strcmp(s, "U32")) { return EEC_SIGNAL_TYPE_UNSIGNED_32BIT; }
    if (!strcmp(s, "S32")) { return EEC_SIGNAL_TYPE_SIGNED_32BIT; }
    if (!strcmp(s, "U64")) { return EEC_SIGNAL_TYPE_UNSIGNED_64BIT; }
    if (!strcmp(s, "S64")) { return EEC_SIGNAL_TYPE_SIGNED_64BIT; }
    if (!strcmp(s, "F32")) { return EEC_SIGNAL_TYPE_FLOAT_32BIT; }
    if (!strcmp(s, "F64")) { return EEC_SIGNAL_TYPE_FLOAT_64BIT; }
    return EEC_SIGNAL_TYPE_UNSIGNED_8BIT;
}

static uint16_t type_bits(EEC_SignalType_t t)
{
    switch (t) {
        case EEC_SIGNAL_TYPE_UNSIGNED_1BIT:  return 1U;
        case EEC_SIGNAL_TYPE_UNSIGNED_8BIT:
        case EEC_SIGNAL_TYPE_SIGNED_8BIT:    return 8U;
        case EEC_SIGNAL_TYPE_UNSIGNED_16BIT:
        case EEC_SIGNAL_TYPE_SIGNED_16BIT:   return 16U;
        case EEC_SIGNAL_TYPE_UNSIGNED_32BIT:
        case EEC_SIGNAL_TYPE_SIGNED_32BIT:
        case EEC_SIGNAL_TYPE_FLOAT_32BIT:    return 32U;
        case EEC_SIGNAL_TYPE_UNSIGNED_64BIT:
        case EEC_SIGNAL_TYPE_SIGNED_64BIT:
        case EEC_SIGNAL_TYPE_FLOAT_64BIT:    return 64U;
        default:                             return 8U;
    }
}

static EEC_SignalInterface_t map_iface(const char *s)
{
    if (!strcmp(s, "DIGITAL"))    { return EEC_SIGNAL_INTERFACE_DIGITAL; }
    if (!strcmp(s, "ANALOG"))     { return EEC_SIGNAL_INTERFACE_ANALOG; }
    if (!strcmp(s, "PWM"))        { return EEC_SIGNAL_INTERFACE_PWM; }
    if (!strcmp(s, "CAN"))        { return EEC_SIGNAL_INTERFACE_CAN; }
    if (!strcmp(s, "LIN"))        { return EEC_SIGNAL_INTERFACE_LIN; }
    if (!strcmp(s, "SENT"))       { return EEC_SIGNAL_INTERFACE_SENT; }
    if (!strcmp(s, "ETHERNET"))   { return EEC_SIGNAL_INTERFACE_ETHERNET; }
    if (!strcmp(s, "RESISTANCE")) { return EEC_SIGNAL_INTERFACE_RESISTANCE; }
    if (!strcmp(s, "FREQUENCY"))  { return EEC_SIGNAL_INTERFACE_FREQUENCY; }
    if (!strcmp(s, "CURRENT"))    { return EEC_SIGNAL_INTERFACE_CURRENT; }
    if (!strcmp(s, "FLEXRAY"))    { return EEC_SIGNAL_INTERFACE_FLEXRAY; }
    if (!strcmp(s, "POWER"))      { return EEC_SIGNAL_INTERFACE_POWER; }
    if (!strcmp(s, "GROUND"))     { return EEC_SIGNAL_INTERFACE_GROUND; }
    return EEC_SIGNAL_INTERFACE_CAN;
}

static EEC_SignalUnit_t map_unit(const char *s)
{
    if (!strcmp(s, "BOOLEAN")) { return EEC_SIGNAL_UNIT_BOOLEAN; }
    if (!strcmp(s, "VOLT"))    { return EEC_SIGNAL_UNIT_VOLT; }
    if (!strcmp(s, "AMPERE"))  { return EEC_SIGNAL_UNIT_AMPERE; }
    if (!strcmp(s, "HERTZ"))   { return EEC_SIGNAL_UNIT_HERTZ; }
    if (!strcmp(s, "PERCENT")) { return EEC_SIGNAL_UNIT_PERCENT; }
    if (!strcmp(s, "RPM"))     { return EEC_SIGNAL_UNIT_RPM; }
    if (!strcmp(s, "CELSIUS")) { return EEC_SIGNAL_UNIT_CELSIUS; }
    if (!strcmp(s, "BAR"))     { return EEC_SIGNAL_UNIT_BAR; }
    if (!strcmp(s, "DEGREE"))  { return EEC_SIGNAL_UNIT_DEGREE; }
    return EEC_SIGNAL_UNIT_NONE;
}

/* ── Architecture lookups by name ──────────────────────────────────────── */

static EEC_System_t *find_system(EEC_Architecture_t *arch, const char *name)
{
    uint32_t i;
    for (i = 0U; i < arch->system_count; ++i) {
        if (arch->systems[i] && strcmp(arch->systems[i]->name, name) == 0) {
            return arch->systems[i];
        }
    }
    return NULL;
}

static EEC_Ecu_t *find_ecu(EEC_Architecture_t *arch, const char *name)
{
    uint32_t i;
    for (i = 0U; i < arch->ecu_count; ++i) {
        if (arch->ecus[i] && strcmp(arch->ecus[i]->name, name) == 0) {
            return arch->ecus[i];
        }
    }
    return NULL;
}

static EEC_Bus_t *find_bus(EEC_Architecture_t *arch, const char *name)
{
    uint32_t i;
    for (i = 0U; i < arch->bus_count; ++i) {
        if (arch->buses[i] && strcmp(arch->buses[i]->name, name) == 0) {
            return arch->buses[i];
        }
    }
    return NULL;
}

static EEC_Signal_t *find_swc_variable(EEC_Swc_t *swc, const char *name)
{
    uint32_t i;
    for (i = 0U; i < swc->variable_count; ++i) {
        if (swc->variables[i] && strcmp(swc->variables[i]->name, name) == 0) {
            return swc->variables[i];
        }
    }
    return NULL;
}

static EEC_System_t *find_system_by_ref(EEC_Architecture_t *arch, const char *ref)
{
    uint32_t i;
    if (!ref || ref[0] == '\0') { return NULL; }
    for (i = 0U; i < arch->system_count; ++i) {
        if (arch->systems[i] && strcmp(arch->systems[i]->ref_2x, ref) == 0) {
            return arch->systems[i];
        }
    }
    return NULL;
}

/* Find an already-loaded SWC by its (author-defined) Ref-2X. Used to reject
 * duplicate SWC identifiers at import time. */
static EEC_Swc_t *find_swc_by_ref(EEC_Architecture_t *arch, const char *ref)
{
    uint32_t i, s;
    if (!ref || ref[0] == '\0') { return NULL; }
    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *sys = arch->systems[i];
        if (!sys) { continue; }
        for (s = 0U; s < sys->swc_count; ++s) {
            if (sys->swcs[s] && strcmp(sys->swcs[s]->ref_2x, ref) == 0) {
                return sys->swcs[s];
            }
        }
    }
    return NULL;
}

/* ── Nested parsers ────────────────────────────────────────────────────── */

static void parse_variables(Jr *r, EEC_Swc_t *swc)
{
    if (!jr_char(r, '[')) { return; }
    for (;;) {
        const char *vs;
        char name[64] = {0};
        char type[8]  = {0};
        char iface[16] = {0};
        char unit[16] = {0};
        double mn = 0.0, mx = 0.0, res = 1.0, sca = 1.0;

        jr_ws(r);
        if (jr_char(r, ']')) { break; }
        if (!jr_char(r, '{')) { break; }
        vs = r->cur;

        if (jr_seek(r, vs, "name"))       { (void)jr_string(r, name, sizeof(name)); }
        if (jr_seek(r, vs, "type"))       { (void)jr_string(r, type, sizeof(type)); }
        if (jr_seek(r, vs, "interface"))  { (void)jr_string(r, iface, sizeof(iface)); }
        if (jr_seek(r, vs, "unit"))       { (void)jr_string(r, unit, sizeof(unit)); }
        if (jr_seek(r, vs, "min"))        { mn = jr_number(r); }
        if (jr_seek(r, vs, "max"))        { mx = jr_number(r); }
        if (jr_seek(r, vs, "resolution")) { res = jr_number(r); }
        if (jr_seek(r, vs, "scaling"))    { sca = jr_number(r); }

        if (name[0] != '\0') {
            (void)EEC_Swc_CreateVariable(swc, name,
                                         map_type(type[0] ? type : "U8"),
                                         map_iface(iface[0] ? iface : "CAN"),
                                         map_unit(unit),
                                         (float)mn, (float)mx, (float)res, (float)sca);
        }

        r->cur = vs;
        jr_skip_object_body(r);
        jr_ws(r);
        if (jr_char(r, ',')) { continue; }
        (void)jr_char(r, ']');
        break;
    }
}

static void parse_tx(Jr *r, EEC_Architecture_t *arch, EEC_Swc_t *swc, EEC_Message_t *msg)
{
    if (!jr_char(r, '[')) { return; }
    for (;;) {
        const char *ts;
        char bus_name[64] = {0};
        double port = 1.0, cycle = 0.0;
        EEC_Bus_t *bus;

        jr_ws(r);
        if (jr_char(r, ']')) { break; }
        if (!jr_char(r, '{')) { break; }
        ts = r->cur;

        if (jr_seek(r, ts, "bus"))      { (void)jr_string(r, bus_name, sizeof(bus_name)); }
        if (jr_seek(r, ts, "port"))     { port = jr_number(r); }
        if (jr_seek(r, ts, "cycle_ms")) { cycle = jr_number(r); }

        bus = find_bus(arch, bus_name);
        if (bus && swc->allocated_ecu) {
            (void)EEC_Message_AddTxPort(msg, bus, swc->allocated_ecu,
                                        (uint8_t)port, (uint32_t)cycle);
        }

        r->cur = ts;
        jr_skip_object_body(r);
        jr_ws(r);
        if (jr_char(r, ',')) { continue; }
        (void)jr_char(r, ']');
        break;
    }
}

/* Parse a "signals" array. Entries may be a plain string (auto-packed) or an
 * object {"name":..,"start_bit":..,"length":..}. Auto-packing places each
 * signal at the next free bit using its natural bit width. */
static void parse_signals(Jr *r, EEC_Swc_t *swc, EEC_Message_t *msg)
{
    uint16_t next_bit = 0U;
    if (!jr_char(r, '[')) { return; }
    for (;;) {
        char name[64] = {0};
        int explicit_start = -1;
        int explicit_len = -1;
        EEC_Signal_t *sig;
        uint16_t start, len;

        jr_ws(r);
        if (jr_char(r, ']')) { break; }

        if (r->cur < r->buf + r->len && *r->cur == '"') {
            (void)jr_string(r, name, sizeof(name));
        } else if (jr_char(r, '{')) {
            const char *ss = r->cur;
            if (jr_seek(r, ss, "name"))      { (void)jr_string(r, name, sizeof(name)); }
            if (jr_seek(r, ss, "start_bit")) { explicit_start = (int)jr_number(r); }
            if (jr_seek(r, ss, "length"))    { explicit_len = (int)jr_number(r); }
            r->cur = ss;
            jr_skip_object_body(r);
        } else {
            break;
        }

        sig = (name[0] != '\0') ? find_swc_variable(swc, name) : NULL;
        if (sig) {
            len = (explicit_len >= 0) ? (uint16_t)explicit_len : type_bits(sig->type);
            start = (explicit_start >= 0) ? (uint16_t)explicit_start : next_bit;
            (void)EEC_Message_AddSignal(msg, sig, start, len, true,
                                        sig->scaling, 0.0f);
            next_bit = (uint16_t)(start + len);
        }

        jr_ws(r);
        if (jr_char(r, ',')) { continue; }
        (void)jr_char(r, ']');
        break;
    }

    /* Auto-grow DLC to fit the packed signals (bytes, min 0). */
    {
        uint16_t need_bytes = (uint16_t)((next_bit + 7U) / 8U);
        if (msg->dlc < need_bytes) {
            msg->dlc = (uint8_t)need_bytes;
        }
    }
}

static void parse_messages(Jr *r, EEC_Architecture_t *arch, EEC_Swc_t *swc)
{
    if (!jr_char(r, '[')) { return; }
    for (;;) {
        const char *ms;
        char name[64] = {0};
        double frame_id = 0.0, dlc = 0.0;
        bool extended = false;
        EEC_Message_t *msg;

        jr_ws(r);
        if (jr_char(r, ']')) { break; }
        if (!jr_char(r, '{')) { break; }
        ms = r->cur;

        if (jr_seek(r, ms, "name"))     { (void)jr_string(r, name, sizeof(name)); }
        if (jr_seek(r, ms, "frame_id")) { frame_id = jr_number(r); }
        if (jr_seek(r, ms, "extended")) { extended = jr_bool(r); }
        if (jr_seek(r, ms, "dlc"))      { dlc = jr_number(r); }

        msg = EEC_Swc_CreateMessage(swc, name, (uint32_t)frame_id, extended, (uint8_t)dlc);
        if (msg) {
            if (jr_seek(r, ms, "signals")) { parse_signals(r, swc, msg); }
            if (jr_seek(r, ms, "tx"))      { parse_tx(r, arch, swc, msg); }
        }

        r->cur = ms;
        jr_skip_object_body(r);
        jr_ws(r);
        if (jr_char(r, ',')) { continue; }
        (void)jr_char(r, ']');
        break;
    }
}

static int parse_swc(Jr *r, EEC_Architecture_t *arch)
{
    const char *ss;
    char name[64] = {0};
    char ref2x[26] = {0};
    char sysname[64] = {0};
    char sysref[26] = {0};
    char ecuname[64] = {0};
    EEC_System_t *sys;
    EEC_Swc_t *swc;

    if (!jr_char(r, '{')) { return 0; }
    ss = r->cur;

    if (jr_seek(r, ss, "name"))          { (void)jr_string(r, name, sizeof(name)); }
    if (jr_seek(r, ss, "ref_2x"))        { (void)jr_string(r, ref2x, sizeof(ref2x)); }
    if (jr_seek(r, ss, "system"))        { (void)jr_string(r, sysname, sizeof(sysname)); }
    if (jr_seek(r, ss, "system_ref_2x")) { (void)jr_string(r, sysref, sizeof(sysref)); }
    if (jr_seek(r, ss, "allocated_ecu")) { (void)jr_string(r, ecuname, sizeof(ecuname)); }

    if (sysname[0] == '\0' && sysref[0] == '\0') {
        r->cur = ss;
        jr_skip_object_body(r);
        return 0;
    }

    /* Reject a duplicate SWC identifier (Ref-2X) rather than silently cloning. */
    if (ref2x[0] != '\0' && find_swc_by_ref(arch, ref2x)) {
        EEC_Log_Printf(EEC_LOG_WARN,
                       "SWC '%s': duplicate Ref-2X '%s' — skipped",
                       name[0] ? name : sysname, ref2x);
        r->cur = ss;
        jr_skip_object_body(r);
        return 0;
    }

    /* Resolve the owning system: prefer the stable system Ref-2X, then name. */
    sys = find_system_by_ref(arch, sysref);
    if (!sys) {
        sys = find_system(arch, sysname);
    }
    if (sys) {
        /* Linked to a system already imported (System JSON). */
        EEC_Log_Printf(EEC_LOG_INFO,
                       "SWC '%s' (2X=%s) linked to existing system '%s'",
                       name[0] ? name : sysname, ref2x[0] ? ref2x : "-", sys->name);
    } else {
        /* No such system: create a software-only system for this SWC.
         * (If you meant to attach to an imported system, check the name/ref.) */
        sys = EEC_Architecture_CreateSystem(arch, sysname[0] ? sysname : name);
        if (sys) {
            sys->auto_mapping_enabled = false;  /* software system, no device pins */
            EEC_Log_Printf(EEC_LOG_WARN,
                           "SWC '%s': system '%s' not found among imported systems — "
                           "created a new software-only system",
                           name[0] ? name : sysname, sysname[0] ? sysname : sysref);
        }
    }
    if (!sys) {
        r->cur = ss;
        jr_skip_object_body(r);
        return 0;
    }

    swc = EEC_System_CreateSwc(sys, name[0] ? name : sysname);
    if (swc) {
        if (ref2x[0] != '\0') {
            strncpy(swc->ref_2x, ref2x, sizeof(swc->ref_2x) - 1U);
            swc->ref_2x[sizeof(swc->ref_2x) - 1U] = '\0';
        }
        if (ecuname[0] != '\0') {
            EEC_Swc_AllocateToEcu(swc, find_ecu(arch, ecuname));
        }
        if (jr_seek(r, ss, "variables")) { parse_variables(r, swc); }
        if (jr_seek(r, ss, "messages"))  { parse_messages(r, arch, swc); }
    }

    r->cur = ss;
    jr_skip_object_body(r);
    return swc ? 1 : 0;
}

/* ── Public entry point ────────────────────────────────────────────────── */

int EEC_Import_swc_json(EEC_Architecture_t *arch, const char *filename)
{
    char *text;
    size_t len = 0U;
    Jr r;
    int count = 0;

    if (!arch || !filename) {
        return -1;
    }
    text = jr_read_file(filename, &len);
    if (!text) {
        return -1;
    }

    r.buf = text;
    r.cur = text;
    r.len = len;

    if (jr_char(&r, '{')) {
        const char *root = r.cur;
        if (jr_seek(&r, root, "swcs") && jr_char(&r, '[')) {
            for (;;) {
                jr_ws(&r);
                if (jr_char(&r, ']')) { break; }
                count += parse_swc(&r, arch);
                jr_ws(&r);
                if (jr_char(&r, ',')) { continue; }
                (void)jr_char(&r, ']');
                break;
            }
        }
    }

    free(text);
    EEC_Log_Printf(EEC_LOG_INFO, "SWC import: %d SWC(s) from %s", count, filename);
    return count;
}
