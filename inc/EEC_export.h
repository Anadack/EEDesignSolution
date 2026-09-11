/**
 * @file    EEC_export.h
 * @brief   E/E Architect Design — JSON and HTML export helpers.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#ifndef EEC_EXPORT_H
#define EEC_EXPORT_H

#include "EEC_architecture.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @brief Export the full architecture model to a JSON document.
 *  @param arch Architecture to serialize.
 *  @param filename Output JSON file path.
 *  @return 0 on success, -1 on invalid input or file creation failure.
 */
int EEC_Export_architecture_json(const EEC_Architecture_t *arch, const char *filename);

/** @brief Export the physical-architecture JSON consumed by the Python pinout generators.
 *  This export includes ECU pins, mapping state, allocation summaries, and connector
 *  summaries used by the physical HTML generation scripts.
 *  @param arch Architecture to serialize.
 *  @param filename Output JSON file path.
 *  @return 0 on success, -1 on invalid input or file creation failure.
 */
int EEC_Export_physical_architecture_json(const EEC_Architecture_t *arch, const char *filename);

/** @brief Emit a minimal HTML file that points users to the shipped full-pinout templates.
 *  @param filename Output HTML file path.
 *  @param ecu_name ECU name shown in the generated document.
 *  @param variant ECU variant label shown in the generated document.
 *  @return 0 on success, -1 on invalid input or file creation failure.
 */
int EEC_Export_full_pinout_template_html(const char *filename, const char *ecu_name, const char *variant);

#ifdef __cplusplus
}
#endif
#endif
