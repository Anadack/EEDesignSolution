
/**
 * @file    EEC_library.c
 * @brief   E/E Architect Design — Reusable component library implementation.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */

#include "EEC_types.h"
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <stdarg.h>
#include "EEC_library.h"
#include "EEC_agco.h"
#include "EEC_log.h"
#include "EEC_pin_helpers.h"
#include "EEC_naming.h"

/* ════════════════════════════════════════════════════════════════════════
 *  Internal helpers
 * ════════════════════════════════════════════════════════════════════════ */

static void lib_json_escape(FILE *f, const char *s)
{
    const unsigned char *p = (const unsigned char *)(s ? s : "");
    fputc('"', f);
    while (*p) {
        switch (*p) {
            case '\\': fputs("\\\\", f); break;
            case '"':  fputs("\\\"", f); break;
            case '\n': fputs("\\n", f);  break;
            case '\r': fputs("\\r", f);  break;
            case '\t': fputs("\\t", f);  break;
            default:   fputc(*p, f);     break;
        }
        ++p;
    }
    fputc('"', f);
}

/* ── Minimal JSON pull-reader ──────────────────────────────────────────
 *  Reads an entire file into memory, then provides helpers to walk over
 *  the text and extract strings, numbers, arrays, and objects.  This is
 *  intentionally simple – no DOM tree, no allocations beyond the initial
 *  file buffer.
 */
typedef struct {
    const char *buf;   /* full file contents (NUL-terminated) */

/*
 * ──────────────────────────────────────────────────────────────────────────────
 *  E/E Architect Design — Reusable Component Library Implementation
 *
 *  This file implements the import, export, and management logic for the
 *  reusable component library. It provides routines for reading and writing
 *  device, signal, ECU, and system definitions in JSON format, as well as
 *  helpers for library validation, batch operations, and AGCO-specific
 *  extensions.
 *
 *  Major responsibilities:
 *    - Import/export of library objects (devices, signals, ECUs, bundles)
 *    - JSON parsing, validation, and error reporting
 *    - Batch helpers for efficient library operations
 *    - AGCO extensions for supplier and variant management
 *
 *  The library is designed for extensibility and robust error handling.
 * ──────────────────────────────────────────────────────────────────────────────
 */

/**
 * @brief Write a JSON-escaped string to a file.
 *
 * Escapes special characters (backslash, quote, newline, etc.) in the input
 * string and writes the result to the given file stream, surrounded by quotes.
 * Used for safe JSON serialization of string fields in library export.
 *
 * @param f File stream to write to.
 * @param s Input string to escape and write.
 */
    const char *cur;   /* current read cursor                  */
    size_t      len;   /* total length                         */
} JsonReader;

static char *read_entire_file(const char *path, size_t *out_len)
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
    buf[sz] = '\0';
    fclose(f);
    if (out_len) *out_len = (size_t)sz;
    return buf;
}

static void skip_ws(JsonReader *r)
{
    while (r->cur < r->buf + r->len && isspace((unsigned char)*r->cur))
        ++r->cur;
}

static bool match_char(JsonReader *r, char c)
{
    skip_ws(r);
    if (r->cur < r->buf + r->len && *r->cur == c) { ++r->cur; return true; }
    return false;
}

/* Read a quoted JSON string into a caller-supplied buffer.  Returns the
   number of characters copied (excluding '\0'), or -1 on error. */
static int read_string(JsonReader *r, char *out, size_t out_sz)
{
    size_t n = 0;
    skip_ws(r);
    if (*r->cur != '"') return -1;
    ++r->cur;
    while (r->cur < r->buf + r->len && *r->cur != '"') {
        char c = *r->cur++;
        if (c == '\\' && r->cur < r->buf + r->len) {
            char esc = *r->cur++;
            switch (esc) {
                case '"':  c = '"';  break;
                case '\\': c = '\\'; break;
                case 'n':  c = '\n'; break;
                case 'r':  c = '\r'; break;
                case 't':  c = '\t'; break;
                default:   c = esc;  break;
            }
        }
        if (n + 1 < out_sz) out[n] = c;
        ++n;
    }
    if (*r->cur == '"') ++r->cur;
    if (n < out_sz) out[n] = '\0'; else if (out_sz > 0) out[out_sz - 1] = '\0';
    return (int)n;
}

static double read_number(JsonReader *r)
{
    char *end = NULL;
    double v;
    skip_ws(r);
    v = strtod(r->cur, &end);
    if (end > r->cur) r->cur = end;
    return v;
}

static int read_int(JsonReader *r)
{
    return (int)read_number(r);
}

/* Skip one JSON value (string, number, object, array, bool, null). */
static void skip_value(JsonReader *r)
{
    int depth;
    skip_ws(r);
    switch (*r->cur) {
        case '"': { char tmp[1]; read_string(r, tmp, 0); break; }
        case '{': case '[':
            depth = 0;
            do {
                if (*r->cur == '{' || *r->cur == '[') ++depth;
                else if (*r->cur == '}' || *r->cur == ']') --depth;
                else if (*r->cur == '"') { char t[512]; read_string(r, t, sizeof(t)); continue; }
                ++r->cur;
            } while (depth > 0 && r->cur < r->buf + r->len);
            break;
        default:
            while (r->cur < r->buf + r->len && *r->cur != ',' && *r->cur != '}' && *r->cur != ']')
                ++r->cur;
            break;
    }
}

/* Seek to a named key inside the current object.  Assumes the opening '{'
   has already been consumed.  On return the cursor is right after the ':',
   ready to read the value.  Returns false if the key was not found (rewinds
   to the position after '{'). */
static bool seek_key(JsonReader *r, const char *key)
{
    const char *start = r->cur;
    char k[128];
    skip_ws(r);
    while (r->cur < r->buf + r->len && *r->cur != '}') {
        skip_ws(r);
        if (*r->cur == ',') { ++r->cur; skip_ws(r); }
        if (read_string(r, k, sizeof(k)) < 0) break;
        if (!match_char(r, ':')) break;
        if (strcmp(k, key) == 0) return true;
        skip_value(r);
    }
    r->cur = start;
    return false;
}

/* ── Enum-from-string lookup tables ────────────────────────────────────── */

static EEC_SignalType_t parse_signal_type(const char *s)
{
    if (!s) return EEC_SIGNAL_TYPE_RESERVED;
    if (strcmp(s, "U1")  == 0 || strcmp(s, "UNSIGNED_1BIT") == 0)  return EEC_SIGNAL_TYPE_UNSIGNED_1BIT;
    if (strcmp(s, "U8")  == 0 || strcmp(s, "UNSIGNED_8BIT") == 0)  return EEC_SIGNAL_TYPE_UNSIGNED_8BIT;
    if (strcmp(s, "S8")  == 0 || strcmp(s, "SIGNED_8BIT") == 0)    return EEC_SIGNAL_TYPE_SIGNED_8BIT;
    if (strcmp(s, "U16") == 0 || strcmp(s, "UNSIGNED_16BIT") == 0) return EEC_SIGNAL_TYPE_UNSIGNED_16BIT;
    if (strcmp(s, "S16") == 0 || strcmp(s, "SIGNED_16BIT") == 0)   return EEC_SIGNAL_TYPE_SIGNED_16BIT;
    if (strcmp(s, "U32") == 0 || strcmp(s, "UNSIGNED_32BIT") == 0) return EEC_SIGNAL_TYPE_UNSIGNED_32BIT;
    if (strcmp(s, "S32") == 0 || strcmp(s, "SIGNED_32BIT") == 0)   return EEC_SIGNAL_TYPE_SIGNED_32BIT;
    if (strcmp(s, "U64") == 0 || strcmp(s, "UNSIGNED_64BIT") == 0) return EEC_SIGNAL_TYPE_UNSIGNED_64BIT;
    if (strcmp(s, "S64") == 0 || strcmp(s, "SIGNED_64BIT") == 0)   return EEC_SIGNAL_TYPE_SIGNED_64BIT;
    if (strcmp(s, "F32") == 0 || strcmp(s, "FLOAT_32BIT") == 0)    return EEC_SIGNAL_TYPE_FLOAT_32BIT;
    if (strcmp(s, "F64") == 0 || strcmp(s, "FLOAT_64BIT") == 0)    return EEC_SIGNAL_TYPE_FLOAT_64BIT;
    return EEC_SIGNAL_TYPE_RESERVED;
}

static EEC_SignalInterface_t parse_signal_interface(const char *s)
{
    if (!s) return EEC_SIGNAL_INTERFACE_RESERVED;
    if (strcmp(s, "DIGITAL")    == 0) return EEC_SIGNAL_INTERFACE_DIGITAL;
    if (strcmp(s, "ANALOG")     == 0) return EEC_SIGNAL_INTERFACE_ANALOG;
    if (strcmp(s, "PWM")        == 0) return EEC_SIGNAL_INTERFACE_PWM;
    if (strcmp(s, "CAN")        == 0) return EEC_SIGNAL_INTERFACE_CAN;
    if (strcmp(s, "LIN")        == 0) return EEC_SIGNAL_INTERFACE_LIN;
    if (strcmp(s, "SENT")       == 0) return EEC_SIGNAL_INTERFACE_SENT;
    if (strcmp(s, "ETHERNET")   == 0) return EEC_SIGNAL_INTERFACE_ETHERNET;
    if (strcmp(s, "RESISTANCE") == 0) return EEC_SIGNAL_INTERFACE_RESISTANCE;
    if (strcmp(s, "FREQUENCY")  == 0) return EEC_SIGNAL_INTERFACE_FREQUENCY;
    if (strcmp(s, "CURRENT")    == 0) return EEC_SIGNAL_INTERFACE_CURRENT;
    if (strcmp(s, "FLEXRAY")    == 0) return EEC_SIGNAL_INTERFACE_FLEXRAY;
    if (strcmp(s, "POWER")      == 0) return EEC_SIGNAL_INTERFACE_POWER;
    if (strcmp(s, "GROUND")     == 0) return EEC_SIGNAL_INTERFACE_GROUND;
    return EEC_SIGNAL_INTERFACE_RESERVED;
}

static EEC_SignalUnit_t parse_signal_unit(const char *s)
{
    if (!s) return EEC_SIGNAL_UNIT_NONE;
    if (strcmp(s, "BOOLEAN") == 0) return EEC_SIGNAL_UNIT_BOOLEAN;
    if (strcmp(s, "VOLT")    == 0) return EEC_SIGNAL_UNIT_VOLT;
    if (strcmp(s, "AMPERE")  == 0) return EEC_SIGNAL_UNIT_AMPERE;
    if (strcmp(s, "HERTZ")   == 0) return EEC_SIGNAL_UNIT_HERTZ;
    if (strcmp(s, "PERCENT") == 0) return EEC_SIGNAL_UNIT_PERCENT;
    if (strcmp(s, "RPM")     == 0) return EEC_SIGNAL_UNIT_RPM;
    if (strcmp(s, "CELSIUS") == 0) return EEC_SIGNAL_UNIT_CELSIUS;
    if (strcmp(s, "BAR")     == 0) return EEC_SIGNAL_UNIT_BAR;
    if (strcmp(s, "DEGREE")  == 0) return EEC_SIGNAL_UNIT_DEGREE;
    return EEC_SIGNAL_UNIT_NONE;
}

static EEC_PinRole_t parse_pin_role(const char *s)
{
    if (!s) return EEC_PIN_ROLE_UNASSIGNED;
    if (strcmp(s, "INPUT")  == 0) return EEC_PIN_ROLE_INPUT;
    if (strcmp(s, "OUTPUT") == 0) return EEC_PIN_ROLE_OUTPUT;
    if (strcmp(s, "INOUT")  == 0) return EEC_PIN_ROLE_INOUT;
    if (strcmp(s, "SUPPLY") == 0) return EEC_PIN_ROLE_SUPPLY;
    if (strcmp(s, "GROUND") == 0) return EEC_PIN_ROLE_GROUND;
    return EEC_PIN_ROLE_UNASSIGNED;
}

static EEC_ObjectPriority_t parse_priority(const char *s)
{
    if (!s) return EEC_PRIORITY_LOW;
    if (strcmp(s, "CRITICAL") == 0) return EEC_PRIORITY_CRITICAL;
    if (strcmp(s, "HIGH") == 0) return EEC_PRIORITY_HIGH;
    if (strcmp(s, "MEDIUM") == 0) return EEC_PRIORITY_MEDIUM;
    return EEC_PRIORITY_LOW;
}

static EEC_SafetyClass_t parse_safety(const char *s)
{
    if (!s) return EEC_SAFETY_QM;
    if (strcmp(s, "QM") == 0) return EEC_SAFETY_QM;
    /* Legacy label */
    if (strcmp(s, "SAFETY_RELATED") == 0) return EEC_SAFETY_AGPL_A;
    /* AgPL labels (ISO 25119 agricultural machinery) */
    if (strcmp(s, "AgPL_A") == 0) return EEC_SAFETY_AGPL_A;
    if (strcmp(s, "AgPL_B") == 0) return EEC_SAFETY_AGPL_B;
    if (strcmp(s, "AgPL_C") == 0) return EEC_SAFETY_AGPL_C;
    if (strcmp(s, "AgPL_D") == 0) return EEC_SAFETY_AGPL_D;
    if (strcmp(s, "AgPL_E") == 0) return EEC_SAFETY_AGPL_D; /* AgPL_E maps to highest level */
    /* Case-insensitive aliases */
    if (strcmp(s, "AGPL_A") == 0) return EEC_SAFETY_AGPL_A;
    if (strcmp(s, "AGPL_B") == 0) return EEC_SAFETY_AGPL_B;
    if (strcmp(s, "AGPL_C") == 0) return EEC_SAFETY_AGPL_C;
    if (strcmp(s, "AGPL_D") == 0) return EEC_SAFETY_AGPL_D;
    return EEC_SAFETY_QM;
}

