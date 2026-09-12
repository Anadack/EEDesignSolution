/* Hermetic unit test for verification rule P1 (per-connector power budget).
 *
 * Builds a connector with a known aggregate current capacity (rated_current
 * x total_cavities), maps actuators onto its pins with known nominal_current
 * draws, and asserts the P1 ERROR fires when the sum exceeds capacity; then
 * a healthy connector and asserts it stays silent. Uses tmpfile() so it is
 * portable (no hardcoded paths). */

#include "EEC_architecture.h"
#include "EEC_verify.h"

#include <stdio.h>
#include <string.h>

static int report_contains(FILE *f, const char *needle)
{
    char buf[8192];
    size_t n;
    int found;
    fflush(f);
    rewind(f);
    n = fread(buf, 1, sizeof(buf) - 1U, f);
    buf[n] = '\0';
    found = strstr(buf, needle) != NULL;
    return found;
}

/* Build one ECU with a single connector of `cavities` pins rated at
 * `rated_a` A/contact, then map `count` actuators drawing `each_a` A onto
 * `count` of its pins (role OUTPUT, matching ECU OUTPUT pins). */
static EEC_Architecture_t *build(uint8_t cavities, float rated_a, int count, float each_a)
{
    EEC_Architecture_t *arch = EEC_Architecture_Create("t");
    EEC_Ecu_t *ecu = EEC_Architecture_CreateEcu(arch, "ECU_A", "AEC_MEDIUM");
    EEC_System_t *sys = EEC_Architecture_CreateSystem(arch, "S");
    EEC_Component_t *comp = EEC_System_CreateComponent(sys, "C");
    int i;

    EEC_Ecu_CreateConnector(ecu, "X1", "", EEC_CONNECTOR_FAMILY_CUSTOM, EEC_CONNECTOR_GENDER_MALE, cavities);
    for (i = 0; i < (int)cavities; ++i) {
        char nm[32];
        snprintf(nm, sizeof(nm), "OUT_%d", i);
        EEC_Ecu_CreatePin(ecu, (uint32_t)(i + 1), "X1", nm, "OUT", EEC_PIN_ROLE_OUTPUT,
                          EEC_PIN_INTERFACE_DIGITAL, 0xFFFFFFFFU, 0U, "0..14 V", "");
    }
    /* Set the connector's aggregate-capacity inputs directly (public struct
     * field, same pattern as other qa tests setting bus->bitrate etc.). */
    ecu->connectors[0].rated_current = rated_a;

    for (i = 0; i < count; ++i) {
        char nm[32], pname[32];
        EEC_Signal_t *sig;
        EEC_Actuator_t *act;
        EEC_DevicePin_t *dp;
        snprintf(nm, sizeof(nm), "SIG_%d", i);
        snprintf(pname, sizeof(pname), "ACT_%d", i);
        sig = EEC_Architecture_CreateSignalEx(arch, nm, EEC_SIGNAL_TYPE_UNSIGNED_1BIT,
                                              EEC_SIGNAL_INTERFACE_DIGITAL, EEC_SIGNAL_UNIT_NONE,
                                              0.0f, 1.0f, 1.0f, 1.0f);
        act = EEC_Component_CreateActuator(comp, pname);
        dp = EEC_Actuator_CreatePin(act, 1U, EEC_PIN_ROLE_INPUT, sig, EEC_PIN_INTERFACE_DIGITAL, "IN");
        dp->nominal_current = each_a;
        EEC_Ecu_ConnectSignalToPin(ecu, "X1", (uint32_t)(i + 1), sig);
    }

    return arch;
}

int main(void)
{
    int failures = 0;

    /* Overloaded: 4 cavities x 1 A/contact = 4 A capacity; 4 actuators x
     * 2 A each = 8 A drawn -> 200% of capacity. */
    {
        EEC_Architecture_t *arch = build(4U, 1.0f, 4, 2.0f);
        FILE *f = tmpfile();
        EEC_Verify_architecture(arch, f);
        if (report_contains(f, "P1 power budget") && report_contains(f, "exceeds capacity")) {
            printf("[PASS] P1 fires on overloaded connector\n");
        } else {
            printf("[FAIL] P1 did NOT fire on overloaded connector\n");
            ++failures;
        }
        fclose(f);
        EEC_Architecture_Destroy(arch);
    }

    /* Healthy: 8 cavities x 5 A/contact = 40 A capacity; 2 actuators x
     * 0.5 A each = 1 A drawn -> 2.5% of capacity. */
    {
        EEC_Architecture_t *arch = build(8U, 5.0f, 2, 0.5f);
        FILE *f = tmpfile();
        EEC_Verify_architecture(arch, f);
        if (!report_contains(f, "power budget") || report_contains(f, "[PASS] P1")) {
            printf("[PASS] P1 silent/passing on healthy connector\n");
        } else {
            printf("[FAIL] P1 wrongly flagged healthy connector\n");
            ++failures;
        }
        fclose(f);
        EEC_Architecture_Destroy(arch);
    }

    printf("=== Result: %s ===\n", failures == 0 ? "all passed" : "FAILURES");
    return failures == 0 ? 0 : 1;
}
