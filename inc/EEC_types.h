/**
 * @file    EEC_types.h
 * @brief   E/E Architect Design — Common enumerations and constants.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#ifndef EEC_TYPES_H
#define EEC_TYPES_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ── Object ID encoding ──
 * Every object id is uint32_t = (object_seq << 8) | variant_id.
 *   Bits 31-8 : per-type sequential counter (up to 16 777 215 objects per type).
 *   Bits  7-0 : variant byte (0 = base, 1..255 for variants).
 * Only System, Sensor, Actuator, and ECU are authorized to have variant_id != 0.
 */
#define EEC_ID_SEQ(id)            ((uint32_t)((id) >> 8))
#define EEC_ID_VARIANT(id)        ((uint8_t)((id) & 0xFFU))
#define EEC_ID_MAKE(seq, var)     ((uint32_t)(((seq) << 8) | ((var) & 0xFFU)))

/** @brief Maximum number of CAN node addresses stored by one ECU. */
#define EEC_ECU_MAX_CAN_ADDRESSES 10U

/** @brief Maximum number of receiver ECUs stored per CAN message signal. */
#define EEC_MSG_MAX_RX 16U

/** @brief Maximum number of platforms a system can be mounted on. */
#define EEC_SYSTEM_MAX_PLATFORMS  8U

/** @brief Maximum number of brands a system can be assigned to. */
#define EEC_SYSTEM_MAX_BRANDS     8U

/** @brief AGCO brand assignment for a system. */
typedef enum EEC_Brand_e {
    EEC_BRAND_FENDT = 0,
    EEC_BRAND_MASSEY_FERGUSON,
    EEC_BRAND_VALTRA,
    EEC_BRAND_COUNT             /**< Sentinel — number of defined brands. */
} EEC_Brand_t;

/** @brief Signal type used for compatibility and exports. */
typedef enum EEC_SignalType_e {
    EEC_SIGNAL_TYPE_UNSIGNED_1BIT = 0,
    EEC_SIGNAL_TYPE_UNSIGNED_8BIT,
    EEC_SIGNAL_TYPE_SIGNED_8BIT,
    EEC_SIGNAL_TYPE_UNSIGNED_16BIT,
    EEC_SIGNAL_TYPE_SIGNED_16BIT,
    EEC_SIGNAL_TYPE_UNSIGNED_32BIT,
    EEC_SIGNAL_TYPE_SIGNED_32BIT,
    EEC_SIGNAL_TYPE_UNSIGNED_64BIT,
    EEC_SIGNAL_TYPE_SIGNED_64BIT,
    EEC_SIGNAL_TYPE_FLOAT_32BIT,
    EEC_SIGNAL_TYPE_FLOAT_64BIT,
    EEC_SIGNAL_TYPE_RESERVED
} EEC_SignalType_t;

/** @brief Electrical or communication interface used for routing a signal to a pin. */
typedef enum EEC_SignalInterface_e {
    EEC_SIGNAL_INTERFACE_DIGITAL = 0,
    EEC_SIGNAL_INTERFACE_ANALOG,
    EEC_SIGNAL_INTERFACE_PWM,
    EEC_SIGNAL_INTERFACE_CAN,
    EEC_SIGNAL_INTERFACE_LIN,
    EEC_SIGNAL_INTERFACE_SENT,
    EEC_SIGNAL_INTERFACE_ETHERNET,
    EEC_SIGNAL_INTERFACE_RESISTANCE,  /**< Resistive sensor (NTC/PTC/potentiometer with excitation). */
    EEC_SIGNAL_INTERFACE_FREQUENCY,   /**< Frequency/period measurement (VR, Hall). */
    EEC_SIGNAL_INTERFACE_CURRENT,     /**< Current loop sensor (4–20 mA). */
    EEC_SIGNAL_INTERFACE_FLEXRAY,     /**< FlexRay differential bus. */
    EEC_SIGNAL_INTERFACE_POWER,
    EEC_SIGNAL_INTERFACE_GROUND,
    EEC_SIGNAL_INTERFACE_RESERVED
} EEC_SignalInterface_t;