static EEC_SignalInterface_t cap_mask_to_interface(uint32_t mask)
{
    if (mask & (1U << 3)) return EEC_SIGNAL_INTERFACE_CAN;
    if (mask & (1U << 6)) return EEC_SIGNAL_INTERFACE_ETHERNET;
    if (mask & (1U << 11)) return EEC_SIGNAL_INTERFACE_FLEXRAY;
    if (mask & (1U << 5)) return EEC_SIGNAL_INTERFACE_SENT;
    if (mask & (1U << 4)) return EEC_SIGNAL_INTERFACE_LIN;
    if (mask & (1U << 12)) return EEC_SIGNAL_INTERFACE_CURRENT;
    if (mask & (1U << 10)) return EEC_SIGNAL_INTERFACE_FREQUENCY;
    if (mask & (1U << 9)) return EEC_SIGNAL_INTERFACE_RESISTANCE;
    if (mask & (1U << 2)) return EEC_SIGNAL_INTERFACE_PWM;
    if (mask & (1U << 1)) return EEC_SIGNAL_INTERFACE_ANALOG;
    if (mask & (1U << 0)) return EEC_SIGNAL_INTERFACE_DIGITAL;
    if (mask & (1U << 7)) return EEC_SIGNAL_INTERFACE_POWER;
    if (mask & (1U << 8)) return EEC_SIGNAL_INTERFACE_GROUND;
    return EEC_SIGNAL_INTERFACE_RESERVED;
}

static EEC_SignalInterface_t parse_interface_type(const char *s)
{
    if (!s) return EEC_SIGNAL_INTERFACE_RESERVED;
    if (strcmp(s, "DIGITAL") == 0)   return EEC_SIGNAL_INTERFACE_DIGITAL;
    if (strcmp(s, "ANALOG") == 0)    return EEC_SIGNAL_INTERFACE_ANALOG;
    if (strcmp(s, "PWM") == 0)       return EEC_SIGNAL_INTERFACE_PWM;
    if (strcmp(s, "CAN") == 0)       return EEC_SIGNAL_INTERFACE_CAN;
    if (strcmp(s, "LIN") == 0)       return EEC_SIGNAL_INTERFACE_LIN;
    if (strcmp(s, "SENT") == 0)      return EEC_SIGNAL_INTERFACE_SENT;
    if (strcmp(s, "ETHERNET") == 0)  return EEC_SIGNAL_INTERFACE_ETHERNET;
    if (strcmp(s, "RESISTANCE") == 0) return EEC_SIGNAL_INTERFACE_RESISTANCE;
    if (strcmp(s, "FREQUENCY") == 0) return EEC_SIGNAL_INTERFACE_FREQUENCY;
    if (strcmp(s, "CURRENT") == 0)  return EEC_SIGNAL_INTERFACE_CURRENT;
    if (strcmp(s, "FLEXRAY") == 0)   return EEC_SIGNAL_INTERFACE_FLEXRAY;
    if (strcmp(s, "POWER") == 0)     return EEC_SIGNAL_INTERFACE_POWER;
    if (strcmp(s, "GROUND") == 0)    return EEC_SIGNAL_INTERFACE_GROUND;
    /* Extended SRC-style types */
    if (strcmp(s, "ANALOG_CURRENT") == 0) return EEC_SIGNAL_INTERFACE_CURRENT;
    if (strcmp(s, "DSM") == 0)         return EEC_SIGNAL_INTERFACE_FREQUENCY;
    if (strcmp(s, "TEMPERATURE") == 0)  return EEC_SIGNAL_INTERFACE_RESISTANCE;
    if (strcmp(s, "PWM_HIGHSIDE") == 0 || strcmp(s, "PWM_LOWSIDE") == 0)    return EEC_SIGNAL_INTERFACE_PWM;
    if (strcmp(s, "SWITCH_HIGHSIDE") == 0 || strcmp(s, "SWITCH_HIGHSIDE_SMALL") == 0) return EEC_SIGNAL_INTERFACE_DIGITAL;
    if (strcmp(s, "LED_LOWSIDE") == 0) return EEC_SIGNAL_INTERFACE_PWM;
    if (strcmp(s, "SUPPLY") == 0 || strcmp(s, "IGNITION") == 0 || strcmp(s, "SENSOR_SUPPLY") == 0) return EEC_SIGNAL_INTERFACE_POWER;
    return EEC_SIGNAL_INTERFACE_RESERVED;
}

static EEC_SystemLevel_t parse_system_level(const char *s)
{
    if (!s) return EEC_SYSTEM_LEVEL_SL0;
    if (strcmp(s, "SL4") == 0) return EEC_SYSTEM_LEVEL_SL4;
    if (strcmp(s, "SL3") == 0) return EEC_SYSTEM_LEVEL_SL3;
    if (strcmp(s, "SL2") == 0) return EEC_SYSTEM_LEVEL_SL2;
    if (strcmp(s, "SL1") == 0) return EEC_SYSTEM_LEVEL_SL1;
    return EEC_SYSTEM_LEVEL_SL0;
}

/* ══════════════════════════════════════════════════════════════════════════
 *  Helper: write one signal-batch entry
 * ══════════════════════════════════════════════════════════════════════════ */

typedef struct {
    char prefix[64];
    char part_number[64];
    int  count;
    char type_str[32];
    char interface_str[32];
    char unit_str[32];
    char role_str[32];
    char priority_str[32];
    char safety_str[32];
    uint32_t electrical_requirement;
    float min_val, max_val, resolution, scaling;
    EEC_DigitalStructure_t digital_structure;
} SignalBatch;

/** Detect whether signals[i..] form a batch with a shared prefix and
 *  consecutive _NN suffixes.  Return batch length. */
static int detect_batch(const EEC_DevicePin_t *pins, uint32_t start, uint32_t total,
                         SignalBatch *batch)
{
    const EEC_DevicePin_t *first;
    const EEC_Signal_t *sig;
    const char *name;
    char *uscore;
    size_t prefix_len;
    uint32_t i;
    int n = 1;

    if (start >= total) return 0;
    first = &pins[start];
    sig = first->signal;
    if (!sig) { memset(batch, 0, sizeof(*batch)); return 1; }

    name = sig->name;
    uscore = strrchr(name, '_');
    if (!uscore || uscore == name) {
        prefix_len = strlen(name);
    } else {
        /* Check that the suffix is a number */
        const char *after = uscore + 1;
        while (*after && isdigit((unsigned char)*after)) ++after;
        if (*after != '\0') {
            prefix_len = strlen(name);
        } else {
            prefix_len = (size_t)(uscore - name);
        }
    }
    if (prefix_len >= sizeof(batch->prefix)) prefix_len = sizeof(batch->prefix) - 1;
    memcpy(batch->prefix, name, prefix_len);
    batch->prefix[prefix_len] = '\0';

    strncpy(batch->type_str,      EEC_Signal_TypeString(sig->type), sizeof(batch->type_str) - 1);
    strncpy(batch->interface_str, EEC_Signal_InterfaceString(sig->interface_type), sizeof(batch->interface_str) - 1);
    strncpy(batch->unit_str,      EEC_Signal_UnitString(sig->unit), sizeof(batch->unit_str) - 1);
    strncpy(batch->role_str,      EEC_Pin_RoleString(first->role), sizeof(batch->role_str) - 1);
    strncpy(batch->priority_str,  EEC_Priority_String(sig->priority), sizeof(batch->priority_str) - 1);
    strncpy(batch->safety_str,    EEC_Safety_String(sig->safety), sizeof(batch->safety_str) - 1);
    strncpy(batch->part_number,    sig->part_number, sizeof(batch->part_number) - 1);
    batch->part_number[sizeof(batch->part_number) - 1] = '\0';
    batch->electrical_requirement = first->electrical_requirement;
    batch->min_val    = sig->min_value;
    batch->max_val    = sig->max_value;
    batch->resolution = sig->resolution;
    batch->scaling    = sig->scaling;
    batch->digital_structure = sig->digital_structure;

    /* Extend the batch as long as the next pin shares the same attributes */
    for (i = start + 1; i < total; ++i) {
        const EEC_Signal_t *s2 = pins[i].signal;
        if (!s2) break;
        if (s2->type           != sig->type)           break;
        if (s2->interface_type != sig->interface_type)  break;
        if (s2->unit           != sig->unit)            break;
        if (s2->priority       != sig->priority)        break;
        if (s2->safety         != sig->safety)          break;
        if (pins[i].role       != first->role)          break;
        if (pins[i].electrical_requirement != first->electrical_requirement) break;
        if (strcmp(s2->part_number, sig->part_number) != 0) break;
        /* Check prefix matches */
        if (strncmp(s2->name, batch->prefix, prefix_len) != 0) break;
        ++n;
    }
    batch->count = n;
    return n;
}

static void write_signal_batch(FILE *f, const SignalBatch *b, bool trailing_comma)
{
    fprintf(f, "          {\n");
    fprintf(f, "            \"prefix\": "); lib_json_escape(f, b->prefix);
    fprintf(f, ",\n            \"count\": %d", b->count);
    fprintf(f, ",\n            \"type\": ");      lib_json_escape(f, b->type_str);
    fprintf(f, ",\n            \"interface\": ");  lib_json_escape(f, b->interface_str);
    fprintf(f, ",\n            \"unit\": ");       lib_json_escape(f, b->unit_str);
    fprintf(f, ",\n            \"role\": ");       lib_json_escape(f, b->role_str);
    fprintf(f, ",\n            \"priority\": ");   lib_json_escape(f, b->priority_str);
    fprintf(f, ",\n            \"safety\": ");    lib_json_escape(f, b->safety_str);
    fprintf(f, ",\n            \"part_number\": "); lib_json_escape(f, b->part_number);
    fprintf(f, ",\n            \"electrical_requirement\": %u", b->electrical_requirement);
    fprintf(f, ",\n            \"min\": %.3f, \"max\": %.3f", b->min_val, b->max_val);
    fprintf(f, ",\n            \"resolution\": %.3f, \"scaling\": %.3f", b->resolution, b->scaling);
    fprintf(f, ",\n            \"digital_structure\": \"");
    // Export digital_structure as string
    switch (b->digital_structure) {
        case EEC_DIGITAL_STRUCTURE_PULLUP:   fprintf(f, "PULLUP"); break;
        case EEC_DIGITAL_STRUCTURE_PULLDOWN: fprintf(f, "PULLDOWN"); break;
        case EEC_DIGITAL_STRUCTURE_FLOATING: fprintf(f, "FLOATING"); break;
        default:                             fprintf(f, "UNSPECIFIED"); break;
    }
    fprintf(f, "\"");
    fprintf(f, "\n          }%s\n", trailing_comma ? "," : "");
}

/* Write all signals of one device as batches. */
static void write_device_signals(FILE *f, const EEC_DevicePin_t *pins, uint32_t pin_count)
{
    uint32_t pos = 0;
    fprintf(f, "        \"signals\": [\n");
    while (pos < pin_count) {
        SignalBatch batch;
        int n = detect_batch(pins, pos, pin_count, &batch);
        if (n <= 0) { ++pos; continue; }
        write_signal_batch(f, &batch, pos + (uint32_t)n < pin_count);
        pos += (uint32_t)n;
    }
    fprintf(f, "        ]");
}

/* Write the connectors array of one device. */
static void write_device_connectors(FILE *f, const EEC_Connector_t *connectors, uint32_t count, int indent)
{
    uint32_t i;
    char pad[32];
    memset(pad, ' ', sizeof(pad));
    if ((size_t)indent >= sizeof(pad)) indent = (int)sizeof(pad) - 1;
    pad[indent] = '\0';

    fprintf(f, "%s\"connectors\": [\n", pad);
    for (i = 0; i < count; ++i) {
        const EEC_Connector_t *c = &connectors[i];
        fprintf(f, "%s  { \"name\": ", pad);
        lib_json_escape(f, c->name);
        fprintf(f, ", \"part_number\": ");
        lib_json_escape(f, c->part_number);
        fprintf(f, ", \"family\": ");
        lib_json_escape(f, EEC_Connector_FamilyString(c->family));
        fprintf(f, ", \"gender\": ");
        lib_json_escape(f, EEC_Connector_GenderString(c->gender));
        fprintf(f, ", \"total_cavities\": %u", c->total_cavities);
        fprintf(f, ", \"used_cavities\": %u", c->used_cavities);
        fprintf(f, ", \"max_pin_number\": %u", c->max_pin_number);
        fprintf(f, ", \"sealed\": %s", c->sealed ? "true" : "false");
        if (c->ip_rating[0]) { fprintf(f, ", \"ip_rating\": "); lib_json_escape(f, c->ip_rating); }
        if (c->color[0]) { fprintf(f, ", \"color\": "); lib_json_escape(f, c->color); }
        if (c->mounting[0]) { fprintf(f, ", \"mounting\": "); lib_json_escape(f, c->mounting); }
        if (c->rated_voltage > 0.0f) fprintf(f, ", \"rated_voltage\": %.1f", (double)c->rated_voltage);
        if (c->rated_current > 0.0f) fprintf(f, ", \"rated_current\": %.1f", (double)c->rated_current);
        fprintf(f, ", \"temperature_min\": %.1f, \"temperature_max\": %.1f", (double)c->temperature_min, (double)c->temperature_max);
        fprintf(f, " }%s\n", (i + 1 < count) ? "," : "");
    }
    fprintf(f, "%s]", pad);
}

/* ── Import connectors array from JSON into a sensor, actuator, or ECU ── */
typedef enum { CONN_TARGET_SENSOR, CONN_TARGET_ACTUATOR, CONN_TARGET_ECU } ConnTargetKind;

