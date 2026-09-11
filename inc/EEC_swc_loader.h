/**
 * @file    EEC_swc_loader.h
 * @brief   E/E Architect Design — Data-driven SWC / CAN message importer.
 * @author  Anadack Temtching Dassi
 * @date    2026
 *
 * Loads software components (SWCs), their software variables, and the CAN
 * messages they publish from a JSON data file — so the whole CAN topology is
 * driven by data, not code. Signal bit layout inside a frame is auto-derived
 * from each signal's type when not given explicitly, so adding or changing a
 * variable automatically reflows the message (and every downstream export:
 * data dictionary, DBC, verification).
 */
#ifndef EEC_SWC_LOADER_H
#define EEC_SWC_LOADER_H

#include "EEC_architecture.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @brief Import SWCs, variables and CAN messages from a JSON data file.
 *
 *  Systems, ECUs and buses are resolved by name against the architecture
 *  (a referenced system is created if missing). Message signals are auto-packed
 *  by bit width unless explicit start_bit/length are provided.
 *
 *  @param arch     Architecture receiving the SWCs (must already hold the ECUs
 *                  and buses referenced by name).
 *  @param filename Path to the .swc.json data file.
 *  @return Number of SWCs imported, or -1 on invalid input or file failure.
 */
int EEC_Import_swc_json(EEC_Architecture_t *arch, const char *filename);

#ifdef __cplusplus
}
#endif
#endif
