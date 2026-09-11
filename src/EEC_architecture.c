/*
 * @file    EEC_architecture.c
 * @brief   E/E Architect Design — Architecture model creation and management.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */

#include "EEC_architecture.h"
#include "EEC_types.h"
#include "EEC_pin_helpers.h"
#include "EEC_message.h"
#include "EEC_log.h"
#include <stdlib.h>
#include <string.h>

// Infer digital structure for digital input signals if unspecified
static void eec_infer_digital_structure(EEC_Signal_t *signal, EEC_PinRole_t role) {
    if (!signal) return;
    if (signal->interface_type == EEC_SIGNAL_INTERFACE_DIGITAL && role == EEC_PIN_ROLE_INPUT) {
        if (signal->digital_structure == EEC_DIGITAL_STRUCTURE_UNSPECIFIED) {
            // Default to pull-up for safety, can be customized
            signal->digital_structure = EEC_DIGITAL_STRUCTURE_PULLUP;
        }
    }
}

typedef struct EEC_DeviceCommon_s {
    uint32_t id;
    uint8_t variant_id;
    bool obsolete;
    char name[64];
    char part_number[64];
    char supplier_pn[64];
    EEC_ObjectPriority_t priority;
    EEC_SafetyClass_t safety;
    EEC_System_t *owner_system;
    EEC_Architecture_t *owner_architecture;
    EEC_DevicePin_t *pins;
    uint32_t pin_count;
    uint32_t pin_capacity;
    EEC_Connector_t *connectors;

/*
 * ──────────────────────────────────────────────────────────────────────────────
 *  E/E Architect Design — Architecture Model Implementation
 *
 *  This file contains the core logic for creating, managing, and manipulating
 *  the in-memory representation of an embedded system architecture. It provides
 *  the data structures and functions for systems, devices, pins, signals, and
 *  their relationships, supporting the full workflow from construction to export.
 *
 *  Major responsibilities:
 *    - System, device, and pin creation and management
 *    - Signal instantiation and property assignment
 *    - Architecture-level validation and consistency checks
 *    - Helper routines for mapping, inference, and export
 *
 *  All objects are reference-linked for fast traversal and batch operations.
 *  This module is the backbone of the E/E Architect Design framework.
 * ──────────────────────────────────────────────────────────────────────────────
 */

/**
 * @brief Infer the digital structure (pull-up/pull-down) for digital input signals.
 *
 * If a signal is a digital input and its digital_structure is unspecified,
 * this function assigns a default (pull-up) for safety. This can be customized
 * by the user or downstream logic.
 *
 * @param signal Pointer to the signal to update.
 * @param role   Pin role (should be EEC_PIN_ROLE_INPUT for digital inputs).
 */
    uint32_t connector_count;
    uint32_t connector_capacity;
} EEC_DeviceCommon_t;

/** @brief Grow a pointer array until it can store @p needed elements. */
static int eec_reserve_ptr_array(void ***array, uint32_t *capacity, uint32_t needed)
{
    void **tmp;
    uint32_t new_capacity = (*capacity == 0U) ? 8U : *capacity;
    while (new_capacity < needed) {
        new_capacity *= 2U;
    }
    tmp = (void **)realloc(*array, new_capacity * sizeof(void *));
    if (!tmp) {
        return -1;
    }
    *array = tmp;
    *capacity = new_capacity;
    return 0;
}

static void eec_copy_string(char *dest, size_t dest_size, const char *src)
{
    size_t copy_len;
    if (!dest || dest_size == 0U) {
        return;
    }
    if (!src) {
        dest[0] = '\0';
        return;
    }

    copy_len = strlen(src);
    if (copy_len >= dest_size) {
        copy_len = dest_size - 1U;
    }
    memcpy(dest, src, copy_len);
    dest[copy_len] = '\0';
}

static EEC_DevicePin_t *eec_device_create_pin_common(EEC_DeviceCommon_t *device, uint32_t number, EEC_PinRole_t role, EEC_Signal_t *signal, EEC_PinInterface_t interface_type, const char *name)
{
    EEC_DevicePin_t *tmp;
    uint32_t cap;
    if (!device) {
        return NULL;
    }

    cap = (device->pin_capacity == 0U) ? 8U : device->pin_capacity;
    while (cap < device->pin_count + 1U) {
        cap *= 2U;
    }
    if (cap != device->pin_capacity) {
        tmp = (EEC_DevicePin_t *)realloc(device->pins, cap * sizeof(EEC_DevicePin_t));
        if (!tmp) {
            return NULL;
        }
        device->pins = tmp;
        device->pin_capacity = cap;
    }

    tmp = &device->pins[device->pin_count++];
    memset(tmp, 0, sizeof(*tmp));
    tmp->id = EEC_ID_MAKE(device->owner_architecture->ids.next_device_pin_id++, 0U);
    tmp->number = number;
    tmp->role = role;
    {
        EEC_SignalInterface_t effective_iface = EEC_SIGNAL_INTERFACE_RESERVED;
        if (interface_type != EEC_PIN_INTERFACE_RESERVED) {
            effective_iface = (EEC_SignalInterface_t)interface_type;
        } else if (signal) {
            effective_iface = signal->interface_type;
        }
        tmp->electrical_requirement = (effective_iface != EEC_SIGNAL_INTERFACE_RESERVED)
            ? EEC_ElectricalDefaultRequirement(effective_iface, role)
            : 0U;
        tmp->interface_type = (interface_type != EEC_PIN_INTERFACE_RESERVED)
            ? interface_type
            : (signal ? (EEC_PinInterface_t)signal->interface_type : EEC_PIN_INTERFACE_RESERVED);
    }
    tmp->signal = signal;
    eec_copy_string(tmp->name, sizeof(tmp->name), name);


    // Infer digital structure for digital input signals
    if (signal) {
        eec_infer_digital_structure(signal, role);
    }

    EEC_Log_Printf(EEC_LOG_TRACE, "Created device pin #%u '%s/%u'", tmp->id, device->name, tmp->number);
    return tmp;
}

