/**
 * @file    test_dbc_roundtrip.c
 * @brief   Round-trip test for the C-core CAN DBC import/export (EEC_dbc.c).
 *
 * Builds a small architecture with two CAN messages (one standard 11-bit,
 * one extended 29-bit), exports the bus to a .dbc file, re-imports it into a
 * fresh architecture, and verifies that message identity, DLC, signal count
 * and per-signal bit layout survive the round-trip.
 *
 * Standalone harness (own main). Compile with the same src/EEC_*.c list used
 * by qa/run_tests.sh plus src/EEC_message.c and src/EEC_dbc.c.
 */
#include "EEC_architecture.h"
#include "EEC_message.h"
#include "EEC_dbc.h"

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

static const char *DBC_PATH = "qa_dbc_roundtrip.dbc";

static EEC_Message_t *find_msg(const EEC_Swc_t *swc, const char *name)
{
    uint32_t m;
    if (!swc) { return NULL; }
    for (m = 0U; m < swc->message_count; ++m) {
        if (swc->messages[m] && strcmp(swc->messages[m]->name, name) == 0) {
            return swc->messages[m];
        }
    }
    return NULL;
}

static const EEC_MessageSignal_t *find_entry(const EEC_Message_t *msg, const char *sig_name)
{
    uint32_t e;
    if (!msg) { return NULL; }
    for (e = 0U; e < msg->entry_count; ++e) {
        if (msg->entries[e].signal && strcmp(msg->entries[e].signal->name, sig_name) == 0) {
            return &msg->entries[e];
        }
    }
    return NULL;
}

int main(void)
{
    printf("=== DBC round-trip test ===\n");

    /* ── 1. Build the source architecture ──────────────────────────────── */
    EEC_Architecture_t *src = EEC_Architecture_Create("DBC_RT_Source");
    EEC_Bus_t          *bus = EEC_Architecture_CreateBus(src, "CAN1", EEC_BUS_TYPE_CAN);
    EEC_Ecu_t          *ecu = EEC_Architecture_CreateEcu(src, "ECU_TX", "SMALL");
    EEC_System_t       *sys = EEC_Architecture_CreateSystem(src, "RT_System");
    EEC_Swc_t          *swc = EEC_System_CreateSwc(sys, "RT_SWC");

    CHECK(src && bus && ecu && sys && swc, "source objects created");
    EEC_Swc_AllocateToEcu(swc, ecu);

    /* Message 1: standard 11-bit frame, two signals. */
    EEC_Message_t *m1 = EEC_Swc_CreateMessage(swc, "EngineStatus", 0x0C0U, false, 8U);
    EEC_Signal_t  *rpm  = EEC_Swc_CreateVariable(swc, "EngineRPM",
        EEC_SIGNAL_TYPE_UNSIGNED_16BIT, EEC_SIGNAL_INTERFACE_CAN, EEC_SIGNAL_UNIT_RPM,
        0.0f, 8000.0f, 1.0f, 0.125f);
    EEC_Signal_t  *tmp  = EEC_Swc_CreateVariable(swc, "EngineTemp",
        EEC_SIGNAL_TYPE_UNSIGNED_8BIT, EEC_SIGNAL_INTERFACE_CAN, EEC_SIGNAL_UNIT_CELSIUS,
        0.0f, 200.0f, 1.0f, 1.0f);
    EEC_Message_AddSignal(m1, rpm, 0U, 16U, true, 0.125f, 0.0f);
    EEC_Message_AddSignal(m1, tmp, 16U, 8U, true, 1.0f, -40.0f);
    EEC_Message_AddTxPort(m1, bus, ecu, 1U, 100U);

    /* Message 2: extended 29-bit frame, one signal. */
    EEC_Message_t *m2 = EEC_Swc_CreateMessage(swc, "VehicleSpeed", 0x18FEF100U, true, 8U);
    EEC_Signal_t  *spd  = EEC_Swc_CreateVariable(swc, "WheelSpeed",
        EEC_SIGNAL_TYPE_UNSIGNED_16BIT, EEC_SIGNAL_INTERFACE_CAN, EEC_SIGNAL_UNIT_NONE,
        0.0f, 65535.0f, 1.0f, 1.0f);
    EEC_Message_AddSignal(m2, spd, 0U, 16U, true, 1.0f, 0.0f);
    EEC_Message_AddTxPort(m2, bus, ecu, 1U, 50U);

    CHECK(m1 && m2 && rpm && tmp && spd, "source messages/signals created");

    /* ── 2. Export the bus to a .dbc file ──────────────────────────────── */
    int written = EEC_Export_dbc_bus(src, bus, DBC_PATH);
    CHECK(written == 2, "export wrote 2 messages (got %d)", written);

    /* ── 3. Re-import into a fresh architecture ─────────────────────────── */
    EEC_Architecture_t *dst  = EEC_Architecture_Create("DBC_RT_Dest");
    EEC_System_t       *dsys = EEC_Architecture_CreateSystem(dst, "RT_Imported");
    EEC_Swc_t          *dswc = EEC_System_CreateSwc(dsys, "RT_Imported_SWC");
    int imported = EEC_Import_dbc(dst, dswc, DBC_PATH);
    CHECK(imported == 2, "import read 2 messages (got %d)", imported);
    CHECK(dswc && dswc->message_count == 2U, "imported SWC owns 2 messages");

    /* ── 4. Verify message + signal fidelity ───────────────────────────── */
    const EEC_Message_t *im1 = find_msg(dswc, "EngineStatus");
    CHECK(im1 != NULL, "message 'EngineStatus' round-tripped");
    if (im1) {
        CHECK(im1->frame_id == 0x0C0U, "EngineStatus frame_id preserved (0x%X)", im1->frame_id);
        CHECK(im1->is_extended == false, "EngineStatus is standard 11-bit");
        CHECK(im1->dlc == 8U, "EngineStatus dlc preserved (%u)", im1->dlc);
        CHECK(im1->entry_count == 2U, "EngineStatus has 2 signals (%u)", im1->entry_count);

        const EEC_MessageSignal_t *e_rpm = find_entry(im1, "EngineRPM");
        const EEC_MessageSignal_t *e_tmp = find_entry(im1, "EngineTemp");
        CHECK(e_rpm && e_rpm->start_bit == 0U && e_rpm->length == 16U,
              "EngineRPM layout 0|16 preserved");
        CHECK(e_tmp && e_tmp->start_bit == 16U && e_tmp->length == 8U,
              "EngineTemp layout 16|8 preserved");
    }

    const EEC_Message_t *im2 = find_msg(dswc, "VehicleSpeed");
    CHECK(im2 != NULL, "message 'VehicleSpeed' round-tripped");
    if (im2) {
        CHECK(im2->frame_id == 0x18FEF100U, "VehicleSpeed frame_id preserved (0x%X)", im2->frame_id);
        CHECK(im2->is_extended == true, "VehicleSpeed is extended 29-bit");
        CHECK(im2->entry_count == 1U, "VehicleSpeed has 1 signal (%u)", im2->entry_count);
    }

    /* ── Cleanup ───────────────────────────────────────────────────────── */
    EEC_Architecture_Destroy(src);
    EEC_Architecture_Destroy(dst);
    remove(DBC_PATH);

    printf("\n=== Result: %d passed, %d failed ===\n", g_pass, g_fail);
    return (g_fail == 0) ? 0 : 1;
}
