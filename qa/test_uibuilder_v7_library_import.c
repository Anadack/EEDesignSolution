/**
 * @file    test_uibuilder_v7_library_import.c
 * @brief   Regression test for "Import Library" -> "Add to selected parent"
 *          in uibuilder/EE_Architect_Design_v7_6.html: a sensor/actuator
 *          JSON loaded from library/sensors or library/actuators must, once
 *          attached to a System's component and exported (vNext or Legacy),
 *          still carry its electrical pin data through the real C loader.
 *
 * Why this needs its own test: EEC_Library_ImportSensor()/ImportActuator()
 * (the STANDALONE-file import path, covered by test_library_import_export.c)
 * apply an extra "pins[]" electrical overlay (import_pin_electrical_overlay
 * in EEC_library.c) that is NOT invoked when a device is embedded inside a
 * System's components[]/devices[] (IMPORT_DEVICE_OBJECT ->
 * import_signal_batch reads electrical fields straight off each *signal*).
 * uibuilder v7_6's cSignal(s, linkedPin(d,s)) compensates for this at
 * export time by copying the matching pin's electrical fields onto its
 * signal — this test locks in that only the signals[] path actually
 * matters for a library device attached to a System, using a compact but
 * representative embedded export (the exact shape cComponent()/cDevice()/
 * cSignal()/cConnector() produce, verified once against a real "Import
 * Library" -> "Add to selected parent" -> "Export vNext" session; the
 * "Legacy" devices[] export was verified identically in the same session).
 */
#include "EEC_architecture.h"
#include "EEC_library.h"

#include <stdio.h>
#include <string.h>
#include <math.h>

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond, ...) do { \
    if (cond) { g_pass++; printf("  [PASS] "); } \
    else      { g_fail++; printf("  [FAIL] "); } \
    printf(__VA_ARGS__); \
    printf("\n"); \
} while (0)
#define CLOSE(a, b) (fabs((double)(a) - (double)(b)) < 0.001)

static const char *SYS_PATH = "qa_uibuilder_v7_library_import.json";

/* Compact, representative uibuilder v7_6 export: a System with 1 component
 * holding 1 library-imported actuator (2 pins/signals: supply + command).
 * Field shapes/values mirror cSystem()/cComponent()/cDevice()/cSignal()/
 * cConnector() exactly, including the "_copy" name suffix cloneWithNewIds()
 * appends when a library item is attached ("Add to selected parent"). */