static EEC_Connector_t *eec_device_create_connector_common(
    EEC_DeviceCommon_t *device,
    const char *name,
    const char *part_number,
    EEC_ConnectorFamily_t family,
    EEC_ConnectorGender_t gender,
    uint8_t total_cavities
)
{
    EEC_Connector_t *con;
    EEC_Connector_t *tmp;
    uint32_t cap;
    if (!device || !name) {
        return NULL;
    }

    cap = (device->connector_capacity == 0U) ? 4U : device->connector_capacity;
    while (cap < device->connector_count + 1U) {
        cap *= 2U;
    }
    if (cap != device->connector_capacity) {
        tmp = (EEC_Connector_t *)realloc(device->connectors, cap * sizeof(EEC_Connector_t));
        if (!tmp) {
            return NULL;
        }
        device->connectors = tmp;
        device->connector_capacity = cap;
    }

    con = &device->connectors[device->connector_count++];
    memset(con, 0, sizeof(*con));
    con->id = EEC_ID_MAKE(device->owner_architecture->ids.next_connector_id++, 0U);
    eec_copy_string(con->name, sizeof(con->name), name);
    if (part_number) {
        eec_copy_string(con->part_number, sizeof(con->part_number), part_number);
    }
    con->family = family;
    con->gender = gender;
    con->total_cavities = total_cavities;
    con->used_cavities = 0U;
    con->sealed = false;
    con->rated_voltage = 0.0f;
    con->rated_current = 0.0f;
    con->temperature_min = -40.0f;
    con->temperature_max = 125.0f;

    EEC_Log_Printf(EEC_LOG_TRACE, "Created connector #%u '%s' on '%s'", con->id, con->name, device->name);
    return con;
}

EEC_Connector_t *EEC_Sensor_CreateConnector(
    EEC_Sensor_t *sensor,
    const char *name,
    const char *part_number,
    EEC_ConnectorFamily_t family,
    EEC_ConnectorGender_t gender,
    uint8_t total_cavities
)
{
    return eec_device_create_connector_common((EEC_DeviceCommon_t *)sensor, name, part_number, family, gender, total_cavities);
}

EEC_Connector_t *EEC_Actuator_CreateConnector(
    EEC_Actuator_t *actuator,
    const char *name,
    const char *part_number,
    EEC_ConnectorFamily_t family,
    EEC_ConnectorGender_t gender,
    uint8_t total_cavities
)
{
    return eec_device_create_connector_common((EEC_DeviceCommon_t *)actuator, name, part_number, family, gender, total_cavities);
}

EEC_Architecture_t *EEC_Architecture_Create(const char *name)
{
    EEC_Architecture_t *arch = (EEC_Architecture_t *)calloc(1U, sizeof(EEC_Architecture_t));
    if (!arch) {
        return NULL;
    }

    /* Initialize ID generators. */
    arch->id = EEC_ID_MAKE(1U, 0U);
    arch->ids.next_architecture_id = 2U;
    arch->ids.next_signal_id = 1U;
    arch->ids.next_system_id = 1U;
    arch->ids.next_component_id = 1U;
    arch->ids.next_device_id = 1U;
    arch->ids.next_device_pin_id = 1U;
    arch->ids.next_ecu_id = 1U;
    arch->ids.next_ecu_pin_id = 1U;
    arch->ids.next_bus_id = 1U;
    arch->ids.next_connector_id = 1U;
    arch->priority = EEC_PRIORITY_LOW;
    arch->safety = EEC_SAFETY_QM;

    EEC_Architecture_SetName(arch, name ? name : "Architecture");
    EEC_Log_Printf(EEC_LOG_INFO, "Created architecture '%s'", arch->name);
    return arch;
}

void EEC_Architecture_SetName(EEC_Architecture_t *arch, const char *name)
{
    if (!arch || !name) {
        return;
    }
    strncpy(arch->name, name, sizeof(arch->name) - 1U);
    arch->name[sizeof(arch->name) - 1U] = '\0';
}

EEC_Signal_t *EEC_Architecture_CreateSignalEx(
    EEC_Architecture_t *arch,
    const char *name,
    EEC_SignalType_t type,
    EEC_SignalInterface_t interface_type,
    EEC_SignalUnit_t unit,
    float min_value,
    float max_value,
    float resolution,
    float scaling
)
{
    EEC_Signal_t *signal;
    if (!arch || !name) {
        return NULL;
    }

    signal = (EEC_Signal_t *)calloc(1U, sizeof(EEC_Signal_t));
    if (!signal) {
        return NULL;
    }

    signal->id = EEC_ID_MAKE(arch->ids.next_signal_id++, 0U);
    strncpy(signal->name, name, sizeof(signal->name) - 1U);
    signal->priority = EEC_PRIORITY_LOW;
    signal->safety = EEC_SAFETY_QM;
    signal->type = type;
    signal->interface_type = interface_type;
    signal->unit = unit;
    signal->min_value = min_value;
    signal->max_value = max_value;
    signal->resolution = resolution;
    signal->scaling = scaling;
    signal->owner_architecture = arch;

    if (eec_reserve_ptr_array((void ***)&arch->signals, &arch->signal_capacity, arch->signal_count + 1U) != 0) {
        free(signal);
        return NULL;
    }

    arch->signals[arch->signal_count++] = signal;
    EEC_Log_Printf(EEC_LOG_TRACE, "Registered signal #%u '%s'", signal->id, signal->name);
    return signal;
}