static void import_connectors(JsonReader *r,
                               void *target, ConnTargetKind kind)
{
    while (r->cur < r->buf + r->len && *r->cur != ']') {
        char c_name[32] = "", c_pn[64] = "", c_family_s[32] = "", c_gender_s[32] = "";
        char c_color[16] = "", c_mount[32] = "", c_ip[8] = "";
        int c_cavities = 0, c_used_cavities = -1, c_max_pin = 0;
        bool c_sealed = false;
        float c_rv = 0, c_rc = 0, c_tmin = -40.0f, c_tmax = 125.0f;
        const char *obj_start;
        EEC_Connector_t *conn = NULL;

        skip_ws(r);
        if (*r->cur == ',') { ++r->cur; skip_ws(r); }
        if (*r->cur == ']') break;
        if (!match_char(r, '{')) break;
        obj_start = r->cur;

        if (seek_key(r, "name"))            read_string(r, c_name, sizeof(c_name));
        r->cur = obj_start;
        if (seek_key(r, "part_number"))     read_string(r, c_pn, sizeof(c_pn));
        r->cur = obj_start;
        if (seek_key(r, "family"))          read_string(r, c_family_s, sizeof(c_family_s));
        r->cur = obj_start;
        if (seek_key(r, "gender"))          read_string(r, c_gender_s, sizeof(c_gender_s));
        r->cur = obj_start;
        if (seek_key(r, "total_cavities"))  c_cavities = read_int(r);
        r->cur = obj_start;
        if (seek_key(r, "used_cavities"))   c_used_cavities = read_int(r);
        r->cur = obj_start;
        if (seek_key(r, "max_pin_number"))  c_max_pin = read_int(r);
        r->cur = obj_start;
        if (seek_key(r, "sealed")) {
            skip_ws(r);
            c_sealed = (r->cur < r->buf + r->len && *r->cur == 't');
            skip_value(r);
        }
        r->cur = obj_start;
        if (seek_key(r, "color"))           read_string(r, c_color, sizeof(c_color));
        r->cur = obj_start;
        if (seek_key(r, "mounting"))        read_string(r, c_mount, sizeof(c_mount));
        r->cur = obj_start;
        if (seek_key(r, "ip_rating"))       read_string(r, c_ip, sizeof(c_ip));
        r->cur = obj_start;
        if (seek_key(r, "rated_voltage"))   c_rv = (float)read_number(r);
        r->cur = obj_start;
        if (seek_key(r, "rated_current"))   c_rc = (float)read_number(r);
        r->cur = obj_start;
        if (seek_key(r, "temperature_min")) c_tmin = (float)read_number(r);
        r->cur = obj_start;
        if (seek_key(r, "temperature_max")) c_tmax = (float)read_number(r);

        if (kind == CONN_TARGET_SENSOR)
            conn = EEC_Sensor_CreateConnector((EEC_Sensor_t *)target, c_name, c_pn,
                        EEC_Connector_ParseFamily(c_family_s),
                        EEC_Connector_ParseGender(c_gender_s),
                        (uint8_t)c_cavities);
        else if (kind == CONN_TARGET_ACTUATOR)
            conn = EEC_Actuator_CreateConnector((EEC_Actuator_t *)target, c_name, c_pn,
                        EEC_Connector_ParseFamily(c_family_s),
                        EEC_Connector_ParseGender(c_gender_s),
                        (uint8_t)c_cavities);
        else
            conn = EEC_Ecu_CreateConnector((EEC_Ecu_t *)target, c_name, c_pn,
                        EEC_Connector_ParseFamily(c_family_s),
                        EEC_Connector_ParseGender(c_gender_s),
                        (uint8_t)c_cavities);

        if (conn) {
            conn->max_pin_number = (uint32_t)c_max_pin;
            conn->used_cavities = (uint8_t)((c_used_cavities >= 0) ? c_used_cavities : c_cavities);
            conn->sealed = c_sealed;
            snprintf(conn->color, sizeof(conn->color), "%s", c_color);
            snprintf(conn->mounting, sizeof(conn->mounting), "%s", c_mount);
            snprintf(conn->ip_rating, sizeof(conn->ip_rating), "%s", c_ip);
            conn->rated_voltage = c_rv;
            conn->rated_current = c_rc;
            conn->temperature_min = c_tmin;
            conn->temperature_max = c_tmax;
        }

        /* Skip to end of connector object */
        {
            int depth = 1;
            r->cur = obj_start;
            while (r->cur < r->buf + r->len && depth > 0) {
                if (*r->cur == '{') ++depth;
                else if (*r->cur == '}') --depth;
                else if (*r->cur == '"') { char t[512]; read_string(r, t, sizeof(t)); continue; }
                ++r->cur;
            }
        }
    }
}

/* ══════════════════════════════════════════════════════════════════════════
 *  EXPORT functions
 * ══════════════════════════════════════════════════════════════════════════ */

int EEC_Library_ExportSystem(const EEC_System_t *system, const char *filepath)
{
    FILE *f;
    uint32_t i;
    uint32_t total_devices;

    if (!system || !filepath) return -1;
    f = fopen(filepath, "w");
    if (!f) { EEC_Log_Printf(EEC_LOG_ERROR, "Library: cannot open %s for writing", filepath); return -1; }

    total_devices = 0U;
    for (i = 0; i < system->component_count; ++i) {
        const EEC_Component_t *comp = system->components[i];
        if (comp) { total_devices += comp->sensor_count + comp->actuator_count; }
    }

    fprintf(f, "{\n");
    fprintf(f, "  \"type\": \"system\",\n");
    fprintf(f, "  \"name\": "); lib_json_escape(f, system->name); fprintf(f, ",\n");
    fprintf(f, "  \"part_number\": "); lib_json_escape(f, system->part_number); fprintf(f, ",\n");
    fprintf(f, "  \"version\": \"1.0\",\n");
    fprintf(f, "  \"system_level\": "); lib_json_escape(f, EEC_System_LevelString(system->system_level)); fprintf(f, ",\n");
    fprintf(f, "  \"Ref-2X\": "); lib_json_escape(f, system->ref_2x); fprintf(f, ",\n");
    fprintf(f, "  \"priority\": "); lib_json_escape(f, EEC_Priority_String(system->priority)); fprintf(f, ",\n");
    fprintf(f, "  \"safety\": "); lib_json_escape(f, EEC_Safety_String(system->safety)); fprintf(f, ",\n");
    fprintf(f, "  \"location\": "); lib_json_escape(f, system->location); fprintf(f, ",\n");
    fprintf(f, "  \"take_rate\": %.1f,\n", (double)system->take_rate);
    fprintf(f, "  \"is_mandatory\": %s,\n", system->is_mandatory ? "true" : "false");
    fprintf(f, "  \"devices\": [\n");

    {
        bool first_dev = true;
        uint32_t c;
        for (c = 0; c < system->component_count; ++c) {
            const EEC_Component_t *comp = system->components[c];
            if (!comp) continue;
            for (i = 0; i < comp->sensor_count; ++i) {
                const EEC_Sensor_t *s = comp->sensors[i];
                if (!s) continue;
                if (!first_dev) { fprintf(f, ",\n"); }
                fprintf(f, "    {\n");
                fprintf(f, "      \"name\": "); lib_json_escape(f, s->name); fprintf(f, ",\n");
                fprintf(f, "      \"part_number\": "); lib_json_escape(f, s->part_number); fprintf(f, ",\n");
                fprintf(f, "      \"device_type\": \"SENSOR\",\n");
                fprintf(f, "      \"priority\": "); lib_json_escape(f, EEC_Priority_String(s->priority)); fprintf(f, ",\n");
                fprintf(f, "      \"safety\": "); lib_json_escape(f, EEC_Safety_String(s->safety)); fprintf(f, ",\n");
                fprintf(f, "      ");
                write_device_signals(f, s->pins, s->pin_count);
                if (s->connector_count > 0) {
                    fprintf(f, ",\n      ");
                    write_device_connectors(f, s->connectors, s->connector_count, 6);
                }
                fprintf(f, "\n    }");
                first_dev = false;
            }
            for (i = 0; i < comp->actuator_count; ++i) {
                const EEC_Actuator_t *a = comp->actuators[i];
                if (!a) continue;
                if (!first_dev) { fprintf(f, ",\n"); }
                fprintf(f, "    {\n");
                fprintf(f, "      \"name\": "); lib_json_escape(f, a->name); fprintf(f, ",\n");
                fprintf(f, "      \"part_number\": "); lib_json_escape(f, a->part_number); fprintf(f, ",\n");
                fprintf(f, "      \"device_type\": \"ACTUATOR\",\n");
                fprintf(f, "      \"priority\": "); lib_json_escape(f, EEC_Priority_String(a->priority)); fprintf(f, ",\n");
                fprintf(f, "      \"safety\": "); lib_json_escape(f, EEC_Safety_String(a->safety)); fprintf(f, ",\n");
                fprintf(f, "      ");
                write_device_signals(f, a->pins, a->pin_count);
                if (a->connector_count > 0) {
                    fprintf(f, ",\n      ");
                    write_device_connectors(f, a->connectors, a->connector_count, 6);
                }
                fprintf(f, "\n    }");
                first_dev = false;
            }
        }
        if (!first_dev) { fprintf(f, "\n"); }
    }

    fprintf(f, "  ]\n}\n");
    fclose(f);
    EEC_Log_Printf(EEC_LOG_INFO, "Library: exported system '%s' -> %s (%u device(s))",
                  system->name, filepath, total_devices);
    return 0;
}


int EEC_Library_ExportSensor(const EEC_Sensor_t *sensor, const char *filepath)
{
    FILE *f;
    if (!sensor || !filepath) return -1;
    f = fopen(filepath, "w");
    if (!f) { EEC_Log_Printf(EEC_LOG_ERROR, "Library: cannot open %s for writing", filepath); return -1; }

    fprintf(f, "{\n");
    fprintf(f, "  \"type\": \"sensor\",\n");
    fprintf(f, "  \"name\": "); lib_json_escape(f, sensor->name); fprintf(f, ",\n");
    fprintf(f, "  \"part_number\": "); lib_json_escape(f, sensor->part_number); fprintf(f, ",\n");
    fprintf(f, "  \"version\": \"1.0\",\n");
    fprintf(f, "  \"priority\": "); lib_json_escape(f, EEC_Priority_String(sensor->priority)); fprintf(f, ",\n");
    fprintf(f, "  \"safety\": "); lib_json_escape(f, EEC_Safety_String(sensor->safety)); fprintf(f, ",\n");
    fprintf(f, "  ");
    write_device_signals(f, sensor->pins, sensor->pin_count);
    if (sensor->connector_count > 0) {
        fprintf(f, ",\n  ");
        write_device_connectors(f, sensor->connectors, sensor->connector_count, 2);
    }
    fprintf(f, "\n}\n");
    fclose(f);
    EEC_Log_Printf(EEC_LOG_INFO, "Library: exported sensor '%s' -> %s (%u pin(s))",
                  sensor->name, filepath, sensor->pin_count);
    return 0;
}


int EEC_Library_ExportActuator(const EEC_Actuator_t *actuator, const char *filepath)
{
    FILE *f;
    if (!actuator || !filepath) return -1;
    f = fopen(filepath, "w");
    if (!f) { EEC_Log_Printf(EEC_LOG_ERROR, "Library: cannot open %s for writing", filepath); return -1; }

    fprintf(f, "{\n");
    fprintf(f, "  \"type\": \"actuator\",\n");
    fprintf(f, "  \"name\": "); lib_json_escape(f, actuator->name); fprintf(f, ",\n");
    fprintf(f, "  \"part_number\": "); lib_json_escape(f, actuator->part_number); fprintf(f, ",\n");
    fprintf(f, "  \"version\": \"1.0\",\n");
    fprintf(f, "  \"priority\": "); lib_json_escape(f, EEC_Priority_String(actuator->priority)); fprintf(f, ",\n");
    fprintf(f, "  \"safety\": "); lib_json_escape(f, EEC_Safety_String(actuator->safety)); fprintf(f, ",\n");
    fprintf(f, "  ");
    write_device_signals(f, actuator->pins, actuator->pin_count);
    if (actuator->connector_count > 0) {
        fprintf(f, ",\n  ");
        write_device_connectors(f, actuator->connectors, actuator->connector_count, 2);
    }
    fprintf(f, "\n}\n");
    fclose(f);
    EEC_Log_Printf(EEC_LOG_INFO, "Library: exported actuator '%s' -> %s (%u pin(s))",
                  actuator->name, filepath, actuator->pin_count);
    return 0;
}


int EEC_Library_ExportSignalGroup(EEC_Signal_t *const *signals, uint32_t count,
                                  const char *name, const char *filepath)
{
    FILE *f;
    uint32_t pos = 0;

    if (!signals || !count || !filepath) return -1;
    f = fopen(filepath, "w");
    if (!f) return -1;

    fprintf(f, "{\n");
    fprintf(f, "  \"type\": \"signal_group\",\n");
    fprintf(f, "  \"name\": "); lib_json_escape(f, name ? name : "unnamed"); fprintf(f, ",\n");
    fprintf(f, "  \"version\": \"1.0\",\n");
    fprintf(f, "  \"priority\": \"LOW\",\n");
    fprintf(f, "  \"safety\": \"QM\",\n");
    fprintf(f, "  \"signals\": [\n");

    while (pos < count) {
        const EEC_Signal_t *sig = signals[pos];
        if (!sig) { ++pos; continue; }
        fprintf(f, "    {\n");
        fprintf(f, "      \"prefix\": "); lib_json_escape(f, sig->name); fprintf(f, ",\n");
        fprintf(f, "      \"count\": 1,\n");
        fprintf(f, "      \"type\": ");      lib_json_escape(f, EEC_Signal_TypeString(sig->type)); fprintf(f, ",\n");
        fprintf(f, "      \"interface\": ");  lib_json_escape(f, EEC_Signal_InterfaceString(sig->interface_type)); fprintf(f, ",\n");
        fprintf(f, "      \"unit\": ");       lib_json_escape(f, EEC_Signal_UnitString(sig->unit)); fprintf(f, ",\n");
        fprintf(f, "      \"priority\": ");   lib_json_escape(f, EEC_Priority_String(sig->priority)); fprintf(f, ",\n");
        fprintf(f, "      \"safety\": ");    lib_json_escape(f, EEC_Safety_String(sig->safety)); fprintf(f, ",\n");
        fprintf(f, "      \"part_number\": "); lib_json_escape(f, sig->part_number); fprintf(f, ",\n");
        fprintf(f, "      \"min\": %.3f, \"max\": %.3f,\n", sig->min_value, sig->max_value);
        fprintf(f, "      \"resolution\": %.3f, \"scaling\": %.3f\n", sig->resolution, sig->scaling);
        ++pos;
        fprintf(f, "    }%s\n", pos < count ? "," : "");
    }

    fprintf(f, "  ]\n}\n");
    fclose(f);
    EEC_Log_Printf(EEC_LOG_INFO, "Library: exported signal group '%s' -> %s (%u signal(s))",
                  name ? name : "unnamed", filepath, count);
    return 0;
}


