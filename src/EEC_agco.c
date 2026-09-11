/**
 * @file    EEC_agco.c
 * @brief   E/E Architect Design — AGCO ECU factory implementation.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#include "EEC_agco.h"
#include "EEC_log.h"
#include <stdarg.h>
#include <string.h>
#include <stdio.h>
#include "EEC_pin_helpers.h"

/** @brief One static pin template used to instantiate a pre-filled physical pin. */
typedef struct EEC_PinTemplate_s {
    const char *connector;       /**< Connector name. */
    uint32_t pin;                /**< Physical cavity number. */
    const char *name;            /**< Default pin name. */
    const char *group;           /**< Main I/O group. */
    EEC_PinRole_t role;           /**< Physical role. */
    uint32_t capability_mask;    /**< Supported capability mask. */
    uint32_t diagnostic_flags;   /**< Supported diagnostics. */
    const char *electrical;      /**< Default electrical description. */
    const char *sw_config;       /**< Default software configuration text. */
    const char *functions[5];    /**< Alternative group or function tags. */
} EEC_PinTemplate_t;

/** @brief Shared I/O group descriptors.
 *  These descriptors are based on the AGCO group definitions used in the HTML templates.
 */
typedef struct EEC_GroupSpec_s {
    const char *key;
    const char *prefix;
    const char *group;
    const char *alt;
    EEC_SignalInterface_t interface_type;
    EEC_PinRole_t role;
    uint32_t diag;
    uint32_t elec_cap;
    const char *electrical;
    const char *sw_config;
} EEC_GroupSpec_t;