static const char *SYS_JSON =
"{\n"
"  \"type\": \"system\", \"schema_version\": \"eec-system-1.4\", \"name\": \"LibImportTest\",\n"
"  \"part_number\": \"\", \"version\": \"1.0\", \"system_level\": \"SL1\", \"Ref-2X\": \"\",\n"
"  \"priority\": \"MEDIUM\", \"safety\": \"QM\", \"location\": \"\", \"take_rate\": 100,\n"
"  \"is_mandatory\": true, \"auto_mapping_enabled\": true,\n"
"  \"components\": [\n"
"    {\n"
"      \"name\": \"Component\", \"priority\": \"MEDIUM\", \"safety\": \"QM\",\n"
"      \"is_mandatory\": true, \"mapping_enabled\": true,\n"
"      \"sensors\": [],\n"
"      \"actuators\": [\n"
"        {\n"
"          \"name\": \"HYD_PDR10830_Prop_Press_Vlv_copy\", \"part_number\": \"CONFIGURE_ORDER_VARIANT\",\n"
"          \"supplier_pn\": \"CONFIGURE_ORDER_VARIANT\", \"device_type\": \"ACTUATOR\",\n"
"          \"schema_version\": \"eec-actuator-1.5\", \"drive_topology\": \"\", \"actuator_template\": \"\",\n"
"          \"is_mandatory\": true, \"mapping_enabled\": true, \"priority\": \"MEDIUM\", \"safety\": \"QM\",\n"
"          \"signals\": [\n"
"            {\n"
"              \"prefix\": \"HYD_PDR10830_Prop_Press_Vlv_Sup\", \"count\": 1, \"type\": \"U16\",\n"
"              \"interface\": \"POWER\", \"unit\": \"VOLT\", \"role\": \"SUPPLY\", \"priority\": \"MEDIUM\",\n"
"              \"safety\": \"QM\", \"part_number\": \"\", \"electrical_requirement\": 0,\n"
"              \"min\": 0, \"max\": 24, \"resolution\": 0.1, \"scaling\": 1,\n"
"              \"digital_structure\": \"UNSPECIFIED\", \"nominal_current\": 0, \"inrush_current\": 0,\n"
"              \"max_voltage\": 0, \"diagnostics_required\": 0, \"safety_relevant\": false,\n"
"              \"ground_class\": \"POWER\", \"required_reset_state\": \"OFF\",\n"
"              \"required_sensor_supply\": \"UNKNOWN\", \"required_sensor_ground\": \"UNKNOWN\",\n"
"              \"required_supply_voltage\": 24, \"required_supply_voltage_min\": 0,\n"
"              \"required_supply_voltage_max\": 0, \"preferred_supply_voltage\": 0\n"
"            },\n"
"            {\n"
"              \"prefix\": \"HYD_PDR10830_Cmd\", \"count\": 1, \"type\": \"U16\",\n"
"              \"interface\": \"PWM\", \"unit\": \"PERCENT\", \"role\": \"INPUT\", \"priority\": \"HIGH\",\n"
"              \"safety\": \"QM\", \"part_number\": \"\", \"electrical_requirement\": 0,\n"
"              \"min\": 0, \"max\": 100, \"resolution\": 0.1, \"scaling\": 1,\n"
"              \"digital_structure\": \"UNSPECIFIED\", \"nominal_current\": 0, \"inrush_current\": 0,\n"
"              \"max_voltage\": 0, \"diagnostics_required\": 0, \"safety_relevant\": false,\n"
"              \"ground_class\": \"POWER\", \"required_reset_state\": \"OFF\",\n"
"              \"required_sensor_supply\": \"UNKNOWN\", \"required_sensor_ground\": \"UNKNOWN\",\n"
"              \"required_supply_voltage\": 24, \"required_supply_voltage_min\": 0,\n"
"              \"required_supply_voltage_max\": 0, \"preferred_supply_voltage\": 0\n"
"            }\n"
"          ],\n"
"          \"pins\": [\n"
"            {\n"
"              \"number\": 1, \"name\": \"PIN1_HYD_PDR10830_Prop_Press_Vlv_Sup\", \"connector\": \"X1\",\n"
"              \"cavity\": 1, \"role\": \"SUPPLY\", \"interface_type\": \"POWER\", \"signal\": \"HYD_PDR10830_Prop_Press_Vlv_Sup\",\n"
"              \"electrical_requirement\": 0, \"nominal_current\": 0, \"inrush_current\": 0, \"max_voltage\": 0,\n"
"              \"diagnostics_required\": 0, \"safety_relevant\": false, \"ground_class\": \"POWER\",\n"
"              \"required_reset_state\": \"OFF\", \"required_sensor_supply\": \"UNKNOWN\",\n"
"              \"required_sensor_ground\": \"UNKNOWN\", \"required_supply_voltage\": 24,\n"
"              \"required_supply_voltage_min\": 0, \"required_supply_voltage_max\": 0, \"preferred_supply_voltage\": 0\n"
"            },\n"
"            {\n"
"              \"number\": 2, \"name\": \"PIN2_HYD_PDR10830_Cmd\", \"connector\": \"X1\",\n"
"              \"cavity\": 2, \"role\": \"INPUT\", \"interface_type\": \"PWM\", \"signal\": \"HYD_PDR10830_Cmd\",\n"
"              \"electrical_requirement\": 0, \"nominal_current\": 0, \"inrush_current\": 0, \"max_voltage\": 0,\n"
"              \"diagnostics_required\": 0, \"safety_relevant\": false, \"ground_class\": \"POWER\",\n"
"              \"required_reset_state\": \"OFF\", \"required_sensor_supply\": \"UNKNOWN\",\n"
"              \"required_sensor_ground\": \"UNKNOWN\", \"required_supply_voltage\": 24,\n"
"              \"required_supply_voltage_min\": 0, \"required_supply_voltage_max\": 0, \"preferred_supply_voltage\": 0\n"
"            }\n"
"          ],\n"
"          \"connectors\": [\n"
"            {\n"
"              \"name\": \"X1\", \"part_number\": \"CONFIGURE_FROM_SELECTED_VARIANT\", \"family\": \"CUSTOM\",\n"
"              \"gender\": \"MALE\", \"total_cavities\": 2, \"used_cavities\": 2, \"max_pin_number\": 2,\n"
"              \"sealed\": false, \"color\": \"\", \"mounting\": \"\", \"ip_rating\": \"\",\n"
"              \"rated_voltage\": 0, \"rated_current\": 0, \"temperature_min\": 0, \"temperature_max\": 0\n"
"            }\n"
"          ]\n"
"        }\n"
"      ]\n"
"    }\n"
"  ]\n"
"}\n";

