/**
 * @file    EEC_types.c
 * @brief   E/E Architect Design — Type conversion utilities.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#include "EEC_types.h"
#include "EEC_architecture.h"
#include <string.h>

const char *EEC_Signal_TypeString(EEC_SignalType_t type)
{
    switch (type) {
        case EEC_SIGNAL_TYPE_UNSIGNED_1BIT: return "U1";
        case EEC_SIGNAL_TYPE_UNSIGNED_8BIT: return "U8";
        case EEC_SIGNAL_TYPE_SIGNED_8BIT: return "S8";
        case EEC_SIGNAL_TYPE_UNSIGNED_16BIT: return "U16";
        case EEC_SIGNAL_TYPE_SIGNED_16BIT: return "S16";
        case EEC_SIGNAL_TYPE_UNSIGNED_32BIT: return "U32";
        case EEC_SIGNAL_TYPE_SIGNED_32BIT: return "S32";
        case EEC_SIGNAL_TYPE_UNSIGNED_64BIT: return "U64";
        case EEC_SIGNAL_TYPE_SIGNED_64BIT: return "S64";
        case EEC_SIGNAL_TYPE_FLOAT_32BIT: return "F32";
        case EEC_SIGNAL_TYPE_FLOAT_64BIT: return "F64";
        case EEC_SIGNAL_TYPE_RESERVED: return "RESERVED";
        default: return "UNKNOWN";
    }
}

uint32_t EEC_Signal_TypeBitWidth(EEC_SignalType_t type)
{
    switch (type) {
        case EEC_SIGNAL_TYPE_UNSIGNED_1BIT: return 1U;
        case EEC_SIGNAL_TYPE_UNSIGNED_8BIT:
        case EEC_SIGNAL_TYPE_SIGNED_8BIT: return 8U;
        case EEC_SIGNAL_TYPE_UNSIGNED_16BIT:
        case EEC_SIGNAL_TYPE_SIGNED_16BIT: return 16U;
        case EEC_SIGNAL_TYPE_UNSIGNED_32BIT:
        case EEC_SIGNAL_TYPE_SIGNED_32BIT:
        case EEC_SIGNAL_TYPE_FLOAT_32BIT: return 32U;
        case EEC_SIGNAL_TYPE_UNSIGNED_64BIT:
        case EEC_SIGNAL_TYPE_SIGNED_64BIT:
        case EEC_SIGNAL_TYPE_FLOAT_64BIT: return 64U;
        default: return 0U;
    }
}

bool EEC_Signal_TypeIsSigned(EEC_SignalType_t type)
{
    switch (type) {
        case EEC_SIGNAL_TYPE_SIGNED_8BIT:
        case EEC_SIGNAL_TYPE_SIGNED_16BIT:
        case EEC_SIGNAL_TYPE_SIGNED_32BIT:
        case EEC_SIGNAL_TYPE_SIGNED_64BIT:
        case EEC_SIGNAL_TYPE_FLOAT_32BIT:
        case EEC_SIGNAL_TYPE_FLOAT_64BIT:
            return true;
        default:
            return false;
    }
}

const char *EEC_Signal_InterfaceString(EEC_SignalInterface_t interface_type)
{
    switch (interface_type) {
        case EEC_SIGNAL_INTERFACE_DIGITAL: return "DIGITAL";
        case EEC_SIGNAL_INTERFACE_ANALOG: return "ANALOG";
        case EEC_SIGNAL_INTERFACE_PWM: return "PWM";
        case EEC_SIGNAL_INTERFACE_CAN: return "CAN";
        case EEC_SIGNAL_INTERFACE_LIN: return "LIN";
        case EEC_SIGNAL_INTERFACE_SENT: return "SENT";
        case EEC_SIGNAL_INTERFACE_ETHERNET: return "ETHERNET";
        case EEC_SIGNAL_INTERFACE_RESISTANCE: return "RESISTANCE";
        case EEC_SIGNAL_INTERFACE_FREQUENCY: return "FREQUENCY";
        case EEC_SIGNAL_INTERFACE_CURRENT: return "CURRENT";
        case EEC_SIGNAL_INTERFACE_FLEXRAY: return "FLEXRAY";
        case EEC_SIGNAL_INTERFACE_POWER: return "POWER";
        case EEC_SIGNAL_INTERFACE_GROUND: return "GROUND";
        case EEC_SIGNAL_INTERFACE_RESERVED: return "RESERVED";
        default: return "UNKNOWN";
    }
}

const char *EEC_Signal_UnitString(EEC_SignalUnit_t unit)
{
    switch (unit) {
        case EEC_SIGNAL_UNIT_NONE: return "NONE";
        case EEC_SIGNAL_UNIT_BOOLEAN: return "BOOLEAN";
        case EEC_SIGNAL_UNIT_VOLT: return "VOLT";
        case EEC_SIGNAL_UNIT_AMPERE: return "AMPERE";
        case EEC_SIGNAL_UNIT_HERTZ: return "HERTZ";
        case EEC_SIGNAL_UNIT_PERCENT: return "PERCENT";
        case EEC_SIGNAL_UNIT_RPM: return "RPM";
        case EEC_SIGNAL_UNIT_CELSIUS: return "CELSIUS";
        case EEC_SIGNAL_UNIT_BAR: return "BAR";
        case EEC_SIGNAL_UNIT_DEGREE: return "DEGREE";
        default: return "UNKNOWN";
    }
}

const char *EEC_Pin_RoleString(EEC_PinRole_t role)
{
    switch (role) {
        case EEC_PIN_ROLE_INPUT: return "INPUT";
        case EEC_PIN_ROLE_OUTPUT: return "OUTPUT";
        case EEC_PIN_ROLE_INOUT: return "INOUT";
        case EEC_PIN_ROLE_SUPPLY: return "SUPPLY";
        case EEC_PIN_ROLE_GROUND: return "GROUND";
        case EEC_PIN_ROLE_UNASSIGNED: return "UNASSIGNED";
        default: return "UNKNOWN";
    }
}

const char *EEC_Device_TypeString(EEC_DeviceType_t type)
{
    switch (type) {
        case EEC_DEVICE_SENSOR: return "SENSOR";
        case EEC_DEVICE_ACTUATOR: return "ACTUATOR";
        case EEC_DEVICE_GATEWAY: return "GATEWAY";
        default: return "UNKNOWN";
    }
}

const char *EEC_Priority_String(EEC_ObjectPriority_t priority)
{
    switch (priority) {
        case EEC_PRIORITY_LOW: return "LOW";
        case EEC_PRIORITY_MEDIUM: return "MEDIUM";
        case EEC_PRIORITY_HIGH: return "HIGH";
        case EEC_PRIORITY_CRITICAL: return "CRITICAL";
        default: return "UNKNOWN";
    }
}

const char *EEC_Safety_String(EEC_SafetyClass_t safety)
{
    switch (safety) {
        case EEC_SAFETY_QM: return "QM";
        case EEC_SAFETY_AGPL_A: return "AgPL_A";
        case EEC_SAFETY_AGPL_B: return "AgPL_B";
        case EEC_SAFETY_AGPL_C: return "AgPL_C";
        case EEC_SAFETY_AGPL_D: return "AgPL_D";
        default: return "UNKNOWN";
    }
}

const char *EEC_System_LevelString(EEC_SystemLevel_t level)
{
    switch (level) {
        case EEC_SYSTEM_LEVEL_SL0: return "SL0";
        case EEC_SYSTEM_LEVEL_SL1: return "SL1";
        case EEC_SYSTEM_LEVEL_SL2: return "SL2";
        case EEC_SYSTEM_LEVEL_SL3: return "SL3";
        case EEC_SYSTEM_LEVEL_SL4: return "SL4";
        default: return "UNKNOWN";
    }
}

uint32_t EEC_Signal_InterfaceToCapability(EEC_SignalInterface_t interface_type)
{
    switch (interface_type) {
        case EEC_SIGNAL_INTERFACE_DIGITAL: return 1U << 0;
        case EEC_SIGNAL_INTERFACE_ANALOG: return 1U << 1;
        case EEC_SIGNAL_INTERFACE_PWM: return 1U << 2;
        case EEC_SIGNAL_INTERFACE_CAN: return 1U << 3;
        case EEC_SIGNAL_INTERFACE_LIN: return 1U << 4;
        case EEC_SIGNAL_INTERFACE_SENT: return 1U << 5;
        case EEC_SIGNAL_INTERFACE_ETHERNET: return 1U << 6;
        case EEC_SIGNAL_INTERFACE_RESISTANCE: return 1U << 9;
        case EEC_SIGNAL_INTERFACE_FREQUENCY: return 1U << 10;
        case EEC_SIGNAL_INTERFACE_CURRENT: return 1U << 12;
        case EEC_SIGNAL_INTERFACE_FLEXRAY: return 1U << 11;
        case EEC_SIGNAL_INTERFACE_POWER: return 1U << 7;
        case EEC_SIGNAL_INTERFACE_GROUND: return 1U << 8;
        default: return 0U;
    }
}

uint32_t EEC_ElectricalDefaultRequirement(EEC_SignalInterface_t iface, EEC_PinRole_t role)
{
    switch (iface) {
        case EEC_SIGNAL_INTERFACE_ANALOG:
            return (role == EEC_PIN_ROLE_INPUT) ? EEC_ELEC_VOLTAGE_IN : 0U;
        case EEC_SIGNAL_INTERFACE_PWM:
            /* PWM load topology varies (HS/LS) — set explicitly per device. */
            return 0U;
        case EEC_SIGNAL_INTERFACE_DIGITAL:
            if (role == EEC_PIN_ROLE_OUTPUT) return (uint32_t)(EEC_ELEC_HIGH_SIDE | EEC_ELEC_PUSH_PULL);
            if (role == EEC_PIN_ROLE_INPUT) return (uint32_t)(EEC_ELEC_VOLTAGE_IN);
            return 0U;
        case EEC_SIGNAL_INTERFACE_SENT:
            return (uint32_t)(EEC_ELEC_PULLUP | EEC_ELEC_VOLTAGE_IN);
        case EEC_SIGNAL_INTERFACE_RESISTANCE:
            return (uint32_t)(EEC_ELEC_PULLUP | EEC_ELEC_CURRENT_SENSE);
        case EEC_SIGNAL_INTERFACE_FREQUENCY:
            return (uint32_t)(EEC_ELEC_VOLTAGE_IN | EEC_ELEC_PULLUP);
        case EEC_SIGNAL_INTERFACE_CURRENT:
            return (uint32_t)(EEC_ELEC_CURRENT_SENSE);
        case EEC_SIGNAL_INTERFACE_FLEXRAY:
            return (uint32_t)(EEC_ELEC_DIFFERENTIAL);
        case EEC_SIGNAL_INTERFACE_CAN:
            return (uint32_t)(EEC_ELEC_DIFFERENTIAL);
        case EEC_SIGNAL_INTERFACE_LIN:
            return (uint32_t)(EEC_ELEC_PULLUP);
        case EEC_SIGNAL_INTERFACE_ETHERNET:
            return (uint32_t)(EEC_ELEC_DIFFERENTIAL);
        default:
            return 0U;
    }
}

