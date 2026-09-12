/*
 * @file    EEC_naming.c
 * @brief   E/E Architect Design — Signal naming convention implementation.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#include "EEC_naming.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

/* ─────────────────────────────────────────────────────────────────────────── */
/* System Code Mapping Tables                                                   */
/* ─────────────────────────────────────────────────────────────────────────── */

static const struct {
    const char *system_name;
    EEC_SystemCode_t code;
    const char *code_str;
    const char *meaning;
} SYSTEM_CODES[] = {
    { "Rear_Hydraulic_Hitch_System",              EEC_SYSTEM_CODE_RHIT, "RHIT", "Rear Hitch" },
    { "HYDAC_Selected_Sensor_Examples",           EEC_SYSTEM_CODE_HYDD, "HYDD", "Hydraulics Distribution" },
    { "BRAKE_SYSTEM",                             EEC_SYSTEM_CODE_BRK,  "BRK",  "Brake System" },
    { "Example_System_with_Bosch_Rexroth_Coil_Actuators", EEC_SYSTEM_CODE_BREX, "BREX", "Rexroth Coils" },
    { "Example_HYDAC_Coil_Topologies_System",     EEC_SYSTEM_CODE_COIL, "COIL", "Hydraulic Coils" },
    { "Example_System_with_selected_elobau_angle_sensors", EEC_SYSTEM_CODE_ELB, "ELB", "Elobau Sensors" },
};
static const size_t SYSTEM_CODES_COUNT = sizeof(SYSTEM_CODES) / sizeof(SYSTEM_CODES[0]);

static const struct {
    EEC_TypeCode_t code;
    const char *code_str;
    const char *meaning;
} TYPE_CODES[] = {
    { EEC_TYPE_CODE_SNSR,  "SNSR", "Sensor signal" },
    { EEC_TYPE_CODE_SWT,   "SWT",  "Switch signal" },
    { EEC_TYPE_CODE_PWR,   "PWR",  "Power supply rail" },
    { EEC_TYPE_CODE_GND,   "GND",  "Ground / return" },
    { EEC_TYPE_CODE_CAN,   "CAN",  "CAN Bus signal" },
    { EEC_TYPE_CODE_LIN,   "LIN",  "LIN Bus signal" },
    { EEC_TYPE_CODE_CMD,   "CMD",  "Command signal" },
    { EEC_TYPE_CODE_AI,    "AI",   "Analog/Current input" },
};
static const size_t TYPE_CODES_COUNT = sizeof(TYPE_CODES) / sizeof(TYPE_CODES[0]);

/* ─────────────────────────────────────────────────────────────────────────── */
/* System Code Functions                                                        */
/* ─────────────────────────────────────────────────────────────────────────── */

EEC_SystemCode_t EEC_GetSystemCode(const char *system_name)
{
    if (!system_name || !system_name[0]) {
        return EEC_SYSTEM_CODE_UNKNOWN;
    }

    for (size_t i = 0; i < SYSTEM_CODES_COUNT; ++i) {
        if (strcmp(SYSTEM_CODES[i].system_name, system_name) == 0) {
            return SYSTEM_CODES[i].code;
        }
    }
    return EEC_SYSTEM_CODE_UNKNOWN;
}