/** @brief Electrical or communication interface used for routing a signal to a pin. */
typedef enum EEC_PinInterface_e {
    EEC_PIN_INTERFACE_DIGITAL = 0,
    EEC_PIN_INTERFACE_ANALOG,
    EEC_PIN_INTERFACE_PWM,
    EEC_PIN_INTERFACE_CAN,
    EEC_PIN_INTERFACE_LIN,
    EEC_PIN_INTERFACE_SENT,
    EEC_PIN_INTERFACE_ETHERNET,
    EEC_PIN_INTERFACE_RESISTANCE,  /**< Resistive sensor (NTC/PTC/potentiometer with excitation). */
    EEC_PIN_INTERFACE_FREQUENCY,   /**< Frequency/period measurement (VR, Hall). */
    EEC_PIN_INTERFACE_CURRENT,     /**< Current loop sensor (4–20 mA). */
    EEC_PIN_INTERFACE_FLEXRAY,     /**< FlexRay differential bus. */
    EEC_PIN_INTERFACE_POWER,
    EEC_PIN_INTERFACE_GROUND,
    EEC_PIN_INTERFACE_RESERVED
} EEC_PinInterface_t;

/** @brief Engineering unit of a signal. */
typedef enum EEC_SignalUnit_e {
    EEC_SIGNAL_UNIT_NONE = 0,
    EEC_SIGNAL_UNIT_BOOLEAN,
    EEC_SIGNAL_UNIT_VOLT,
    EEC_SIGNAL_UNIT_AMPERE,
    EEC_SIGNAL_UNIT_HERTZ,
    EEC_SIGNAL_UNIT_PERCENT,
    EEC_SIGNAL_UNIT_RPM,
    EEC_SIGNAL_UNIT_CELSIUS,
    EEC_SIGNAL_UNIT_BAR,
    EEC_SIGNAL_UNIT_DEGREE
} EEC_SignalUnit_t;

/** @brief Logical role of a pin. */
typedef enum EEC_PinRole_e {
    EEC_PIN_ROLE_INPUT = 0,
    EEC_PIN_ROLE_OUTPUT,
    EEC_PIN_ROLE_INOUT,
    EEC_PIN_ROLE_SUPPLY,
    EEC_PIN_ROLE_GROUND,
    EEC_PIN_ROLE_UNASSIGNED
} EEC_PinRole_t;

/** @brief Device type classification. */
typedef enum EEC_DeviceType_e {
    EEC_DEVICE_SENSOR = 0,
    EEC_DEVICE_ACTUATOR,
    EEC_DEVICE_GATEWAY
} EEC_DeviceType_t;

/** @brief Relative urgency used to prioritize framework objects. */
typedef enum EEC_ObjectPriority_e {
    EEC_PRIORITY_LOW = 0,
    EEC_PRIORITY_MEDIUM,
    EEC_PRIORITY_HIGH,
    EEC_PRIORITY_CRITICAL
} EEC_ObjectPriority_t;

/** @brief Safety classification applied to framework objects (ISO 25119 AgPL). */
typedef enum EEC_SafetyClass_e {
    EEC_SAFETY_QM = 0,
    EEC_SAFETY_AGPL_A,
    EEC_SAFETY_AGPL_B,
    EEC_SAFETY_AGPL_C,
    EEC_SAFETY_AGPL_D
} EEC_SafetyClass_t;

#ifndef EEC_SAFETY_RELATED
#define EEC_SAFETY_RELATED EEC_SAFETY_AGPL_A
#endif


/** @brief System-level classification used on AM systems. */
typedef enum EEC_SystemLevel_e {
    EEC_SYSTEM_LEVEL_SL0 = 0,
    EEC_SYSTEM_LEVEL_SL1,
    EEC_SYSTEM_LEVEL_SL2,
    EEC_SYSTEM_LEVEL_SL3,
    EEC_SYSTEM_LEVEL_SL4
} EEC_SystemLevel_t;

/** @brief Bus communication type. */
typedef enum EEC_BusType_e {
    EEC_BUS_TYPE_CAN = 0,
    EEC_BUS_TYPE_ISOBUS,
    EEC_BUS_TYPE_LIN,
    EEC_BUS_TYPE_ETHERNET,
    EEC_BUS_TYPE_FLEXRAY,
    EEC_BUS_TYPE_CUSTOM
} EEC_BusType_t;

/** @brief Electrical property flags shared by ECU pin capabilities and
 *  device pin requirements.  Used as a bitmask. */
