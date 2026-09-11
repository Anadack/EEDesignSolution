/**
 * @file    EEC_component_loader.c
 * @brief   E/E Architect Design — Component template loader implementation.
 *
 * Reads a JSON file that follows the "eec-component-1.0" schema and
 * assembles the corresponding runtime component inside the architecture.
 *
 * JSON schema contract (eec-component-1.0):
 * @verbatim
 * {
 *   "schema":      "eec-component-1.0",
 *   "type":        "component",
 *   "name":        "<component name>",
 *   "part_number": "<optional part number>",
 *   "ref_2x":      "<optional Ref-2X identifier>",
 *   "description": "<short functional description>",
 *   "supplier":    "<supplier name>",
 *   "location":    "<vehicle zone>",
 *   "take_rate":   100.0,
 *   "is_mandatory": true,
 *   "priority":    "HIGH",
 *   "safety":      "AgPL_B",
 *   "devices": [
 *     {
 *       "device_type":    "sensor",
 *       "instance_name":  "<unique name for this instance>",
 *       "path":           "<relative path to sensor JSON>",
 *       "is_mandatory":   true,
 *       "safety":         "AgPL_B",
 *       "notes":          "<engineering notes>"
 *     },
 *     {
 *       "device_type":    "actuator",
 *       "instance_name":  "<unique name for this instance>",
 *       "path":           "<relative path to actuator JSON>",
 *       ...
 *     }
 *   ]
 * }
 * @endverbatim
 *
 * Implementation notes:
 *   - A minimal, allocation-free JSON scanner is used.  It finds key-value
 *     pairs by text search rather than building a DOM tree.
 *   - The "devices" array is iterated by locating successive '{' tokens
 *     inside the array brackets.
 *   - Unknown keys are silently ignored for forward compatibility.
 *
 * @author  Anadack Temtching Dassi
 * @date    2026
 */

#include "EEC_component_loader.h"
#include "EEC_library.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* =========================================================================
 * Internal JSON scanner helpers
 * =========================================================================
 * These helpers parse the controlled, single-level JSON produced by the
 * component template generator.  They are intentionally simple — no
 * recursive descent, no heap allocation — because the schema is fixed.
 */

/** Maximum length of any single string value in the component template. */
#define CL_MAX_VALUE 256

/** Maximum number of device entries in one component template. */
#define CL_MAX_DEVICES 32

/** Maximum file size we are willing to load into memory (128 KiB). */
#define CL_MAX_FILE_BYTES (128U * 1024U)

/**
 * @brief Read an entire text file into a heap-allocated NUL-terminated buffer.
 *
 * The caller is responsible for calling free() on the returned pointer.
 *
 * @param filepath  Path to the file to read.
 * @return          Pointer to the buffer, or NULL on failure.
 */
static char *cl_read_file(const char *filepath)
{
    FILE   *f;
    long    sz;
    char   *buf;
    size_t  n;

    f = fopen(filepath, "rb");
    if (!f) {
        return NULL;
    }

    /* Determine file size. */
    if (fseek(f, 0L, SEEK_END) != 0) {
        fclose(f);
        return NULL;
    }
    sz = ftell(f);
    rewind(f);

    if (sz <= 0 || (size_t)sz >= CL_MAX_FILE_BYTES) {
        fclose(f);
        return NULL;
    }

    buf = (char *)malloc((size_t)sz + 1U);
    if (!buf) {
        fclose(f);
        return NULL;
    }

    n = fread(buf, 1U, (size_t)sz, f);
    fclose(f);

    buf[n] = '\0';
    return buf;
}

/**
 * @brief Extract the string value associated with a JSON key.
 *
 * Searches for the pattern  "key": "value"  inside @p buf starting at
 * @p start.  On success copies the value (without surrounding quotes)
 * into @p out.
 *
 * @param buf    NUL-terminated JSON buffer to search.
 * @param start  Byte offset at which to begin the search.
 * @param key    JSON key name (without quotes).
 * @param out    Destination buffer.
 * @param out_sz Size of @p out in bytes.
 * @return       true on success, false when the key is absent or the
 *               value is not a JSON string.
 */
static bool cl_get_string(const char *buf, size_t start,
                          const char *key, char *out, size_t out_sz)
{
    char        search[CL_MAX_VALUE];
    const char *p;
    const char *q;
    size_t      len;

    if (!buf || !key || !out || out_sz == 0U) {
        return false;
    }

    /* Build the search pattern  "key"  (just the key with quotes). */
    snprintf(search, sizeof(search), "\"%s\"", key);

    p = strstr(buf + start, search);
    if (!p) {
        return false;
    }
    p += strlen(search);

    /* Skip optional whitespace and colon. */
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r' || *p == ':') {
        p++;
    }

    /* Expect an opening quote for the string value. */
    if (*p != '"') {
        return false;
    }
    p++; /* move past the opening quote */

    /* Scan to the closing quote, honouring escape sequences. */
    q = p;
    while (*q && *q != '"') {
        if (*q == '\\' && *(q + 1) != '\0') {
            q++; /* skip one escaped character */
        }
        q++;
    }

    len = (size_t)(q - p);
    if (len >= out_sz) {
        len = out_sz - 1U;
    }
    memcpy(out, p, len);
    out[len] = '\0';

    return true;
}

