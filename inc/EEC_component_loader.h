/**
 * @file    EEC_component_loader.h
 * @brief   E/E Architect Design — Component template loader.
 *
 * This module loads a component JSON template (schema "eec-component-1.0")
 * and assembles the corresponding runtime objects inside the architecture.
 *
 * A component template is a JSON file that describes:
 *   - Component metadata: name, part number, location, safety class, etc.
 *   - A "devices" array listing the sensors and actuators that belong to the
 *     component, each referencing a sensor or actuator JSON file by relative
 *     path.
 *
 * Typical usage:
 * @code
 *   EEC_System_t    *sys  = EEC_Architecture_CreateSystem(arch, "Rear Hitch System");
 *   EEC_Component_t *comp = EEC_ComponentLoader_Load(
 *                               arch, sys,
 *                               "library/components/Hydraulic_Rear_Hitch_Control.eec-component-1.0.json");
 *   if (!comp) {
 *       fprintf(stderr, "[ERROR] Component load failed\n");
 *   }
 * @endcode
 *
 * The loader calls EEC_Library_ImportSensor() and EEC_Library_ImportActuator()
 * internally, so every device inherits the full import logic (connector data,
 * signal definitions, electrical requirements, diagnostics flags, etc.).
 *
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#ifndef EEC_COMPONENT_LOADER_H
#define EEC_COMPONENT_LOADER_H

#include <stdio.h>
#include "EEC_architecture.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Load a component from a JSON template and register it in a system.
 *
 * Opens the file at @p filepath, reads the component metadata and the
 * "devices" array, creates an EEC_Component_t inside @p system, then imports
 * each sensor and actuator listed in the template using the standard library
 * import functions.
 *
 * On success all devices are attached to the returned component and their
 * signals are registered in @p arch so they can be mapped to ECU pins.
 *
 * @param arch      Target architecture (must not be NULL).
 * @param system    Target system to attach the component to (must not be NULL).
 * @param filepath  Path to the "eec-component-1.0" JSON template file.
 * @return          Pointer to the newly created component, or NULL on error.
 *
 * @note  The function silently skips individual devices whose JSON file is
 *        missing and continues loading the remaining ones, printing a warning
 *        for each skipped entry.  The caller should verify that
 *        component->sensor_count and component->actuator_count match the
 *        expected counts if strict completeness is required.
 */
EEC_Component_t *EEC_ComponentLoader_Load(EEC_Architecture_t *arch,
                                          EEC_System_t       *system,
                                          const char         *filepath);

/**
 * @brief Print a human-readable summary of a loaded component to @p out.
 *
 * Lists the component name, part number, safety class and every device
 * (sensor or actuator) with its instance name, mapped/unmapped status and
 * signal count.  Useful as a post-load sanity check.
 *
 * @param comp  Component to summarise (must not be NULL).
 * @param out   Output file stream; pass stdout for console output.
 */
void EEC_ComponentLoader_PrintSummary(const EEC_Component_t *comp, FILE *out);

#ifdef __cplusplus
}
#endif
#endif /* EEC_COMPONENT_LOADER_H */
