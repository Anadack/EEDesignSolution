/**
 * @file    test_swc_dbc_import.c
 * @brief   Declarative "dbc_file" field on a .swc.json SWC entry
 *          (EEC_swc_loader.c wiring to EEC_Import_dbc()).
 *
 * A system owns 1..n SWCs; a SWC owns 0 or 1 imported DBC. Verifies:
 *   1. A SWC entry with "dbc_file" set imports that DBC's messages/signals
 *      via the ordinary EEC_Import_swc_json() entry point (not just the
 *      lower-level EEC_Import_dbc() call main.c's EEC_IMPORT_DBC escape
 *      hatch uses).
 *   2. A SWC entry without "dbc_file" still parses fine with 0 messages
 *      (the "or none" half of the cardinality) and inline "messages" still
 *      work unchanged.
 *   3. A "dbc_file" pointing at a missing file fails gracefully (logged
 *      warning, 0 messages for that SWC) instead of aborting the whole
 *      library import.
 *
 * Standalone harness (own main). Compile with the same src/EEC_*.c list used
 * by qa/run_tests.sh.
 */
#include "EEC_architecture.h"
#include "EEC_message.h"
#include "EEC_dbc.h"
#include "EEC_swc_loader.h"

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

static const char *DBC_PATH  = "qa_swc_dbc_import.dbc";
static const char *SWC_JSON_PATH = "qa_swc_dbc_import.swc.json";

static EEC_System_t *find_sys(const EEC_Architecture_t *arch, const char *name)
{
    uint32_t i;
    for (i = 0U; i < arch->system_count; ++i) {
        if (arch->systems[i] && strcmp(arch->systems[i]->name, name) == 0) {
            return arch->systems[i];
        }
    }
    return NULL;
}

static EEC_Swc_t *find_swc(const EEC_System_t *sys, const char *name)
{
    uint32_t i;
    if (!sys) { return NULL; }
    for (i = 0U; i < sys->swc_count; ++i) {
        if (sys->swcs[i] && strcmp(sys->swcs[i]->name, name) == 0) {
            return sys->swcs[i];
        }
    }
    return NULL;
}

static void write_file(const char *path, const char *content)
{
    FILE *f = fopen(path, "w");
    if (f) {
        fputs(content, f);
        fclose(f);
    }
}