/**
 * @brief Find the byte offset of the "devices" array opening bracket.
 *
 * Locates the first '[' that follows the "devices" key.
 *
 * @param buf  NUL-terminated JSON buffer.
 * @return     Byte offset of '[', or (size_t)-1 when not found.
 */
static size_t cl_find_devices_array(const char *buf)
{
    const char *p;

    p = strstr(buf, "\"devices\"");
    if (!p) {
        return (size_t)-1;
    }
    p = strchr(p, '[');
    if (!p) {
        return (size_t)-1;
    }
    return (size_t)(p - buf);
}

/**
 * @brief Locate the next device object '{' within the devices array.
 *
 * Starting at @p search_start, finds the next '{' that lies before the
 * closing ']' of the devices array.
 *
 * @param buf           NUL-terminated JSON buffer.
 * @param array_start   Byte offset of the '[' of the devices array.
 * @param search_start  Byte offset from which to begin searching.
 * @param[out] obj_end  Set to the byte offset of the matching '}'.
 * @return              Byte offset of '{', or (size_t)-1 when no more
 *                      device objects are found.
 */
static size_t cl_next_device_object(const char *buf,
                                    size_t array_start,
                                    size_t search_start,
                                    size_t *obj_end)
{
    const char *arr;
    const char *p;
    const char *close_bracket;
    const char *open_brace;
    const char *close_brace;
    int         depth;

    *obj_end = (size_t)-1;

    arr = buf + array_start;

    /* The array must be closed at some point. */
    close_bracket = strchr(arr, ']');
    if (!close_bracket) {
        return (size_t)-1;
    }

    /* Start searching from the caller-supplied offset. */
    if (search_start < array_start) {
        search_start = array_start;
    }
    p = buf + search_start;

    /* Skip forward to the next '{' that is still inside the array. */
    open_brace = strchr(p, '{');
    if (!open_brace || open_brace > close_bracket) {
        return (size_t)-1;
    }

    /* Find the matching '}' by counting nesting depth. */
    depth = 0;
    close_brace = open_brace;
    while (*close_brace) {
        if (*close_brace == '{') {
            depth++;
        } else if (*close_brace == '}') {
            depth--;
            if (depth == 0) {
                break;
            }
        }
        close_brace++;
    }

    if (depth != 0 || *close_brace != '}') {
        return (size_t)-1;
    }

    *obj_end = (size_t)(close_brace - buf);
    return (size_t)(open_brace - buf);
}

/* =========================================================================
 * Device descriptor — parsed from one entry in the "devices" array
 * =========================================================================
 */

/** @brief Parsed representation of one device entry from the template. */
typedef struct {
    char device_type[32];      /**< "sensor" or "actuator". */
    char instance_name[64];    /**< Unique instance name for this device. */
    char path[CL_MAX_VALUE];   /**< Relative path to the device JSON file. */
} ComponentDevice_t;

/* =========================================================================
 * Public API
 * =========================================================================
 */

