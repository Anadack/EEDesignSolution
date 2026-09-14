/**
 * @file    test_uibuilder_v8_export.c
 * @brief   Schema-alignment regression test for uibuilder/EE_Architect_Design_v8_0.html.
 *
 * The HTML tool's pure-logic module (the <script> block between its DOM-only
 * UI wiring, marked "no DOM access ... required() from Node") builds ECU,
 * System and SWC JSON objects. This test embeds the EXACT output of that
 * module's built-in loadExample() for all three kinds — verified once by
 * extracting the module and running it under Node, see the session record —
 * and feeds it through the REAL C importers used by the framework:
 * EEC_Library_ImportEcu(), EEC_Library_ImportSystem(), EEC_Import_swc_json().
 *
 * If a future change to the JSON schema (field names, "Ref-2X" casing, the
 * flat "devices[]" shape, SWC cardinality, ...) breaks compatibility with
 * what the authoring tool emits, this test fails — it is the tool's contract
 * with the real loaders, not just a self-consistency check inside the HTML.
 */
#include "EEC_architecture.h"
#include "EEC_library.h"
#include "EEC_swc_loader.h"

#include <stdio.h>
#include <string.h>

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond, ...) do { \
    if (cond) { g_pass++; printf("  [PASS] "); } \
    else      { g_fail++; printf("  [FAIL] "); } \
    printf(__VA_ARGS__); \
    printf("\n"); \
} while (0)

static const char *ECU_PATH = "qa_uibuilder_v8_ecu.json";
static const char *SYS_PATH = "qa_uibuilder_v8_system.json";
static const char *SWC_PATH = "qa_uibuilder_v8_swc.json";

/* Byte-for-byte output of uibuilder v8_0's L.buildEcu({name:"EXAMPLE_ECU",
 * variant:"MEDIUM", can_addresses:["0x10"]}) plus its example pins[]/connectors[]. */
static const char *ECU_JSON =
"{\n"
"  \"type\": \"ecu\", \"name\": \"EXAMPLE_ECU\", \"part_number\": \"\",\n"
"  \"variant\": \"MEDIUM\", \"priority\": \"MEDIUM\", \"safety\": \"QM\",\n"
"  \"location\": \"\", \"can_addresses\": [\"0x10\"],\n"
"  \"pins\": [\n"
"    {\"connector\":\"X1\",\"physical_number\":1,\"name\":\"SUPPLY_01\",\"group\":\"SUPPLY\",\"role\":\"SUPPLY\",\"type\":\"POWER\",\"electrical_capability\":0,\"diagnostic_flags\":0,\"electrical\":\"\",\"sw_config\":\"\",\"device_pin_desc\":\"\"},\n"
"    {\"connector\":\"X1\",\"physical_number\":2,\"name\":\"GND_01\",\"group\":\"GROUND\",\"role\":\"GROUND\",\"type\":\"GROUND\",\"electrical_capability\":0,\"diagnostic_flags\":0,\"electrical\":\"\",\"sw_config\":\"\",\"device_pin_desc\":\"\"},\n"
"    {\"connector\":\"X1\",\"physical_number\":3,\"name\":\"CAN1_H\",\"group\":\"CAN_1\",\"role\":\"INOUT\",\"type\":\"CAN\",\"electrical_capability\":128,\"diagnostic_flags\":64,\"electrical\":\"\",\"sw_config\":\"\",\"device_pin_desc\":\"\"}\n"
"  ],\n"
"  \"connectors\": [{\"name\":\"X1\",\"part_number\":\"\",\"family\":\"CUSTOM\",\"total_cavities\":3,\"used_cavities\":3,\"max_pin_number\":3}]\n"
"}\n";

/* Byte-for-byte output of uibuilder v8_0's L.buildSystem({name:"EXAMPLE_System",
 * ref2x:"SYS-EXAMPLE-01"}) plus its example devices[] (1 sensor, 1 signal). */