static const EEC_GroupSpec_t G_GROUPS[] = {
    {"SUPPLY", "SUPPLY", "SUPPLY", "", EEC_SIGNAL_INTERFACE_POWER, EEC_PIN_ROLE_SUPPLY, 0U, 0U, "Battery / sensor supply | Protected supply line", "Enable"},
    {"GROUND", "GND", "GROUND", "", EEC_SIGNAL_INTERFACE_GROUND, EEC_PIN_ROLE_GROUND, 0U, 0U, "Chassis / signal ground | Low impedance return", ""},
    {"DO_HS_HC", "OUT_DO_HS_HC", "DO_HS_HC", "", EEC_SIGNAL_INTERFACE_DIGITAL, EEC_PIN_ROLE_OUTPUT, EEC_DIAG_OPEN_LOAD|EEC_DIAG_SHORT_GND|EEC_DIAG_SHORT_BAT|EEC_DIAG_OVERCURRENT, EEC_ELEC_HIGH_SIDE|EEC_ELEC_PUSH_PULL, "0..14 V | Static high-side · 4.5 A nominal", "Drive Strength"},
    {"PWM_HS_HC", "OUT_PWM_HS_HC", "PWM_HS_HC", "DO_HS_HC", EEC_SIGNAL_INTERFACE_PWM, EEC_PIN_ROLE_OUTPUT, EEC_DIAG_OPEN_LOAD|EEC_DIAG_OVERCURRENT|EEC_DIAG_THERMAL_WARN, EEC_ELEC_HIGH_SIDE|EEC_ELEC_PUSH_PULL, "0..14 V | 40 Hz .. 500 Hz · High-side", "Drive Strength|PWM Freq"},
    {"PWM_LS_HC", "OUT_PWM_LS_HC", "PWM_LS_HC", "", EEC_SIGNAL_INTERFACE_PWM, EEC_PIN_ROLE_OUTPUT, EEC_DIAG_OPEN_LOAD|EEC_DIAG_OVERCURRENT|EEC_DIAG_THERMAL_WARN, EEC_ELEC_LOW_SIDE, "0..14 V | 40 Hz .. 500 Hz · Low-side", "Drive Strength|PWM Freq"},
    {"PWM_HS_LC", "OUT_PWM_HS_LC", "PWM_HS_LC", "", EEC_SIGNAL_INTERFACE_PWM, EEC_PIN_ROLE_OUTPUT, EEC_DIAG_OPEN_LOAD|EEC_DIAG_SHORT_GND|EEC_DIAG_SHORT_BAT|EEC_DIAG_RANGE_CHECK, EEC_ELEC_HIGH_SIDE|EEC_ELEC_CURRENT_SENSE, "0..18 V | 40 Hz .. 500 Hz · High-side low-current", "PWM Freq|Current Sense"},
    {"DIF_0_10K_AIV_16", "IN_DIF_AIV16", "DIF_0_10K", "AIV_16", EEC_SIGNAL_INTERFACE_ANALOG, EEC_PIN_ROLE_INPUT, EEC_DIAG_OPEN_LOAD|EEC_DIAG_SHORT_GND|EEC_DIAG_SHORT_BAT|EEC_DIAG_RANGE_CHECK, EEC_ELEC_PULLUP|EEC_ELEC_PULLDOWN|EEC_ELEC_VOLTAGE_IN, "0..18 V / 0..10 kHz | 5 mV resolution · configurable thresholds", "Pull-Up|Pull-Down|Interrupt|Filter"},
    {"AIV_5_AIV_16_AIV_RES", "IN_AIV_RES", "AIV_5", "AIV_16|AIV_RES", EEC_SIGNAL_INTERFACE_ANALOG, EEC_PIN_ROLE_INPUT, EEC_DIAG_OPEN_LOAD|EEC_DIAG_SHORT_GND|EEC_DIAG_SHORT_BAT|EEC_DIAG_RANGE_CHECK, EEC_ELEC_PULLUP|EEC_ELEC_PULLDOWN|EEC_ELEC_VOLTAGE_IN, "0.05..4.95 V / 0.5..18.0 V | ADC 12-bit · configurable pull-up/down", "Pull-Up|Pull-Down|Interrupt|Filter"},
    {"AIV_5_AIV_16_AIV_RES_AII_4_20", "IN_AII_AIV", "AII_4_20", "AIV_5|AIV_16|AIV_RES", EEC_SIGNAL_INTERFACE_ANALOG, EEC_PIN_ROLE_INPUT, EEC_DIAG_OPEN_LOAD|EEC_DIAG_SHORT_GND|EEC_DIAG_SHORT_BAT|EEC_DIAG_RANGE_CHECK, EEC_ELEC_PULLUP|EEC_ELEC_PULLDOWN|EEC_ELEC_VOLTAGE_IN|EEC_ELEC_CURRENT_SENSE, "0.3..24 mA / 0.5..18.0 V | 7 µA / 5 mV resolution", "Pull-Up|Pull-Down|Interrupt|Filter"},
    {"AIV_5_AIV_16_AIV_RES_SENT", "IN_SENT", "SENT", "AIV_5|AIV_16|AIV_RES", EEC_SIGNAL_INTERFACE_SENT, EEC_PIN_ROLE_INPUT, EEC_DIAG_LINE_BREAK|EEC_DIAG_PLAUSIBILITY, EEC_ELEC_PULLUP|EEC_ELEC_VOLTAGE_IN, "Digital pulse input | SENT capable", "Interrupt|Filter"},
    {"AIV_5_AIV_16_AIV_RES_AII_4_20_SENT", "IN_AII_SENT", "SENT", "AIV_5|AIV_16|AII_4_20", EEC_SIGNAL_INTERFACE_SENT, EEC_PIN_ROLE_INPUT, EEC_DIAG_LINE_BREAK|EEC_DIAG_PLAUSIBILITY|EEC_DIAG_SHORT_BAT, EEC_ELEC_PULLUP|EEC_ELEC_VOLTAGE_IN|EEC_ELEC_CURRENT_SENSE, "0.3..24 mA / SENT input | Current + SENT capable", "Interrupt|Filter|Mode Select"},
    {"IN_DIG_01", "IN_DIG_WAKE", "IN_DIG_01", "", EEC_SIGNAL_INTERFACE_DIGITAL, EEC_PIN_ROLE_INPUT, EEC_DIAG_OPEN_LOAD|EEC_DIAG_SHORT_GND|EEC_DIAG_SHORT_BAT|EEC_DIAG_RANGE_CHECK, EEC_ELEC_PULLUP|EEC_ELEC_PULLDOWN|EEC_ELEC_VOLTAGE_IN, "0..19.3 V | Wake input · 4.8 mV resolution", "Wakeup|Interrupt|Filter"},
    {"CAN", "CAN", "CAN", "", EEC_SIGNAL_INTERFACE_CAN, EEC_PIN_ROLE_INOUT, 0U, EEC_ELEC_DIFFERENTIAL, "0..18 V monitor | Differential bus line", "Wakeup"},
    {"ETH", "ETH", "ETHERNET", "", EEC_SIGNAL_INTERFACE_ETHERNET, EEC_PIN_ROLE_INOUT, 0U, EEC_ELEC_DIFFERENTIAL, "100Base-T1 / 1000Base-T1 | Differential pair", "Wakeup"},
    {"LIN", "LIN", "LIN", "", EEC_SIGNAL_INTERFACE_LIN, EEC_PIN_ROLE_INOUT, 0U, EEC_ELEC_DIFFERENTIAL, "12 V TRM30 | Master · 2.4..20 kbit · 1000 Ohm pull-up", "Baudrate"},
    {"SENSOR_SUPPLY", "OUT_SUP_ANA", "SENSOR_SUPPLY", "", EEC_SIGNAL_INTERFACE_POWER, EEC_PIN_ROLE_OUTPUT, EEC_DIAG_OPEN_LOAD|EEC_DIAG_SHORT_GND|EEC_DIAG_SHORT_BAT|EEC_DIAG_RANGE_CHECK, 0U, "5.0 / 8.5 / 10.0 V selectable | FS-Classified · ISO 7637-2 · Self-protection", "Enable|Voltage Select"},
    {"SENSOR_SUPPLY_GND", "OUT_SUP_ANA_GND", "SENSOR_SUPPLY_GND", "", EEC_SIGNAL_INTERFACE_GROUND, EEC_PIN_ROLE_GROUND, 0U, 0U, "Sensor supply ground return | Dedicated GND", ""},
    {"RESERVED", "RSV", "RESERVED", "", EEC_SIGNAL_INTERFACE_RESERVED, EEC_PIN_ROLE_UNASSIGNED, 0U, 0U, "Reserved cavity | No I/O group assigned yet", ""}
};

