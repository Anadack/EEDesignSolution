/**
 * @file    EEC_datadict.h
 * @brief   E/E Architect Design — Data dictionary export (logical + physical
 *          signals grouped per module / system).
 * @author  Anadack Temtching Dassi
 * @date    2026
 *
 * The data dictionary lists, for every system (module), each of its signals
 * with both:
 *   - its LOGICAL definition (type, interface, unit, range, safety, priority),
 *   - its PHYSICAL realisation (ECU pin: connector, pin number, role, interface)
 *     for device signals, or its CAN transport (message, frame id, bus) for
 *     software variables produced by the system's SWCs.
 */
#ifndef EEC_DATADICT_H
#define EEC_DATADICT_H

#include "EEC_architecture.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @brief Export the data dictionary as a structured JSON document.
 *  @param arch Architecture to describe.
 *  @param filename Output JSON path.
 *  @return Number of signal rows written, or -1 on invalid input or file failure.
 */
int EEC_Export_data_dictionary_json(const EEC_Architecture_t *arch, const char *filename);

/** @brief Export the data dictionary as a flat CSV table.
 *  @param arch Architecture to describe.
 *  @param filename Output CSV path.
 *  @return Number of signal rows written, or -1 on invalid input or file failure.
 */
int EEC_Export_data_dictionary_csv(const EEC_Architecture_t *arch, const char *filename);

/** @brief Export the data dictionary as a self-contained HTML document.
 *  @param arch Architecture to describe.
 *  @param filename Output HTML path.
 *  @return Number of signal rows written, or -1 on invalid input or file failure.
 */
int EEC_Export_data_dictionary_html(const EEC_Architecture_t *arch, const char *filename);

#ifdef __cplusplus
}
#endif
#endif