EEC_System_t *EEC_Architecture_CreateSystem(EEC_Architecture_t *arch, const char *name)
{
    EEC_System_t *system;
    if (!arch || !name) {
        return NULL;
    }

    system = (EEC_System_t *)calloc(1U, sizeof(EEC_System_t));
    if (!system) {
        return NULL;
    }

    system->id = EEC_ID_MAKE(arch->ids.next_system_id++, 0U);
    system->variant_id = 0U;
    strncpy(system->name, name, sizeof(system->name) - 1U);
    system->ref_2x[0] = '\0';
    system->system_level = EEC_SYSTEM_LEVEL_SL0;
    system->priority = EEC_PRIORITY_LOW;
    system->safety = EEC_SAFETY_QM;
    system->is_mandatory = true;
    system->auto_mapping_enabled = true;
    system->owner_architecture = arch;

    if (eec_reserve_ptr_array((void ***)&arch->systems, &arch->system_capacity, arch->system_count + 1U) != 0) {
        free(system);
        return NULL;
    }

    arch->systems[arch->system_count++] = system;
    EEC_Log_Printf(EEC_LOG_TRACE, "Created system #%u '%s'", system->id, system->name);
    return system;
}

EEC_Component_t *EEC_System_CreateComponent(EEC_System_t *system, const char *name)
{
    EEC_Component_t *comp;
    if (!system || !system->owner_architecture || !name) {
        return NULL;
    }

    comp = (EEC_Component_t *)calloc(1U, sizeof(EEC_Component_t));
    if (!comp) {
        return NULL;
    }

    comp->id = EEC_ID_MAKE(system->owner_architecture->ids.next_component_id++, 0U);
    comp->variant_id = 0U;
    eec_copy_string(comp->name, sizeof(comp->name), name);
    comp->ref_2x[0] = '\0';
    comp->description[0] = '\0';
    comp->supplier[0] = '\0';
    comp->location[0] = '\0';
    comp->priority = EEC_PRIORITY_LOW;
    comp->safety = EEC_SAFETY_QM;
    comp->owner_system = system;
    comp->owner_architecture = system->owner_architecture;

    if (eec_reserve_ptr_array((void ***)&system->components, &system->component_capacity, system->component_count + 1U) != 0) {
        free(comp);
        return NULL;
    }

    system->components[system->component_count++] = comp;
    EEC_Log_Printf(EEC_LOG_TRACE, "Created component #%u '%s' on system '%s'", comp->id, comp->name, system->name);
    return comp;
}

EEC_Sensor_t *EEC_Component_CreateSensor(EEC_Component_t *component, const char *name)
{
    EEC_Sensor_t *sensor;
    if (!component || !component->owner_architecture || !name) {
        return NULL;
    }

    sensor = (EEC_Sensor_t *)calloc(1U, sizeof(EEC_Sensor_t));
    if (!sensor) {
        return NULL;
    }

    sensor->id = EEC_ID_MAKE(component->owner_architecture->ids.next_device_id++, 0U);
    sensor->variant_id = 0U;
    eec_copy_string(sensor->name, sizeof(sensor->name), name);
    sensor->priority = EEC_PRIORITY_LOW;
    sensor->safety = EEC_SAFETY_QM;
    sensor->is_mandatory = false;
    sensor->mapping_enabled = true;
    sensor->owner_system = component->owner_system;
    sensor->owner_architecture = component->owner_architecture;

    if (eec_reserve_ptr_array((void ***)&component->sensors, &component->sensor_capacity, component->sensor_count + 1U) != 0) {
        free(sensor);
        return NULL;
    }

    component->sensors[component->sensor_count++] = sensor;
    EEC_Log_Printf(EEC_LOG_TRACE, "Created sensor #%u '%s' on component '%s'", sensor->id, sensor->name, component->name);
    return sensor;
}

EEC_Actuator_t *EEC_Component_CreateActuator(EEC_Component_t *component, const char *name)
{
    EEC_Actuator_t *actuator;
    if (!component || !component->owner_architecture || !name) {
        return NULL;
    }

    actuator = (EEC_Actuator_t *)calloc(1U, sizeof(EEC_Actuator_t));
    if (!actuator) {
        return NULL;
    }

    actuator->id = EEC_ID_MAKE(component->owner_architecture->ids.next_device_id++, 0U);
    actuator->variant_id = 0U;
    eec_copy_string(actuator->name, sizeof(actuator->name), name);
    actuator->priority = EEC_PRIORITY_LOW;
    actuator->safety = EEC_SAFETY_QM;
    actuator->is_mandatory = false;
    actuator->mapping_enabled = true;
    actuator->owner_system = component->owner_system;
    actuator->owner_architecture = component->owner_architecture;

    if (eec_reserve_ptr_array((void ***)&component->actuators, &component->actuator_capacity, component->actuator_count + 1U) != 0) {
        free(actuator);
        return NULL;
    }

    component->actuators[component->actuator_count++] = actuator;
    EEC_Log_Printf(EEC_LOG_TRACE, "Created actuator #%u '%s' on component '%s'", actuator->id, actuator->name, component->name);
    return actuator;
}