static void write_file(const char *path, const char *content)
{
    FILE *f = fopen(path, "w");
    if (f) { fputs(content, f); fclose(f); }
}

int main(void)
{
    printf("=== uibuilder v7_6 library-import (Add to selected parent) regression test ===\n");

    write_file(SYS_PATH, SYS_JSON);

    EEC_Architecture_t *arch = EEC_Architecture_Create("LibImportRegressionTest");
    EEC_System_t *sys = EEC_Library_ImportSystem(arch, SYS_PATH);

    CHECK(sys != NULL, "System imported");
    if (!sys) { EEC_Architecture_Destroy(arch); remove(SYS_PATH); return 1; }
    CHECK(sys->component_count == 1U, "1 component (got %u)", sys->component_count);
    if (sys->component_count != 1U) { EEC_Architecture_Destroy(arch); remove(SYS_PATH); return 1; }

    const EEC_Component_t *comp = sys->components[0];
    CHECK(comp->actuator_count == 1U, "1 actuator attached from library (got %u)", comp->actuator_count);
    CHECK(comp->sensor_count == 0U, "0 sensors (got %u)", comp->sensor_count);

    if (comp->actuator_count == 1U) {
        const EEC_Actuator_t *act = comp->actuators[0];
        CHECK(strcmp(act->name, "HYD_PDR10830_Prop_Press_Vlv_copy") == 0,
              "actuator name preserved with cloneWithNewIds() '_copy' suffix (got '%s')", act->name);
        CHECK(act->pin_count == 2U, "actuator has 2 device pins (got %u)", act->pin_count);
        CHECK(act->connector_count == 1U, "actuator has 1 connector (got %u)", act->connector_count);
        if (act->connector_count == 1U) {
            CHECK(act->connectors[0].total_cavities == 2U,
                  "connector total_cavities == 2 (got %u)", act->connectors[0].total_cavities);
        }
        const EEC_DevicePin_t *sup = NULL;
        for (uint32_t i = 0; i < act->pin_count; ++i) {
            if (act->pins[i].signal && strcmp(act->pins[i].signal->name, "HYD_PDR10830_Prop_Press_Vlv_Sup") == 0) {
                sup = &act->pins[i];
            }
        }
        CHECK(sup != NULL, "pin linked to the supply signal found");
        if (sup) {
            /* This is the crux of the regression this test guards: the
             * library JSON's per-pin electrical data (ground_class,
             * required_supply_voltage) must survive uibuilder's export
             * even though it is not carried by a top-level "pins[]" overlay
             * for System-embedded devices -- only by being baked into the
             * matching signal object via cSignal(s, linkedPin(d,s)). */
            CHECK(sup->ground_class == EEC_GND_POWER,
                  "supply pin ground_class == POWER (got %d)", (int)sup->ground_class);
            CHECK(CLOSE(sup->required_supply_voltage, 24.0),
                  "supply pin required_supply_voltage == 24 (got %g)", (double)sup->required_supply_voltage);
            CHECK(sup->role == EEC_PIN_ROLE_SUPPLY,
                  "supply pin role == SUPPLY (got %d)", (int)sup->role);
        }
    }

    EEC_Architecture_Destroy(arch);
    remove(SYS_PATH);

    printf("\n=== Result: %d passed, %d failed ===\n", g_pass, g_fail);
    return (g_fail == 0) ? 0 : 1;
}
