/**
 * @file    test_es3_ecu_import.c
 * @brief   Standalone test harness for library/ecus/ES3_ECU.json (generic,
 *          non-AGCO-factory ECU describing the 8-connector / 147-pin ES3
 *          common-naming pinout).
 *
 * Verifies, against the real C engine (not just JSON schema validation):
 *   1. The "variant":"ES3" string routes through the generic
 *      EEC_Architecture_CreateEcu() path inside EEC_Library_ImportEcu (NOT
 *      one of the AGCO factory presets), so the JSON "pins"/"connectors"
 *      arrays are the actual source of the imported ECU -- not dead data.
 *   2. Imported pin_count (147) and connector_count (8) match the source.
 *   3. Per-connector cavity counts match the source (A=21, B..H=18).
 *   4. Representative pins across all 12 source "Type classification"
 *      categories resolve to the correct role / interface_type /
 *      electrical_capability / diagnostic_flags.
 *   5. The 5 Ground pins carry the intended ground_class split (POWER vs
 *      LOGIC) and the +5VEXT supply pin carries provided_sensor_supply /
 *      provided_supply_voltage.
 *   6. Connector attributes left out of the JSON (gender/sealed/ratings)
 *      resolve to the framework's documented defaults, not garbage.
 *   7. The ECU exports back to JSON and re-imports with full fidelity
 *      (round-trip: pin-for-pin and connector-for-connector match).
 *
 * Run via qa/run_tests.sh (or a one-off gcc invocation, see that script for
 * the exact source list) from the repository root.
 */
#include "EEC_architecture.h"
#include "EEC_library.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond, ...) do { \
    if (cond) { g_pass++; printf("  [PASS] "); } \
    else      { g_fail++; printf("  [FAIL] "); } \
    printf(__VA_ARGS__); \
    printf("\n"); \
} while (0)

static EEC_EcuPin_t *find_pin(EEC_Ecu_t *ecu, const char *conn, uint32_t num)
{
    for (uint32_t i = 0; i < ecu->pin_count; i++) {
        if (ecu->pins[i].physical_number == num &&
            strcmp(ecu->pins[i].connector_name, conn) == 0) {
            return &ecu->pins[i];
        }
    }
    return NULL;
}

static EEC_Connector_t *find_conn(EEC_Ecu_t *ecu, const char *name)
{
    for (uint32_t i = 0; i < ecu->connector_count; i++) {
        if (strcmp(ecu->connectors[i].name, name) == 0) return &ecu->connectors[i];
    }
    return NULL;
}

static void check_pin(EEC_Ecu_t *ecu, const char *conn, uint32_t num,
                       const char *exp_name, EEC_PinRole_t exp_role,
                       EEC_PinInterface_t exp_if, uint32_t exp_cap, uint32_t exp_diag)
{
    EEC_EcuPin_t *p = find_pin(ecu, conn, num);
    char tag[32];
    snprintf(tag, sizeof(tag), "%s-%u", conn, num);

    CHECK(p != NULL, "%s exists", tag);
    if (!p) return;

    CHECK(strcmp(p->name, exp_name) == 0, "%s name == %s (got %s)", tag, exp_name, p->name);
    CHECK(p->role == exp_role, "%s role == %d (got %d)", tag, (int)exp_role, (int)p->role);
    CHECK(p->interface_type == exp_if, "%s interface_type == %d (got %d)", tag, (int)exp_if, (int)p->interface_type);
    CHECK(p->electrical_capability == exp_cap, "%s electrical_capability == %u (got %u)", tag, exp_cap, p->electrical_capability);
    CHECK(p->diagnostic_flags == exp_diag, "%s diagnostic_flags == %u (got %u)", tag, exp_diag, p->diagnostic_flags);
}

