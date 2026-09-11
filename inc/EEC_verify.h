/**
 * @file    EEC_verify.h
 * @brief   E/E Architect Design — Architecture verification and reporting.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#ifndef EEC_VERIFY_H
#define EEC_VERIFY_H

#include "EEC_architecture.h"
#include <stdio.h>

#ifdef __cplusplus
extern "C" {
#endif

/** @brief Verify architecture consistency and write a human-readable report.
 *  @param arch Architecture to verify.
 *  @param report Output stream receiving the verification report.
 *  @return Number of detected errors, or -1 on invalid input.
 */
int EEC_Verify_architecture(const EEC_Architecture_t *arch, FILE *report);

/** @brief Verify CAN message / SWC coherence (C1-C5) and write a report section.
 *  Checks: every message has a tx port (C1); tx ECU matches SWC allocation and has a
 *  bus (C2); every entry references a signal (C3); signals fit the frame with no bit
 *  overlap (C4); frame_id is unique per bus (C5).
 *  @param arch Architecture to verify.
 *  @param report Output stream receiving the CAN verification section.
 *  @return Number of detected errors, or -1 on invalid input.
 */
int EEC_Verify_can(const EEC_Architecture_t *arch, FILE *report);

/** @brief Write ECU pin allocation statistics for the architecture.
 *  The report includes per-ECU and global totals for total pins, allocated pins,
 *  free pins, and allocation percentage.
 *  @param arch Architecture to inspect.
 *  @param report Output stream receiving the allocation summary.
 *  @return 0 on success, -1 on invalid input.
 */
int EEC_Report_pin_allocation(const EEC_Architecture_t *arch, FILE *report);

#ifdef __cplusplus
}
#endif
#endif
