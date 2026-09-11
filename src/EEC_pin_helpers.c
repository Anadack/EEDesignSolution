/**
 * @file    EEC_pin_helpers.c
 * @brief   Helper routines to populate ECU pin metadata from JSON or
 *          programmatic input.
 */

#include "EEC_pin_helpers.h"
#include "EEC_types.h"
#include "EEC_architecture.h"
#include <string.h>
#include <ctype.h>
#include <stdio.h>

/* Local utility: parse a voltage nominal from an electrical description.
 * Returns 1 on success and writes nominal to out_v, otherwise 0.
 */
static int parse_voltage_nominal(const char *electrical, float *out_v)
{
    const char *p;
    float v1, v2;
    if (!electrical || !out_v) return 0;

    /* try range pattern like "0..18 V" */
    p = electrical;
    while (*p) {
        if (sscanf(p, "%f..%f V", &v1, &v2) == 2) {
            *out_v = (v1 + v2) * 0.5f;
            return 1;
        }
        ++p;
    }

    /* try to find last 'V' and parse the number immediately preceding it */
    p = strrchr(electrical, 'V');
    if (p) {
        const char *q = p;
        /* move left to start of number */
        while (q > electrical && isspace((unsigned char)*(q-1))) --q;
        const char *start = q;
        while (start > electrical) {
            const char c = *(start-1);
            if ((c >= '0' && c <= '9') || c == '.' || c == '-' || c == '+') --start;
            else break;
        }
        if (start < p) {
            if (sscanf(start, "%f", out_v) == 1) return 1;
        }
    }

    /* fallback: first floating number in the text */
    p = electrical;
    while (*p) {
        if (sscanf(p, "%f", &v1) == 1) { *out_v = v1; return 1; }
        ++p;
    }
    return 0;
}

/* Local utility: parse nominal/maximum current in amps from electrical text.
 * Returns 1 on success and writes amps to out_a, otherwise 0.
 */
static int parse_current_max(const char *electrical, float *out_a)
{
    const char *p;
    float v;
    if (!electrical || !out_a) return 0;
    p = electrical;
    while (*p) {
        if (sscanf(p, "%f A", &v) == 1) { *out_a = v; return 1; }
        if (sscanf(p, "%f mA", &v) == 1) { *out_a = v / 1000.0f; return 1; }
        ++p;
    }
    return 0;
}

/* Map a ground class string to enum. */
static EEC_GroundClass_t parse_ground_class(const char *s)
{
    if (!s) return EEC_GND_UNCLASSIFIED;
    if (strcmp(s, "LOGIC") == 0 || strcmp(s, "SENSOR_GND") == 0) return EEC_GND_LOGIC;
    if (strcmp(s, "POWER") == 0 || strcmp(s, "BATT_GND") == 0) return EEC_GND_POWER;
    return EEC_GND_UNCLASSIFIED;
}

void EEC_Pin_PopulateProvidedFromData(EEC_EcuPin_t *pin,
    const char *name, const char *group, const char *electrical,
    const char *supply_enum_token, float voltage_nominal, float current_max_a,
    const char *ground_name, const char *ground_class_str)
{
    float vtmp;

    if (!pin) return;

    /* Supply enum token preferred */
    if (supply_enum_token && supply_enum_token[0]) {
        pin->provided_sensor_supply = EEC_SensorSupply_Parse(supply_enum_token);
    } else {
        /* try name, then group, then electrical text */
        pin->provided_sensor_supply = EEC_SensorSupply_Parse(name);
        if (pin->provided_sensor_supply == EEC_SENSOR_SUPPLY_UNKNOWN)
            pin->provided_sensor_supply = EEC_SensorSupply_Parse(group);
        if (pin->provided_sensor_supply == EEC_SENSOR_SUPPLY_UNKNOWN && electrical)
            pin->provided_sensor_supply = EEC_SensorSupply_Parse(electrical);
    }

    /* Provided voltage */
    if (voltage_nominal > 0.0f) {
        pin->provided_supply_voltage = voltage_nominal;
    } else if (parse_voltage_nominal(electrical, &vtmp)) {
        pin->provided_supply_voltage = vtmp;
    }

    /* Provided current capacity */
    if (current_max_a > 0.0f) {
        pin->current_max = current_max_a;
    } else if (parse_current_max(electrical, &vtmp)) {
        pin->current_max = vtmp;
    }

    /* Ground */
    if (ground_name && ground_name[0]) {
        pin->provided_sensor_ground = EEC_SensorGround_Parse(ground_name);
    } else {
        pin->provided_sensor_ground = EEC_SensorGround_Parse(group);
        if (pin->provided_sensor_ground == EEC_SENSOR_GROUND_UNKNOWN && name)
            pin->provided_sensor_ground = EEC_SensorGround_Parse(name);
        if (pin->provided_sensor_ground == EEC_SENSOR_GROUND_UNKNOWN && electrical)
            pin->provided_sensor_ground = EEC_SensorGround_Parse(electrical);
    }

    /* Ground class mapping */
    if (ground_class_str && ground_class_str[0]) {
        pin->ground_class = parse_ground_class(ground_class_str);
    }
}
