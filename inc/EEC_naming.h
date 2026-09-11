/**
 * @file    EEC_naming.h
 * @brief   E/E Architect Design — Signal naming convention (SYSTEM_Function_[POSITION_]TYPE).
 * @author  Anadack Temtching Dassi
 * @date    2026
 *
 * Provides automated signal naming following the convention:
 *   SYSTEM_Function_[POSITION_]TYPE
 *
 * Example: HYDD_AnglPosn01_SNSR
 *   HYDD = Hydraulics Distribution (system code)
 *   AnglPosn = Angle Position (function)
 *   01 = Optional position index
 *   SNSR = Sensor (type code)
 *
 * Supports:
 * - Automatic system code mapping (device system → HYDD, BRK, RHIT, etc.)
 * - Type code extraction from interface + role
 * - Function name parsing from original signal names
 * - Position index extraction
 * - Full clean name generation
 * - Compliance validation
 */
#ifndef EEC_NAMING_H
#define EEC_NAMING_H

#include <stddef.h>
#include "EEC_architecture.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ─────────────────────────────────────────────────────────────────────────── */
/* System Code Enumeration                                                      */
/* ─────────────────────────────────────────────────────────────────────────── */

/** @brief System code abbreviations for signal naming convention. */
typedef enum EEC_SystemCode_e {
    EEC_SYSTEM_CODE_HYDD = 0,    /**< Hydraulics Distribution */
    EEC_SYSTEM_CODE_BRK,          /**< Brake System */
    EEC_SYSTEM_CODE_RHIT,         /**< Rear Hitch */
    EEC_SYSTEM_CODE_BREX,         /**< Rexroth Coils */
    EEC_SYSTEM_CODE_COIL,         /**< Hydraulic Coils */
    EEC_SYSTEM_CODE_ELB,          /**< Elobau Sensors */
    EEC_SYSTEM_CODE_UNKNOWN       /**< Unknown or custom system */
} EEC_SystemCode_t;

/* ─────────────────────────────────────────────────────────────────────────── */
/* Type Code Enumeration                                                        */
/* ─────────────────────────────────────────────────────────────────────────── */

/** @brief Type codes for the final segment of signal names. */
typedef enum EEC_TypeCode_e {
    EEC_TYPE_CODE_SNSR = 0,      /**< Sensor signal */
    EEC_TYPE_CODE_SWT,            /**< Switch signal */
    EEC_TYPE_CODE_PWR,            /**< Power supply rail */
    EEC_TYPE_CODE_GND,            /**< Ground / return */
    EEC_TYPE_CODE_CAN,            /**< CAN Bus signal */
    EEC_TYPE_CODE_LIN,            /**< LIN Bus signal */
    EEC_TYPE_CODE_CMD,            /**< Command signal (PWM, etc.) */
    EEC_TYPE_CODE_AI,             /**< Analog/Current input */
    EEC_TYPE_CODE_UNKNOWN         /**< Unknown type */
} EEC_TypeCode_t;

/* ─────────────────────────────────────────────────────────────────────────── */
/* System Code Mapping API                                                      */
/* ─────────────────────────────────────────────────────────────────────────── */

/**
 * @brief Map a system name to its standardized system code.
 *
 * Maps full system names (e.g., "Rear_Hydraulic_Hitch_System") to
 * abbreviated codes (e.g., "RHIT").
 *
 * @param system_name  The system name from the architecture.
 * @return System code enumeration value.
 */
EEC_SystemCode_t EEC_GetSystemCode(const char *system_name);

/**
 * @brief Convert system code enum to string (e.g., EEC_SYSTEM_CODE_HYDD → "HYDD").
 *
 * @param code System code enumeration value.
 * @return Pointer to static string (do not free). Returns "UNKN" for invalid codes.
 */
const char *EEC_SystemCodeString(EEC_SystemCode_t code);

/* ─────────────────────────────────────────────────────────────────────────── */
/* Type Code Mapping API                                                        */
/* ─────────────────────────────────────────────────────────────────────────── */

/**
 * @brief Map interface type and role to a standardized type code.
 *
 * Combines interface (ANALOG, DIGITAL, CAN, POWER, GROUND, etc.)
 * and role (INPUT, OUTPUT, SUPPLY, GROUND, etc.) to produce
 * a type code (SNSR, SWT, PWR, GND, CAN, CMD, AI, etc.).
 *
 * @param interface_type  Signal interface type from architecture.
 * @param role            Signal role (INPUT, OUTPUT, SUPPLY, GROUND, INOUT).
 * @return Type code enumeration value.
 */