EEC_DevicePin_t *EEC_Sensor_CreatePin(EEC_Sensor_t *sensor, uint32_t number, EEC_PinRole_t role, EEC_Signal_t *signal, EEC_PinInterface_t interface_type, const char *name)
{
    return eec_device_create_pin_common((EEC_DeviceCommon_t *)sensor, number, role, signal, interface_type, name);
}

EEC_DevicePin_t *EEC_Actuator_CreatePin(EEC_Actuator_t *actuator, uint32_t number, EEC_PinRole_t role, EEC_Signal_t *signal, EEC_PinInterface_t interface_type, const char *name)
{
    return eec_device_create_pin_common((EEC_DeviceCommon_t *)actuator, number, role, signal, interface_type, name);
}

/* ── Backward-compatibility wrappers ──────────────────────────────────── */

static EEC_Component_t *get_or_create_default_component(EEC_System_t *system)
{
    uint32_t i;
    for (i = 0; i < system->component_count; ++i) {
        if (strcmp(system->components[i]->name, "Default") == 0) {
            return system->components[i];
        }
    }
    return EEC_System_CreateComponent(system, "Default");
}

EEC_Sensor_t *EEC_System_CreateSensor(EEC_System_t *system, const char *name)
{
    EEC_Component_t *comp;
    if (!system) { return NULL; }
    comp = get_or_create_default_component(system);
    if (!comp) { return NULL; }
    return EEC_Component_CreateSensor(comp, name);
}

EEC_Actuator_t *EEC_System_CreateActuator(EEC_System_t *system, const char *name)
{
    EEC_Component_t *comp;
    if (!system) { return NULL; }
    comp = get_or_create_default_component(system);
    if (!comp) { return NULL; }
    return EEC_Component_CreateActuator(comp, name);
}

bool EEC_System_AddPlatform(EEC_System_t *system, const char *platform)
{
    uint32_t i;
    if (!system || !platform || platform[0] == '\0') { return false; }
    if (system->platform_count >= EEC_SYSTEM_MAX_PLATFORMS) { return false; }
    for (i = 0; i < system->platform_count; ++i) {
        if (strcmp(system->platforms[i], platform) == 0) { return false; }
    }
    eec_copy_string(system->platforms[system->platform_count], sizeof(system->platforms[0]), platform);
    system->platform_count++;
    return true;
}

bool EEC_System_AddBrand(EEC_System_t *system, EEC_Brand_t brand)
{
    uint32_t i;
    if (!system || (uint32_t)brand >= (uint32_t)EEC_BRAND_COUNT) { return false; }
    if (system->brand_count >= EEC_SYSTEM_MAX_BRANDS) { return false; }
    for (i = 0; i < system->brand_count; ++i) {
        if (system->brands[i] == brand) { return false; }
    }
    system->brands[system->brand_count++] = brand;
    return true;
}

const char *EEC_Brand_ToString(EEC_Brand_t brand)
{
    switch (brand) {
        case EEC_BRAND_FENDT:            return "Fendt";
        case EEC_BRAND_MASSEY_FERGUSON:  return "Massey Ferguson";
        case EEC_BRAND_VALTRA:           return "Valtra";
        default:                         return "Unknown";
    }
}

uint32_t EEC_System_GetPlatforms(const EEC_System_t *system, char out_platforms[][32], uint32_t max_count)
{
    uint32_t i, count;
    if (!system || !out_platforms || max_count == 0) { return 0; }
    count = system->platform_count < max_count ? system->platform_count : max_count;
    for (i = 0; i < count; ++i) {
        strncpy(out_platforms[i], system->platforms[i], 31);
        out_platforms[i][31] = '\0';
    }
    return count;
}

uint32_t EEC_System_GetBrands(const EEC_System_t *system, EEC_Brand_t *out_brands, uint32_t max_count)
{
    uint32_t i, count;
    if (!system || !out_brands || max_count == 0) { return 0; }
    count = system->brand_count < max_count ? system->brand_count : max_count;
    for (i = 0; i < count; ++i) {
        out_brands[i] = system->brands[i];
    }
    return count;
}

void EEC_System_PrintApplicability(const EEC_System_t *system)
{
    uint32_t i;
    if (!system) { return; }

    EEC_Log_Printf(EEC_LOG_INFO, "System '%s' applicability:", system->name);

    if (system->platform_count == 0) {
        EEC_Log_Write(EEC_LOG_INFO, "  Platforms: (none assigned)");
    } else {
        for (i = 0; i < system->platform_count; ++i) {
            EEC_Log_Printf(EEC_LOG_INFO, "  Platform[%u]: %s", i, system->platforms[i]);
        }
    }

    if (system->brand_count == 0) {
        EEC_Log_Write(EEC_LOG_INFO, "  Brands: (none assigned)");
    } else {
        for (i = 0; i < system->brand_count; ++i) {
            EEC_Log_Printf(EEC_LOG_INFO, "  Brand[%u]: %s", i, EEC_Brand_ToString(system->brands[i]));
        }
    }
}