const char *EEC_Bus_TypeString(EEC_BusType_t type)
{
    switch (type) {
        case EEC_BUS_TYPE_CAN:      return "CAN";
        case EEC_BUS_TYPE_ISOBUS:   return "ISOBUS";
        case EEC_BUS_TYPE_LIN:      return "LIN";
        case EEC_BUS_TYPE_ETHERNET: return "ETHERNET";
        case EEC_BUS_TYPE_FLEXRAY:  return "FLEXRAY";
        case EEC_BUS_TYPE_CUSTOM:   return "CUSTOM";
        default:                   return "UNKNOWN";
    }
}

EEC_BusType_t EEC_Bus_ParseType(const char *str)
{
    if (!str) return EEC_BUS_TYPE_CUSTOM;
    if (strcmp(str, "CAN")      == 0) return EEC_BUS_TYPE_CAN;
    if (strcmp(str, "ISOBUS")   == 0) return EEC_BUS_TYPE_ISOBUS;
    if (strcmp(str, "LIN")      == 0) return EEC_BUS_TYPE_LIN;
    if (strcmp(str, "ETHERNET") == 0) return EEC_BUS_TYPE_ETHERNET;
    if (strcmp(str, "FLEXRAY")  == 0) return EEC_BUS_TYPE_FLEXRAY;
    return EEC_BUS_TYPE_CUSTOM;
}