static const char *SYSTEM_JSON =
"{\n"
"  \"type\": \"system\", \"schema_version\": \"eec-system-1.4\", \"name\": \"EXAMPLE_System\", \"part_number\": \"\",\n"
"  \"version\": \"1.0\", \"system_level\": \"SL1\", \"Ref-2X\": \"SYS-EXAMPLE-01\",\n"
"  \"priority\": \"MEDIUM\", \"safety\": \"QM\", \"location\": \"\",\n"
"  \"take_rate\": 100, \"is_mandatory\": true, \"auto_mapping_enabled\": true,\n"
"  \"devices\": [\n"
"    {\n"
"      \"type\": \"sensor\", \"schema_version\": \"eec-sensor-1.5\", \"id\": \"dev_example_pressure_sensor\",\n"
"      \"name\": \"Example_Pressure_Sensor\", \"device_type\": \"SENSOR\", \"part_number\": \"\", \"supplier_pn\": \"\",\n"
"      \"sensor_template\": \"CUSTOM\", \"is_mandatory\": true, \"mapping_enabled\": true, \"priority\": \"MEDIUM\",\n"
"      \"safety\": \"QM\", \"manufacturer\": \"ACME\", \"description\": \"\", \"notes\": \"\",\n"
"      \"owner_system\": \"\", \"owner_architecture\": \"EE_Architecture\",\n"
"      \"connectors\": [{\"id\":\"con_x1\",\"name\":\"X1\",\"part_number\":\"\",\"family\":\"CUSTOM\",\"gender\":\"MALE\",\"total_cavities\":3,\"used_cavities\":3,\"max_pin_number\":3,\"sealed\":true,\"color\":\"black\",\"mounting\":\"\",\"ip_rating\":\"IP67\",\"rated_voltage\":36.0,\"rated_current\":1.0,\"temperature_min\":-40,\"temperature_max\":125}],\n"
"      \"signals\": [{\"id\":\"sig_example_pressure_4_20ma\",\"prefix\":\"Example_Pressure_4_20mA\",\"name\":\"Example_Pressure_4_20mA\",\"count\":1,\"type\":\"U1\",\"interface\":\"CURRENT\",\"unit\":\"BAR\",\"min\":0,\"max\":40,\"resolution\":1,\"scaling\":1,\"priority\":\"MEDIUM\",\"safety\":\"QM\",\"part_number\":\"\",\"digital_structure\":\"UNSPECIFIED\",\"electrical_requirement\":0,\"role\":\"OUTPUT\",\"description\":\"\",\"notes\":\"\",\"is_mapped\":false,\"nominal_current\":0.02,\"inrush_current\":0.02,\"max_voltage\":0,\"diagnostics_required\":0,\"safety_relevant\":false,\"ground_class\":\"LOGIC\",\"required_reset_state\":\"OFF\",\"required_sensor_supply\":\"UNKNOWN\",\"required_sensor_ground\":\"UNKNOWN\",\"required_supply_voltage\":0}]\n"
"    }\n"
"  ]\n"
"}\n";

/* Byte-for-byte output of uibuilder v8_0's makeSwcEntry + makeVariable + makeMessage
 * for its built-in SWC example (1 SWC, 1 variable, 1 message referencing it). */
