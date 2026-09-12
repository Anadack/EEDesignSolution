/**
 * @file    test_library_import_export.c
 * @brief   Standalone test harness: import / map / export round-trip for the
 *          5 new elobau sensor library files (lever switch, PTO switch x2,
 *          pushbutton x2) added under library/sensors/{lever_switch,pto_switch,pushbutton}/.
 *
 * Verifies, against the real C engine (not just JSON schema validation):
 *   1. Each file imports into a component via EEC_Library_ImportSensor.
 *   2. Imported pin/connector/signal counts match the source JSON.
 *   3. Every device signal maps onto a real ECU pin via EEC_System_connect_to_ecus,
 *      using the 3 real AEC ECU presets (SMALL/MEDIUM/LARGE) as pin resources.
 *   4. Each imported sensor exports back to JSON via EEC_Library_ExportSensor.
 *   5. The exported JSON re-imports cleanly into a fresh architecture with
 *      matching pin/connector counts (round-trip fidelity).
 *
 * Run via qa/run_tests.sh from the repository root.
 */
#include "EEC_architecture.h"
#include "EEC_connect.h"
#include "EEC_library.h"
#include "EEC_verify.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond, ...) do { \
    if (cond) { g_pass++; printf("  [PASS] "); } \
    else      { g_fail++; printf("  [FAIL] "); } \
    printf(__VA_ARGS__); \
    printf("\n"); \
} while (0)

typedef struct {
    const char *path;
    uint32_t    expected_pins;
    uint32_t    expected_connectors;
} TestFile_t;

static const TestFile_t k_files[] = {
    { "library/sensors/lever_switch/ELO_351RHS_LeverSwitch_3Pos_4Wire.eec-sensor-1.5.json",        4, 1 },
    { "library/sensors/pto_switch/ELO_145PTO_PTOSwitch_2Channel_Cable.eec-sensor-1.5.json",        3, 1 },
    { "library/sensors/pto_switch/ELO_145PTO_PTOSwitch_2Channel_AMPSuperseal.eec-sensor-1.5.json", 3, 1 },
    { "library/sensors/pushbutton/ELO_145AB_PushButton_CircuitI_2Wire.eec-sensor-1.5.json",        2, 1 },
    { "library/sensors/pushbutton/ELO_145AB_PushButton_CircuitIX_LED_3Wire.eec-sensor-1.5.json",   3, 1 },
};
static const int k_file_count = (int)(sizeof(k_files) / sizeof(k_files[0]));

/* Portable temp directory for the export round-trip below: no hardcoded
 * author-machine path, so this test runs unmodified in any environment. */
#ifdef _WIN32
#include <windows.h>
static void make_temp_dir(char *out, size_t out_size)
{
    char base[MAX_PATH];
    GetTempPathA((DWORD)sizeof(base), base);
    snprintf(out, out_size, "%sEEC_qa_XXXXXX", base);
    _mktemp_s(out, out_size);
    CreateDirectoryA(out, NULL);
}
#else
#include <unistd.h>
static void make_temp_dir(char *out, size_t out_size)
{
    const char *tmp = getenv("TMPDIR");
    snprintf(out, out_size, "%s/EEC_qa_XXXXXX", (tmp && tmp[0]) ? tmp : "/tmp");
    if (!mkdtemp(out)) {
        snprintf(out, out_size, "/tmp");
    }
}
#endif