const char *EEC_Connector_FamilyString(EEC_ConnectorFamily_t family)
{
    switch (family) {
        case EEC_CONNECTOR_FAMILY_DEUTSCH:        return "DEUTSCH";
        case EEC_CONNECTOR_FAMILY_AMP_SUPERSEAL:  return "AMP_SUPERSEAL";
        case EEC_CONNECTOR_FAMILY_MOLEX:          return "MOLEX";
        case EEC_CONNECTOR_FAMILY_TE_CONNECTIVITY: return "TE_CONNECTIVITY";
        case EEC_CONNECTOR_FAMILY_YAZAKI:         return "YAZAKI";
        case EEC_CONNECTOR_FAMILY_JAE:            return "JAE";
        case EEC_CONNECTOR_FAMILY_AMPSEAL:        return "AMPSEAL";
        case EEC_CONNECTOR_FAMILY_CUSTOM:         return "CUSTOM";
        default:                                 return "UNKNOWN";
    }
}

EEC_ConnectorFamily_t EEC_Connector_ParseFamily(const char *str)
{
    if (!str) return EEC_CONNECTOR_FAMILY_CUSTOM;
    if (strcmp(str, "DEUTSCH")        == 0) return EEC_CONNECTOR_FAMILY_DEUTSCH;
    if (strcmp(str, "AMP_SUPERSEAL")  == 0) return EEC_CONNECTOR_FAMILY_AMP_SUPERSEAL;
    if (strcmp(str, "MOLEX")          == 0) return EEC_CONNECTOR_FAMILY_MOLEX;
    if (strcmp(str, "TE_CONNECTIVITY") == 0) return EEC_CONNECTOR_FAMILY_TE_CONNECTIVITY;
    if (strcmp(str, "YAZAKI")         == 0) return EEC_CONNECTOR_FAMILY_YAZAKI;
    if (strcmp(str, "JAE")            == 0) return EEC_CONNECTOR_FAMILY_JAE;
    if (strcmp(str, "AMPSEAL")        == 0) return EEC_CONNECTOR_FAMILY_AMPSEAL;
    return EEC_CONNECTOR_FAMILY_CUSTOM;
}