int EEC_Library_ExportEcu(const EEC_Ecu_t *ecu, const char *filepath)
{
    FILE *f;
    uint8_t i;

    if (!ecu || !filepath) return -1;
    f = fopen(filepath, "w");
    if (!f) return -1;

    fprintf(f, "{\n");
    fprintf(f, "  \"type\": \"ecu\",\n");
    fprintf(f, "  \"name\": "); lib_json_escape(f, ecu->name); fprintf(f, ",\n");
    fprintf(f, "  \"part_number\": "); lib_json_escape(f, ecu->part_number); fprintf(f, ",\n");
    fprintf(f, "  \"variant\": "); lib_json_escape(f, ecu->variant); fprintf(f, ",\n");
    fprintf(f, "  \"priority\": "); lib_json_escape(f, EEC_Priority_String(ecu->priority)); fprintf(f, ",\n");
    fprintf(f, "  \"safety\": "); lib_json_escape(f, EEC_Safety_String(ecu->safety)); fprintf(f, ",\n");
    fprintf(f, "  \"location\": "); lib_json_escape(f, ecu->location); fprintf(f, ",\n");
    fprintf(f, "  \"can_addresses\": [");
    for (i = 0; i < ecu->can_address_count; ++i) {
        if (i) fprintf(f, ", ");
        fprintf(f, "\"0x%02X\"", ecu->can_addresses[i]);
    }
    fprintf(f, "],\n");

    /* Export full pin list for round-trip fidelity */
    fprintf(f, "  \"pins\": [\n");
    {
        uint32_t p;
        for (p = 0; p < ecu->pin_count; ++p) {
            const EEC_EcuPin_t *pin = &ecu->pins[p];
            uint32_t fn;
            if (p > 0) fprintf(f, ",\n");
            fprintf(f, "    {");
            fprintf(f, "\"connector\":"); lib_json_escape(f, pin->connector_name);
            fprintf(f, ",\"physical_number\":%u", pin->physical_number);
            fprintf(f, ",\"name\":"); lib_json_escape(f, pin->name);
            fprintf(f, ",\"group\":"); lib_json_escape(f, pin->main_group);
            fprintf(f, ",\"role\":"); lib_json_escape(f, EEC_Pin_RoleString(pin->role));
            fprintf(f, ",\"type\":"); lib_json_escape(f, EEC_Signal_InterfaceString(cap_mask_to_interface(pin->supported_capability_mask)));
            fprintf(f, ",\"electrical_capability\":%u", pin->electrical_capability);
            fprintf(f, ",\"diagnostic_flags\":%u", pin->diagnostic_flags);
            fprintf(f, ",\"electrical\":"); lib_json_escape(f, pin->electrical);
            fprintf(f, ",\"sw_config\":"); lib_json_escape(f, pin->sw_config);
            fprintf(f, ",\"device_pin_desc\":"); lib_json_escape(f, pin->device_pin_desc);
            /* Mirror the importer's optional nested 'supply' object so provided
             * supply/ground/ground_class state (which has no name/group/electrical
             * text fallback for ground_class) survives an export/re-import cycle. */
            if (pin->provided_sensor_supply != EEC_SENSOR_SUPPLY_UNKNOWN ||
                pin->provided_supply_voltage > 0.0f ||
                pin->current_max > 0.0f ||
                pin->provided_sensor_ground != EEC_SENSOR_GROUND_UNKNOWN ||
                pin->ground_class != EEC_GND_UNCLASSIFIED) {
                bool wrote_field = false;
                fprintf(f, ",\"supply\":{");
                if (pin->provided_sensor_supply != EEC_SENSOR_SUPPLY_UNKNOWN) {
                    fprintf(f, "\"enum\":"); lib_json_escape(f, EEC_SensorSupply_ToString(pin->provided_sensor_supply));
                    wrote_field = true;
                }
                if (pin->provided_supply_voltage > 0.0f) {
                    fprintf(f, "%s\"voltage_nominal\":%g", wrote_field ? "," : "", (double)pin->provided_supply_voltage);
                    wrote_field = true;
                }
                if (pin->current_max > 0.0f) {
                    fprintf(f, "%s\"current_max_a\":%g", wrote_field ? "," : "", (double)pin->current_max);
                    wrote_field = true;
                }
                if (pin->provided_sensor_ground != EEC_SENSOR_GROUND_UNKNOWN) {
                    fprintf(f, "%s\"ground_name\":", wrote_field ? "," : ""); lib_json_escape(f, EEC_SensorGround_ToString(pin->provided_sensor_ground));
                    wrote_field = true;
                }
                if (pin->ground_class != EEC_GND_UNCLASSIFIED) {
                    fprintf(f, "%s\"ground_class\":\"%s\"", wrote_field ? "," : "",
                            pin->ground_class == EEC_GND_POWER ? "POWER" : "LOGIC");
                }
                fprintf(f, "}");
            }
            if (pin->function_count > 0) {
                fprintf(f, ",\"functions\":[");
                for (fn = 0; fn < pin->function_count; ++fn) {
                    if (fn > 0) fprintf(f, ",");
                    lib_json_escape(f, pin->functions[fn]);
                }
                fprintf(f, "]");
            }
            fprintf(f, "}");
        }
    }
    fprintf(f, "\n  ]");
    if (ecu->connector_count > 0) {
        fprintf(f, ",\n  ");
        write_device_connectors(f, ecu->connectors, ecu->connector_count, 2);
    }
    fprintf(f, "\n}\n");
    fclose(f);
    EEC_Log_Printf(EEC_LOG_INFO, "Library: exported ECU preset '%s' (%s) -> %s",
                  ecu->name, ecu->variant, filepath);
    return 0;
}


int EEC_Library_ExportBundle(const EEC_Architecture_t *arch, const char *filepath)
{
    FILE *f;
    uint32_t i;

    if (!arch || !filepath) return -1;
    f = fopen(filepath, "w");
    if (!f) return -1;

    fprintf(f, "{\n");
    fprintf(f, "  \"type\": \"bundle\",\n");
    fprintf(f, "  \"name\": "); lib_json_escape(f, arch->name); fprintf(f, ",\n");
    fprintf(f, "  \"part_number\": "); lib_json_escape(f, arch->part_number); fprintf(f, ",\n");
    fprintf(f, "  \"version\": \"1.0\",\n");
    fprintf(f, "  \"priority\": "); lib_json_escape(f, EEC_Priority_String(arch->priority)); fprintf(f, ",\n");
    fprintf(f, "  \"safety\": "); lib_json_escape(f, EEC_Safety_String(arch->safety)); fprintf(f, ",\n");

    /* ECU presets */
    fprintf(f, "  \"ecus\": [\n");
    for (i = 0; i < arch->ecu_count; ++i) {
        const EEC_Ecu_t *ecu = arch->ecus[i];
        uint8_t j;
        fprintf(f, "    {\n");
        fprintf(f, "      \"name\": "); lib_json_escape(f, ecu->name); fprintf(f, ",\n");
        fprintf(f, "      \"part_number\": "); lib_json_escape(f, ecu->part_number); fprintf(f, ",\n");
        fprintf(f, "      \"variant\": "); lib_json_escape(f, ecu->variant); fprintf(f, ",\n");
        fprintf(f, "      \"priority\": "); lib_json_escape(f, EEC_Priority_String(ecu->priority)); fprintf(f, ",\n");
        fprintf(f, "      \"safety\": "); lib_json_escape(f, EEC_Safety_String(ecu->safety)); fprintf(f, ",\n");
        fprintf(f, "      \"location\": "); lib_json_escape(f, ecu->location); fprintf(f, ",\n");
        fprintf(f, "      \"can_addresses\": [");
        for (j = 0; j < ecu->can_address_count; ++j) {
            if (j) fprintf(f, ", ");
            fprintf(f, "\"0x%02X\"", ecu->can_addresses[j]);
        }
        fprintf(f, "]\n    }%s\n", (i + 1 < arch->ecu_count) ? "," : "");
    }
    fprintf(f, "  ],\n");

    /* Systems (full signal definitions inline) */
    fprintf(f, "  \"systems\": [\n");
    for (i = 0; i < arch->system_count; ++i) {
        const EEC_System_t *sys = arch->systems[i];
        uint32_t c, d;
        bool first_dev = true;
        fprintf(f, "    {\n");
        fprintf(f, "      \"name\": "); lib_json_escape(f, sys->name); fprintf(f, ",\n");
        fprintf(f, "      \"part_number\": "); lib_json_escape(f, sys->part_number); fprintf(f, ",\n");
        fprintf(f, "      \"system_level\": "); lib_json_escape(f, EEC_System_LevelString(sys->system_level)); fprintf(f, ",\n");
        fprintf(f, "      \"Ref-2X\": "); lib_json_escape(f, sys->ref_2x); fprintf(f, ",\n");
        fprintf(f, "      \"priority\": "); lib_json_escape(f, EEC_Priority_String(sys->priority)); fprintf(f, ",\n");
        fprintf(f, "      \"safety\": "); lib_json_escape(f, EEC_Safety_String(sys->safety)); fprintf(f, ",\n");
        fprintf(f, "      \"location\": "); lib_json_escape(f, sys->location); fprintf(f, ",\n");
        fprintf(f, "      \"take_rate\": %.1f,\n", (double)sys->take_rate);
        fprintf(f, "      \"is_mandatory\": %s,\n", sys->is_mandatory ? "true" : "false");
        fprintf(f, "      \"devices\": [\n");

        for (c = 0; c < sys->component_count; ++c) {
            const EEC_Component_t *comp = sys->components[c];
            if (!comp) continue;
            for (d = 0; d < comp->sensor_count; ++d) {
                const EEC_Sensor_t *s = comp->sensors[d];
                if (!s) continue;
                if (!first_dev) { fprintf(f, ",\n"); }
                fprintf(f, "        {\n");
                fprintf(f, "          \"name\": "); lib_json_escape(f, s->name); fprintf(f, ",\n");
                fprintf(f, "          \"part_number\": "); lib_json_escape(f, s->part_number); fprintf(f, ",\n");
                fprintf(f, "          \"device_type\": \"SENSOR\",\n");
                fprintf(f, "          \"priority\": "); lib_json_escape(f, EEC_Priority_String(s->priority)); fprintf(f, ",\n");
                fprintf(f, "          \"safety\": "); lib_json_escape(f, EEC_Safety_String(s->safety)); fprintf(f, ",\n");
                fprintf(f, "          ");
                write_device_signals(f, s->pins, s->pin_count);
                if (s->connector_count > 0) {
                    fprintf(f, ",\n          ");
                    write_device_connectors(f, s->connectors, s->connector_count, 10);
                }
                fprintf(f, "\n        }");
                first_dev = false;
            }
            for (d = 0; d < comp->actuator_count; ++d) {
                const EEC_Actuator_t *a = comp->actuators[d];
                if (!a) continue;
                if (!first_dev) { fprintf(f, ",\n"); }
                fprintf(f, "        {\n");
                fprintf(f, "          \"name\": "); lib_json_escape(f, a->name); fprintf(f, ",\n");
                fprintf(f, "          \"part_number\": "); lib_json_escape(f, a->part_number); fprintf(f, ",\n");
                fprintf(f, "          \"device_type\": \"ACTUATOR\",\n");
                fprintf(f, "          \"priority\": "); lib_json_escape(f, EEC_Priority_String(a->priority)); fprintf(f, ",\n");
                fprintf(f, "          \"safety\": "); lib_json_escape(f, EEC_Safety_String(a->safety)); fprintf(f, ",\n");
                fprintf(f, "          ");
                write_device_signals(f, a->pins, a->pin_count);
                if (a->connector_count > 0) {
                    fprintf(f, ",\n          ");
                    write_device_connectors(f, a->connectors, a->connector_count, 10);
                }
                fprintf(f, "\n        }");
                first_dev = false;
            }
        }
        if (!first_dev) { fprintf(f, "\n"); }
        fprintf(f, "      ]\n");
        fprintf(f, "    }%s\n", (i + 1 < arch->system_count) ? "," : "");
    }
    fprintf(f, "  ],\n");

    /* Buses */
    fprintf(f, "  \"buses\": [\n");
    for (i = 0; i < arch->bus_count; ++i) {
        const EEC_Bus_t *bus = arch->buses[i];
        uint32_t n;
        fprintf(f, "    {\n");
        fprintf(f, "      \"name\": "); lib_json_escape(f, bus->name); fprintf(f, ",\n");
        fprintf(f, "      \"part_number\": "); lib_json_escape(f, bus->part_number); fprintf(f, ",\n");
        fprintf(f, "      \"type\": "); lib_json_escape(f, EEC_Bus_TypeString(bus->type)); fprintf(f, ",\n");
        fprintf(f, "      \"Ref-2X\": "); lib_json_escape(f, bus->ref_2x); fprintf(f, ",\n");
        fprintf(f, "      \"bitrate\": %u,\n", bus->bitrate);
        fprintf(f, "      \"priority\": "); lib_json_escape(f, EEC_Priority_String(bus->priority)); fprintf(f, ",\n");
        fprintf(f, "      \"safety\": "); lib_json_escape(f, EEC_Safety_String(bus->safety)); fprintf(f, ",\n");
        fprintf(f, "      \"nodes\": [");
        for (n = 0; n < bus->node_count; ++n) {
            fprintf(f, "\n        { \"ecu\": ");
            lib_json_escape(f, bus->nodes[n].ecu ? bus->nodes[n].ecu->name : "");
            fprintf(f, ", \"port_index\": %u }", bus->nodes[n].port_index);
            if (n + 1U < bus->node_count) fprintf(f, ",");
        }
        if (bus->node_count > 0U) fprintf(f, "\n      ");
        fprintf(f, "],\n");
        fprintf(f, "      \"signals\": [");
        for (n = 0; n < bus->signal_count; ++n) {
            fprintf(f, "\n        ");
            lib_json_escape(f, bus->signals[n] ? bus->signals[n]->name : "");
            if (n + 1U < bus->signal_count) fprintf(f, ",");
        }
        if (bus->signal_count > 0U) fprintf(f, "\n      ");
        fprintf(f, "]\n");
        fprintf(f, "    }%s\n", (i + 1 < arch->bus_count) ? "," : "");
    }
    fprintf(f, "  ]\n");

    fprintf(f, "}\n");
    fclose(f);

    EEC_Log_Printf(EEC_LOG_INFO, "Library: exported bundle '%s' -> %s (%u ECU(s), %u system(s))",
                  arch->name, filepath, arch->ecu_count, arch->system_count);
    return 0;
}


