/**
 * @file    EEC_dbc.h
 * @brief   E/E Architect Design — CAN DBC (Vector) import/export.
 * @author  Anadack Temtching Dassi
 * @date    2026
 *
 * One DBC file corresponds to one CAN network (bus). Export walks every SWC
 * message that has a transmit binding on the target bus and emits the standard
 * BU_ / BO_ / SG_ records. Import parses BO_ / SG_ records into messages owned
 * by a given SWC.
 */
#ifndef EEC_DBC_H
#define EEC_DBC_H

#include "EEC_architecture.h"
#include <stdio.h>

#ifdef __cplusplus
extern "C" {
#endif

/** @brief Export one bus to a Vector-compatible .dbc file.
 *  @param arch     Owning architecture.
 *  @param bus      Bus whose messages are exported.
 *  @param filename Output .dbc path.
 *  @return Number of messages written, or -1 on invalid input or file failure.
 */
int EEC_Export_dbc_bus(const EEC_Architecture_t *arch, const EEC_Bus_t *bus,
                       const char *filename);

/** @brief Export every CAN/ISOBUS bus to <dir>/<bus_name>.dbc.
 *  @param arch Owning architecture.
 *  @param dir  Output directory (must exist).
 *  @return Number of DBC files written, or -1 on invalid input.
 */
int EEC_Export_dbc_all(const EEC_Architecture_t *arch, const char *dir);

/**
 *  @brief Validate the DBC that would be exported for one CAN/ISOBUS bus and
 *         report DBC-level errors (frame overflow, signal overlap, duplicate
 *         frame-id, duplicate signal name, DLC range, zero length, min>max,
 *         node-not-in-BU_). Returns the number of errors, or -1 on bad input.
 */
int EEC_Dbc_Validate_bus(const EEC_Architecture_t *arch, const EEC_Bus_t *bus,
                         FILE *report);

/**
 *  @brief Validate every CAN/ISOBUS bus's DBC. Returns total error count.
 */
int EEC_Dbc_Validate_all(const EEC_Architecture_t *arch, FILE *report);

/** @brief Import BO_/SG_ records from a .dbc file into messages owned by a SWC.
 *  Referenced signals are created in the architecture with a CAN interface.
 *  @param arch     Owning architecture (receives new signals).
 *  @param swc      SWC that will own the imported messages.
 *  @param filename Input .dbc path.
 *  @return Number of messages imported, or -1 on invalid input or file failure.
 */
int EEC_Import_dbc(EEC_Architecture_t *arch, EEC_Swc_t *swc, const char *filename);

#ifdef __cplusplus
}
#endif
#endif