const char *EEC_Connector_GenderString(EEC_ConnectorGender_t gender)
{
    switch (gender) {
        case EEC_CONNECTOR_GENDER_MALE:   return "MALE";
        case EEC_CONNECTOR_GENDER_FEMALE: return "FEMALE";
        case EEC_CONNECTOR_GENDER_HYBRID: return "HYBRID";
        default:                         return "UNKNOWN";
    }
}

EEC_ConnectorGender_t EEC_Connector_ParseGender(const char *str)
{
    if (!str) return EEC_CONNECTOR_GENDER_MALE;
    if (strcmp(str, "FEMALE") == 0) return EEC_CONNECTOR_GENDER_FEMALE;
    if (strcmp(str, "HYBRID") == 0) return EEC_CONNECTOR_GENDER_HYBRID;
    return EEC_CONNECTOR_GENDER_MALE;
}

bool EEC_Bus_InterfaceCompatible(EEC_BusType_t bus_type, EEC_SignalInterface_t iface)
{
    switch (bus_type) {
        case EEC_BUS_TYPE_CAN:      return iface == EEC_SIGNAL_INTERFACE_CAN;
        case EEC_BUS_TYPE_ISOBUS:   return iface == EEC_SIGNAL_INTERFACE_CAN;
        case EEC_BUS_TYPE_LIN:      return iface == EEC_SIGNAL_INTERFACE_LIN;
        case EEC_BUS_TYPE_ETHERNET: return iface == EEC_SIGNAL_INTERFACE_ETHERNET;
        case EEC_BUS_TYPE_FLEXRAY:  return iface == EEC_SIGNAL_INTERFACE_FLEXRAY;
        case EEC_BUS_TYPE_CUSTOM:   return true;  /* custom allows anything */
        default:                   return false;
    }
}