EEC_TypeCode_t EEC_GetTypeCode(EEC_SignalInterface_t interface_type, EEC_PinRole_t role);

/**
 * @brief Convert type code enum to string (e.g., EEC_TYPE_CODE_SNSR → "SNSR").
 *
 * @param code Type code enumeration value.
 * @return Pointer to static string. Returns "UNKN" for invalid codes.
 */
const char *EEC_TypeCodeString(EEC_TypeCode_t code);

/* ─────────────────────────────────────────────────────────────────────────── */
/* Function Name Extraction API                                                 */
/* ─────────────────────────────────────────────────────────────────────────── */

/**
 * @brief Extract a clean function name from an original signal name.
 *
 * Uses heuristics and pattern matching to extract meaningful function
 * names from raw signal identifiers. Examples:
 *   "HAT1200_Angle_4_20mA" → "AnglPosn"
 *   "EDS410_OUT1_PNP" → "PressSwitch"
 *   "HDA4300_Pressure_0_10V" → "PressMonit"
 *
 * @param original_signal    The original signal name from the architecture.
 * @param device_name        Optional device name for context (may be NULL).
 * @param function_name_out  Output buffer for the extracted function name.
 * @param max_len            Maximum size of function_name_out (should be ≥32).
 * @return 0 on success, -1 on error (insufficient buffer, NULL input).
 */
int EEC_ExtractFunctionName(
    const char *original_signal,
    const char *device_name,
    char *function_name_out,
    size_t max_len);

/* ─────────────────────────────────────────────────────────────────────────── */
/* Position Index Extraction API                                                */
/* ─────────────────────────────────────────────────────────────────────────── */

/**
 * @brief Extract a position index from an original signal name.
 *
 * Searches for numeric suffixes in signal names. Examples:
 *   "HAT1200_01" → "01"
 *   "EDS410_OUT1" → "01"
 *   "HAT1200" → "" (empty, no position)
 *
 * @param original_signal   The original signal name.
 * @param position_out      Output buffer for position index (e.g., "01", "02").
 * @param max_len           Maximum size of position_out (should be ≥8).
 * @return 0 on success, -1 on error. If no position found, position_out is empty string.
 */
int EEC_ExtractPositionIndex(
    const char *original_signal,
    char *position_out,
    size_t max_len);

/* ─────────────────────────────────────────────────────────────────────────── */
/* Full Clean Name Generation API                                               */
/* ─────────────────────────────────────────────────────────────────────────── */

/**
 * @brief Generate a full clean signal name following SYSTEM_Function_[POSITION_]TYPE.
 *
 * Combines system code, function name, optional position, and type code
 * into a standardized signal name. Also populates signal structure fields.
 *
 * @param signal       Pointer to signal structure (will be populated with naming fields).
 * @param system_name  Optional system name for code mapping (may be NULL to skip system code).
 * @param role         Pin role used for type code determination (INPUT, OUTPUT, SUPPLY, GROUND, etc.).
 * @return 0 on success, -1 on error (NULL pointer, invalid data).
 */
int EEC_GenerateCleanSignalNameEx(EEC_Signal_t *signal, const char *system_name, EEC_PinRole_t role);

/* ─────────────────────────────────────────────────────────────────────────── */
/* Validation API                                                               */
/* ─────────────────────────────────────────────────────────────────────────── */

/**
 * @brief Validate a signal's naming convention compliance.
 *
 * Checks if a signal's clean_signal_name follows the SYSTEM_Function_[POSITION_]TYPE
 * pattern. Optionally returns detailed reason for non-compliance.
 *
 * @param signal        Pointer to signal to validate.
 * @param reason_out    Optional output buffer for compliance reason (may be NULL).
 * @param max_reason_len Maximum size of reason_out.
 * @return 0 if compliant, -1 if non-compliant.
 */
int EEC_ValidateSignalNaming(
    const EEC_Signal_t *signal,
    char *reason_out,
    size_t max_reason_len);

/**
 * @brief Count how many signals in an architecture comply with naming convention.
 *
 * @param arch  Architecture to audit.
 * @return Number of compliant signals. Returns -1 on error.
 */
int EEC_CountCompliantSignals(const EEC_Architecture_t *arch);

#ifdef __cplusplus
}
#endif
#endif /* EEC_NAMING_H */