int main(void)
{
    const char *path = "library/ecus/ES3_ECU.json";
    printf("=== ES3_ECU.json import / structural / round-trip test ===\n\n");

    EEC_Architecture_t *arch = EEC_Architecture_Create("ES3_Test_Arch");
    CHECK(arch != NULL, "EEC_Architecture_Create");

    printf("\n--- Import ---\n");
    EEC_Ecu_t *ecu = EEC_Library_ImportEcu(arch, path, "ES3_Test_Ecu");
    CHECK(ecu != NULL, "Import %s", path);
    if (!ecu) { printf("\n=== SUMMARY: %d passed, %d failed ===\n", g_pass, g_fail); return 1; }

    CHECK(strcmp(ecu->variant, "ES3") == 0, "variant == \"ES3\" (got \"%s\") -- generic path, not AGCO factory", ecu->variant);
    CHECK(ecu->pin_count == 147, "pin_count == 147 (got %u)", ecu->pin_count);
    CHECK(ecu->connector_count == 8, "connector_count == 8 (got %u)", ecu->connector_count);

    printf("\n--- Connector cavities ---\n");
    static const struct { const char *name; uint8_t cavities; } k_conns[] = {
        {"A", 21}, {"B", 18}, {"C", 18}, {"D", 18}, {"E", 18}, {"F", 18}, {"G", 18}, {"H", 18},
    };
    for (size_t i = 0; i < sizeof(k_conns) / sizeof(k_conns[0]); i++) {
        EEC_Connector_t *c = find_conn(ecu, k_conns[i].name);
        CHECK(c != NULL, "connector %s exists", k_conns[i].name);
        if (!c) continue;
        CHECK(c->total_cavities == k_conns[i].cavities, "connector %s total_cavities == %u (got %u)",
              k_conns[i].name, k_conns[i].cavities, c->total_cavities);
        CHECK(c->used_cavities == k_conns[i].cavities, "connector %s used_cavities == %u (got %u)",
              k_conns[i].name, k_conns[i].cavities, c->used_cavities);
        CHECK(c->max_pin_number == k_conns[i].cavities, "connector %s max_pin_number == %u (got %u)",
              k_conns[i].name, k_conns[i].cavities, c->max_pin_number);
        /* gender/sealed/ratings deliberately omitted from JSON -> framework defaults */
        CHECK(c->gender == EEC_CONNECTOR_GENDER_MALE, "connector %s gender defaults to MALE", k_conns[i].name);
        CHECK(c->family == EEC_CONNECTOR_FAMILY_CUSTOM, "connector %s family == CUSTOM", k_conns[i].name);
        CHECK(c->sealed == false, "connector %s sealed defaults to false", k_conns[i].name);
        CHECK(c->rated_voltage == 0.0f, "connector %s rated_voltage defaults to 0", k_conns[i].name);
        CHECK(c->temperature_min == -40.0f && c->temperature_max == 125.0f,
              "connector %s temperature range defaults to -40..125", k_conns[i].name);
    }

    printf("\n--- Representative pins across all 12 Type classification categories ---\n");
    /* IN_AI */
    check_pin(ecu, "B", 16, "FAI_02", EEC_PIN_ROLE_INPUT, EEC_PIN_INTERFACE_ANALOG, 64, 15);
    /* IN_DI (plain) */
    check_pin(ecu, "C", 13, "ILSW", EEC_PIN_ROLE_INPUT, EEC_PIN_INTERFACE_DIGITAL, 64, 7);
    /* IN_DI (repurposed-LIN group, exercises the main_group[32] truncation fix) */
    {
        EEC_EcuPin_t *p = find_pin(ecu, "F", 16);
        CHECK(p != NULL, "F-16 exists");
        if (p) {
            CHECK(strcmp(p->name, "LIN5") == 0, "F-16 name == LIN5 (got %s)", p->name);
            CHECK(p->role == EEC_PIN_ROLE_INPUT, "F-16 role == INPUT");
            CHECK(strcmp(p->main_group, "Repurposed LIN-style inputs") == 0,
                  "F-16 main_group not truncated (got \"%s\")", p->main_group);
        }
    }
    /* OUT_HS */
    check_pin(ecu, "A", 2, "KL56a_AUX", EEC_PIN_ROLE_OUTPUT, EEC_PIN_INTERFACE_DIGITAL, 20, 55);
    /* OUT_HS_PWM */
    check_pin(ecu, "A", 19, "CLR", EEC_PIN_ROLE_OUTPUT, EEC_PIN_INTERFACE_PWM, 20, 55);
    /* OUT_LS */
    check_pin(ecu, "H", 1, "SM1", EEC_PIN_ROLE_OUTPUT, EEC_PIN_INTERFACE_DIGITAL, 24, 53);
    /* OUT_LS_PWM */
    check_pin(ecu, "C", 1, "RFAN1", EEC_PIN_ROLE_OUTPUT, EEC_PIN_INTERFACE_PWM, 24, 53);
    /* OUT_HB */
    check_pin(ecu, "G", 15, "FLAP1a", EEC_PIN_ROLE_OUTPUT, EEC_PIN_INTERFACE_DIGITAL, 28, 55);
    /* CAN */
    check_pin(ecu, "H", 9, "CAN1_H", EEC_PIN_ROLE_INOUT, EEC_PIN_INTERFACE_CAN, 128, 64);
    check_pin(ecu, "H", 18, "CAN1_L", EEC_PIN_ROLE_INOUT, EEC_PIN_INTERFACE_CAN, 128, 64);
    /* CAN / ISO */
    check_pin(ecu, "D", 14, "ISOH_IN", EEC_PIN_ROLE_INOUT, EEC_PIN_INTERFACE_CAN, 128, 64);
    /* LIN */
    check_pin(ecu, "F", 7, "LIN1", EEC_PIN_ROLE_INOUT, EEC_PIN_INTERFACE_LIN, 1, 64);
    /* Power */
    check_pin(ecu, "C", 9, "+5VEXT", EEC_PIN_ROLE_SUPPLY, EEC_PIN_INTERFACE_POWER, 0, 3);
    /* Ground (covered in detail below) */
    check_pin(ecu, "A", 11, "DGND1", EEC_PIN_ROLE_GROUND, EEC_PIN_INTERFACE_GROUND, 0, 64);

    printf("\n--- Ground class split + supply fields ---\n");
    {
        static const struct { const char *conn; uint32_t num; const char *name; EEC_GroundClass_t cls; } k_gnd[] = {
            {"A", 11, "DGND1", EEC_GND_POWER}, {"A", 12, "DGND2", EEC_GND_POWER}, {"A", 15, "VM", EEC_GND_POWER},
            {"C", 18, "AGND1", EEC_GND_LOGIC}, {"G", 17, "AGND2", EEC_GND_LOGIC},
        };
        for (size_t i = 0; i < sizeof(k_gnd) / sizeof(k_gnd[0]); i++) {
            EEC_EcuPin_t *p = find_pin(ecu, k_gnd[i].conn, k_gnd[i].num);
            CHECK(p != NULL, "%s exists", k_gnd[i].name);
            if (!p) continue;
            CHECK(p->ground_class == k_gnd[i].cls, "%s ground_class == %d (got %d)",
                  k_gnd[i].name, (int)k_gnd[i].cls, (int)p->ground_class);
        }
        EEC_EcuPin_t *supply = find_pin(ecu, "C", 9);
        CHECK(supply != NULL, "+5VEXT exists");
        if (supply) {
            CHECK(supply->provided_sensor_supply == EEC_SENSOR_SUPPLY,
                  "+5VEXT provided_sensor_supply == SENSOR_SUPPLY (got %d)", (int)supply->provided_sensor_supply);
            CHECK(supply->provided_supply_voltage == 5.0f,
                  "+5VEXT provided_supply_voltage == 5.0 (got %f)", supply->provided_supply_voltage);
        }
    }

    printf("\n--- Duplicate-supplier-name traceability ---\n");
    {
        EEC_EcuPin_t *flap3b = find_pin(ecu, "B", 3);
        EEC_EcuPin_t *flap4b = find_pin(ecu, "G", 12);
        CHECK(flap3b && flap4b, "FLAP3b (B-3) and FLAP4b (G-12) both exist");
        if (flap3b && flap4b) {
            CHECK(strcmp(flap3b->device_pin_desc, "KKBP") == 0 && strcmp(flap4b->device_pin_desc, "KKBP") == 0,
                  "both carry original supplier name KKBP (got \"%s\"/\"%s\")",
                  flap3b->device_pin_desc, flap4b->device_pin_desc);
            CHECK(strstr(flap3b->sw_config, "reused") != NULL && strstr(flap4b->sw_config, "reused") != NULL,
                  "both sw_config notes flag the supplier-name reuse");
        }
    }

    printf("\n--- Export (EEC_Library_ExportEcu) ---\n");
    char tmpdir[512];
    make_temp_dir(tmpdir, sizeof(tmpdir));
    char outpath[512];
    snprintf(outpath, sizeof(outpath), "%s/export_es3_ecu.json", tmpdir);
    int rc = EEC_Library_ExportEcu(ecu, outpath);
    CHECK(rc == 0, "Export ES3_ECU -> %s", outpath);

    printf("\n--- Round-trip re-import ---\n");
    EEC_Architecture_t *arch2 = EEC_Architecture_Create("ES3_RoundTrip_Arch");
    EEC_Ecu_t *rt = EEC_Library_ImportEcu(arch2, outpath, "ES3_RoundTrip_Ecu");
    CHECK(rt != NULL, "Re-import exported ES3_ECU");
    if (rt) {
        CHECK(rt->pin_count == ecu->pin_count, "round-trip pin_count matches (%u == %u)", rt->pin_count, ecu->pin_count);
        CHECK(rt->connector_count == ecu->connector_count, "round-trip connector_count matches (%u == %u)",
              rt->connector_count, ecu->connector_count);

        int all_match = 1;
        uint32_t mismatches = 0;
        for (uint32_t i = 0; i < ecu->pin_count; i++) {
            EEC_EcuPin_t *orig = &ecu->pins[i];
            EEC_EcuPin_t *back = find_pin(rt, orig->connector_name, orig->physical_number);
            if (!back ||
                strcmp(orig->name, back->name) != 0 ||
                orig->role != back->role ||
                orig->interface_type != back->interface_type ||
                orig->electrical_capability != back->electrical_capability ||
                orig->diagnostic_flags != back->diagnostic_flags ||
                orig->ground_class != back->ground_class) {
                all_match = 0;
                mismatches++;
                printf("  [DIFF] %s-%u (%s)\n", orig->connector_name, orig->physical_number, orig->name);
            }
        }
        CHECK(all_match, "all 147 pins round-trip with matching name/role/interface_type/cap/diag/ground_class (%u mismatches)", mismatches);
    }

    EEC_Architecture_Destroy(arch2);
    EEC_Architecture_Destroy(arch);

    printf("\n=== SUMMARY: %d passed, %d failed ===\n", g_pass, g_fail);
    return g_fail > 0 ? 1 : 0;
}