/* ---------------- Sensor supply / ground helpers ---------------- */
const char *EEC_SensorSupply_ToString(EEC_SensorSupplyType_t s)
{
    switch (s) {
        case EEC_SUPPLY_OUT_SUP_ANA_5V_01: return "OUT_SUP_ANA_5V_01";
        case EEC_SUPPLY_OUT_SUP_ANA_8V5_10V_01: return "OUT_SUP_ANA_8V5_10V_01";
        case EEC_SUPPLY_OUT_SUP_ANA_8V5_10V_02: return "OUT_SUP_ANA_8V5_10V_02";
        case EEC_BATT_SUPPLY: return "VBAT";
        case EEC_SENSOR_SUPPLY: return "SENSOR_SUPPLY";
        case EEC_SENSOR_SUPPLY_UNKNOWN: return "UNKNOWN";
        default: return "UNKNOWN";
    }
}

EEC_SensorSupplyType_t EEC_SensorSupply_Parse(const char *str)
{
    if (!str) return EEC_SENSOR_SUPPLY_UNKNOWN;
    if (strcmp(str, "OUT_SUP_ANA_5V_01") == 0) return EEC_SUPPLY_OUT_SUP_ANA_5V_01;
    if (strcmp(str, "OUT_SUP_ANA_8V5_10V_01") == 0) return EEC_SUPPLY_OUT_SUP_ANA_8V5_10V_01;
    if (strcmp(str, "OUT_SUP_ANA_8V5_10V_02") == 0) return EEC_SUPPLY_OUT_SUP_ANA_8V5_10V_02;
    if (strcmp(str, "VBAT") == 0 || strcmp(str, "BATT") == 0 || strcmp(str, "BATTERY") == 0) return EEC_BATT_SUPPLY;

    /* Generic short names produced by exports: OUT_SUP_ANA_01..04 */
    if (strncmp(str, "OUT_SUP_ANA_", 12) == 0) {
        /* If numeric suffix present (01..04) treat as generic sensor supply. */
        return EEC_SENSOR_SUPPLY;
    }

    if (strcmp(str, "SENSOR_SUPPLY") == 0) return EEC_SENSOR_SUPPLY;

    return EEC_SENSOR_SUPPLY_UNKNOWN;
}

const char *EEC_SensorGround_ToString(EEC_SensorGroundType_t g)
{
    switch (g) {
        case EEC_SUPPLY_OUT_SUP_ANA_8V5_10V_01_GND: return "OUT_SUP_ANA_8V5_10V_01_GND";
        case EEC_SUPPLY_OUT_SUP_ANA_5V_01_GND: return "OUT_SUP_ANA_5V_01_GND";
        case EEC_SUPPLY_OUT_SUP_ANA_8V5_10V_02_GND: return "OUT_SUP_ANA_8V5_10V_02_GND";
        case EEC_SUPPLY_BATT_GND: return "BATT_GND";
        case EEC_SENSOR_GND: return "SENSOR_GND";
        case EEC_SENSOR_GROUND_UNKNOWN: return "UNKNOWN";
        default: return "UNKNOWN";
    }
}

