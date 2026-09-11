/*
 * @file    test_naming_convention.c
 * @brief   Unit tests for signal naming convention (EEC_naming.c).
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "../inc/EEC_naming.h"
#include "../inc/EEC_architecture.h"

static int test_count = 0;
static int test_passed = 0;

#define TEST(name) void test_##name(void); \
    do { \
        test_count++; \
        printf("[TEST %d] %s ... ", test_count, #name); \
        fflush(stdout); \
        test_##name(); \
        printf("PASS\n"); \
        test_passed++; \
    } while (0)

#define ASSERT(cond, msg) \
    if (!(cond)) { \
        printf("FAIL: %s\n", msg); \
        exit(1); \
    }

/* ─────────────────────────────────────────────────────────────────────────── */
/* Test: System Code Mapping                                                    */
/* ─────────────────────────────────────────────────────────────────────────── */

void test_system_code_rhit(void)
{
    EEC_SystemCode_t code = EEC_GetSystemCode("Rear_Hydraulic_Hitch_System");
    ASSERT(code == EEC_SYSTEM_CODE_RHIT, "Expected RHIT code");
    ASSERT(strcmp(EEC_SystemCodeString(code), "RHIT") == 0, "Expected 'RHIT' string");
}

void test_system_code_brake(void)
{
    EEC_SystemCode_t code = EEC_GetSystemCode("BRAKE_SYSTEM");
    ASSERT(code == EEC_SYSTEM_CODE_BRK, "Expected BRK code");
    ASSERT(strcmp(EEC_SystemCodeString(code), "BRK") == 0, "Expected 'BRK' string");
}

void test_system_code_unknown(void)
{
    EEC_SystemCode_t code = EEC_GetSystemCode("Unknown_System");
    ASSERT(code == EEC_SYSTEM_CODE_UNKNOWN, "Expected UNKNOWN code");
    ASSERT(strcmp(EEC_SystemCodeString(code), "UNKN") == 0, "Expected 'UNKN' string");
}