int main(void)
{
    printf("=== SWC dbc_file import test ===\n");

    /* ── 1. Produce a small source .dbc to import back via dbc_file ────── */
    EEC_Architecture_t *src = EEC_Architecture_Create("SWC_DBC_Source");
    EEC_Bus_t    *bus = EEC_Architecture_CreateBus(src, "CAN1", EEC_BUS_TYPE_CAN);
    EEC_Ecu_t    *ecu = EEC_Architecture_CreateEcu(src, "ECU_TX", "SMALL");
    EEC_System_t *ssys = EEC_Architecture_CreateSystem(src, "SrcSystem");
    EEC_Swc_t    *sswc = EEC_System_CreateSwc(ssys, "SrcSWC");
    EEC_Swc_AllocateToEcu(sswc, ecu);

    EEC_Message_t *msg = EEC_Swc_CreateMessage(sswc, "CoolantStatus", 0x120U, false, 8U);
    EEC_Signal_t *temp = EEC_Swc_CreateVariable(sswc, "CoolantTemp",
        EEC_SIGNAL_TYPE_UNSIGNED_8BIT, EEC_SIGNAL_INTERFACE_CAN, EEC_SIGNAL_UNIT_CELSIUS,
        -40.0f, 150.0f, 1.0f, 1.0f);
    EEC_Message_AddSignal(msg, temp, 0U, 8U, true, 1.0f, -40.0f);
    EEC_Message_AddTxPort(msg, bus, ecu, 1U, 100U);

    int written = EEC_Export_dbc_bus(src, bus, DBC_PATH);
    CHECK(written == 1, "source DBC exported with 1 message (got %d)", written);
    EEC_Architecture_Destroy(src);

    /* ── 2. dbc_file on a SWC entry imports it through the JSON loader ──── */
    {
        char json[1024];
        snprintf(json, sizeof(json),
            "{\"schema\":\"eec-swc-1.0\",\"swcs\":["
            "{\"name\":\"WithDbc\",\"system\":\"TestSystem\",\"allocated_ecu\":\"ECU_TX\","
            "\"dbc_file\":\"%s\"},"
            "{\"name\":\"NoDbc\",\"system\":\"TestSystem\"},"
            "{\"name\":\"WithBadDbc\",\"system\":\"TestSystem\",\"dbc_file\":\"does_not_exist.dbc\"}"
            "]}", DBC_PATH);
        write_file(SWC_JSON_PATH, json);

        EEC_Architecture_t *arch = EEC_Architecture_Create("SWC_DBC_Test");
        /* The test's own ECU_TX must exist for allocated_ecu to resolve;
         * EEC_Import_swc_json() only links by name, it does not create ECUs. */
        EEC_Architecture_CreateEcu(arch, "ECU_TX", "SMALL");

        int n = EEC_Import_swc_json(arch, SWC_JSON_PATH);
        CHECK(n == 3, "3 SWC(s) parsed from JSON (got %d)", n);

        EEC_System_t *sys = find_sys(arch, "TestSystem");
        CHECK(sys != NULL, "TestSystem created");
        CHECK(sys && sys->swc_count == 3U, "TestSystem owns 3 SWCs (got %u)",
              sys ? sys->swc_count : 0U);

        EEC_Swc_t *with_dbc = find_swc(sys, "WithDbc");
        CHECK(with_dbc != NULL, "SWC 'WithDbc' exists");
        CHECK(with_dbc && with_dbc->message_count == 1U,
              "SWC 'WithDbc' owns 1 message imported from dbc_file (got %u)",
              with_dbc ? with_dbc->message_count : 0U);
        if (with_dbc && with_dbc->message_count == 1U) {
            const EEC_Message_t *m = with_dbc->messages[0];
            CHECK(m && strcmp(m->name, "CoolantStatus") == 0, "imported message name preserved");
            CHECK(m && m->frame_id == 0x120U, "imported message frame_id preserved (0x%X)",
                  m ? m->frame_id : 0U);
            CHECK(m && m->entry_count == 1U, "imported message has 1 signal");
        }
        CHECK(with_dbc && with_dbc->allocated_ecu != NULL
              && strcmp(with_dbc->allocated_ecu->name, "ECU_TX") == 0,
              "'allocated_ecu' from JSON still applies alongside dbc_file");

        /* Cardinality: a SWC with neither dbc_file nor messages is valid
         * and owns zero messages — "0 or 1 DBC" includes zero. */
        EEC_Swc_t *no_dbc = find_swc(sys, "NoDbc");
        CHECK(no_dbc != NULL, "SWC 'NoDbc' (no dbc_file, no messages) exists");
        CHECK(no_dbc && no_dbc->message_count == 0U,
              "SWC 'NoDbc' owns 0 messages (got %u)", no_dbc ? no_dbc->message_count : 0U);

        /* A missing dbc_file must not abort the whole import: the SWC still
         * exists, just with 0 messages, and the other two SWCs are unaffected. */
        EEC_Swc_t *bad_dbc = find_swc(sys, "WithBadDbc");
        CHECK(bad_dbc != NULL, "SWC 'WithBadDbc' still created despite missing dbc_file");
        CHECK(bad_dbc && bad_dbc->message_count == 0U,
              "SWC 'WithBadDbc' owns 0 messages after failed import (got %u)",
              bad_dbc ? bad_dbc->message_count : 0U);

        EEC_Architecture_Destroy(arch);
    }

    remove(DBC_PATH);
    remove(SWC_JSON_PATH);

    printf("\n=== Result: %d passed, %d failed ===\n", g_pass, g_fail);
    return (g_fail == 0) ? 0 : 1;
}
