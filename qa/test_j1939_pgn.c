/* Hermetic unit test for EEC_J1939_PgnFromFrameId() and its use by
 * EEC_Swc_CreateMessage() to auto-populate EEC_Message_t.pgn.
 *
 * Verifies against known real SAE J1939 frame/PGN pairs (not made up):
 *   - EEC1 (Engine Speed), PGN 61444 (0xF004): PDU2 broadcast, group
 *     extension 0x04 is part of the PGN.
 *   - Request PGN, PGN 59904 (0xEA00): PDU1 peer-to-peer; the destination
 *     address byte (0xFF here) must NOT leak into the PGN.
 *   - A standard 11-bit (non-extended) message must get pgn == 0.
 */

#include "EEC_architecture.h"
#include "EEC_message.h"

#include <stdio.h>

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond, ...) do { \
    if (cond) { g_pass++; printf("  [PASS] "); } \
    else      { g_fail++; printf("  [FAIL] "); } \
    printf(__VA_ARGS__); \
    printf("\n"); \
} while (0)

int main(void)
{
    /* EEC1: priority 3, DP 0, PF 0xF0, GE 0x04, SA 0x00 -> PGN 0xF004. */
    uint32_t eec1_id = (3U << 26) | (0xF0U << 16) | (0x04U << 8) | 0x00U;
    CHECK(EEC_J1939_PgnFromFrameId(eec1_id) == 0xF004U,
          "EEC1 frame 0x%08X -> PGN 0x%04X (expected 0xF004)",
          eec1_id, EEC_J1939_PgnFromFrameId(eec1_id));

    /* Request PGN: priority 6, DP 0, PF 0xEA, PS(dest)=0xFF, SA 0x0A -> PGN 0xEA00
     * (the destination address 0xFF must NOT appear in the PGN: PDU1 format). */
    uint32_t request_id = (6U << 26) | (0xEAU << 16) | (0xFFU << 8) | 0x0AU;
    CHECK(EEC_J1939_PgnFromFrameId(request_id) == 0xEA00U,
          "Request frame 0x%08X -> PGN 0x%04X (expected 0xEA00, PDU1 dest-addr excluded)",
          request_id, EEC_J1939_PgnFromFrameId(request_id));

    /* End-to-end: EEC_Swc_CreateMessage auto-derives pgn for extended messages. */
    {
        EEC_Architecture_t *arch = EEC_Architecture_Create("t");
        EEC_System_t *sys = EEC_Architecture_CreateSystem(arch, "S");
        EEC_Swc_t *swc = EEC_System_CreateSwc(sys, "SWC");
        EEC_Message_t *ext_msg = EEC_Swc_CreateMessage(swc, "EEC1", eec1_id, true, 8U);
        EEC_Message_t *std_msg = EEC_Swc_CreateMessage(swc, "StdMsg", 0x100U, false, 8U);

        CHECK(ext_msg->pgn == 0xF004U,
              "EEC_Swc_CreateMessage auto-derived pgn=0x%04X for extended message (expected 0xF004)",
              ext_msg->pgn);
        CHECK(std_msg->pgn == 0U,
              "EEC_Swc_CreateMessage leaves pgn=0 for a standard 11-bit message (got %u)",
              std_msg->pgn);

        EEC_Architecture_Destroy(arch);
    }

    printf("=== Result: %d passed, %d failed ===\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