/* ══════════════════════════════════════════════════════════════════════════
 *  IMPORT helpers: create signals from a batch JSON entry
 * ══════════════════════════════════════════════════════════════════════════ */

/** Parse one signal-batch object from the reader and create the signals in arch.
 *  Pins are attached to either the sensor or the actuator. */
static int import_signal_batch(JsonReader *r, EEC_Architecture_t *arch,
                                EEC_Sensor_t *sensor, EEC_Actuator_t *actuator,
                                uint32_t *pin_counter)
{
    char prefix[64]    = "";
    char part_number[64] = "";
    char type_s[32]    = "";
    char iface_s[32]   = "";
    char unit_s[32]    = "";
    char role_s[32]    = "INPUT";
    char priority_s[32] = "LOW";
    char safety_s[32] = "QM";
    int  count         = 1;
    int  elec_req      = -1;
    char digital_structure_s[16] = "UNSPECIFIED";
    float mn = 0, mx = 0, res = 0.01f, scl = 1.0f;
    float nominal_current = 0.0f, inrush_current = 0.0f, max_voltage = 0.0f, required_supply_voltage = 0.0f;
    int diagnostics_required = 0;
    bool safety_relevant = false;
    char ground_class_s[24] = "UNCLASSIFIED";
    char reset_state_s[24] = "OFF";
    char sensor_supply_s[48] = "UNKNOWN";
    char sensor_ground_s[48] = "UNKNOWN";
    int i;
    const char *obj_start;

    if (!match_char(r, '{')) return -1;
    obj_start = r->cur;

    /* Read all known keys */
    if (seek_key(r, "prefix")) read_string(r, prefix, sizeof(prefix));
    r->cur = obj_start;
    if (seek_key(r, "count")) count = read_int(r);
    r->cur = obj_start;
    if (seek_key(r, "type")) read_string(r, type_s, sizeof(type_s));
    r->cur = obj_start;
    if (seek_key(r, "interface")) read_string(r, iface_s, sizeof(iface_s));
    r->cur = obj_start;
    if (seek_key(r, "unit")) read_string(r, unit_s, sizeof(unit_s));
    r->cur = obj_start;
    if (seek_key(r, "role")) read_string(r, role_s, sizeof(role_s));
    r->cur = obj_start;
    if (seek_key(r, "priority")) read_string(r, priority_s, sizeof(priority_s));
    r->cur = obj_start;
    if (seek_key(r, "safety")) read_string(r, safety_s, sizeof(safety_s));
    r->cur = obj_start;
    if (seek_key(r, "part_number")) read_string(r, part_number, sizeof(part_number));
    r->cur = obj_start;
    if (seek_key(r, "electrical_requirement")) elec_req = read_int(r);
    r->cur = obj_start;
    if (seek_key(r, "min")) mn = (float)read_number(r);
    r->cur = obj_start;
    if (seek_key(r, "max")) mx = (float)read_number(r);
    r->cur = obj_start;
    if (seek_key(r, "resolution")) res = (float)read_number(r);
    r->cur = obj_start;
    if (seek_key(r, "scaling")) scl = (float)read_number(r);
    r->cur = obj_start;
    if (seek_key(r, "digital_structure")) read_string(r, digital_structure_s, sizeof(digital_structure_s));
    r->cur = obj_start;
    if (seek_key(r, "nominal_current")) nominal_current = (float)read_number(r);
    r->cur = obj_start;
    if (seek_key(r, "inrush_current")) inrush_current = (float)read_number(r);
    r->cur = obj_start;
    if (seek_key(r, "max_voltage")) max_voltage = (float)read_number(r);
    r->cur = obj_start;
    if (seek_key(r, "diagnostics_required")) diagnostics_required = read_int(r);
    r->cur = obj_start;
    if (seek_key(r, "safety_relevant")) { skip_ws(r); safety_relevant = (r->cur < r->buf + r->len && *r->cur == 't'); skip_value(r); }
    r->cur = obj_start;
    if (seek_key(r, "ground_class")) read_string(r, ground_class_s, sizeof(ground_class_s));
    r->cur = obj_start;
    if (seek_key(r, "required_reset_state")) read_string(r, reset_state_s, sizeof(reset_state_s));
    r->cur = obj_start;
    if (seek_key(r, "required_sensor_supply")) read_string(r, sensor_supply_s, sizeof(sensor_supply_s));
    r->cur = obj_start;
    if (seek_key(r, "required_sensor_ground")) read_string(r, sensor_ground_s, sizeof(sensor_ground_s));
    r->cur = obj_start;
    if (seek_key(r, "required_supply_voltage")) required_supply_voltage = (float)read_number(r);

    /* Skip to end of object */
    r->cur = obj_start;
    skip_value(r); /* skips remaining content up to closing '}' */
    /* The skip_value started *inside* the object; we already consumed '{'.
       We need to find the matching '}'. */
    /* Actually let's just scan for the '}' */
    {
        int depth = 1;
        r->cur = obj_start;
        while (r->cur < r->buf + r->len && depth > 0) {
            if (*r->cur == '{') ++depth;
            else if (*r->cur == '}') --depth;
            else if (*r->cur == '"') { char t[512]; read_string(r, t, sizeof(t)); continue; }
            ++r->cur;
        }
    }

    if (count < 1) count = 1;
    if (count > 999) count = 999;

    for (i = 0; i < count; ++i) {
        char sig_name[64];
        EEC_Signal_t *sig;
        uint32_t pin_num = *pin_counter;

        if (count == 1) {
            snprintf(sig_name, sizeof(sig_name), "%s", prefix);
        } else {
            snprintf(sig_name, sizeof(sig_name), "%s_%02d", prefix, i + 1);
        }

        sig = EEC_Architecture_CreateSignalEx(
            arch, sig_name,
            parse_signal_type(type_s),
            parse_signal_interface(iface_s),
            parse_signal_unit(unit_s),
            mn, mx, res, scl
        );
        if (!sig) continue;
        sig->priority = parse_priority(priority_s);
        sig->safety = parse_safety(safety_s);
        snprintf(sig->part_number, sizeof(sig->part_number), "%s", part_number);
        // Parse digital_structure string
        if (strcmp(digital_structure_s, "PULLUP") == 0) {
            sig->digital_structure = EEC_DIGITAL_STRUCTURE_PULLUP;
        } else if (strcmp(digital_structure_s, "PULLDOWN") == 0) {
            sig->digital_structure = EEC_DIGITAL_STRUCTURE_PULLDOWN;
        } else if (strcmp(digital_structure_s, "FLOATING") == 0) {
            sig->digital_structure = EEC_DIGITAL_STRUCTURE_FLOATING;
        } else {
            sig->digital_structure = EEC_DIGITAL_STRUCTURE_UNSPECIFIED;
        }
        /* Auto-generate clean signal name following SYSTEM_Function_[POSITION_]TYPE */
        EEC_GenerateCleanSignalNameEx(sig, NULL, parse_pin_role(role_s));

        {
            EEC_DevicePin_t *dp = NULL;
            if (sensor) {
                dp = EEC_Sensor_CreatePin(sensor, pin_num, parse_pin_role(role_s), sig, (EEC_PinInterface_t)sig->interface_type, sig_name);
            } else if (actuator) {
                dp = EEC_Actuator_CreatePin(actuator, pin_num, parse_pin_role(role_s), sig, (EEC_PinInterface_t)sig->interface_type, sig_name);
            }
            if (dp) {
                if (elec_req >= 0) dp->electrical_requirement = (uint32_t)elec_req;
                dp->nominal_current = nominal_current;
                dp->inrush_current = inrush_current;
                dp->max_voltage = max_voltage;
                dp->diagnostics_required = (uint32_t)diagnostics_required;
                dp->safety_relevant = safety_relevant;
                if (strcmp(ground_class_s, "POWER") == 0) dp->ground_class = EEC_GND_POWER;
                else if (strcmp(ground_class_s, "LOGIC") == 0) dp->ground_class = EEC_GND_LOGIC;
                else dp->ground_class = EEC_GND_UNCLASSIFIED;
                if (strcmp(reset_state_s, "ON") == 0) dp->required_reset_state = EEC_RESET_ON;
                else if (strcmp(reset_state_s, "HIGH_Z") == 0) dp->required_reset_state = EEC_RESET_HIGH_Z;
                else dp->required_reset_state = EEC_RESET_OFF;
                dp->required_sensor_supply = EEC_SensorSupply_Parse(sensor_supply_s);
                dp->required_sensor_ground = EEC_SensorGround_Parse(sensor_ground_s);
                dp->required_supply_voltage = required_supply_voltage;
            }
        }
        ++(*pin_counter);
    }
    return count;
}


/**
 * Overlay rich per-physical-pin electrical metadata from a top-level "pins"
 * array onto the device pins already created from "signals". The signals
 * array is the authoritative source for role/interface/logical range, but
 * schemas such as eec-sensor-1.5 / eec-actuator-1.5 only carry electrical
 * ratings (current, voltage, electrical_requirement bitmask, ground class,
 * required supply) on each "pins" entry, cross-referenced to its signal via
 * the "signal" key. Without this overlay those ratings default to zero,
 * which silently disables the electrical-compatibility filter in
 * EEC_System_connect_to_ecus and the matching check in EEC_Verify_architecture.
 */
static void import_pin_electrical_overlay(JsonReader *r, EEC_DevicePin_t *pins, uint32_t pin_count)
{
    if (!seek_key(r, "pins") || !match_char(r, '[')) return;

    while (r->cur < r->buf + r->len && *r->cur != ']') {
        char p_signal[64] = "";
        char ground_class_s[24] = "";
        char reset_state_s[24] = "";
        char sensor_supply_s[48] = "";
        char sensor_ground_s[48] = "";
        bool have_ground_class = false, have_reset = false, have_supply = false, have_ground = false;
        int elec_req = -1, diagnostics_required = -1;
        float nominal_current = 0.0f, inrush_current = 0.0f, max_voltage = 0.0f, required_supply_voltage = 0.0f;
        bool safety_relevant = false;
        const char *pobj_start;
        uint32_t i;

        skip_ws(r);
        if (*r->cur == ',') { ++r->cur; skip_ws(r); }
        if (r->cur >= r->buf + r->len || *r->cur == ']') break;
        if (!match_char(r, '{')) break;
        pobj_start = r->cur;

        if (seek_key(r, "signal")) read_string(r, p_signal, sizeof(p_signal));
        r->cur = pobj_start;
        if (seek_key(r, "electrical_requirement")) elec_req = read_int(r);
        r->cur = pobj_start;
        if (seek_key(r, "nominal_current")) nominal_current = (float)read_number(r);
        r->cur = pobj_start;
        if (seek_key(r, "inrush_current")) inrush_current = (float)read_number(r);
        r->cur = pobj_start;
        if (seek_key(r, "max_voltage")) max_voltage = (float)read_number(r);
        r->cur = pobj_start;
        if (seek_key(r, "diagnostics_required")) diagnostics_required = read_int(r);
        r->cur = pobj_start;
        if (seek_key(r, "safety_relevant")) { skip_ws(r); safety_relevant = (r->cur < r->buf + r->len && *r->cur == 't'); skip_value(r); }
        r->cur = pobj_start;
        if (seek_key(r, "ground_class")) { read_string(r, ground_class_s, sizeof(ground_class_s)); have_ground_class = true; }
        r->cur = pobj_start;
        if (seek_key(r, "required_reset_state")) { read_string(r, reset_state_s, sizeof(reset_state_s)); have_reset = true; }
        r->cur = pobj_start;
        if (seek_key(r, "required_sensor_supply")) { read_string(r, sensor_supply_s, sizeof(sensor_supply_s)); have_supply = true; }
        r->cur = pobj_start;
        if (seek_key(r, "required_sensor_ground")) { read_string(r, sensor_ground_s, sizeof(sensor_ground_s)); have_ground = true; }
        r->cur = pobj_start;
        if (seek_key(r, "required_supply_voltage")) required_supply_voltage = (float)read_number(r);

        /* Advance past this pin object's closing brace. */
        r->cur = pobj_start;
        {
            int depth = 1;
            while (r->cur < r->buf + r->len && depth > 0) {
                if (*r->cur == '{') ++depth;
                else if (*r->cur == '}') --depth;
                else if (*r->cur == '"') { char t[512]; read_string(r, t, sizeof(t)); continue; }
                ++r->cur;
            }
        }

        if (p_signal[0] == '\0') continue;
        for (i = 0; i < pin_count; ++i) {
            EEC_DevicePin_t *dp = &pins[i];
            if (!dp->signal || strcmp(dp->signal->name, p_signal) != 0) continue;
            if (elec_req >= 0) dp->electrical_requirement = (uint32_t)elec_req;
            if (nominal_current > 0.0f) dp->nominal_current = nominal_current;
            if (inrush_current > 0.0f) dp->inrush_current = inrush_current;
            if (max_voltage > 0.0f) dp->max_voltage = max_voltage;
            if (diagnostics_required >= 0) dp->diagnostics_required = (uint32_t)diagnostics_required;
            if (safety_relevant) dp->safety_relevant = true;
            if (have_ground_class) {
                if (strcmp(ground_class_s, "POWER") == 0) dp->ground_class = EEC_GND_POWER;
                else if (strcmp(ground_class_s, "LOGIC") == 0) dp->ground_class = EEC_GND_LOGIC;
            }
            if (have_reset) {
                if (strcmp(reset_state_s, "ON") == 0) dp->required_reset_state = EEC_RESET_ON;
                else if (strcmp(reset_state_s, "HIGH_Z") == 0) dp->required_reset_state = EEC_RESET_HIGH_Z;
                else dp->required_reset_state = EEC_RESET_OFF;
            }
            if (have_supply) dp->required_sensor_supply = EEC_SensorSupply_Parse(sensor_supply_s);
            if (have_ground) dp->required_sensor_ground = EEC_SensorGround_Parse(sensor_ground_s);
            if (required_supply_voltage > 0.0f) dp->required_supply_voltage = required_supply_voltage;
            break;
        }
    }
    match_char(r, ']');
}