typedef enum EEC_ElectricalFlag_e {
    EEC_ELEC_NONE           = 0U,
    EEC_ELEC_PULLUP         = 1U << 0,  /**< Internal pull-up resistor. */
    EEC_ELEC_PULLDOWN       = 1U << 1,  /**< Internal pull-down resistor. */
    EEC_ELEC_HIGH_SIDE      = 1U << 2,  /**< High-side driver / sourcing. */
    EEC_ELEC_LOW_SIDE       = 1U << 3,  /**< Low-side driver / sinking. */
    EEC_ELEC_PUSH_PULL      = 1U << 4,  /**< Push-pull output stage. */
    EEC_ELEC_CURRENT_SENSE  = 1U << 5,  /**< Current measurement (4-20 mA). */
    EEC_ELEC_VOLTAGE_IN     = 1U << 6,  /**< High-impedance voltage input. */
    EEC_ELEC_DIFFERENTIAL   = 1U << 7   /**< Differential signaling (CAN, ETH). */
} EEC_ElectricalFlag_t;

/** @brief Diagnostics bit flags stored on a physical ECU pin. */
typedef enum EEC_DiagFlags_e {
    EEC_DIAG_NONE         = 0U,
    EEC_DIAG_OPEN_LOAD    = 1U << 0,
    EEC_DIAG_SHORT_GND    = 1U << 1,
    EEC_DIAG_SHORT_BAT    = 1U << 2,
    EEC_DIAG_RANGE_CHECK  = 1U << 3,
    EEC_DIAG_OVERCURRENT  = 1U << 4,
    EEC_DIAG_THERMAL_WARN = 1U << 5,
    EEC_DIAG_LINE_BREAK   = 1U << 6,
    EEC_DIAG_PLAUSIBILITY = 1U << 7
} EEC_DiagFlags_t;

/** @brief Ground pin classification — prevents power/logic ground mixing. */
typedef enum EEC_GroundClass_e {
    EEC_GND_UNCLASSIFIED = 0,   /**< No classification (legacy, accepts any). */
    EEC_GND_POWER,              /**< Power ground — for actuators, motors, valves. */
    EEC_GND_LOGIC               /**< Logic/signal ground — for sensors, ADC references. */
} EEC_GroundClass_t;

/** @brief Reset/safe-state for an ECU output pin. */
typedef enum EEC_ResetState_e {
    EEC_RESET_OFF = 0,          /**< Output OFF at reset (default safe). */
    EEC_RESET_ON,               /**< Output ON at reset. */
    EEC_RESET_HIGH_Z            /**< High-impedance at reset. */
} EEC_ResetState_t;

/** @brief Digital input structure for automatic pull-up/pull-down inference. */
typedef enum EEC_DigitalStructure_e {
    EEC_DIGITAL_STRUCTURE_UNSPECIFIED = 0,
    EEC_DIGITAL_STRUCTURE_FLOATING,
    EEC_DIGITAL_STRUCTURE_PULLUP,
    EEC_DIGITAL_STRUCTURE_PULLDOWN
} EEC_DigitalStructure_t;

/** @brief Connector housing manufacturer family. */
typedef enum EEC_ConnectorFamily_e {
    EEC_CONNECTOR_FAMILY_DEUTSCH = 0,       /**< Deutsch (TE Connectivity) series. */
    EEC_CONNECTOR_FAMILY_AMP_SUPERSEAL,     /**< AMP Superseal series. */
    EEC_CONNECTOR_FAMILY_MOLEX,             /**< Molex series. */
    EEC_CONNECTOR_FAMILY_TE_CONNECTIVITY,   /**< TE Connectivity general. */
    EEC_CONNECTOR_FAMILY_YAZAKI,            /**< Yazaki series. */
    EEC_CONNECTOR_FAMILY_JAE,               /**< JAE series. */
    EEC_CONNECTOR_FAMILY_AMPSEAL,           /**< Ampseal series. */
    EEC_CONNECTOR_FAMILY_CUSTOM             /**< Custom / other family. */
} EEC_ConnectorFamily_t;

/** @brief Connector plug gender. */
typedef enum EEC_ConnectorGender_e {
    EEC_CONNECTOR_GENDER_MALE = 0,   /**< Male (plug / header). */
    EEC_CONNECTOR_GENDER_FEMALE,     /**< Female (receptacle / socket). */
    EEC_CONNECTOR_GENDER_HYBRID      /**< Hybrid (mixed pin/socket cavities). */
} EEC_ConnectorGender_t;