EEC_Component_t *EEC_ComponentLoader_Load(EEC_Architecture_t *arch,
                                          EEC_System_t       *system,
                                          const char         *filepath)
{
    char              *buf      = NULL;
    EEC_Component_t   *comp     = NULL;
    char               comp_name[64];
    char               part_num[64];
    char               ref_2x[32];
    char               description[128];
    char               supplier[64];
    char               location[64];
    size_t             devices_start;
    size_t             search   = 0U;
    size_t             obj_start;
    size_t             obj_end;
    ComponentDevice_t  devices[CL_MAX_DEVICES];
    int                device_count = 0;
    int                i;

    /* ------------------------------------------------------------------ */
    /* 1. Guard: validate inputs                                           */
    /* ------------------------------------------------------------------ */
    if (!arch || !system || !filepath) {
        fprintf(stderr, "[ComponentLoader] NULL argument passed to Load()\n");
        return NULL;
    }

    /* ------------------------------------------------------------------ */
    /* 2. Load the template file into memory                               */
    /* ------------------------------------------------------------------ */
    buf = cl_read_file(filepath);
    if (!buf) {
        fprintf(stderr, "[ComponentLoader] Cannot read template: %s\n", filepath);
        return NULL;
    }

    /* ------------------------------------------------------------------ */
    /* 3. Validate schema field                                            */
    /* ------------------------------------------------------------------ */
    if (!strstr(buf, "eec-component-1.0")) {
        fprintf(stderr,
                "[ComponentLoader] File is not an eec-component-1.0 schema: %s\n",
                filepath);
        free(buf);
        return NULL;
    }

    /* ------------------------------------------------------------------ */
    /* 4. Read component metadata (top-level keys)                        */
    /* ------------------------------------------------------------------ */

    /* "name" is mandatory — abort if missing. */
    if (!cl_get_string(buf, 0U, "name", comp_name, sizeof(comp_name))) {
        fprintf(stderr, "[ComponentLoader] Missing \"name\" key in: %s\n", filepath);
        free(buf);
        return NULL;
    }

    /* Optional metadata fields — use empty strings as defaults. */
    if (!cl_get_string(buf, 0U, "part_number", part_num, sizeof(part_num))) {
        part_num[0] = '\0';
    }
    if (!cl_get_string(buf, 0U, "ref_2x", ref_2x, sizeof(ref_2x))) {
        ref_2x[0] = '\0';
    }
    if (!cl_get_string(buf, 0U, "description", description, sizeof(description))) {
        description[0] = '\0';
    }
    if (!cl_get_string(buf, 0U, "supplier", supplier, sizeof(supplier))) {
        supplier[0] = '\0';
    }
    if (!cl_get_string(buf, 0U, "location", location, sizeof(location))) {
        location[0] = '\0';
    }

    /* ------------------------------------------------------------------ */
    /* 5. Parse the "devices" array                                        */
    /* ------------------------------------------------------------------ */

    /* Find where the devices array starts in the buffer. */
    devices_start = cl_find_devices_array(buf);
    if (devices_start == (size_t)-1) {
        fprintf(stderr, "[ComponentLoader] No \"devices\" array found in: %s\n", filepath);
        free(buf);
        return NULL;
    }

    /*
     * Walk through each device object '{...}' inside the array.
     * We parse device_type, instance_name and path for each entry.
     */
    search = devices_start + 1U; /* start right after '[' */
    while (device_count < CL_MAX_DEVICES) {
        ComponentDevice_t *dev = &devices[device_count];

        obj_start = cl_next_device_object(buf, devices_start, search, &obj_end);
        if (obj_start == (size_t)-1) {
            break; /* No more device objects in the array */
        }

        /* Extract the three mandatory fields from the device object. */
        if (!cl_get_string(buf, obj_start, "device_type",
                           dev->device_type, sizeof(dev->device_type))) {
            dev->device_type[0] = '\0';
        }
        if (!cl_get_string(buf, obj_start, "instance_name",
                           dev->instance_name, sizeof(dev->instance_name))) {
            dev->instance_name[0] = '\0';
        }
        if (!cl_get_string(buf, obj_start, "path",
                           dev->path, sizeof(dev->path))) {
            dev->path[0] = '\0';
        }

        /*
         * Only accept device entries that have all three required fields.
         * Entries with missing fields are printed as a warning and skipped.
         */
        if (dev->device_type[0] && dev->instance_name[0] && dev->path[0]) {
            device_count++;
        } else {
            fprintf(stderr,
                    "[ComponentLoader] Skipping incomplete device entry in: %s\n",
                    filepath);
        }

        /* Advance the search cursor past the current device object. */
        search = obj_end + 1U;
    }

    free(buf);
    buf = NULL;

    if (device_count == 0) {
        fprintf(stderr, "[ComponentLoader] No valid device entries found in: %s\n", filepath);
        return NULL;
    }

    /* ------------------------------------------------------------------ */
    /* 6. Create the runtime component inside the system                  */
    /* ------------------------------------------------------------------ */

    comp = EEC_System_CreateComponent(system, comp_name);
    if (!comp) {
        fprintf(stderr, "[ComponentLoader] EEC_System_CreateComponent failed for: %s\n",
                comp_name);
        return NULL;
    }

    /* Copy optional metadata fields into the component struct.
     * snprintf guarantees NUL-termination and avoids the -Wstringop-truncation
     * warning that strncpy triggers when source and destination are the same size. */
    if (part_num[0]) {
        snprintf(comp->part_number, sizeof(comp->part_number), "%s", part_num);
    }
    if (ref_2x[0]) {
        snprintf(comp->ref_2x, sizeof(comp->ref_2x), "%s", ref_2x);
    }
    if (description[0]) {
        snprintf(comp->description, sizeof(comp->description), "%s", description);
    }
    if (supplier[0]) {
        snprintf(comp->supplier, sizeof(comp->supplier), "%s", supplier);
    }
    if (location[0]) {
        snprintf(comp->location, sizeof(comp->location), "%s", location);
    }

    printf("[ComponentLoader] Created component '%s' from: %s\n", comp_name, filepath);

    /* ------------------------------------------------------------------ */
    /* 7. Import each device listed in the "devices" array               */
    /* ------------------------------------------------------------------ */

    for (i = 0; i < device_count; ++i) {
        const ComponentDevice_t *dev = &devices[i];

        if (strcmp(dev->device_type, "sensor") == 0) {
            /*
             * Import a sensor from its JSON file and attach it to the
             * component.  EEC_Library_ImportSensor handles all connector,
             * pin and signal setup internally.
             */
            EEC_Sensor_t *sensor = EEC_Library_ImportSensor(arch, comp, dev->path);
            if (!sensor) {
                fprintf(stderr,
                        "[ComponentLoader] [WARN] Could not import sensor '%s' from: %s\n",
                        dev->instance_name, dev->path);
            } else {
                /*
                 * Rename the sensor to the instance_name declared in the
                 * template so that reports distinguish multiple instances of
                 * the same catalogue part (e.g. two identical pressure sensors
                 * on left and right circuits).
                 */
                strncpy(sensor->name, dev->instance_name,
                        sizeof(sensor->name) - 1U);
                sensor->name[sizeof(sensor->name) - 1U] = '\0';
                printf("[ComponentLoader]   + sensor  '%s' <- %s\n",
                       dev->instance_name, dev->path);
            }

        } else if (strcmp(dev->device_type, "actuator") == 0) {
            /*
             * Import an actuator from its JSON file and attach it to the
             * component.  Same mechanics as sensor import above.
             */
            EEC_Actuator_t *act = EEC_Library_ImportActuator(arch, comp, dev->path);
            if (!act) {
                fprintf(stderr,
                        "[ComponentLoader] [WARN] Could not import actuator '%s' from: %s\n",
                        dev->instance_name, dev->path);
            } else {
                strncpy(act->name, dev->instance_name,
                        sizeof(act->name) - 1U);
                act->name[sizeof(act->name) - 1U] = '\0';
                printf("[ComponentLoader]   + actuator '%s' <- %s\n",
                       dev->instance_name, dev->path);
            }

        } else {
            fprintf(stderr,
                    "[ComponentLoader] [WARN] Unknown device_type '%s' for '%s' — skipped\n",
                    dev->device_type, dev->instance_name);
        }
    }

    printf("[ComponentLoader] Component '%s' loaded: %u sensor(s), %u actuator(s)\n",
           comp_name,
           comp->sensor_count,
           comp->actuator_count);

    return comp;
}