/* ══════════════════════════════════════════════════════════════════════════
 *  IMPORT functions
 * ══════════════════════════════════════════════════════════════════════════ */

EEC_System_t *EEC_Library_ImportSystem(EEC_Architecture_t *arch, const char *filepath)
{
    char *buf;
    size_t len;
    JsonReader r;
    EEC_System_t *sys = NULL;
    char name[64] = "ImportedSystem";
    char system_level_s[16] = "SL0";
    char priority_s[32] = "LOW";
    char safety_s[32] = "QM";
    const char *obj_start;

    if (!arch || !filepath) return NULL;
    buf = read_entire_file(filepath, &len);
    if (!buf) { EEC_Log_Printf(EEC_LOG_ERROR, "Library: cannot read %s", filepath); return NULL; }
    r.buf = buf; r.cur = buf; r.len = len;

    if (!match_char(&r, '{')) { free(buf); return NULL; }
    obj_start = r.cur;

    /* Read system name */
    if (seek_key(&r, "name")) read_string(&r, name, sizeof(name));
    r.cur = obj_start;
    if (seek_key(&r, "system_level")) read_string(&r, system_level_s, sizeof(system_level_s));
    r.cur = obj_start;
    if (seek_key(&r, "priority")) read_string(&r, priority_s, sizeof(priority_s));
    r.cur = obj_start;
    if (seek_key(&r, "safety")) read_string(&r, safety_s, sizeof(safety_s));
    r.cur = obj_start;

    sys = EEC_Architecture_CreateSystem(arch, name);
    if (!sys) { free(buf); return NULL; }
    sys->system_level = parse_system_level(system_level_s);
    sys->priority = parse_priority(priority_s);
    sys->safety = parse_safety(safety_s);

    /* Read optional flags */
    {
        const char *p = obj_start;
        r.cur = p;
        if (seek_key(&r, "is_mandatory")) {
            skip_ws(&r);
            sys->is_mandatory = (r.cur < r.buf + r.len && *r.cur == 't');
            skip_value(&r);
        }
        r.cur = p;
        if (seek_key(&r, "auto_mapping_enabled")) {
            skip_ws(&r);
            sys->auto_mapping_enabled = (r.cur < r.buf + r.len && *r.cur != 'f');
            skip_value(&r);
        }
        r.cur = obj_start;
    }
    {
        char ref_2x_s[26] = "";
        char pn[64] = "";
        r.cur = obj_start;
        if (seek_key(&r, "Ref-2X")) read_string(&r, ref_2x_s, sizeof(ref_2x_s));
        strncpy(sys->ref_2x, ref_2x_s, sizeof(sys->ref_2x) - 1);
        sys->ref_2x[sizeof(sys->ref_2x) - 1] = '\0';
        r.cur = obj_start;
        if (seek_key(&r, "part_number")) read_string(&r, pn, sizeof(pn));
        snprintf(sys->part_number, sizeof(sys->part_number), "%s", pn);
    }

    /* ── Helper: import one device object starting at current reader position ── */
    /* Parses a device {name,device_type,mapping_enabled,is_mandatory,safety,priority,
       part_number,signals[],connectors[]} and attaches it to the given component.    */
#define IMPORT_DEVICE_OBJECT(comp_ptr) do { \
        char dev_name[64] = "Device"; \
        char dev_type[32] = "SENSOR"; \
        char dev_priority_s[32] = "LOW"; \
        char dev_safety_s[32] = "QM"; \
        const char *dev_start; \
        EEC_Sensor_t  *sensor   = NULL; \
        EEC_Actuator_t *actuator = NULL; \
        uint32_t pin_counter = 1; \
        skip_ws(&r); \
        if (*r.cur == ',') { ++r.cur; skip_ws(&r); } \
        if (*r.cur == ']') break; \
        if (!match_char(&r, '{')) break; \
        dev_start = r.cur; \
        if (seek_key(&r, "name"))        { read_string(&r, dev_name,      sizeof(dev_name)); }      r.cur = dev_start; \
        if (seek_key(&r, "device_type")){ read_string(&r, dev_type,       sizeof(dev_type)); }       r.cur = dev_start; \
        if (seek_key(&r, "priority"))   { read_string(&r, dev_priority_s, sizeof(dev_priority_s)); } r.cur = dev_start; \
        if (seek_key(&r, "safety"))     { read_string(&r, dev_safety_s,   sizeof(dev_safety_s)); }   r.cur = dev_start; \
        if (strcmp(dev_type, "ACTUATOR") == 0) { \
            actuator = EEC_Component_CreateActuator((comp_ptr), dev_name); \
            if (actuator) { \
                char dpn[64] = ""; \
                actuator->priority = parse_priority(dev_priority_s); \
                actuator->safety   = parse_safety(dev_safety_s); \
                r.cur = dev_start; \
                if (seek_key(&r, "part_number")) read_string(&r, dpn, sizeof(dpn)); \
                snprintf(actuator->part_number, sizeof(actuator->part_number), "%s", dpn); \
                r.cur = dev_start; \
                if (seek_key(&r, "mapping_enabled")) { skip_ws(&r); actuator->mapping_enabled = (*r.cur != 'f'); skip_value(&r); } \
                r.cur = dev_start; \
                if (seek_key(&r, "is_mandatory"))    { skip_ws(&r); actuator->is_mandatory    = (*r.cur == 't'); skip_value(&r); } \
            } \
        } else { \
            sensor = EEC_Component_CreateSensor((comp_ptr), dev_name); \
            if (sensor) { \
                char dpn[64] = ""; \
                sensor->priority = parse_priority(dev_priority_s); \
                sensor->safety   = parse_safety(dev_safety_s); \
                r.cur = dev_start; \
                if (seek_key(&r, "part_number")) read_string(&r, dpn, sizeof(dpn)); \
                snprintf(sensor->part_number, sizeof(sensor->part_number), "%s", dpn); \
                r.cur = dev_start; \
                if (seek_key(&r, "mapping_enabled")) { skip_ws(&r); sensor->mapping_enabled = (*r.cur != 'f'); skip_value(&r); } \
                r.cur = dev_start; \
                if (seek_key(&r, "is_mandatory"))    { skip_ws(&r); sensor->is_mandatory    = (*r.cur == 't'); skip_value(&r); } \
            } \
        } \
        r.cur = dev_start; \
        if (seek_key(&r, "signals") && match_char(&r, '[')) { \
            while (r.cur < r.buf + r.len && *r.cur != ']') { \
                skip_ws(&r); \
                if (*r.cur == ',') { ++r.cur; skip_ws(&r); } \
                if (*r.cur == ']') break; \
                import_signal_batch(&r, arch, sensor, actuator, &pin_counter); \
            } \
            match_char(&r, ']'); \
        } \
        r.cur = dev_start; \
        if (seek_key(&r, "connectors") && match_char(&r, '[')) { \
            void *target = sensor ? (void *)sensor : (void *)actuator; \
            ConnTargetKind kind = sensor ? CONN_TARGET_SENSOR : CONN_TARGET_ACTUATOR; \
            if (target) import_connectors(&r, target, kind); \
            match_char(&r, ']'); \
        } \
        { /* Skip to end of device object */ \
            int depth = 1; \
            r.cur = dev_start; \
            while (r.cur < r.buf + r.len && depth > 0) { \
                if (*r.cur == '{') ++depth; \
                else if (*r.cur == '}') --depth; \
                else if (*r.cur == '"') { char t[512]; read_string(&r, t, sizeof(t)); continue; } \
                ++r.cur; \
            } \
        } \
    } while (0)

    /* ── Parse devices (legacy flat format) or components (vNext format) ── */
    {
        EEC_Component_t *default_comp = EEC_System_CreateComponent(sys, "Default");
        r.cur = obj_start;

        /* Legacy: "devices": [...] — flat array of sensors/actuators */
        if (seek_key(&r, "devices") && match_char(&r, '[')) {
            while (r.cur < r.buf + r.len && *r.cur != ']') {
                IMPORT_DEVICE_OBJECT(default_comp);
            }
            match_char(&r, ']');
        } else {
            /* vNext: "components": [{name,sensors:[...],actuators:[...]},...] */
            r.cur = obj_start;
            if (seek_key(&r, "components") && match_char(&r, '[')) {
                while (r.cur < r.buf + r.len && *r.cur != ']') {
                    const char *comp_start;
                    skip_ws(&r);
                    if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
                    if (*r.cur == ']') break;
                    if (!match_char(&r, '{')) break;
                    comp_start = r.cur;

                    /* Parse sensors[] within this component */
                    r.cur = comp_start;
                    if (seek_key(&r, "sensors") && match_char(&r, '[')) {
                        while (r.cur < r.buf + r.len && *r.cur != ']') {
                            IMPORT_DEVICE_OBJECT(default_comp);
                        }
                        match_char(&r, ']');
                    }

                    /* Parse actuators[] within this component */
                    r.cur = comp_start;
                    if (seek_key(&r, "actuators") && match_char(&r, '[')) {
                        while (r.cur < r.buf + r.len && *r.cur != ']') {
                            IMPORT_DEVICE_OBJECT(default_comp);
                        }
                        match_char(&r, ']');
                    }

                    /* Skip to end of component object */
                    {
                        int depth = 1;
                        r.cur = comp_start;
                        while (r.cur < r.buf + r.len && depth > 0) {
                            if (*r.cur == '{') ++depth;
                            else if (*r.cur == '}') --depth;
                            else if (*r.cur == '"') { char t[512]; read_string(&r, t, sizeof(t)); continue; }
                            ++r.cur;
                        }
                    }
                }
                match_char(&r, ']');
            }
        }
    }
#undef IMPORT_DEVICE_OBJECT

    free(buf);
    EEC_Log_Printf(EEC_LOG_INFO, "Library: imported system '%s' from %s", name, filepath);
    return sys;
}


int EEC_Library_ImportSignalGroup(EEC_Architecture_t *arch,
                                  EEC_Sensor_t *target_sensor,
                                  EEC_Actuator_t *target_actuator,
                                  const char *filepath)
{
    char *buf;
    size_t len;
    JsonReader r;
    int total = 0;
    uint32_t pin_counter = 1;

    if (!arch || !filepath) return -1;
    if (!target_sensor && !target_actuator) return -1;
    buf = read_entire_file(filepath, &len);
    if (!buf) return -1;
    r.buf = buf; r.cur = buf; r.len = len;

    if (!match_char(&r, '{')) { free(buf); return -1; }

    /* Determine starting pin number from existing pins on the target device */
    if (target_sensor && target_sensor->pin_count > 0) {
        pin_counter = target_sensor->pins[target_sensor->pin_count - 1].number + 1;
    } else if (target_actuator && target_actuator->pin_count > 0) {
        pin_counter = target_actuator->pins[target_actuator->pin_count - 1].number + 1;
    }

    if (seek_key(&r, "signals") && match_char(&r, '[')) {
        while (r.cur < r.buf + r.len && *r.cur != ']') {
            skip_ws(&r);
            if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
            if (*r.cur == ']') break;
            int n = import_signal_batch(&r, arch, target_sensor, target_actuator, &pin_counter);
            if (n > 0) total += n;
        }
    }

    free(buf);
    return total;
}


EEC_Sensor_t *EEC_Library_ImportSensor(EEC_Architecture_t *arch, EEC_Component_t *component, const char *filepath)
{
    char *buf;
    size_t len;
    JsonReader r;
    char name[64] = "ImportedSensor";
    char priority_s[32] = "LOW";
    char safety_s[32] = "QM";
    const char *obj_start;
    EEC_Sensor_t *sensor = NULL;
    uint32_t pin_counter = 1;

    if (!arch || !component || !filepath) return NULL;
    buf = read_entire_file(filepath, &len);
    if (!buf) { EEC_Log_Printf(EEC_LOG_ERROR, "Library: cannot read %s", filepath); return NULL; }
    r.buf = buf; r.cur = buf; r.len = len;

    if (!match_char(&r, '{')) { free(buf); return NULL; }
    obj_start = r.cur;

    if (seek_key(&r, "name")) read_string(&r, name, sizeof(name));
    r.cur = obj_start;
    if (seek_key(&r, "priority")) read_string(&r, priority_s, sizeof(priority_s));
    r.cur = obj_start;
    if (seek_key(&r, "safety")) read_string(&r, safety_s, sizeof(safety_s));
    r.cur = obj_start;

    sensor = EEC_Component_CreateSensor(component, name);
    if (!sensor) { free(buf); return NULL; }
    sensor->priority = parse_priority(priority_s);
    sensor->safety = parse_safety(safety_s);
    {
        char pn[64] = "";
        r.cur = obj_start;
        if (seek_key(&r, "part_number")) read_string(&r, pn, sizeof(pn));
        snprintf(sensor->part_number, sizeof(sensor->part_number), "%s", pn);
    }

    if (seek_key(&r, "signals") && match_char(&r, '[')) {
        while (r.cur < r.buf + r.len && *r.cur != ']') {
            skip_ws(&r);
            if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
            if (*r.cur == ']') break;
            import_signal_batch(&r, arch, sensor, NULL, &pin_counter);
        }
        match_char(&r, ']');
    }

    /* Parse connectors array */
    r.cur = obj_start;
    if (seek_key(&r, "connectors") && match_char(&r, '[')) {
        import_connectors(&r, sensor, CONN_TARGET_SENSOR);
        match_char(&r, ']');
    }

    /* Overlay rich electrical ratings from "pins" (if present) onto the
       device pins created above from "signals". */
    r.cur = obj_start;
    import_pin_electrical_overlay(&r, sensor->pins, sensor->pin_count);

    free(buf);
    EEC_Log_Printf(EEC_LOG_INFO, "Library: imported sensor '%s' from %s (%u pin(s))",
                  name, filepath, sensor->pin_count);
    return sensor;
}