const char *EEC_SystemCodeString(EEC_SystemCode_t code)
{
    for (size_t i = 0; i < SYSTEM_CODES_COUNT; ++i) {
        if (SYSTEM_CODES[i].code == code) {
            return SYSTEM_CODES[i].code_str;
        }
    }
    return "UNKN";
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Type Code Functions                                                          */
/* ─────────────────────────────────────────────────────────────────────────── */

EEC_TypeCode_t EEC_GetTypeCode(EEC_SignalInterface_t interface_type, EEC_PinRole_t role)
{
    switch (interface_type) {
        case EEC_SIGNAL_INTERFACE_POWER:
            return EEC_TYPE_CODE_PWR;
        case EEC_SIGNAL_INTERFACE_GROUND:
            return EEC_TYPE_CODE_GND;
        case EEC_SIGNAL_INTERFACE_CAN:
            return EEC_TYPE_CODE_CAN;
        case EEC_SIGNAL_INTERFACE_LIN:
            return EEC_TYPE_CODE_LIN;
        case EEC_SIGNAL_INTERFACE_ANALOG:
        case EEC_SIGNAL_INTERFACE_CURRENT:
            return (role == EEC_PIN_ROLE_INPUT) ? EEC_TYPE_CODE_SNSR : EEC_TYPE_CODE_AI;
        case EEC_SIGNAL_INTERFACE_DIGITAL:
            return (role == EEC_PIN_ROLE_INPUT) ? EEC_TYPE_CODE_SWT : EEC_TYPE_CODE_CMD;
        case EEC_SIGNAL_INTERFACE_PWM:
            return EEC_TYPE_CODE_CMD;
        default:
            return EEC_TYPE_CODE_UNKNOWN;
    }
}

const char *EEC_TypeCodeString(EEC_TypeCode_t code)
{
    for (size_t i = 0; i < TYPE_CODES_COUNT; ++i) {
        if (TYPE_CODES[i].code == code) {
            return TYPE_CODES[i].code_str;
        }
    }
    return "UNKN";
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Function Name Extraction                                                     */
/* ─────────────────────────────────────────────────────────────────────────── */

static int is_camel_case_boundary(char c1, char c2)
{
    return islower((unsigned char)c1) && isupper((unsigned char)c2);
}

static int extract_camel_case_parts(const char *str, char **parts, size_t max_parts)
{
    if (!str || !str[0] || !parts) return 0;

    size_t count = 0;
    size_t len = strlen(str);
    size_t start = 0;

    for (size_t i = 0; i < len && count < max_parts; ++i) {
        if ((i > 0 && is_camel_case_boundary(str[i-1], str[i])) || str[i] == '_') {
            if (i > start) {
                size_t part_len = i - start;
                char *part = malloc(part_len + 1);
                if (!part) return count;
                strncpy(part, &str[start], part_len);
                part[part_len] = '\0';
                parts[count++] = part;
            }
            start = (str[i] == '_') ? i + 1 : i;
        }
    }

    if (start < len && count < max_parts) {
        size_t part_len = len - start;
        char *part = malloc(part_len + 1);
        if (!part) return count;
        strncpy(part, &str[start], part_len);
        part[part_len] = '\0';
        parts[count++] = part;
    }

    return count;
}

int EEC_ExtractFunctionName(
    const char *original_signal,
    const char *device_name,
    char *function_name_out,
    size_t max_len)
{
    (void)device_name; /* reserved for future device-scoped naming */
    if (!original_signal || !function_name_out || max_len < 4) {
        return -1;
    }

    char *parts[16] = {0};
    int count = extract_camel_case_parts(original_signal, parts, 16);

    if (count < 2) {
        strncpy(function_name_out, original_signal, max_len - 1);
        function_name_out[max_len - 1] = '\0';
        goto cleanup;
    }

    /* Skip first part (usually device identifier) and last part (usually interface type) */
    if (count >= 3) {
        strncpy(function_name_out, parts[1], max_len - 1);
        function_name_out[max_len - 1] = '\0';
    } else if (count == 2) {
        strncpy(function_name_out, parts[0], max_len - 1);
        function_name_out[max_len - 1] = '\0';
    } else {
        strncpy(function_name_out, original_signal, max_len - 1);
        function_name_out[max_len - 1] = '\0';
    }

cleanup:
    for (int i = 0; i < count; ++i) {
        free(parts[i]);
    }

    return 0;
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Position Index Extraction                                                    */
/* ─────────────────────────────────────────────────────────────────────────── */

int EEC_ExtractPositionIndex(
    const char *original_signal,
    char *position_out,
    size_t max_len)
{
    if (!original_signal || !position_out || max_len < 1) {
        return -1;
    }

    position_out[0] = '\0';

    size_t len = strlen(original_signal);
    int last_digit_start = -1;
    int last_digit_len = 0;

    for (size_t i = len; i > 0; --i) {
        if (isdigit((unsigned char)original_signal[i-1])) {
            if (last_digit_start == -1) {
                last_digit_start = i - 1;
            }
            last_digit_len++;
        } else if (last_digit_start != -1) {
            break;
        }
    }

    if (last_digit_start != -1 && last_digit_len <= 2 && last_digit_len <= (int)(max_len - 1)) {
        strncpy(position_out, &original_signal[last_digit_start], last_digit_len);
        position_out[last_digit_len] = '\0';
    }

    return 0;
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Full Clean Name Generation                                                   */
/* ─────────────────────────────────────────────────────────────────────────── */

int EEC_GenerateCleanSignalNameEx(EEC_Signal_t *signal, const char *system_name, EEC_PinRole_t role)
{
    if (!signal) {
        return -1;
    }

    EEC_SystemCode_t sys_code = system_name ? EEC_GetSystemCode(system_name) : EEC_SYSTEM_CODE_UNKNOWN;
    EEC_TypeCode_t type_code = EEC_GetTypeCode(signal->interface_type, role);

    strncpy(signal->system_code, EEC_SystemCodeString(sys_code), sizeof(signal->system_code) - 1);
    signal->system_code[sizeof(signal->system_code) - 1] = '\0';

    if (EEC_ExtractFunctionName(signal->name, NULL, signal->function_name, sizeof(signal->function_name)) != 0) {
        return -1;
    }

    if (EEC_ExtractPositionIndex(signal->name, signal->position_index, sizeof(signal->position_index)) != 0) {
        return -1;
    }

    strncpy(signal->type_code, EEC_TypeCodeString(type_code), sizeof(signal->type_code) - 1);
    signal->type_code[sizeof(signal->type_code) - 1] = '\0';

    /* Build full clean name: SYSTEM_Function_[POSITION_]TYPE */
    char temp[128] = {0};
    if (signal->position_index[0] != '\0') {
        snprintf(temp, sizeof(temp), "%s_%s_%s_%s",
                 signal->system_code,
                 signal->function_name,
                 signal->position_index,
                 signal->type_code);
    } else {
        snprintf(temp, sizeof(temp), "%s_%s_%s",
                 signal->system_code,
                 signal->function_name,
                 signal->type_code);
    }

    strncpy(signal->clean_signal_name, temp, sizeof(signal->clean_signal_name) - 1);
    signal->clean_signal_name[sizeof(signal->clean_signal_name) - 1] = '\0';
    signal->is_auto_named = 1;

    return 0;
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Validation                                                                   */
/* ─────────────────────────────────────────────────────────────────────────── */

int EEC_ValidateSignalNaming(
    const EEC_Signal_t *signal,
    char *reason_out,
    size_t max_reason_len)
{
    if (!signal) {
        if (reason_out && max_reason_len > 0) {
            strncpy(reason_out, "NULL signal", max_reason_len - 1);
            reason_out[max_reason_len - 1] = '\0';
        }
        return -1;
    }

    if (!signal->clean_signal_name[0]) {
        if (reason_out && max_reason_len > 0) {
            strncpy(reason_out, "No clean_signal_name generated", max_reason_len - 1);
            reason_out[max_reason_len - 1] = '\0';
        }
        return -1;
    }

    if (!signal->system_code[0] || !signal->function_name[0] || !signal->type_code[0]) {
        if (reason_out && max_reason_len > 0) {
            strncpy(reason_out, "Incomplete naming components (system, function, or type missing)", max_reason_len - 1);
            reason_out[max_reason_len - 1] = '\0';
        }
        return -1;
    }

    if (reason_out && max_reason_len > 0) {
        strncpy(reason_out, "Compliant with SYSTEM_Function_[POSITION_]TYPE", max_reason_len - 1);
        reason_out[max_reason_len - 1] = '\0';
    }

    return 0;
}

int EEC_CountCompliantSignals(const EEC_Architecture_t *arch)
{
    if (!arch) {
        return -1;
    }

    int compliant_count = 0;
    for (uint32_t i = 0; i < arch->signal_count; ++i) {
        if (arch->signals[i] && EEC_ValidateSignalNaming(arch->signals[i], NULL, 0) == 0) {
            compliant_count++;
        }
    }

    return compliant_count;
}