static const EEC_GroupSpec_t *find_group(const char *key)
{
    size_t i;
    for (i = 0U; i < sizeof(G_GROUPS) / sizeof(G_GROUPS[0]); ++i) {
        if (strcmp(G_GROUPS[i].key, key) == 0) {
            return &G_GROUPS[i];
        }
    }
    return &G_GROUPS[sizeof(G_GROUPS) / sizeof(G_GROUPS[0]) - 1U];
}

/** @brief Append one pipe-separated function string to the pin functions list. */
static void add_functions_from_text(EEC_EcuPin_t *pin, const char *main_group, const char *text)
{
    char buffer[160];
    char *token;
    char *next;
    if (!pin || !text || !text[0]) {
        return;
    }
    strncpy(buffer, text, sizeof(buffer) - 1U);
    buffer[sizeof(buffer) - 1U] = '\0';

    token = buffer;
    while (token && token[0] != '\0') {
        next = strchr(token, '|');
        if (next) {
            *next = '\0';
        }
        if ((!main_group || strcmp(main_group, token) != 0) && token[0] != '\0') {
            EEC_EcuPin_AddFunction(pin, token);
        }
        token = next ? (next + 1) : NULL;
    }
}

/** @brief Build one pin template line from a group and a connector/pin pair. */
static void create_pin_from_group(EEC_Ecu_t *ecu, const EEC_GroupSpec_t *spec, uint32_t index, const char *connector, uint32_t physical_pin)
{
    char pin_name[64];
    EEC_EcuPin_t *pin;
    if (strncmp(spec->key, "CAN", 3) == 0) {
        const uint32_t bus_index = (index + 1U) / 2U;
        snprintf(pin_name, sizeof(pin_name), "CAN%u_%c", bus_index, (index % 2U) ? 'H' : 'L');
    } else if (strncmp(spec->key, "ETH", 3) == 0) {
        const uint32_t pair_index = (index + 1U) / 2U;
        snprintf(pin_name, sizeof(pin_name), "ETH%u_%c", pair_index, (index % 2U) ? 'P' : 'N');
    } else {
        snprintf(pin_name, sizeof(pin_name), "%s_%02u", spec->prefix, index);
    }

    pin = EEC_Ecu_CreatePin(
        ecu,
        physical_pin,
        connector,
        pin_name,
        spec->group,
        spec->role,
        (EEC_PinInterface_t)spec->interface_type,
        EEC_Signal_InterfaceToCapability(spec->interface_type),
        spec->diag,
        spec->electrical,
        spec->sw_config
    );
    if (!pin) {
        return;
    }
    pin->electrical_capability = spec->elec_cap;
    /* PWM high-side pins can also serve as static digital outputs (SW drives
       100% duty cycle).  This allows ON/OFF valves to fall back to PWM pins
       when all dedicated DO_HS pins are consumed. */
    if (spec->interface_type == EEC_SIGNAL_INTERFACE_PWM &&
        (spec->elec_cap & EEC_ELEC_HIGH_SIDE)) {
        pin->supported_capability_mask |= EEC_Signal_InterfaceToCapability(EEC_SIGNAL_INTERFACE_DIGITAL);
    }
    /* DIF_0_10K pins support frequency measurement (0..10 kHz configurable). */
    if (strstr(spec->key, "DIF_0_10K") != NULL) {
        pin->supported_capability_mask |= EEC_Signal_InterfaceToCapability(EEC_SIGNAL_INTERFACE_FREQUENCY);
    }
    /* AIV_RES pins support resistance measurement (resistive sensor input). */
    if (strstr(spec->key, "AIV_RES") != NULL) {
        pin->supported_capability_mask |= EEC_Signal_InterfaceToCapability(EEC_SIGNAL_INTERFACE_RESISTANCE);
    }
    /* AII/AIV analog input pins also accept raw ANALOG voltage signals. */
    if (strstr(spec->key, "AII") != NULL || strstr(spec->key, "AIV") != NULL) {
        pin->supported_capability_mask |= EEC_Signal_InterfaceToCapability(EEC_SIGNAL_INTERFACE_ANALOG);
    }
    /* FREQUENCY inputs can also accept plain DIGITAL on/off signals. */
    if (spec->interface_type == EEC_SIGNAL_INTERFACE_FREQUENCY) {
        pin->supported_capability_mask |= EEC_Signal_InterfaceToCapability(EEC_SIGNAL_INTERFACE_DIGITAL);
    }
    /* LOW_SIDE PWM outputs also serve as static digital sinking outputs. */
    if (spec->interface_type == EEC_SIGNAL_INTERFACE_PWM &&
        (spec->elec_cap & EEC_ELEC_LOW_SIDE)) {
        pin->supported_capability_mask |= EEC_Signal_InterfaceToCapability(EEC_SIGNAL_INTERFACE_DIGITAL);
    }
    add_functions_from_text(pin, spec->group, spec->alt);
    /* Populate provided info so programmatic ECU creation mirrors importer. */
    if (pin) {
        EEC_Pin_PopulateProvidedFromData(pin, pin_name, spec->group, spec->electrical, NULL, 0.0f, 0.0f, NULL, NULL);
    }
}