EEC_Ecu_t *EEC_Architecture_CreateEcu(EEC_Architecture_t *arch, const char *name, const char *variant)
{
    EEC_Ecu_t *ecu;
    if (!arch || !name || !variant) {
        return NULL;
    }

    ecu = (EEC_Ecu_t *)calloc(1U, sizeof(EEC_Ecu_t));
    if (!ecu) {
        return NULL;
    }

    ecu->id = EEC_ID_MAKE(arch->ids.next_ecu_id++, 0U);
    ecu->variant_id = 0U;
    strncpy(ecu->name, name, sizeof(ecu->name) - 1U);
    strncpy(ecu->variant, variant, sizeof(ecu->variant) - 1U);
    ecu->priority = EEC_PRIORITY_LOW;
    ecu->safety = EEC_SAFETY_QM;
    ecu->owner_architecture = arch;

    if (eec_reserve_ptr_array((void ***)&arch->ecus, &arch->ecu_capacity, arch->ecu_count + 1U) != 0) {
        free(ecu);
        return NULL;
    }

    arch->ecus[arch->ecu_count++] = ecu;
    EEC_Log_Printf(EEC_LOG_TRACE, "Created ECU #%u '%s'", ecu->id, ecu->name);
    return ecu;
}

EEC_EcuPin_t *EEC_Ecu_CreatePin(
    EEC_Ecu_t *ecu,
    uint32_t physical_number,
    const char *connector_name,
    const char *name,
    const char *main_group,
    EEC_PinRole_t role,
    EEC_PinInterface_t interface_type,
    uint32_t supported_capability_mask,
    uint32_t diagnostic_flags,
    const char *electrical,
    const char *sw_config
)
{
    EEC_EcuPin_t *pin;
    EEC_EcuPin_t *tmp;
    uint32_t cap;

    if (!ecu || !connector_name || !name || !main_group) {
        return NULL;
    }

    cap = (ecu->pin_capacity == 0U) ? 16U : ecu->pin_capacity;
    while (cap < ecu->pin_count + 1U) {
        cap *= 2U;
    }
    if (cap != ecu->pin_capacity) {
        tmp = (EEC_EcuPin_t *)realloc(ecu->pins, cap * sizeof(EEC_EcuPin_t));
        if (!tmp) {
            return NULL;
        }
        ecu->pins = tmp;
        ecu->pin_capacity = cap;
    }

    pin = &ecu->pins[ecu->pin_count++];
    memset(pin, 0, sizeof(*pin));
    pin->id = EEC_ID_MAKE(ecu->owner_architecture->ids.next_ecu_pin_id++, 0U);
    pin->physical_number = physical_number;
    strncpy(pin->connector_name, connector_name, sizeof(pin->connector_name) - 1U);
    strncpy(pin->name, name, sizeof(pin->name) - 1U);
    strncpy(pin->main_group, main_group, sizeof(pin->main_group) - 1U);
    if (electrical) {
        strncpy(pin->electrical, electrical, sizeof(pin->electrical) - 1U);
    }
    if (sw_config) {
        strncpy(pin->sw_config, sw_config, sizeof(pin->sw_config) - 1U);
    }
    pin->role = role;
    pin->interface_type = interface_type;
    pin->supported_capability_mask = supported_capability_mask;
    pin->diagnostic_flags = diagnostic_flags;
    /* Default: no AgPL restriction unless explicitly set by ECU factory or import. */
    pin->max_agpl = EEC_AGPL_E;
    /* Populate provided_* fields (supply/ground/voltage/current) from
     * structured inputs or free-text parsing so programmatic creation and
     * importer behavior remain consistent. */
    EEC_Pin_PopulateProvidedFromData(pin, pin->name, pin->main_group, pin->electrical,
        NULL, 0.0f, 0.0f, NULL, NULL);
    return pin;
}

bool EEC_EcuPin_AddFunction(EEC_EcuPin_t *pin, const char *function_name)
{
    char **tmp;
    uint32_t cap;
    if (!pin || !function_name) {
        return false;
    }

    cap = (pin->function_capacity == 0U) ? 4U : pin->function_capacity;
    while (cap < pin->function_count + 1U) {
        cap *= 2U;
    }
    if (cap != pin->function_capacity) {
        tmp = (char **)realloc(pin->functions, cap * sizeof(char *));
        if (!tmp) {
            return false;
        }
        pin->functions = tmp;
        pin->function_capacity = cap;
    }

    const size_t fn_len = strlen(function_name);
    pin->functions[pin->function_count] = (char *)calloc(fn_len + 1U, 1U);
    if (!pin->functions[pin->function_count]) {
        return false;
    }
    memcpy(pin->functions[pin->function_count], function_name, fn_len + 1U);
    pin->function_count++;
    return true;
}

EEC_Connector_t *EEC_Ecu_CreateConnector(
    EEC_Ecu_t *ecu,
    const char *name,
    const char *part_number,
    EEC_ConnectorFamily_t family,
    EEC_ConnectorGender_t gender,
    uint8_t total_cavities
)
{
    EEC_Connector_t *con;
    EEC_Connector_t *tmp;
    uint32_t cap;
    if (!ecu || !name) {
        return NULL;
    }

    cap = (ecu->connector_capacity == 0U) ? 4U : ecu->connector_capacity;
    while (cap < ecu->connector_count + 1U) {
        cap *= 2U;
    }
    if (cap != ecu->connector_capacity) {
        tmp = (EEC_Connector_t *)realloc(ecu->connectors, cap * sizeof(EEC_Connector_t));
        if (!tmp) {
            return NULL;
        }
        ecu->connectors = tmp;
        ecu->connector_capacity = cap;
    }

    con = &ecu->connectors[ecu->connector_count++];
    memset(con, 0, sizeof(*con));
    con->id = EEC_ID_MAKE(ecu->owner_architecture->ids.next_connector_id++, 0U);
    eec_copy_string(con->name, sizeof(con->name), name);
    if (part_number) {
        eec_copy_string(con->part_number, sizeof(con->part_number), part_number);
    }
    con->family = family;
    con->gender = gender;
    con->total_cavities = total_cavities;
    con->used_cavities = 0U;
    con->sealed = false;
    con->rated_voltage = 0.0f;
    con->rated_current = 0.0f;
    con->temperature_min = -40.0f;
    con->temperature_max = 125.0f;

    EEC_Log_Printf(EEC_LOG_TRACE, "Created connector #%u '%s' on ECU '%s'", con->id, con->name, ecu->name);
    return con;
}

