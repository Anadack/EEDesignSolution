/**
 * @file    EEC_pin_helpers.h
 * @brief   Helpers to populate ECU/device pin metadata from structured
 *          JSON fields or free-text descriptions.
 */
#ifndef EEC_PIN_HELPERS_H
#define EEC_PIN_HELPERS_H

#include "EEC_types.h"

/* Forward declare the ECU pin structure to avoid including the full
 * architecture header here and prevent circular includes. The .c file
 * includes `EEC_architecture.h` to access the full definition. */
struct EEC_EcuPin_s;
typedef struct EEC_EcuPin_s EEC_EcuPin_t;

#ifdef __cplusplus
extern "C" {
#endif

/* Populate provided supply/ground/voltage/current fields on an ECU pin.
 * Parameters mirror typical JSON/import fields. Fields may be NULL/0
 * when unavailable; the function will fall back to name/group/electrical
 * text parsing where possible.
 */
void EEC_Pin_PopulateProvidedFromData(EEC_EcuPin_t *pin,
    const char *name, const char *group, const char *electrical,
    const char *supply_enum_token, float voltage_nominal, float current_max_a,
    const char *ground_name, const char *ground_class_str);

#ifdef __cplusplus
}
#endif

#endif /* EEC_PIN_HELPERS_H */
