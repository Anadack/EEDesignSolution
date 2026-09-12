/* Hermetic unit test for verification rule B9 (CAN busload).
 *
 * Builds a deliberately overloaded CAN bus (low bitrate + fast-cycle frames)
 * and asserts the B9 busload ERROR fires; then a healthy bus and asserts it
 * does not. Uses tmpfile() so it is portable (no hardcoded paths). */

#include "EEC_architecture.h"
#include "EEC_message.h"
#include "EEC_verify.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static int report_contains(FILE *f, const char *needle)
{
    char buf[8192];
    size_t n;
    long end;
    int found = 0;
    fflush(f);
    end = ftell(f);
    rewind(f);
    n = fread(buf, 1, sizeof(buf) - 1U, f);
    buf[n] = '\0';
    (void)end;
    if (strstr(buf, needle)) found = 1;
    return found;
}

/* Build one CAN bus carrying `count` frames of DLC 8 at `cycle_ms`, at `bitrate`. */
static EEC_Architecture_t *build(uint32_t bitrate, uint32_t cycle_ms, int count)
{
    EEC_Architecture_t *arch = EEC_Architecture_Create("t");
    EEC_Bus_t *bus = EEC_Architecture_CreateBus(arch, "CAN_A", EEC_BUS_TYPE_CAN);
    EEC_Ecu_t *ecu = EEC_Architecture_CreateEcu(arch, "ECU_A", "AEC_MEDIUM");
    EEC_System_t *sys = EEC_Architecture_CreateSystem(arch, "S");
    EEC_Swc_t *swc = EEC_System_CreateSwc(sys, "SWC");
    int i;
    bus->bitrate = bitrate;
    for (i = 0; i < count; ++i) {
        char nm[32];
        EEC_Message_t *msg;
        snprintf(nm, sizeof(nm), "MSG_%d", i);
        msg = EEC_Swc_CreateMessage(swc, nm, 0x100U + (uint32_t)i, false, 8U);
        EEC_Message_AddTxPort(msg, bus, ecu, 1U, cycle_ms);
    }
    EEC_Architecture_RebuildBusMessages(arch);
    return arch;
}

int main(void)
{
    int failures = 0;

    /* Overloaded: 125 kbps, 30 frames every 1 ms -> ~far over 80%. */
    {
        EEC_Architecture_t *arch = build(125000U, 1U, 30);
        FILE *f = tmpfile();
        EEC_Verify_architecture(arch, f);
        if (report_contains(f, "B9 busload") && report_contains(f, "exceeds 80%")) {
            printf("[PASS] B9 fires on overloaded bus\n");
        } else {
            printf("[FAIL] B9 did NOT fire on overloaded bus\n");
            ++failures;
        }
        fclose(f);
        EEC_Architecture_Destroy(arch);
    }

    /* Healthy: 500 kbps, 3 frames every 100 ms -> well under 1%. */
    {
        EEC_Architecture_t *arch = build(500000U, 100U, 3);
        FILE *f = tmpfile();
        EEC_Verify_architecture(arch, f);
        if (!report_contains(f, "exceeds 80%")) {
            printf("[PASS] B9 silent on healthy bus\n");
        } else {
            printf("[FAIL] B9 wrongly fired on healthy bus\n");
            ++failures;
        }
        fclose(f);
        EEC_Architecture_Destroy(arch);
    }

    printf("=== Result: %s ===\n", failures == 0 ? "all passed" : "FAILURES");
    return failures == 0 ? 0 : 1;
}