bool EEC_Ecu_AddCanAddress(EEC_Ecu_t *ecu, uint8_t address)
{
    uint8_t i;
    if (!ecu || ecu->can_address_count >= EEC_ECU_MAX_CAN_ADDRESSES) {
        return false;
    }
    for (i = 0U; i < ecu->can_address_count; ++i) {
        if (ecu->can_addresses[i] == address) {
            return false;
        }
    }
    ecu->can_addresses[ecu->can_address_count++] = address;
    return true;
}

bool EEC_Ecu_HasCanAddress(const EEC_Ecu_t *ecu, uint8_t address)
{
    uint8_t i;
    if (!ecu) {
        return false;
    }
    for (i = 0U; i < ecu->can_address_count; ++i) {
        if (ecu->can_addresses[i] == address) {
            return true;
        }
    }
    return false;
}

EEC_EcuPin_t *EEC_Ecu_FindPin(EEC_Ecu_t *ecu, const char *connector_name, uint32_t physical_number)
{
    uint32_t i;
    if (!ecu || !connector_name) {
        return NULL;
    }
    for (i = 0U; i < ecu->pin_count; ++i) {
        if (ecu->pins[i].physical_number == physical_number &&
            strcmp(ecu->pins[i].connector_name, connector_name) == 0) {
            return &ecu->pins[i];
        }
    }
    return NULL;
}

bool EEC_Ecu_IsPinCompatible(const EEC_EcuPin_t *pin, const EEC_Signal_t *signal)
{
    uint32_t mask;
    if (!pin || !signal) {
        return false;
    }
    /* GROUND pins can accept multiple connections; other pins are exclusive. */
    if (pin->is_occupied && pin->role != EEC_PIN_ROLE_GROUND) {
        return false;
    }
    mask = EEC_Signal_InterfaceToCapability(signal->interface_type);
    return (mask != 0U) && ((pin->supported_capability_mask & mask) != 0U);
}

bool EEC_Ecu_ConnectSignalToPin(EEC_Ecu_t *ecu, const char *connector_name, uint32_t physical_number, EEC_Signal_t *signal)
{
    EEC_EcuPin_t *pin = EEC_Ecu_FindPin(ecu, connector_name, physical_number);
    if (!pin || !signal) {
        return false;
    }
    if (!EEC_Ecu_IsPinCompatible(pin, signal)) {
        return false;
    }
    pin->connected_signal = signal;
    signal->is_mapped = true;

    /* GROUND pins can accept multiple device connections (star topology). */
    if (pin->role == EEC_PIN_ROLE_GROUND) {
        pin->gnd_connect_count++;
        pin->is_occupied = true; /* Mark occupied but mapping still allows more. */
    } else {
        pin->is_occupied = true;
    }
    return true;
}

/* ══════════════════════════════════════════════════════════════════════════
 *  Bus API
 * ══════════════════════════════════════════════════════════════════════════ */

EEC_Bus_t *EEC_Architecture_CreateBus(EEC_Architecture_t *arch, const char *name, EEC_BusType_t type)
{
    EEC_Bus_t *bus;
    if (!arch || !name) {
        return NULL;
    }

    bus = (EEC_Bus_t *)calloc(1U, sizeof(EEC_Bus_t));
    if (!bus) {
        return NULL;
    }

    bus->id = EEC_ID_MAKE(arch->ids.next_bus_id++, 0U);
    eec_copy_string(bus->name, sizeof(bus->name), name);
    bus->ref_2x[0] = '\0';
    bus->type = type;
    bus->bitrate = 0U;
    bus->priority = EEC_PRIORITY_LOW;
    bus->safety = EEC_SAFETY_QM;
    bus->owner_architecture = arch;

    if (eec_reserve_ptr_array((void ***)&arch->buses, &arch->bus_capacity, arch->bus_count + 1U) != 0) {
        free(bus);
        return NULL;
    }

    arch->buses[arch->bus_count++] = bus;
    EEC_Log_Printf(EEC_LOG_TRACE, "Created bus #%u '%s' (%s)", bus->id, bus->name, EEC_Bus_TypeString(bus->type));
    return bus;
}

/** @brief Check if an ECU+port is already connected to ANY bus in the architecture. */
static EEC_Bus_t *eec_find_bus_for_ecu_port(const EEC_Architecture_t *arch, const EEC_Ecu_t *ecu, uint8_t port_index)
{
    uint32_t b, n;
    for (b = 0; b < arch->bus_count; ++b) {
        EEC_Bus_t *bus = arch->buses[b];
        if (!bus) continue;
        for (n = 0; n < bus->node_count; ++n) {
            if (bus->nodes[n].ecu == ecu && bus->nodes[n].port_index == port_index) {
                return bus;
            }
        }
    }
    return NULL;
}