void test_system_code_null(void)
{
    EEC_SystemCode_t code = EEC_GetSystemCode(NULL);
    ASSERT(code == EEC_SYSTEM_CODE_UNKNOWN, "Expected UNKNOWN for NULL input");
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Test: Type Code Mapping                                                      */
/* ─────────────────────────────────────────────────────────────────────────── */

void test_type_code_power(void)
{
    EEC_TypeCode_t code = EEC_GetTypeCode(EEC_SIGNAL_INTERFACE_POWER, EEC_PIN_ROLE_SUPPLY);
    ASSERT(code == EEC_TYPE_CODE_PWR, "Expected PWR code");
    ASSERT(strcmp(EEC_TypeCodeString(code), "PWR") == 0, "Expected 'PWR' string");
}

void test_type_code_ground(void)
{
    EEC_TypeCode_t code = EEC_GetTypeCode(EEC_SIGNAL_INTERFACE_GROUND, EEC_PIN_ROLE_GROUND);
    ASSERT(code == EEC_TYPE_CODE_GND, "Expected GND code");
    ASSERT(strcmp(EEC_TypeCodeString(code), "GND") == 0, "Expected 'GND' string");
}

void test_type_code_analog_input(void)
{
    EEC_TypeCode_t code = EEC_GetTypeCode(EEC_SIGNAL_INTERFACE_ANALOG, EEC_PIN_ROLE_INPUT);
    ASSERT(code == EEC_TYPE_CODE_SNSR, "Expected SNSR code for analog input");
}

void test_type_code_can(void)
{
    EEC_TypeCode_t code = EEC_GetTypeCode(EEC_SIGNAL_INTERFACE_CAN, EEC_PIN_ROLE_INOUT);
    ASSERT(code == EEC_TYPE_CODE_CAN, "Expected CAN code");
    ASSERT(strcmp(EEC_TypeCodeString(code), "CAN") == 0, "Expected 'CAN' string");
}

void test_type_code_pwm_cmd(void)
{
    EEC_TypeCode_t code = EEC_GetTypeCode(EEC_SIGNAL_INTERFACE_PWM, EEC_PIN_ROLE_OUTPUT);
    ASSERT(code == EEC_TYPE_CODE_CMD, "Expected CMD code for PWM output");
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Test: Function Name Extraction                                               */
/* ─────────────────────────────────────────────────────────────────────────── */

void test_function_extraction_hat1200(void)
{
    char function[32] = {0};
    int ret = EEC_ExtractFunctionName("HAT1200_Angle_4_20mA", NULL, function, sizeof(function));
    ASSERT(ret == 0, "Function extraction should succeed");
    ASSERT(strlen(function) > 0, "Function name should not be empty");
}

void test_function_extraction_eds410(void)
{
    char function[32] = {0};
    int ret = EEC_ExtractFunctionName("EDS410_OUT1_PNP", NULL, function, sizeof(function));
    ASSERT(ret == 0, "Function extraction should succeed");
    ASSERT(strlen(function) > 0, "Function name should not be empty");
}

void test_function_extraction_null_input(void)
{
    char function[32] = {0};
    int ret = EEC_ExtractFunctionName(NULL, NULL, function, sizeof(function));
    ASSERT(ret != 0, "Should fail with NULL input");
}

void test_function_extraction_small_buffer(void)
{
    char function[2] = {0};
    int ret = EEC_ExtractFunctionName("HAT1200_Angle", NULL, function, sizeof(function));
    ASSERT(ret != 0, "Should fail with insufficient buffer");
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Test: Position Index Extraction                                              */
/* ─────────────────────────────────────────────────────────────────────────── */

void test_position_extraction_hat1200(void)
{
    char position[8] = {0};
    int ret = EEC_ExtractPositionIndex("HAT1200_01", position, sizeof(position));
    ASSERT(ret == 0, "Position extraction should succeed");
}

void test_position_extraction_no_position(void)
{
    char position[8] = {0};
    int ret = EEC_ExtractPositionIndex("HAT1200", position, sizeof(position));
    ASSERT(ret == 0, "Position extraction should succeed");
    ASSERT(position[0] == '\0', "No position should return empty string");
}

void test_position_extraction_eds410(void)
{
    char position[8] = {0};
    int ret = EEC_ExtractPositionIndex("EDS410_OUT1", position, sizeof(position));
    ASSERT(ret == 0, "Position extraction should succeed");
}

void test_position_extraction_null_input(void)
{
    char position[8] = {0};
    int ret = EEC_ExtractPositionIndex(NULL, position, sizeof(position));
    ASSERT(ret != 0, "Should fail with NULL input");
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Test: Full Clean Name Generation                                             */
/* ─────────────────────────────────────────────────────────────────────────── */

void test_clean_name_generation(void)
{
    EEC_Signal_t sig = {0};
    strncpy(sig.name, "HAT1200_Angle_4_20mA", sizeof(sig.name) - 1);
    sig.interface_type = EEC_SIGNAL_INTERFACE_CURRENT;

    int ret = EEC_GenerateCleanSignalNameEx(&sig, NULL, EEC_PIN_ROLE_INPUT);
    ASSERT(ret == 0, "Clean name generation should succeed");
    ASSERT(strlen(sig.clean_signal_name) > 0, "Clean signal name should not be empty");
    ASSERT(sig.is_auto_named, "Signal should be marked as auto-named");
    ASSERT(strlen(sig.function_name) > 0, "Function name should be populated");
    ASSERT(strlen(sig.type_code) > 0, "Type code should be populated");
}

void test_clean_name_generation_null(void)
{
    int ret = EEC_GenerateCleanSignalNameEx(NULL, NULL, EEC_PIN_ROLE_INPUT);
    ASSERT(ret != 0, "Should fail with NULL signal");
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Test: Validation                                                             */
/* ─────────────────────────────────────────────────────────────────────────── */

void test_validate_compliant_signal(void)
{
    EEC_Signal_t sig = {0};
    strncpy(sig.name, "HAT1200_Angle_4_20mA", sizeof(sig.name) - 1);
    sig.interface_type = EEC_SIGNAL_INTERFACE_CURRENT;

    EEC_GenerateCleanSignalNameEx(&sig, NULL, EEC_PIN_ROLE_INPUT);

    char reason[128] = {0};
    int ret = EEC_ValidateSignalNaming(&sig, reason, sizeof(reason));
    ASSERT(ret == 0, "Compliant signal should validate");
    ASSERT(strlen(reason) > 0, "Validation reason should be populated");
}

void test_validate_null_signal(void)
{
    char reason[128] = {0};
    int ret = EEC_ValidateSignalNaming(NULL, reason, sizeof(reason));
    ASSERT(ret != 0, "NULL signal should not validate");
    ASSERT(strlen(reason) > 0, "Reason should be populated even on failure");
}

void test_validate_incomplete_signal(void)
{
    EEC_Signal_t sig = {0};
    sig.clean_signal_name[0] = '\0';

    int ret = EEC_ValidateSignalNaming(&sig, NULL, 0);
    ASSERT(ret != 0, "Signal without clean_signal_name should not validate");
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Main Test Runner                                                             */
/* ─────────────────────────────────────────────────────────────────────────── */

int main(void)
{
    printf("\n════════════════════════════════════════════════════════════════\n");
    printf("  Signal Naming Convention Unit Tests (EEC_naming.c)\n");
    printf("════════════════════════════════════════════════════════════════\n\n");

    /* System Code Tests */
    printf("▶ System Code Mapping\n");
    TEST(system_code_rhit);
    TEST(system_code_brake);
    TEST(system_code_unknown);
    TEST(system_code_null);

    /* Type Code Tests */
    printf("\n▶ Type Code Mapping\n");
    TEST(type_code_power);
    TEST(type_code_ground);
    TEST(type_code_analog_input);
    TEST(type_code_can);
    TEST(type_code_pwm_cmd);

    /* Function Extraction Tests */
    printf("\n▶ Function Name Extraction\n");
    TEST(function_extraction_hat1200);
    TEST(function_extraction_eds410);
    TEST(function_extraction_null_input);
    TEST(function_extraction_small_buffer);

    /* Position Extraction Tests */
    printf("\n▶ Position Index Extraction\n");
    TEST(position_extraction_hat1200);
    TEST(position_extraction_no_position);
    TEST(position_extraction_eds410);
    TEST(position_extraction_null_input);

    /* Clean Name Generation Tests */
    printf("\n▶ Full Clean Name Generation\n");
    TEST(clean_name_generation);
    TEST(clean_name_generation_null);

    /* Validation Tests */
    printf("\n▶ Validation\n");
    TEST(validate_compliant_signal);
    TEST(validate_null_signal);
    TEST(validate_incomplete_signal);

    /* Summary */
    printf("\n════════════════════════════════════════════════════════════════\n");
    printf("Results: %d/%d tests passed\n", test_passed, test_count);
    printf("════════════════════════════════════════════════════════════════\n\n");

    if (test_passed == test_count) {
        printf("✓ All tests passed!\n\n");
        return 0;
    } else {
        printf("✗ Some tests failed.\n\n");
        return 1;
    }
}
