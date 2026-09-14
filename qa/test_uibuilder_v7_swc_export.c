/**
 * @file    test_uibuilder_v7_swc_export.c
 * @brief   Schema-alignment regression test for the SWC tab added to
 *          uibuilder/EE_Architect_Design_v7_6.html.
 *
 * That tab's cSwc()/cSwcVariable()/cSwcMessage() functions build a
 * {schema:'eec-swc-1.0', swcs:[...]} file from the UI's in-memory model.
 * This test embeds the EXACT bytes that "Export SWC JSON" produced for a
 * SWC created, filled in and message-wired entirely through the live tool
 * in a real headless-browser session (name/system/allocated_ecu fields,
 * one variable, one message with frame_id "0x120" referencing that
 * variable) — captured once, see the session record — and feeds it
 * through the REAL C entry point, EEC_Import_swc_json(), exactly as
 * src/main.c does for every library/swc SWC file.
 *
 * If a future change to the SWC JSON schema breaks compatibility with what
 * this tab emits, this test fails — it is the tab's contract with the real
 * loader, not just a self-consistency check inside the HTML.
 */
#include "EEC_architecture.h"
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

static const char *SWC_PATH = "qa_uibuilder_v7_swc.json";

/* Byte-for-byte capture of uibuilder v7_6's "Export SWC JSON" output for a
 * SWC created via the SWC tab UI (name/system/allocated_ecu fields, one
 * "+ Variable", one "+ Message" with its ExampleSignal checkbox checked). */
static const char *SWC_JSON =
"{\n"
"  \"schema\": \"eec-swc-1.0\",\n"
"  \"swcs\": [\n"
"    {\n"
"      \"name\": \"Example_SWC\",\n"
"      \"system\": \"EXAMPLE_System\",\n"
"      \"allocated_ecu\": \"EXAMPLE_ECU\",\n"
"      \"variables\": [\n"
"        {\n"
"          \"name\": \"ExampleSignal\",\n"
"          \"type\": \"U16\",\n"
"          \"interface\": \"CAN\",\n"
"          \"unit\": \"NONE\",\n"
"          \"min\": 0,\n"
"          \"max\": 65535,\n"
"          \"resolution\": 1,\n"
"          \"scaling\": 1\n"
"        }\n"
"      ],\n"
"      \"messages\": [\n"
"        {\n"
"          \"name\": \"ExampleStatus\",\n"
"          \"frame_id\": 288,\n"
"          \"extended\": false,\n"
"          \"tx\": [\n"
"            {\n"
"              \"bus\": \"CAN1\",\n"
"              \"port\": 1,\n"
"              \"cycle_ms\": 100\n"
"            }\n"
"          ],\n"
"          \"signals\": [\n"
"            {\n"
"              \"name\": \"ExampleSignal\"\n"
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
    printf("=== uibuilder v7_6 SWC tab export schema-alignment test ===\n");

    write_file(SWC_PATH, SWC_JSON);

    EEC_Architecture_t *arch = EEC_Architecture_Create("UibuilderV7SwcTest");
    EEC_Ecu_t *ecu = EEC_Architecture_CreateEcu(arch, "EXAMPLE_ECU", "SMALL");
    EEC_System_t *sys = EEC_Architecture_CreateSystem(arch, "EXAMPLE_System");

    int n = EEC_Import_swc_json(arch, SWC_PATH);
    CHECK(n == 1, "1 SWC parsed from uibuilder v7_6 SWC-tab JSON (got %d)", n);
    CHECK(sys->swc_count == 1U, "System owns 1 SWC after import (got %u)", sys->swc_count);
    if (sys->swc_count == 1U) {
        const EEC_Swc_t *swc = sys->swcs[0];
        CHECK(strcmp(swc->name, "Example_SWC") == 0, "swc.name preserved (got '%s')", swc->name);
        CHECK(swc->allocated_ecu == ecu, "swc.allocated_ecu resolves by name to the imported ECU");
        CHECK(swc->message_count == 1U, "swc has 1 message (got %u)", swc->message_count);
        if (swc->message_count == 1U) {
            const EEC_Message_t *m = swc->messages[0];
            CHECK(strcmp(m->name, "ExampleStatus") == 0, "message.name preserved (got '%s')", m->name);
            CHECK(m->frame_id == 0x120U, "message.frame_id preserved (got 0x%X)", m->frame_id);
            CHECK(m->entry_count == 1U, "message's signal resolved from variables[] (got %u)", m->entry_count);
        }
    }

    EEC_Architecture_Destroy(arch);
    remove(SWC_PATH);

    printf("\n=== Result: %d passed, %d failed ===\n", g_pass, g_fail);
    return (g_fail == 0) ? 0 : 1;
}