EEC_SensorGroundType_t EEC_SensorGround_Parse(const char *str)
{
    if (!str) return EEC_SENSOR_GROUND_UNKNOWN;
    if (strcmp(str, "OUT_SUP_ANA_8V5_10V_01_GND") == 0) return EEC_SUPPLY_OUT_SUP_ANA_8V5_10V_01_GND;
    if (strcmp(str, "OUT_SUP_ANA_5V_01_GND") == 0) return EEC_SUPPLY_OUT_SUP_ANA_5V_01_GND;
    if (strcmp(str, "OUT_SUP_ANA_8V5_10V_02_GND") == 0) return EEC_SUPPLY_OUT_SUP_ANA_8V5_10V_02_GND;
    if (strcmp(str, "BATT_GND") == 0 || strcmp(str, "VBAT_GND") == 0) return EEC_SUPPLY_BATT_GND;

    /* Generic ground labels produced by exports: OUT_SUP_ANA_GND_01.. */
    if (strncmp(str, "OUT_SUP_ANA_GND_", 16) == 0) return EEC_SENSOR_GND;

    if (strcmp(str, "SENSOR_GND") == 0) return EEC_SENSOR_GND;

    return EEC_SENSOR_GROUND_UNKNOWN;
}

bool EEC_Pin_SupplyCompatible(const EEC_EcuPin_t *ecu_pin, const EEC_DevicePin_t *dev_pin)
{
    if (!ecu_pin || !dev_pin) return false;

    /* Device must request a supply role to use this compatibility check. */
    if (dev_pin->role != EEC_PIN_ROLE_SUPPLY) return false;

    /* ECU pin must be a supply pin or capable of providing power. */
    if (ecu_pin->role != EEC_PIN_ROLE_SUPPLY) return false;

    /* Supply type compatibility: allow generic or exact matches. */
    if (dev_pin->required_sensor_supply != EEC_SENSOR_SUPPLY_UNKNOWN &&
        ecu_pin->provided_sensor_supply != EEC_SENSOR_SUPPLY_UNKNOWN) {
        if (dev_pin->required_sensor_supply != EEC_SENSOR_SUPPLY &&
            ecu_pin->provided_sensor_supply != EEC_SENSOR_SUPPLY &&
            dev_pin->required_sensor_supply != ecu_pin->provided_sensor_supply) {
            return false;
        }
    }

    /* Ground/return compatibility */
    if (dev_pin->required_sensor_ground != EEC_SENSOR_GROUND_UNKNOWN &&
        ecu_pin->provided_sensor_ground != EEC_SENSOR_GROUND_UNKNOWN &&
        dev_pin->required_sensor_ground != ecu_pin->provided_sensor_ground) {
        return false;
    }

    /* Ground class compatibility (POWER vs LOGIC) */
    if (dev_pin->ground_class != EEC_GND_UNCLASSIFIED &&
        ecu_pin->ground_class != EEC_GND_UNCLASSIFIED &&
        dev_pin->ground_class != ecu_pin->ground_class) {
        return false;
    }

    /* Current capacity check */
    if (ecu_pin->current_max > 0.0f && dev_pin->nominal_current > 0.0f) {
        if (ecu_pin->current_max < dev_pin->nominal_current) return false;
    }

    /* Voltage compatibility (if both specified) */
    if (ecu_pin->provided_supply_voltage > 0.0f && dev_pin->required_supply_voltage > 0.0f) {
        /* Allow +/-10% tolerance */
        float min_ok = dev_pin->required_supply_voltage * 0.9f;
        float max_ok = dev_pin->required_supply_voltage * 1.1f;
        if (ecu_pin->provided_supply_voltage < min_ok || ecu_pin->provided_supply_voltage > max_ok) return false;
    }

    return true;
}