int EEC_Bus_ConnectEcu(EEC_Bus_t *bus, EEC_Ecu_t *ecu, uint8_t port_index)
{
    EEC_BusNode_t *tmp;
    uint32_t cap, n;
    EEC_Bus_t *existing;

    if (!bus || !ecu || port_index == 0U || !bus->owner_architecture) {
        return -1;
    }

    /* Check if already on this bus */
    for (n = 0; n < bus->node_count; ++n) {
        if (bus->nodes[n].ecu == ecu && bus->nodes[n].port_index == port_index) {
            EEC_Log_Printf(EEC_LOG_WARN, "Bus '%s': ECU '%s' port %u already connected", bus->name, ecu->name, port_index);
            return -3;
        }
    }

    /* Check if port is on another bus */
    existing = eec_find_bus_for_ecu_port(bus->owner_architecture, ecu, port_index);
    if (existing) {
        EEC_Log_Printf(EEC_LOG_WARN, "Bus '%s': ECU '%s' port %u already on bus '%s'",
                       bus->name, ecu->name, port_index, existing->name);
        return -2;
    }

    /* Grow array */
    cap = (bus->node_capacity == 0U) ? 4U : bus->node_capacity;
    while (cap < bus->node_count + 1U) cap *= 2U;
    if (cap != bus->node_capacity) {
        tmp = (EEC_BusNode_t *)realloc(bus->nodes, cap * sizeof(EEC_BusNode_t));
        if (!tmp) return -1;
        bus->nodes = tmp;
        bus->node_capacity = cap;
    }

    bus->nodes[bus->node_count].ecu = ecu;
    bus->nodes[bus->node_count].port_index = port_index;
    bus->node_count++;

    EEC_Log_Printf(EEC_LOG_TRACE, "Bus '%s': connected ECU '%s' port %u", bus->name, ecu->name, port_index);
    return 0;
}

int EEC_Bus_AddSignal(EEC_Bus_t *bus, EEC_Signal_t *signal)
{
    uint32_t i;
    if (!bus || !signal) {
        return -1;
    }

    /* Interface compatibility */
    if (!EEC_Bus_InterfaceCompatible(bus->type, signal->interface_type)) {
        EEC_Log_Printf(EEC_LOG_WARN, "Bus '%s' (%s): signal '%s' has incompatible interface %s",
                       bus->name, EEC_Bus_TypeString(bus->type), signal->name,
                       EEC_Signal_InterfaceString(signal->interface_type));
        return -2;
    }

    /* Duplicate check */
    for (i = 0; i < bus->signal_count; ++i) {
        if (bus->signals[i] == signal) return -3;
    }

    if (eec_reserve_ptr_array((void ***)&bus->signals, &bus->signal_capacity, bus->signal_count + 1U) != 0) {
        return -1;
    }

    bus->signals[bus->signal_count++] = signal;
    return 0;
}

static void eec_bus_add_device_signals(EEC_Bus_t *bus, const EEC_DevicePin_t *pins, uint32_t pin_count, int *added)
{
    uint32_t p;
    for (p = 0; p < pin_count; ++p) {
        if (pins[p].signal && EEC_Bus_InterfaceCompatible(bus->type, pins[p].signal->interface_type)) {
            if (EEC_Bus_AddSignal(bus, pins[p].signal) == 0) {
                (*added)++;
            }
        }
    }
}

int EEC_Bus_ConnectSystemSignals(EEC_Bus_t *bus, const EEC_System_t *system)
{
    uint32_t c, s;
    int added = 0;
    if (!bus || !system) return -1;

    for (c = 0; c < system->component_count; ++c) {
        const EEC_Component_t *comp = system->components[c];
        if (!comp) continue;
        for (s = 0; s < comp->sensor_count; ++s) {
            if (comp->sensors[s]) eec_bus_add_device_signals(bus, comp->sensors[s]->pins, comp->sensors[s]->pin_count, &added);
        }
        for (s = 0; s < comp->actuator_count; ++s) {
            if (comp->actuators[s]) eec_bus_add_device_signals(bus, comp->actuators[s]->pins, comp->actuators[s]->pin_count, &added);
        }
    }

    EEC_Log_Printf(EEC_LOG_TRACE, "Bus '%s': auto-connected %d signals from system '%s'", bus->name, added, system->name);
    return added;
}

uint8_t EEC_Ecu_CountCanPorts(const EEC_Ecu_t *ecu)
{
    uint32_t i;
    uint8_t max_port = 0;
    if (!ecu) return 0;
    for (i = 0; i < ecu->pin_count; ++i) {
        const char *n = ecu->pins[i].name;
        unsigned int idx;
        if (n && strncmp(n, "CAN", 3) == 0 && sscanf(n + 3, "%u", &idx) == 1) {
            if ((uint8_t)idx > max_port) max_port = (uint8_t)idx;
        }
    }
    return max_port;
}

uint8_t EEC_Ecu_CountEthernetPorts(const EEC_Ecu_t *ecu)
{
    uint32_t i;
    uint8_t max_port = 0;
    if (!ecu) return 0;
    for (i = 0; i < ecu->pin_count; ++i) {
        const char *n = ecu->pins[i].name;
        unsigned int idx;
        if (n && strncmp(n, "ETH", 3) == 0 && sscanf(n + 3, "%u", &idx) == 1) {
            if ((uint8_t)idx > max_port) max_port = (uint8_t)idx;
        }
    }
    return max_port;
}