void EEC_ComponentLoader_PrintSummary(const EEC_Component_t *comp, FILE *out)
{
    uint32_t i;
    uint32_t mapped_signals;
    uint32_t total_signals;
    uint32_t j;

    if (!comp || !out) {
        return;
    }

    fprintf(out, "=== Component Summary ===\n");
    fprintf(out, "  Name        : %s\n", comp->name);
    fprintf(out, "  Part number : %s\n",
            comp->part_number[0] ? comp->part_number : "(none)");
    fprintf(out, "  Ref-2X      : %s\n",
            comp->ref_2x[0] ? comp->ref_2x : "(none)");
    fprintf(out, "  Description : %s\n",
            comp->description[0] ? comp->description : "(none)");
    fprintf(out, "  Location    : %s\n",
            comp->location[0] ? comp->location : "(none)");
    fprintf(out, "  Sensors     : %u\n", comp->sensor_count);
    fprintf(out, "  Actuators   : %u\n", comp->actuator_count);

    /* --- Print sensor details --- */
    for (i = 0U; i < comp->sensor_count; ++i) {
        const EEC_Sensor_t *s = comp->sensors[i];
        if (!s) {
            continue;
        }

        /* Count mapped vs total signals for this sensor. */
        mapped_signals = 0U;
        total_signals  = s->pin_count;
        for (j = 0U; j < s->pin_count; ++j) {
            if (s->pins[j].signal && s->pins[j].signal->is_mapped) {
                mapped_signals++;
            }
        }

        fprintf(out, "  [S%u] %-40s  pins=%u  mapped=%u/%u\n",
                i + 1U, s->name, s->pin_count, mapped_signals, total_signals);
    }

    /* --- Print actuator details --- */
    for (i = 0U; i < comp->actuator_count; ++i) {
        const EEC_Actuator_t *a = comp->actuators[i];
        if (!a) {
            continue;
        }

        mapped_signals = 0U;
        total_signals  = a->pin_count;
        for (j = 0U; j < a->pin_count; ++j) {
            if (a->pins[j].signal && a->pins[j].signal->is_mapped) {
                mapped_signals++;
            }
        }

        fprintf(out, "  [A%u] %-40s  pins=%u  mapped=%u/%u\n",
                i + 1U, a->name, a->pin_count, mapped_signals, total_signals);
    }

    fprintf(out, "=========================\n");
}