static const char *SWC_JSON =
"{\n"
"  \"schema\": \"eec-swc-1.0\",\n"
"  \"swcs\": [\n"
"    {\n"
"      \"name\": \"Example_SWC\", \"system\": \"EXAMPLE_System\", \"allocated_ecu\": \"EXAMPLE_ECU\",\n"
"      \"variables\": [{\"name\":\"ExampleSignal\",\"type\":\"U16\",\"interface\":\"CAN\",\"unit\":\"NONE\",\"min\":0,\"max\":65535,\"resolution\":1,\"scaling\":1}],\n"
"      \"messages\": [{\"name\":\"ExampleStatus\",\"frame_id\":288,\"extended\":false,\"tx\":[{\"bus\":\"CAN1\",\"port\":1,\"cycle_ms\":100}],\"signals\":[{\"name\":\"ExampleSignal\"}]}]\n"
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
    printf("=== uibuilder v8_0 export schema-alignment test ===\n");

    write_file(ECU_PATH, ECU_JSON);
    write_file(SYS_PATH, SYSTEM_JSON);
    write_file(SWC_PATH, SWC_JSON);

    EEC_Architecture_t *arch = EEC_Architecture_Create("UibuilderV8Test");

    /* ── ECU ─────────────────────────────────────────────────────────── */
    EEC_Ecu_t *ecu = EEC_Library_ImportEcu(arch, ECU_PATH, NULL);
    CHECK(ecu != NULL, "ECU imported from uibuilder-shaped JSON");
    CHECK(ecu && strcmp(ecu->name, "EXAMPLE_ECU") == 0, "ECU name preserved (got '%s')",
          ecu ? ecu->name : "?");
    CHECK(ecu && strcmp(ecu->variant, "MEDIUM") == 0, "ECU variant preserved (got '%s')",
          ecu ? ecu->variant : "?");
    CHECK(ecu && ecu->pin_count == 3U, "ECU has 3 pins from JSON (got %u)",
          ecu ? ecu->pin_count : 0U);
    CHECK(ecu && ecu->can_address_count == 1U && ecu->can_addresses[0] == 0x10U,
          "ECU has 1 CAN address 0x10 (got count=%u)", ecu ? ecu->can_address_count : 0U);
    if (ecu && ecu->pin_count == 3U) {
        const EEC_EcuPin_t *p2 = &ecu->pins[2];
        CHECK(strcmp(p2->name, "CAN1_H") == 0, "pin[2].name == CAN1_H (got '%s')", p2->name);
        CHECK(p2->electrical_capability == 128U, "pin[2].electrical_capability == 128 (got %u)",
              p2->electrical_capability);
        CHECK(p2->diagnostic_flags == 64U, "pin[2].diagnostic_flags == 64 (got %u)",
              p2->diagnostic_flags);
        CHECK(p2->role == EEC_PIN_ROLE_INOUT, "pin[2].role == INOUT (got %d)", (int)p2->role);
    }
    CHECK(ecu && ecu->connector_count == 1U, "ECU has 1 connector (got %u)",
          ecu ? ecu->connector_count : 0U);

    /* ── System ──────────────────────────────────────────────────────── */
    EEC_System_t *sys = EEC_Library_ImportSystem(arch, SYS_PATH);
    CHECK(sys != NULL, "System imported from uibuilder-shaped JSON");
    CHECK(sys && strcmp(sys->name, "EXAMPLE_System") == 0, "System name preserved (got '%s')",
          sys ? sys->name : "?");
    CHECK(sys && strcmp(sys->ref_2x, "SYS-EXAMPLE-01") == 0, "System \"Ref-2X\" key correctly parsed (got '%s')",
          sys ? sys->ref_2x : "?");
    CHECK(sys && sys->component_count == 1U, "System has 1 (Default) component (got %u)",
          sys ? sys->component_count : 0U);
    if (sys && sys->component_count == 1U) {
        const EEC_Component_t *comp = sys->components[0];
        CHECK(comp->sensor_count == 1U, "flat devices[] sensor landed in Default component (got %u)",
              comp->sensor_count);
        if (comp->sensor_count == 1U) {
            const EEC_Sensor_t *s = comp->sensors[0];
            CHECK(strcmp(s->name, "Example_Pressure_Sensor") == 0,
                  "sensor.name preserved (got '%s')", s->name);
            CHECK(s->connector_count == 1U, "sensor has 1 connector (got %u)", s->connector_count);
            CHECK(s->pin_count == 1U, "sensor's 1 signal produced 1 device pin (got %u)", s->pin_count);
        }
    }

    /* ── SWC ─────────────────────────────────────────────────────────── */
    int n = EEC_Import_swc_json(arch, SWC_PATH);
    CHECK(n == 1, "1 SWC parsed from uibuilder-shaped JSON (got %d)", n);
    CHECK(sys && sys->swc_count == 1U, "System owns 1 SWC after import (got %u)",
          sys ? sys->swc_count : 0U);
    if (sys && sys->swc_count == 1U) {
        const EEC_Swc_t *swc = sys->swcs[0];
        CHECK(strcmp(swc->name, "Example_SWC") == 0, "swc.name preserved (got '%s')", swc->name);
        CHECK(swc->allocated_ecu == ecu, "swc.allocated_ecu resolves by name to the imported ECU");
        CHECK(swc->message_count == 1U, "swc has 1 message (got %u)", swc->message_count);
        if (swc->message_count == 1U) {
            const EEC_Message_t *m = swc->messages[0];
            CHECK(strcmp(m->name, "ExampleStatus") == 0, "message.name preserved (got '%s')", m->name);
            CHECK(m->frame_id == 0x120U, "message.frame_id preserved (got 0x%X)", m->frame_id);
            CHECK(m->entry_count == 1U, "message's signal cross-referenced from variables[] (got %u)",
                  m->entry_count);
        }
    }

    EEC_Architecture_Destroy(arch);

    remove(ECU_PATH);
    remove(SYS_PATH);
    remove(SWC_PATH);

    printf("\n=== Result: %d passed, %d failed ===\n", g_pass, g_fail);
    return (g_fail == 0) ? 0 : 1;
}