EEC_Actuator_t *EEC_Library_ImportActuator(EEC_Architecture_t *arch, EEC_Component_t *component, const char *filepath)
{
    char *buf;
    size_t len;
    JsonReader r;
    char name[64] = "ImportedActuator";
    char priority_s[32] = "LOW";
    char safety_s[32] = "QM";
    const char *obj_start;
    EEC_Actuator_t *actuator = NULL;
    uint32_t pin_counter = 1;

    if (!arch || !component || !filepath) return NULL;
    buf = read_entire_file(filepath, &len);
    if (!buf) { EEC_Log_Printf(EEC_LOG_ERROR, "Library: cannot read %s", filepath); return NULL; }
    r.buf = buf; r.cur = buf; r.len = len;

    if (!match_char(&r, '{')) { free(buf); return NULL; }
    obj_start = r.cur;

    if (seek_key(&r, "name")) read_string(&r, name, sizeof(name));
    r.cur = obj_start;
    if (seek_key(&r, "priority")) read_string(&r, priority_s, sizeof(priority_s));
    r.cur = obj_start;
    if (seek_key(&r, "safety")) read_string(&r, safety_s, sizeof(safety_s));
    r.cur = obj_start;

    actuator = EEC_Component_CreateActuator(component, name);
    if (!actuator) { free(buf); return NULL; }
    actuator->priority = parse_priority(priority_s);
    actuator->safety = parse_safety(safety_s);
    {
        char pn[64] = "";
        r.cur = obj_start;
        if (seek_key(&r, "part_number")) read_string(&r, pn, sizeof(pn));
        snprintf(actuator->part_number, sizeof(actuator->part_number), "%s", pn);
    }

    if (seek_key(&r, "signals") && match_char(&r, '[')) {
        while (r.cur < r.buf + r.len && *r.cur != ']') {
            skip_ws(&r);
            if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
            if (*r.cur == ']') break;
            import_signal_batch(&r, arch, NULL, actuator, &pin_counter);
        }
        match_char(&r, ']');
    }

    /* Parse connectors array */
    r.cur = obj_start;
    if (seek_key(&r, "connectors") && match_char(&r, '[')) {
        import_connectors(&r, actuator, CONN_TARGET_ACTUATOR);
        match_char(&r, ']');
    }

    /* Overlay rich electrical ratings from "pins" (if present) onto the
       device pins created above from "signals". */
    r.cur = obj_start;
    import_pin_electrical_overlay(&r, actuator->pins, actuator->pin_count);

    free(buf);
    EEC_Log_Printf(EEC_LOG_INFO, "Library: imported actuator '%s' from %s (%u pin(s))",
                  name, filepath, actuator->pin_count);
    return actuator;
}


EEC_Ecu_t *EEC_Library_ImportEcu(EEC_Architecture_t *arch, const char *filepath,
                                const char *instance_name)
{
    char *buf;
    size_t len;
    JsonReader r;
    char name[64] = "ECU";
    char variant[64] = "";
    char priority_s[32] = "LOW";
    char safety_s[32] = "QM";
    const char *obj_start;
    EEC_Ecu_t *ecu = NULL;

    if (!arch || !filepath) return NULL;
    buf = read_entire_file(filepath, &len);
    if (!buf) return NULL;
    r.buf = buf; r.cur = buf; r.len = len;

    if (!match_char(&r, '{')) { free(buf); return NULL; }
    obj_start = r.cur;

    if (seek_key(&r, "name")) read_string(&r, name, sizeof(name));
    r.cur = obj_start;
    if (seek_key(&r, "variant")) read_string(&r, variant, sizeof(variant));
    r.cur = obj_start;
    if (seek_key(&r, "priority")) read_string(&r, priority_s, sizeof(priority_s));
    r.cur = obj_start;
    if (seek_key(&r, "safety")) read_string(&r, safety_s, sizeof(safety_s));
    r.cur = obj_start;

    /* Use the AEC factory for known AGCO variants, else create a bare ECU */
    {
        const char *inst = (instance_name && instance_name[0]) ? instance_name : name;
        /* We create with 0 CAN addresses first, then add them from JSON */
        if (strcmp(variant, "LARGE") == 0) {
            ecu = EEC_Agco_CreateEcuLarge(arch, inst, 0);
        } else if (strcmp(variant, "MEDIUM") == 0) {
            ecu = EEC_Agco_CreateEcuMedium(arch, inst, 0);
        } else if (strcmp(variant, "SMALL") == 0) {
            ecu = EEC_Agco_CreateEcuSmall(arch, inst, 0);
        } else {
            /* Generic ECU: create bare, pins will come from JSON */
            ecu = EEC_Architecture_CreateEcu(arch, inst, variant[0] ? variant : "GENERIC");
        }
    }

    if (ecu) {
        ecu->priority = parse_priority(priority_s);
        ecu->safety = parse_safety(safety_s);
        {
            char pn[64] = "";
            r.cur = obj_start;
            if (seek_key(&r, "part_number")) read_string(&r, pn, sizeof(pn));
            snprintf(ecu->part_number, sizeof(ecu->part_number), "%s", pn);
        }
    }

    if (ecu && seek_key(&r, "can_addresses") && match_char(&r, '[')) {
        while (r.cur < r.buf + r.len && *r.cur != ']') {
            char addr_str[16] = "";
            unsigned long addr;
            skip_ws(&r);
            if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
            if (*r.cur == ']') break;
            read_string(&r, addr_str, sizeof(addr_str));
            addr = strtoul(addr_str, NULL, 0);
            if (addr <= 0xFF) {
                EEC_Ecu_AddCanAddress(ecu, (uint8_t)addr);
            }
        }
        match_char(&r, ']');
    }

    /* ── Import pins from JSON if present (generic ECU support) ── */
    r.cur = obj_start;
    if (ecu && seek_key(&r, "pins") && match_char(&r, '[')) {
        /* Free function arrays from factory-generated pins before clearing */
        {
            uint32_t fi;
            for (fi = 0U; fi < ecu->pin_count; ++fi) {
                uint32_t fj;
                for (fj = 0U; fj < ecu->pins[fi].function_count; ++fj) {
                    free(ecu->pins[fi].functions[fj]);
                }
                free(ecu->pins[fi].functions);
                ecu->pins[fi].functions = NULL;
                ecu->pins[fi].function_count = 0U;
                ecu->pins[fi].function_capacity = 0U;
            }
        }
        ecu->pin_count = 0;
        while (r.cur < r.buf + r.len && *r.cur != ']') {
            char p_conn[32] = "", p_name[64] = "", p_group[64] = "";
            char p_role_s[16] = "", p_type_s[32] = "";
            char p_elec[256] = "", p_swcfg[160] = "";
            char p_desc[128] = "";
            /* structured supply/ground optional fields */
            char p_supply_enum[64] = "";
            double p_supply_v_nom = 0.0;
            double p_supply_i_max = 0.0;
            char p_ground_name[64] = "";
            char p_ground_class[32] = "";
            int  p_num = 0;
            uint32_t p_elec_cap = 0;
            uint32_t p_diag = 0;
            const char *pin_start;
            EEC_EcuPin_t *pin;
            EEC_SignalInterface_t iface;

            skip_ws(&r);
            if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
            if (*r.cur == ']') break;
            if (!match_char(&r, '{')) break;
            pin_start = r.cur;

            if (seek_key(&r, "connector"))       read_string(&r, p_conn, sizeof(p_conn));
            r.cur = pin_start;
            if (seek_key(&r, "physical_number"))  p_num = read_int(&r);
            r.cur = pin_start;
            if (seek_key(&r, "name"))             read_string(&r, p_name, sizeof(p_name));
            r.cur = pin_start;
            if (seek_key(&r, "group"))            read_string(&r, p_group, sizeof(p_group));
            r.cur = pin_start;
            if (seek_key(&r, "role"))             read_string(&r, p_role_s, sizeof(p_role_s));
            r.cur = pin_start;
            if (seek_key(&r, "type"))             read_string(&r, p_type_s, sizeof(p_type_s));
            r.cur = pin_start;
            if (seek_key(&r, "electrical_capability")) p_elec_cap = (uint32_t)read_int(&r);
            r.cur = pin_start;
            if (seek_key(&r, "diagnostic_flags")) p_diag = (uint32_t)read_int(&r);
            r.cur = pin_start;
            if (seek_key(&r, "electrical"))       read_string(&r, p_elec, sizeof(p_elec));
            r.cur = pin_start;
            if (seek_key(&r, "sw_config"))        read_string(&r, p_swcfg, sizeof(p_swcfg));
            r.cur = pin_start;
            if (seek_key(&r, "device_pin_desc"))  read_string(&r, p_desc, sizeof(p_desc));
            r.cur = pin_start;

            iface = parse_interface_type(p_type_s);
            pin = EEC_Ecu_CreatePin(ecu, (uint32_t)p_num, p_conn, p_name, p_group,
                                   parse_pin_role(p_role_s),
                                   (EEC_PinInterface_t)iface,
                                   EEC_Signal_InterfaceToCapability(iface),
                                   p_diag, p_elec, p_swcfg);
            if (pin) {
                pin->electrical_capability = p_elec_cap;
                /* AII/AIV (Analog Input Interface/Voltage) pins accept ANALOG voltage signals
                   in addition to their primary RESISTANCE measurement capability. */
                if (iface == EEC_SIGNAL_INTERFACE_RESISTANCE &&
                    (strstr(p_name, "AII") != NULL || strstr(p_name, "AIV") != NULL)) {
                    pin->supported_capability_mask |= EEC_Signal_InterfaceToCapability(EEC_SIGNAL_INTERFACE_ANALOG);
                }
                /* FREQUENCY inputs can also serve as plain DIGITAL on/off inputs. */
                if (iface == EEC_SIGNAL_INTERFACE_FREQUENCY) {
                    pin->supported_capability_mask |= EEC_Signal_InterfaceToCapability(EEC_SIGNAL_INTERFACE_DIGITAL);
                }
                /* LOW_SIDE PWM outputs also serve as static digital sinking outputs. */
                if (iface == EEC_SIGNAL_INTERFACE_PWM && (p_elec_cap & EEC_ELEC_LOW_SIDE)) {
                    pin->supported_capability_mask |= EEC_Signal_InterfaceToCapability(EEC_SIGNAL_INTERFACE_DIGITAL);
                }
                snprintf(pin->device_pin_desc, sizeof(pin->device_pin_desc), "%s", p_desc);
                /* Populate provided supply/ground fields from structured JSON when present.
                 * The importer prefers explicit 'supply'/'ground' objects but falls back
                 * to name/group/electrical text parsing inside the helper.
                 */
                /* attempt to read optional nested 'supply' object */
                if (seek_key(&r, "supply") && match_char(&r, '{')) {
                    const char *sstart = r.cur;
                    if (seek_key(&r, "enum")) read_string(&r, p_supply_enum, sizeof(p_supply_enum));
                    r.cur = sstart;
                    if (seek_key(&r, "voltage_nominal")) p_supply_v_nom = read_number(&r);
                    r.cur = sstart;
                    if (seek_key(&r, "current_max_a")) p_supply_i_max = read_number(&r);
                    r.cur = sstart;
                    if (seek_key(&r, "ground_name")) read_string(&r, p_ground_name, sizeof(p_ground_name));
                    r.cur = sstart;
                    if (seek_key(&r, "ground_class")) read_string(&r, p_ground_class, sizeof(p_ground_class));
                    /* consume '}' */
                    match_char(&r, '}');
                }

                EEC_Pin_PopulateProvidedFromData(pin, p_name, p_group, p_elec,
                    p_supply_enum[0] ? p_supply_enum : NULL,
                    (float)p_supply_v_nom, (float)p_supply_i_max,
                    p_ground_name[0] ? p_ground_name : NULL,
                    p_ground_class[0] ? p_ground_class : NULL);
            }

            /* Import functions array if present */
            if (pin && seek_key(&r, "functions") && match_char(&r, '[')) {
                while (r.cur < r.buf + r.len && *r.cur != ']') {
                    char func_name[128] = "";
                    skip_ws(&r);
                    if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
                    if (*r.cur == ']') break;
                    read_string(&r, func_name, sizeof(func_name));
                    if (func_name[0]) EEC_EcuPin_AddFunction(pin, func_name);
                }
                match_char(&r, ']');
            }

            /* Skip to end of this pin object */
            {
                int depth = 1;
                r.cur = pin_start;
                while (r.cur < r.buf + r.len && depth > 0) {
                    if (*r.cur == '{') depth++;
                    else if (*r.cur == '}') depth--;
                    else if (*r.cur == '"') { char t[512]; read_string(&r, t, sizeof(t)); continue; }
                    r.cur++;
                }
            }
        }
        match_char(&r, ']');
    }

    /* Import ECU connectors from JSON if present */
    r.cur = obj_start;
    if (ecu && seek_key(&r, "connectors") && match_char(&r, '[')) {
        import_connectors(&r, ecu, CONN_TARGET_ECU);
        match_char(&r, ']');
    }

    free(buf);

    if (ecu) {
        EEC_Log_Printf(EEC_LOG_INFO, "Library: imported ECU '%s' (%s, %u pins) from %s",
                      ecu->name, variant, ecu->pin_count, filepath);
    }
    return ecu;
}