/** @brief Power supply / power group types provided by AGCO AEC hardware.
 *  Values derived from the AEC ECU datasheet sensor-supply table and
 *  the TRM30 power group definitions. Use `EEC_SUPPLY_UNKNOWN` when
 *  the supply cannot be determined.
 */
typedef enum EEC_SupplyGROUPType_e {
    EEC_SUPPLY_TRM30_G1 = 0,            /**< TRM30_G1 — Main logic / MCU power group. */
    EEC_SUPPLY_TRM30_G2,                /**< TRM30_G2 — Redundant logic / sensor supply. */
    EEC_SUPPLY_TRM30_G3,                /**< TRM30_G3 — Power outputs group G3. */
    EEC_SUPPLY_TRM30_G4,                /**< TRM30_G4 — Power outputs group G4. */
    EEC_SUPPLY_TRM30_G5,                /**< TRM30_G5 — Power outputs group G5. */
    EEC_SUPPLY_TRM30_G6,                /**< TRM30_G6 — Power outputs group G6. */
    EEC_SUPPLY_UNKNOWN                  /**< Unknown / not applicable. */
} EEC_SupplyGROUPType_t;

/** @brief Named sensor supply outputs (as printed in the AEC datasheet). */
typedef enum EEC_SensorSupplyType_e {
    EEC_SUPPLY_OUT_SUP_ANA_5V_01,       /**< OUT_SUP_ANA_5V_01 */
    EEC_SUPPLY_OUT_SUP_ANA_8V5_10V_01,  /**< OUT_SUP_ANA_8V5_10V_01 */
    EEC_SUPPLY_OUT_SUP_ANA_8V5_10V_02,  /**< OUT_SUP_ANA_8V5_10V_02 */
    EEC_BATT_SUPPLY,                    /**< Battery / VBAT (alias). */
    EEC_SENSOR_SUPPLY,                  /**< Generic sensor supply (alias). */
    EEC_SENSOR_SUPPLY_UNKNOWN           /**< Unknown / not applicable. */
} EEC_SensorSupplyType_t;

/** @brief Dedicated sensor ground / return names. */
typedef enum EEC_SensorGroundType_e {
    EEC_SUPPLY_OUT_SUP_ANA_8V5_10V_01_GND,/**< OUT_SUP_ANA_8V5_10V_01_GND */
    EEC_SUPPLY_OUT_SUP_ANA_5V_01_GND,     /**< OUT_SUP_ANA_5V_01_GND */
    EEC_SUPPLY_OUT_SUP_ANA_8V5_10V_02_GND,/**< OUT_SUP_ANA_8V5_10V_02_GND */
    EEC_SUPPLY_BATT_GND,                  /**< Battery ground (alias). */
    EEC_SENSOR_GND,                       /**< Generic sensor ground (alias). */
    EEC_SENSOR_GROUND_UNKNOWN             /**< Unknown / not applicable. */
} EEC_SensorGroundType_t;

/* --- Sensor supply / ground helpers --- */
/** Convert a sensor supply enum to a display string (datasheet naming). */
const char *EEC_SensorSupply_ToString(EEC_SensorSupplyType_t s);
/** Parse a supply name from a datasheet/JSON string into the enum. */
EEC_SensorSupplyType_t EEC_SensorSupply_Parse(const char *str);

/** Convert a sensor ground enum to a display string. */
const char *EEC_SensorGround_ToString(EEC_SensorGroundType_t g);
/** Parse a ground name from a datasheet/JSON string into the enum. */
EEC_SensorGroundType_t EEC_SensorGround_Parse(const char *str);


/** @brief Convert a payload type enum value to a short display string.
 *  @param type Payload type to convert.
 *  @return Constant string such as U8, S16, or F32.
 */
const char *EEC_Signal_TypeString(EEC_SignalType_t type);

/** @brief Return the nominal bit width of one payload type.
 *  @param type Payload type to inspect.
 *  @return Number of bits used by the payload, or 0 for reserved/unknown values.
 */
uint32_t EEC_Signal_TypeBitWidth(EEC_SignalType_t type);

/** @brief Tell whether a payload type carries signed numeric values.
 *  @param type Payload type to inspect.
 *  @return true for signed integer and floating-point types, false otherwise.
 */
bool EEC_Signal_TypeIsSigned(EEC_SignalType_t type);