int main(void)
{
    printf("=== Task K library test: import / map / export round-trip ===\n\n");

    /* ---- 1. Build a fresh architecture/system/component to import into ---- */
    EEC_Architecture_t *arch = EEC_Architecture_Create("TaskK_Test_Arch");
    CHECK(arch != NULL, "EEC_Architecture_Create");

    EEC_System_t *sys = EEC_Architecture_CreateSystem(arch, "TaskK_Test_System");
    CHECK(sys != NULL, "EEC_Architecture_CreateSystem");

    EEC_Component_t *comp = EEC_System_CreateComponent(sys, "TaskK_Test_Component");
    CHECK(comp != NULL, "EEC_System_CreateComponent");

    /* ---- 2. Import the 3 real AEC ECUs to provide mapping pin resources ---- */
    printf("\n--- ECU import ---\n");
    EEC_Ecu_t *ecu_small  = EEC_Library_ImportEcu(arch, "library/ecus/AEC_SMALL_2CAN.json",  "TestEcu_Small");
    EEC_Ecu_t *ecu_medium = EEC_Library_ImportEcu(arch, "library/ecus/AEC_MEDIUM_1CAN.json", "TestEcu_Medium");
    EEC_Ecu_t *ecu_large  = EEC_Library_ImportEcu(arch, "library/ecus/AEC_LARGE_3CAN.json",  "TestEcu_Large");
    CHECK(ecu_small  != NULL, "Import AEC_SMALL_2CAN.json");
    CHECK(ecu_medium != NULL, "Import AEC_MEDIUM_1CAN.json");
    CHECK(ecu_large  != NULL, "Import AEC_LARGE_3CAN.json");

    /* ---- 3. Import each of the 5 new sensor library files ---- */
    printf("\n--- Sensor import (%d files) ---\n", k_file_count);
    EEC_Sensor_t *sensors[k_file_count];
    for (int i = 0; i < k_file_count; i++) {
        sensors[i] = EEC_Library_ImportSensor(arch, comp, k_files[i].path);
        CHECK(sensors[i] != NULL, "Import %s", k_files[i].path);
        if (!sensors[i]) continue;

        CHECK(sensors[i]->pin_count == k_files[i].expected_pins,
              "  pin_count == %u (got %u) [%s]",
              k_files[i].expected_pins, sensors[i]->pin_count, k_files[i].path);
        CHECK(sensors[i]->connector_count == k_files[i].expected_connectors,
              "  connector_count == %u (got %u) [%s]",
              k_files[i].expected_connectors, sensors[i]->connector_count, k_files[i].path);

        /* Every imported pin must carry a non-NULL resolved signal pointer. */
        int pins_with_signal = 0;
        for (uint32_t p = 0; p < sensors[i]->pin_count; p++) {
            if (sensors[i]->pins[p].signal != NULL) pins_with_signal++;
        }
        CHECK(pins_with_signal == (int)sensors[i]->pin_count,
              "  all %u pins resolved to a signal object [%s]",
              sensors[i]->pin_count, k_files[i].path);
    }

    /* ---- 4. Verify architecture (pre-mapping sanity pass) ---- */
    printf("\n--- Architecture verify (pre-mapping) ---\n");
    int verify_rc = EEC_Verify_architecture(arch, stdout);
    printf("  EEC_Verify_architecture rc=%d (informational; pre-mapping warnings expected)\n", verify_rc);

    /* ---- 5. Map every signal in the system onto the 3 real ECUs ---- */
    printf("\n--- Mapping (EEC_System_connect_to_ecus) ---\n");
    EEC_Ecu_t *ecus[3] = { ecu_small, ecu_medium, ecu_large };
    int mapped = EEC_System_connect_to_ecus(sys, ecus, 3, stdout);
    printf("  EEC_System_connect_to_ecus -> %d signals connected\n", mapped);
    CHECK(mapped >= 0, "EEC_System_connect_to_ecus did not error");

    int total_signals = 0, mapped_signals = 0;
    for (int i = 0; i < k_file_count; i++) {
        if (!sensors[i]) continue;
        for (uint32_t p = 0; p < sensors[i]->pin_count; p++) {
            EEC_Signal_t *sig = sensors[i]->pins[p].signal;
            if (!sig) continue;
            total_signals++;
            if (sig->is_mapped) mapped_signals++;
            else printf("  [WARN] unmapped signal '%s' (pin '%s' on '%s')\n",
                        sig->name, sensors[i]->pins[p].name, sensors[i]->name);
        }
    }
    printf("  device signals mapped: %d / %d\n", mapped_signals, total_signals);
    CHECK(mapped_signals == total_signals,
          "Every signal across all 5 new sensors mapped to a real ECU pin");

    /* ---- 6. Export each imported sensor back to JSON ---- */
    printf("\n--- Export (EEC_Library_ExportSensor) ---\n");
    char tmpdir[512];
    make_temp_dir(tmpdir, sizeof(tmpdir));
    printf("  (round-trip exports written to %s)\n", tmpdir);
    char outpaths[k_file_count][512];
    for (int i = 0; i < k_file_count; i++) {
        if (!sensors[i]) continue;
        snprintf(outpaths[i], sizeof(outpaths[i]), "%s/export_%d.json", tmpdir, i);
        int rc = EEC_Library_ExportSensor(sensors[i], outpaths[i]);
        CHECK(rc == 0, "Export sensor '%s' -> %s", sensors[i]->name, outpaths[i]);
    }

    /* ---- 7. Re-import the exported JSON into a fresh architecture (round trip) ---- */
    printf("\n--- Round-trip re-import ---\n");
    EEC_Architecture_t *arch2 = EEC_Architecture_Create("TaskK_RoundTrip_Arch");
    EEC_System_t       *sys2  = EEC_Architecture_CreateSystem(arch2, "RoundTrip_System");
    EEC_Component_t    *comp2 = EEC_System_CreateComponent(sys2, "RoundTrip_Component");

    for (int i = 0; i < k_file_count; i++) {
        if (!sensors[i]) continue;
        EEC_Sensor_t *rt = EEC_Library_ImportSensor(arch2, comp2, outpaths[i]);
        CHECK(rt != NULL, "Re-import exported '%s'", sensors[i]->name);
        if (!rt) continue;

        CHECK(rt->pin_count == sensors[i]->pin_count,
              "  round-trip pin_count matches (%u == %u) [%s]",
              rt->pin_count, sensors[i]->pin_count, sensors[i]->name);
        CHECK(rt->connector_count == sensors[i]->connector_count,
              "  round-trip connector_count matches (%u == %u) [%s]",
              rt->connector_count, sensors[i]->connector_count, sensors[i]->name);

        int signal_names_match = 1;
        for (uint32_t p = 0; p < rt->pin_count && p < sensors[i]->pin_count; p++) {
            EEC_Signal_t *a = rt->pins[p].signal;
            EEC_Signal_t *b = sensors[i]->pins[p].signal;
            if (!a || !b || strcmp(a->name, b->name) != 0) { signal_names_match = 0; break; }
        }
        CHECK(signal_names_match, "  round-trip signal names match pin-for-pin [%s]", sensors[i]->name);
    }

    EEC_Architecture_Destroy(arch2);
    EEC_Architecture_Destroy(arch);

    printf("\n=== SUMMARY: %d passed, %d failed ===\n", g_pass, g_fail);
    return g_fail > 0 ? 1 : 0;
}