/** @brief Fill one ECU with all physical pins for the selected variant.
 *  The group allocation is a deterministic baseline matching the pre-filled HTML templates.
 */
static void populate_variant(EEC_Ecu_t *ecu, const char *variant)
{
    typedef struct { const char *group_key; uint32_t count; } GroupCount;
    typedef struct { const char *name; uint32_t count; } ConnectorCount;

    const ConnectorCount *connectors = NULL;
    const GroupCount *groups = NULL;
    size_t connector_count = 0U;
    size_t group_count = 0U;
    size_t i;
    uint32_t physical_index = 0U;
    uint32_t group_item_index = 0U;
    uint32_t connector_pin_cursor = 1U;
    size_t connector_idx = 0U;

    static const ConnectorCount SMALL_CONNECTORS[] = {
        {"X1000", 112U}, {"X1001", 2U}, {"X1002", 2U}, {"X1003", 4U}, {"X1004", 2U}
    };
    static const ConnectorCount MEDIUM_CONNECTORS[] = {
        {"X1", 112U}, {"X2", 48U}, {"X3", 2U}, {"X4", 2U}, {"X5", 2U}, {"X6", 4U}
    };
    static const ConnectorCount LARGE_CONNECTORS[] = {
        {"X1", 112U}, {"X2", 48U}, {"X3", 32U}, {"X4", 4U}, {"X5", 2U}, {"X6", 2U}, {"X7", 2U}
    };

    static const GroupCount SMALL_GROUPS[] = {
        {"SUPPLY", 6U}, {"GROUND", 6U}, {"DO_HS_HC", 6U}, {"PWM_HS_HC", 8U}, {"PWM_LS_HC", 4U},
        {"DIF_0_10K_AIV_16", 8U}, {"AIV_5_AIV_16_AIV_RES", 8U}, {"AIV_5_AIV_16_AIV_RES_AII_4_20", 8U},
        {"AIV_5_AIV_16_AIV_RES_SENT", 8U}, {"IN_DIG_01", 1U},
        {"SENSOR_SUPPLY", 3U}, {"SENSOR_SUPPLY_GND", 3U}, {"LIN", 1U},
        {"CAN", 6U}, {"ETH", 10U}
    };
    static const GroupCount MEDIUM_GROUPS[] = {
        {"SUPPLY", 8U}, {"GROUND", 8U}, {"PWM_HS_LC", 4U}, {"DO_HS_HC", 12U}, {"PWM_HS_HC", 14U}, {"PWM_LS_HC", 6U},
        {"DIF_0_10K_AIV_16", 22U}, {"AIV_5_AIV_16_AIV_RES", 4U}, {"AIV_5_AIV_16_AIV_RES_AII_4_20", 20U},
        {"AIV_5_AIV_16_AIV_RES_SENT", 12U}, {"IN_DIG_01", 1U},
        {"SENSOR_SUPPLY", 4U}, {"SENSOR_SUPPLY_GND", 4U}, {"LIN", 1U},
        {"CAN", 8U}, {"ETH", 10U}
    };
    static const GroupCount LARGE_GROUPS[] = {
        {"SUPPLY", 10U}, {"GROUND", 10U}, {"PWM_HS_LC", 4U}, {"DO_HS_HC", 20U}, {"PWM_HS_HC", 24U}, {"PWM_LS_HC", 10U},
        {"DIF_0_10K_AIV_16", 24U}, {"AIV_5_AIV_16_AIV_RES_AII_4_20", 24U}, {"AIV_5_AIV_16_AIV_RES_AII_4_20_SENT", 12U},
        {"IN_DIG_01", 1U},
        {"SENSOR_SUPPLY", 4U}, {"SENSOR_SUPPLY_GND", 4U}, {"LIN", 1U},
        {"CAN", 8U}, {"ETH", 10U}
    };

    if (strcmp(variant, "MEDIUM") == 0) {
        connectors = MEDIUM_CONNECTORS;
        connector_count = sizeof(MEDIUM_CONNECTORS) / sizeof(MEDIUM_CONNECTORS[0]);
        groups = MEDIUM_GROUPS;
        group_count = sizeof(MEDIUM_GROUPS) / sizeof(MEDIUM_GROUPS[0]);
    } else if (strcmp(variant, "LARGE") == 0) {
        connectors = LARGE_CONNECTORS;
        connector_count = sizeof(LARGE_CONNECTORS) / sizeof(LARGE_CONNECTORS[0]);
        groups = LARGE_GROUPS;
        group_count = sizeof(LARGE_GROUPS) / sizeof(LARGE_GROUPS[0]);
    } else {
        connectors = SMALL_CONNECTORS;
        connector_count = sizeof(SMALL_CONNECTORS) / sizeof(SMALL_CONNECTORS[0]);
        groups = SMALL_GROUPS;
        group_count = sizeof(SMALL_GROUPS) / sizeof(SMALL_GROUPS[0]);
    }

    for (i = 0U; i < group_count; ++i) {
        uint32_t n;
        const EEC_GroupSpec_t *spec = find_group(groups[i].group_key);
        for (n = 1U; n <= groups[i].count; ++n) {
            while (connector_idx < connector_count && connector_pin_cursor > connectors[connector_idx].count) {
                connector_idx++;
                connector_pin_cursor = 1U;
            }
            if (connector_idx >= connector_count) {
                return;
            }
            physical_index++;
            group_item_index++;
            create_pin_from_group(ecu, spec, n, connectors[connector_idx].name, connector_pin_cursor);
            connector_pin_cursor++;
        }
    }

    /* Fill remaining physical cavities as reserved. */
    while (connector_idx < connector_count) {
        const EEC_GroupSpec_t *spec = find_group("RESERVED");
        while (connector_pin_cursor <= connectors[connector_idx].count) {
            group_item_index++;
            create_pin_from_group(ecu, spec, group_item_index, connectors[connector_idx].name, connector_pin_cursor);
            connector_pin_cursor++;
        }
        connector_idx++;
        connector_pin_cursor = 1U;
    }
}