/** @brief Convert an interface enum value to a display string.
 *  @param interface_type Electrical or communication interface to convert.
 *  @return Constant string representation of the interface.
 */
const char *EEC_Signal_InterfaceString(EEC_SignalInterface_t interface_type);

/** @brief Convert an engineering unit enum value to a display string.
 *  @param unit Engineering unit to convert.
 *  @return Constant string representation of the unit.
 */
const char *EEC_Signal_UnitString(EEC_SignalUnit_t unit);

/** @brief Convert a logical pin role enum value to a display string.
 *  @param role Pin role to convert.
 *  @return Constant string representation of the role.
 */
const char *EEC_Pin_RoleString(EEC_PinRole_t role);

/** @brief Convert a device classification enum value to a display string.
 *  @param type Device classification to convert.
 *  @return Constant string representation of the device type.
 */
const char *EEC_Device_TypeString(EEC_DeviceType_t type);

/** @brief Convert an object priority enum value to a display string.
 *  @param priority Object priority to convert.
 *  @return Constant string representation such as LOW or CRITICAL.
 */
const char *EEC_Priority_String(EEC_ObjectPriority_t priority);

/** @brief Convert a safety classification enum value to a display string.
 *  @param safety Safety classification to convert.
 *  @return Constant string representation such as QM or SAFETY_RELATED.
 */
const char *EEC_Safety_String(EEC_SafetyClass_t safety);

/** @brief Convert a system-level enum value to a display string.
 *  @param level System level to convert.
 *  @return Constant string representation such as SL0 or SL3.
 */
const char *EEC_System_LevelString(EEC_SystemLevel_t level);

/** @brief Return default electrical requirement flags for a given interface and role.
 *  @param iface Signal interface type.
 *  @param role Pin role (INPUT, OUTPUT, INOUT, etc.).
 *  @return Bitmask of EEC_ElectricalFlag_t values representing sensible defaults.
 */
uint32_t EEC_ElectricalDefaultRequirement(EEC_SignalInterface_t iface, EEC_PinRole_t role);

/** @brief Map a signal interface to the routing capability bit used by ECU pins.
 *  @param interface_type Electrical or communication interface to map.
 *  @return Capability mask bit for that interface, or 0 when unsupported.
 */
uint32_t EEC_Signal_InterfaceToCapability(EEC_SignalInterface_t interface_type);

/** @brief Convert a bus type enum value to a display string.
 *  @param type Bus type to convert.
 *  @return Constant string such as CAN, ISOBUS, or ETHERNET.
 */
const char *EEC_Bus_TypeString(EEC_BusType_t type);

/** @brief Parse a bus type display string into the matching enum value.
 *  @param str String to parse (e.g. "CAN", "ISOBUS").
 *  @return Matching enum value, or EEC_BUS_TYPE_CUSTOM for unknown strings.
 */
EEC_BusType_t EEC_Bus_ParseType(const char *str);

/** @brief Convert a connector family enum value to a display string.
 *  @param family Connector family to convert.
 *  @return Constant string such as DEUTSCH, MOLEX, etc.
 */
const char *EEC_Connector_FamilyString(EEC_ConnectorFamily_t family);

/** @brief Parse a connector family display string into the matching enum value.
 *  @param str String to parse.
 *  @return Matching enum value, or EEC_CONNECTOR_FAMILY_CUSTOM for unknown strings.
 */
EEC_ConnectorFamily_t EEC_Connector_ParseFamily(const char *str);

/** @brief Convert a connector gender enum value to a display string.
 *  @param gender Connector gender to convert.
 *  @return Constant string such as MALE, FEMALE, HYBRID.
 */
const char *EEC_Connector_GenderString(EEC_ConnectorGender_t gender);

/** @brief Parse a connector gender display string into the matching enum value.
 *  @param str String to parse.
 *  @return Matching enum value, or EEC_CONNECTOR_GENDER_MALE for unknown strings.
 */
EEC_ConnectorGender_t EEC_Connector_ParseGender(const char *str);

/** @brief Check whether a bus type is compatible with a signal interface.
 *  @param bus_type  Bus type.
 *  @param iface     Signal interface type.
 *  @return true when the signal interface can be routed on the given bus.
 */
bool EEC_Bus_InterfaceCompatible(EEC_BusType_t bus_type, EEC_SignalInterface_t iface);

#ifdef __cplusplus
}
#endif
#endif