int EEC_Library_ImportBundle(EEC_Architecture_t *arch, const char *filepath)
{
    char *buf;
    size_t len;
    JsonReader r;
    const char *top_start;
    char priority_s[32] = "LOW";
    char safety_s[32] = "QM";
    int imported = 0;

    if (!arch || !filepath) return -1;
    buf = read_entire_file(filepath, &len);
    if (!buf) return -1;
    r.buf = buf; r.cur = buf; r.len = len;

    if (!match_char(&r, '{')) { free(buf); return -1; }
    top_start = r.cur;
    if (seek_key(&r, "priority")) read_string(&r, priority_s, sizeof(priority_s));
    r.cur = top_start;
    if (seek_key(&r, "safety")) read_string(&r, safety_s, sizeof(safety_s));
    r.cur = top_start;
    arch->priority = parse_priority(priority_s);
    arch->safety = parse_safety(safety_s);
    {
        char pn[64] = "";
        r.cur = top_start;
        if (seek_key(&r, "part_number")) read_string(&r, pn, sizeof(pn));
        snprintf(arch->part_number, sizeof(arch->part_number), "%s", pn);
        r.cur = top_start;
    }

    /* ── Import ECUs ── */
    if (seek_key(&r, "ecus") && match_char(&r, '[')) {
        while (r.cur < r.buf + r.len && *r.cur != ']') {
            char ename[64] = "ECU";
            char evariant[16] = "SMALL";
            char ecu_priority_s[32] = "LOW";
            char ecu_safety_s[32] = "QM";
            const char *ecu_start;
            EEC_Ecu_t *ecu = NULL;

            skip_ws(&r);
            if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
            if (*r.cur == ']') break;

            if (!match_char(&r, '{')) break;
            ecu_start = r.cur;

            if (seek_key(&r, "name")) read_string(&r, ename, sizeof(ename));
            r.cur = ecu_start;
            if (seek_key(&r, "variant")) read_string(&r, evariant, sizeof(evariant));
            r.cur = ecu_start;
            if (seek_key(&r, "priority")) read_string(&r, ecu_priority_s, sizeof(ecu_priority_s));
            r.cur = ecu_start;
            if (seek_key(&r, "safety")) read_string(&r, ecu_safety_s, sizeof(ecu_safety_s));
            r.cur = ecu_start;

            if (strcmp(evariant, "LARGE") == 0)
                ecu = EEC_Agco_CreateEcuLarge(arch, ename, 0);
            else if (strcmp(evariant, "MEDIUM") == 0)
                ecu = EEC_Agco_CreateEcuMedium(arch, ename, 0);
            else
                ecu = EEC_Agco_CreateEcuSmall(arch, ename, 0);

            if (ecu) {
                char epn[64] = "";
                ecu->priority = parse_priority(ecu_priority_s);
                ecu->safety = parse_safety(ecu_safety_s);
                r.cur = ecu_start;
                if (seek_key(&r, "part_number")) read_string(&r, epn, sizeof(epn));
                snprintf(ecu->part_number, sizeof(ecu->part_number), "%s", epn);
            }

            if (ecu && seek_key(&r, "can_addresses") && match_char(&r, '[')) {
                while (r.cur < r.buf + r.len && *r.cur != ']') {
                    char addr_str[16] = "";
                    unsigned long addr;
                    skip_ws(&r);
                    if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
                    if (*r.cur == ']') break;
                    read_string(&r, addr_str, sizeof(addr_str));
                    addr = strtoul(addr_str, NULL, 0);
                    if (addr <= 0xFF) EEC_Ecu_AddCanAddress(ecu, (uint8_t)addr);
                }
                match_char(&r, ']');
            }

            /* Skip to end of ECU object */
            {
                int depth = 1;
                r.cur = ecu_start;
                while (r.cur < r.buf + r.len && depth > 0) {
                    if (*r.cur == '{') ++depth;
                    else if (*r.cur == '}') --depth;
                    else if (*r.cur == '"') { char t[512]; read_string(&r, t, sizeof(t)); continue; }
                    ++r.cur;
                }
            }
            ++imported;
        }
        match_char(&r, ']');
    }

    /* ── Import Systems ── */
    r.cur = top_start;
    if (seek_key(&r, "systems") && match_char(&r, '[')) {
        while (r.cur < r.buf + r.len && *r.cur != ']') {
            char sname[64] = "System";
            char system_level_s[16] = "SL0";
            char system_priority_s[32] = "LOW";
            char system_safety_s[32] = "QM";
            const char *sys_start;
            EEC_System_t *sys;

            skip_ws(&r);
            if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
            if (*r.cur == ']') break;
            if (!match_char(&r, '{')) break;
            sys_start = r.cur;

            if (seek_key(&r, "name")) read_string(&r, sname, sizeof(sname));
            r.cur = sys_start;
            if (seek_key(&r, "system_level")) read_string(&r, system_level_s, sizeof(system_level_s));
            r.cur = sys_start;
            if (seek_key(&r, "priority")) read_string(&r, system_priority_s, sizeof(system_priority_s));
            r.cur = sys_start;
            if (seek_key(&r, "safety")) read_string(&r, system_safety_s, sizeof(system_safety_s));
            r.cur = sys_start;

            sys = EEC_Architecture_CreateSystem(arch, sname);
            if (!sys) break;
            sys->system_level = parse_system_level(system_level_s);
            sys->priority = parse_priority(system_priority_s);
            sys->safety = parse_safety(system_safety_s);
            {
                char ref_2x_s[26] = "";
                r.cur = sys_start;
                if (seek_key(&r, "Ref-2X")) read_string(&r, ref_2x_s, sizeof(ref_2x_s));
                strncpy(sys->ref_2x, ref_2x_s, sizeof(sys->ref_2x) - 1);
                sys->ref_2x[sizeof(sys->ref_2x) - 1] = '\0';
            }
            {
                char spn[64] = "";
                r.cur = sys_start;
                if (seek_key(&r, "part_number")) read_string(&r, spn, sizeof(spn));
                snprintf(sys->part_number, sizeof(sys->part_number), "%s", spn);
            }

            if (seek_key(&r, "devices") && match_char(&r, '[')) {
                EEC_Component_t *bundle_comp = EEC_System_CreateComponent(sys, "Default");
                while (r.cur < r.buf + r.len && *r.cur != ']') {
                    char dname[64] = "Device";
                    char dtype[32] = "SENSOR";
                    char device_priority_s[32] = "LOW";
                    char device_safety_s[32] = "QM";
                    const char *dev_start;
                    EEC_Sensor_t *sensor = NULL;
                    EEC_Actuator_t *actuator = NULL;
                    uint32_t pin_counter = 1;

                    skip_ws(&r);
                    if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
                    if (*r.cur == ']') break;
                    if (!match_char(&r, '{')) break;
                    dev_start = r.cur;

                    if (seek_key(&r, "name")) read_string(&r, dname, sizeof(dname));
                    r.cur = dev_start;
                    if (seek_key(&r, "device_type")) read_string(&r, dtype, sizeof(dtype));
                    r.cur = dev_start;
                    if (seek_key(&r, "priority")) read_string(&r, device_priority_s, sizeof(device_priority_s));
                    r.cur = dev_start;
                    if (seek_key(&r, "safety")) read_string(&r, device_safety_s, sizeof(device_safety_s));
                    r.cur = dev_start;

                    if (strcmp(dtype, "ACTUATOR") == 0) {
                        actuator = EEC_Component_CreateActuator(bundle_comp, dname);
                        if (actuator) {
                            char dpn[64] = "";
                            actuator->priority = parse_priority(device_priority_s);
                            actuator->safety = parse_safety(device_safety_s);
                            r.cur = dev_start;
                            if (seek_key(&r, "part_number")) read_string(&r, dpn, sizeof(dpn));
                            snprintf(actuator->part_number, sizeof(actuator->part_number), "%s", dpn);
                        }
                    } else {
                        sensor = EEC_Component_CreateSensor(bundle_comp, dname);
                        if (sensor) {
                            char dpn[64] = "";
                            sensor->priority = parse_priority(device_priority_s);
                            sensor->safety = parse_safety(device_safety_s);
                            r.cur = dev_start;
                            if (seek_key(&r, "part_number")) read_string(&r, dpn, sizeof(dpn));
                            snprintf(sensor->part_number, sizeof(sensor->part_number), "%s", dpn);
                        }
                    }

                    r.cur = dev_start;
                    if (seek_key(&r, "signals") && match_char(&r, '[')) {
                        while (r.cur < r.buf + r.len && *r.cur != ']') {
                            skip_ws(&r);
                            if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
                            if (*r.cur == ']') break;
                            import_signal_batch(&r, arch, sensor, actuator, &pin_counter);
                        }
                        match_char(&r, ']');
                    }

                    /* Parse connectors array */
                    r.cur = dev_start;
                    if (seek_key(&r, "connectors") && match_char(&r, '[')) {
                        void *target = sensor ? (void *)sensor : (void *)actuator;
                        ConnTargetKind kind = sensor ? CONN_TARGET_SENSOR : CONN_TARGET_ACTUATOR;
                        if (target) import_connectors(&r, target, kind);
                        match_char(&r, ']');
                    }

                    /* Skip to end of device object */
                    {
                        int depth = 1;
                        r.cur = dev_start;
                        while (r.cur < r.buf + r.len && depth > 0) {
                            if (*r.cur == '{') ++depth;
                            else if (*r.cur == '}') --depth;
                            else if (*r.cur == '"') { char t[512]; read_string(&r, t, sizeof(t)); continue; }
                            ++r.cur;
                        }
                    }
                }
                match_char(&r, ']');
            }

            /* Skip to end of system object */
            {
                int depth = 1;
                r.cur = sys_start;
                while (r.cur < r.buf + r.len && depth > 0) {
                    if (*r.cur == '{') ++depth;
                    else if (*r.cur == '}') --depth;
                    else if (*r.cur == '"') { char t[512]; read_string(&r, t, sizeof(t)); continue; }
                    ++r.cur;
                }
            }
            ++imported;
        }
        match_char(&r, ']');
    }

    /* ── Import buses ── */
    r.cur = top_start;
    if (seek_key(&r, "buses") && match_char(&r, '[')) {
        while (r.cur < r.buf + r.len && *r.cur != ']') {
            char bname[64] = "Bus";
            char btype_s[32] = "CAN";
            char bref2x[26] = "";
            char bpriority_s[32] = "LOW";
            char bsafety_s[32] = "QM";
            uint32_t bbitrate = 0;
            const char *bus_start;

            skip_ws(&r);
            if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
            if (*r.cur == ']') break;
            if (*r.cur != '{') break;

            bus_start = r.cur;
            ++r.cur;

            r.cur = bus_start + 1;
            if (seek_key(&r, "name")) read_string(&r, bname, sizeof(bname));
            r.cur = bus_start + 1;
            if (seek_key(&r, "type")) read_string(&r, btype_s, sizeof(btype_s));
            r.cur = bus_start + 1;
            if (seek_key(&r, "Ref-2X")) read_string(&r, bref2x, sizeof(bref2x));
            r.cur = bus_start + 1;
            if (seek_key(&r, "bitrate")) {
                skip_ws(&r);
                if (*r.cur == ':') { ++r.cur; skip_ws(&r); }
                bbitrate = (uint32_t)strtoul(r.cur, NULL, 10);
            }
            r.cur = bus_start + 1;
            if (seek_key(&r, "priority")) read_string(&r, bpriority_s, sizeof(bpriority_s));
            r.cur = bus_start + 1;
            if (seek_key(&r, "safety")) read_string(&r, bsafety_s, sizeof(bsafety_s));

            {
                EEC_Bus_t *bus = EEC_Architecture_CreateBus(arch, bname, EEC_Bus_ParseType(btype_s));
                if (bus) {
                    strncpy(bus->ref_2x, bref2x, sizeof(bus->ref_2x) - 1);
                    bus->ref_2x[sizeof(bus->ref_2x) - 1] = '\0';
                    bus->bitrate = bbitrate;
                    bus->priority = parse_priority(bpriority_s);
                    bus->safety = parse_safety(bsafety_s);
                    {
                        char bpn[64] = "";
                        r.cur = bus_start + 1;
                        if (seek_key(&r, "part_number")) read_string(&r, bpn, sizeof(bpn));
                        snprintf(bus->part_number, sizeof(bus->part_number), "%s", bpn);
                    }

                    /* Parse nodes array */
                    r.cur = bus_start + 1;
                    if (seek_key(&r, "nodes") && match_char(&r, '[')) {
                        while (r.cur < r.buf + r.len && *r.cur != ']') {
                            char ecu_name[64] = "";
                            uint8_t port_idx = 0;
                            skip_ws(&r);
                            if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
                            if (*r.cur == ']') break;
                            if (*r.cur == '{') {
                                const char *nstart = r.cur;
                                r.cur = nstart + 1;
                                if (seek_key(&r, "ecu")) read_string(&r, ecu_name, sizeof(ecu_name));
                                r.cur = nstart + 1;
                                if (seek_key(&r, "port_index")) {
                                    skip_ws(&r);
                                    if (*r.cur == ':') { ++r.cur; skip_ws(&r); }
                                    port_idx = (uint8_t)strtoul(r.cur, NULL, 10);
                                }
                                {
                                    uint32_t ei;
                                    for (ei = 0; ei < arch->ecu_count; ++ei) {
                                        if (arch->ecus[ei] && strcmp(arch->ecus[ei]->name, ecu_name) == 0) {
                                            EEC_Bus_ConnectEcu(bus, arch->ecus[ei], port_idx);
                                            break;
                                        }
                                    }
                                }
                                /* Skip to end of node object */
                                {
                                    int depth = 1;
                                    r.cur = nstart + 1;
                                    while (r.cur < r.buf + r.len && depth > 0) {
                                        if (*r.cur == '{') ++depth;
                                        else if (*r.cur == '}') --depth;
                                        else if (*r.cur == '"') { char t[512]; read_string(&r, t, sizeof(t)); continue; }
                                        ++r.cur;
                                    }
                                }
                            }
                        }
                        match_char(&r, ']');
                    }

                    /* Parse signals array */
                    r.cur = bus_start + 1;
                    if (seek_key(&r, "signals") && match_char(&r, '[')) {
                        while (r.cur < r.buf + r.len && *r.cur != ']') {
                            char signame[128] = "";
                            uint32_t si;
                            skip_ws(&r);
                            if (*r.cur == ',') { ++r.cur; skip_ws(&r); }
                            if (*r.cur == ']') break;
                            read_string(&r, signame, sizeof(signame));
                            for (si = 0; si < arch->signal_count; ++si) {
                                if (arch->signals[si] && strcmp(arch->signals[si]->name, signame) == 0) {
                                    EEC_Bus_AddSignal(bus, arch->signals[si]);
                                    break;
                                }
                            }
                        }
                        match_char(&r, ']');
                    }
                }
            }

            /* Skip to end of bus object */
            {
                int depth = 1;
                r.cur = bus_start + 1;
                while (r.cur < r.buf + r.len && depth > 0) {
                    if (*r.cur == '{') ++depth;
                    else if (*r.cur == '}') --depth;
                    else if (*r.cur == '"') { char t[512]; read_string(&r, t, sizeof(t)); continue; }
                    ++r.cur;
                }
            }
            ++imported;
        }
        match_char(&r, ']');
    }

    free(buf);
    EEC_Log_Printf(EEC_LOG_INFO, "Library: imported bundle from %s (%d component(s))", filepath, imported);
    return imported;
}
