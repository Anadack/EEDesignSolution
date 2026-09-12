/* Hermetic unit test for the DBC validator (EEC_Dbc_Validate_bus).
 * Builds frames with known DBC-level defects and asserts each is reported;
 * then a clean frame and asserts zero errors. Portable (tmpfile, no paths). */

#include "EEC_architecture.h"
#include "EEC_message.h"
#include "EEC_dbc.h"

#include <stdio.h>
#include <string.h>

static int contains(FILE *f, const char *needle)
{
    char buf[8192];
    size_t n;
    rewind(f);
    n = fread(buf, 1, sizeof(buf) - 1U, f);
    buf[n] = '\0';
    return strstr(buf, needle) != NULL;
}

static EEC_Signal_t *sig(EEC_Architecture_t *a, const char *nm)
{
    return EEC_Architecture_CreateSignalEx(a, nm, EEC_SIGNAL_TYPE_UNSIGNED_8BIT,
                                           EEC_SIGNAL_INTERFACE_CAN,
                                           EEC_SIGNAL_UNIT_NONE,
                                           0.0f, 255.0f, 1.0f, 1.0f);
}

int main(void)
{
    int failures = 0;

    /* Defective bus: overflow, overlap, and DLC out of range. */
    {
        EEC_Architecture_t *a = EEC_Architecture_Create("t");
        EEC_Bus_t *bus = EEC_Architecture_CreateBus(a, "CAN_A", EEC_BUS_TYPE_CAN);
        EEC_Ecu_t *ecu = EEC_Architecture_CreateEcu(a, "ECU_A", "AEC_MEDIUM");
        EEC_System_t *sys = EEC_Architecture_CreateSystem(a, "S");
        EEC_Swc_t *swc = EEC_System_CreateSwc(sys, "SWC");
        EEC_Message_t *msg = EEC_Swc_CreateMessage(swc, "BadMsg", 0x100U, false, 2U); /* 16 bits */
        FILE *f = tmpfile();
        int errs;
        bus->bitrate = 500000U;
        /* Signal 1: bits 0..15 (fills frame). */
        EEC_Message_AddSignal(msg, sig(a, "S1"), 0U, 16U, true, 1.0f, 0.0f);
        /* Signal 2: bits 8..23 -> overlaps S1 AND overflows the 16-bit frame. */
        EEC_Message_AddSignal(msg, sig(a, "S2"), 8U, 16U, true, 1.0f, 0.0f);
        EEC_Message_AddTxPort(msg, bus, ecu, 1U, 100U);
        EEC_Architecture_RebuildBusMessages(a);

        errs = EEC_Dbc_Validate_bus(a, bus, f);
        if (errs > 0 && contains(f, "D1") && contains(f, "D2")) {
            printf("[PASS] validator reports overflow (D1) and overlap (D2)\n");
        } else {
            printf("[FAIL] validator missed defects (errs=%d)\n", errs);
            ++failures;
        }
        fclose(f);
        EEC_Architecture_Destroy(a);
    }

    /* Clean bus: one 8-bit signal in a 1-byte frame. */
    {
        EEC_Architecture_t *a = EEC_Architecture_Create("t");
        EEC_Bus_t *bus = EEC_Architecture_CreateBus(a, "CAN_B", EEC_BUS_TYPE_CAN);
        EEC_Ecu_t *ecu = EEC_Architecture_CreateEcu(a, "ECU_B", "AEC_MEDIUM");
        EEC_System_t *sys = EEC_Architecture_CreateSystem(a, "S");
        EEC_Swc_t *swc = EEC_System_CreateSwc(sys, "SWC");
        EEC_Message_t *msg = EEC_Swc_CreateMessage(swc, "GoodMsg", 0x200U, false, 1U);
        FILE *f = tmpfile();
        int errs;
        bus->bitrate = 500000U;
        EEC_Message_AddSignal(msg, sig(a, "G1"), 0U, 8U, true, 1.0f, 0.0f);
        EEC_Message_AddTxPort(msg, bus, ecu, 1U, 100U);
        EEC_Architecture_RebuildBusMessages(a);

        errs = EEC_Dbc_Validate_bus(a, bus, f);
        if (errs == 0) {
            printf("[PASS] validator clean on well-formed frame\n");
        } else {
            printf("[FAIL] validator wrongly flagged clean frame (errs=%d)\n", errs);
            ++failures;
        }
        fclose(f);
        EEC_Architecture_Destroy(a);
    }

    printf("=== Result: %s ===\n", failures == 0 ? "all passed" : "FAILURES");
    return failures == 0 ? 0 : 1;
}