void EEC_Architecture_Destroy(EEC_Architecture_t *arch)
{
    uint32_t i, j, k;
    if (!arch) {
        return;
    }

    for (i = 0U; i < arch->signal_count; ++i) {
        free(arch->signals[i]);
    }

    for (i = 0U; i < arch->system_count; ++i) {
        EEC_System_t *system = arch->systems[i];
        if (!system) {
            continue;
        }
        for (j = 0U; j < system->component_count; ++j) {
            EEC_Component_t *comp = system->components[j];
            if (!comp) continue;
            for (k = 0U; k < comp->sensor_count; ++k) {
                if (comp->sensors[k]) { free(comp->sensors[k]->connectors); free(comp->sensors[k]->pins); free(comp->sensors[k]); }
            }
            for (k = 0U; k < comp->actuator_count; ++k) {
                if (comp->actuators[k]) { free(comp->actuators[k]->connectors); free(comp->actuators[k]->pins); free(comp->actuators[k]); }
            }
            free(comp->sensors);
            free(comp->actuators);
            free(comp);
        }
        free(system->components);
        EEC_System_DestroySwcs(system);
        free(system);
    }

    for (i = 0U; i < arch->ecu_count; ++i) {
        EEC_Ecu_t *ecu = arch->ecus[i];
        if (!ecu) {
            continue;
        }
        for (j = 0U; j < ecu->pin_count; ++j) {
            for (k = 0U; k < ecu->pins[j].function_count; ++k) {
                free(ecu->pins[j].functions[k]);
            }
            free(ecu->pins[j].functions);
        }
        free(ecu->pins);
        free(ecu->connectors);
        free(ecu->hosted_swcs);
        free(ecu);
    }

    free(arch->signals);
    free(arch->systems);
    free(arch->ecus);

    for (i = 0U; i < arch->bus_count; ++i) {
        EEC_Bus_t *bus = arch->buses[i];
        if (!bus) continue;
        free(bus->nodes);
        free(bus->signals);
        free(bus->messages);
        free(bus);
    }
    free(arch->buses);

    for (i = 0U; i < arch->zone_count; ++i) {
        if (arch->zones[i]) {
            free(arch->zones[i]->ecus);
            free(arch->zones[i]);
        }
    }
    free(arch->zones);

    free(arch);
}

/* ── Obsolete object audit ────────────────────────────────────────── */

uint32_t EEC_Architecture_CheckObsolete(const EEC_Architecture_t *arch)
{
    uint32_t warn_count = 0U;
    uint32_t s, c, d, p;

    if (!arch) {
        return 0U;
    }

    /* Check signals. */
    for (s = 0U; s < arch->signal_count; ++s) {
        const EEC_Signal_t *sig = arch->signals[s];
        if (sig && sig->obsolete) {
            EEC_Log_Printf(EEC_LOG_WARN, "[OBSOLETE] Signal '%s' (id=0x%08X) is obsolete", sig->name, sig->id);
            ++warn_count;
        }
    }

    /* Check ECUs and their pins. */
    for (s = 0U; s < arch->ecu_count; ++s) {
        const EEC_Ecu_t *ecu = arch->ecus[s];
        if (!ecu) continue;
        if (ecu->obsolete) {
            EEC_Log_Printf(EEC_LOG_WARN, "[OBSOLETE] ECU '%s' (id=0x%08X) is obsolete", ecu->name, ecu->id);
            ++warn_count;
        }
        for (p = 0U; p < ecu->pin_count; ++p) {
            if (ecu->pins[p].obsolete) {
                EEC_Log_Printf(EEC_LOG_WARN, "[OBSOLETE] EcuPin '%s/%s' (id=0x%08X) is obsolete",
                    ecu->name, ecu->pins[p].name, ecu->pins[p].id);
                ++warn_count;
            }
        }
    }

    /* Check buses. */
    for (s = 0U; s < arch->bus_count; ++s) {
        const EEC_Bus_t *bus = arch->buses[s];
        if (bus && bus->obsolete) {
            EEC_Log_Printf(EEC_LOG_WARN, "[OBSOLETE] Bus '%s' (id=0x%08X) is obsolete", bus->name, bus->id);
            ++warn_count;
        }
    }

    /* Check systems, components, sensors, actuators. */
    for (s = 0U; s < arch->system_count; ++s) {
        const EEC_System_t *sys = arch->systems[s];
        if (!sys) continue;
        if (sys->obsolete) {
            EEC_Log_Printf(EEC_LOG_WARN, "[OBSOLETE] System '%s' (id=0x%08X) is obsolete", sys->name, sys->id);
            ++warn_count;
        }

        for (c = 0U; c < sys->component_count; ++c) {
            const EEC_Component_t *comp = sys->components[c];
            if (!comp) continue;
            if (comp->obsolete) {
                EEC_Log_Printf(EEC_LOG_WARN, "[OBSOLETE] Component '%s' (id=0x%08X) is obsolete", comp->name, comp->id);
                ++warn_count;
            }
            for (d = 0U; d < comp->sensor_count; ++d) {
                if (comp->sensors[d] && comp->sensors[d]->obsolete) {
                    EEC_Log_Printf(EEC_LOG_WARN, "[OBSOLETE] Sensor '%s' (id=0x%08X) is obsolete", comp->sensors[d]->name, comp->sensors[d]->id);
                    ++warn_count;
                }
            }
            for (d = 0U; d < comp->actuator_count; ++d) {
                if (comp->actuators[d] && comp->actuators[d]->obsolete) {
                    EEC_Log_Printf(EEC_LOG_WARN, "[OBSOLETE] Actuator '%s' (id=0x%08X) is obsolete", comp->actuators[d]->name, comp->actuators[d]->id);
                    ++warn_count;
                }
            }
        }
    }

    if (warn_count > 0U) {
        EEC_Log_Printf(EEC_LOG_WARN, "[OBSOLETE] Total: %u obsolete object(s) detected in architecture '%s'", warn_count, arch->name);
    }
    return warn_count;
}