/** @brief Common factory used by the three public EEC_Agco_CreateEcu* wrappers. */
static EEC_Ecu_t *create_variant(EEC_Architecture_t *arch, const char *name, const char *variant, uint8_t can_address_count, va_list args)
{
    uint8_t i;
    EEC_Ecu_t *ecu;
    if (!arch || !name || !variant || can_address_count > EEC_ECU_MAX_CAN_ADDRESSES) {
        return NULL;
    }

    ecu = EEC_Architecture_CreateEcu(arch, name, variant);
    if (!ecu) {
        return NULL;
    }

    for (i = 0U; i < can_address_count; ++i) {
        const int addr = va_arg(args, int);
        EEC_Ecu_AddCanAddress(ecu, (uint8_t)addr);
    }

    populate_variant(ecu, variant);

    /* Apply recommended max AgPL per ECU variant: SMALL->B, MEDIUM->C, LARGE->D */
    {
        EEC_AgplLevel_t rec = EEC_AGPL_E;
        if (strcmp(variant, "SMALL") == 0) rec = EEC_AGPL_B;
        else if (strcmp(variant, "MEDIUM") == 0) rec = EEC_AGPL_C;
        else if (strcmp(variant, "LARGE") == 0) rec = EEC_AGPL_D;
        if (rec != EEC_AGPL_E) {
            uint32_t pi;
            for (pi = 0U; pi < ecu->pin_count; ++pi) {
                ecu->pins[pi].max_agpl = rec;
            }
        }
    }

    EEC_Log_Printf(EEC_LOG_INFO, "Created %s ECU '%s' with %u CAN address(es) and %u physical pin(s)",
                  variant, ecu->name, ecu->can_address_count, ecu->pin_count);
    return ecu;
}

EEC_Ecu_t *EEC_Agco_CreateEcuSmall(EEC_Architecture_t *arch, const char *ecu_name, uint8_t can_address_count, ...)
{
    EEC_Ecu_t *ecu;
    va_list args;
    va_start(args, can_address_count);
    ecu = create_variant(arch, ecu_name, "SMALL", can_address_count, args);
    va_end(args);
    return ecu;
}

EEC_Ecu_t *EEC_Agco_CreateEcuMedium(EEC_Architecture_t *arch, const char *ecu_name, uint8_t can_address_count, ...)
{
    EEC_Ecu_t *ecu;
    va_list args;
    va_start(args, can_address_count);
    ecu = create_variant(arch, ecu_name, "MEDIUM", can_address_count, args);
    va_end(args);
    return ecu;
}

EEC_Ecu_t *EEC_Agco_CreateEcuLarge(EEC_Architecture_t *arch, const char *ecu_name, uint8_t can_address_count, ...)
{
    EEC_Ecu_t *ecu;
    va_list args;
    va_start(args, can_address_count);
    ecu = create_variant(arch, ecu_name, "LARGE", can_address_count, args);
    va_end(args);
    return ecu;
}
