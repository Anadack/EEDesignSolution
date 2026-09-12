/**
 * @file    EEC_dbc.c
 * @brief   E/E Architect Design — CAN DBC (Vector) import/export implementation.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */

#include "EEC_dbc.h"
#include "EEC_message.h"
#include "EEC_log.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define EEC_DBC_EXT_FLAG 0x80000000U
#define EEC_DBC_STD_MASK 0x7FFU
#define EEC_DBC_EXT_MASK 0x1FFFFFFFU

/* ── Helpers ───────────────────────────────────────────────────────────── */

static const char *dbc_unit_str(EEC_SignalUnit_t unit)
{
    switch (unit) {
        case EEC_SIGNAL_UNIT_VOLT:    return "V";
        case EEC_SIGNAL_UNIT_AMPERE:  return "A";
        case EEC_SIGNAL_UNIT_HERTZ:   return "Hz";
        case EEC_SIGNAL_UNIT_PERCENT: return "%";
        case EEC_SIGNAL_UNIT_RPM:     return "rpm";
        case EEC_SIGNAL_UNIT_CELSIUS: return "degC";
        case EEC_SIGNAL_UNIT_BAR:     return "bar";
        case EEC_SIGNAL_UNIT_DEGREE:  return "deg";
        case EEC_SIGNAL_UNIT_NONE:
        case EEC_SIGNAL_UNIT_BOOLEAN:
        default:                      return "";
    }
}

static bool dbc_type_is_signed(EEC_SignalType_t type)
{
    return type == EEC_SIGNAL_TYPE_SIGNED_8BIT  ||
           type == EEC_SIGNAL_TYPE_SIGNED_16BIT ||
           type == EEC_SIGNAL_TYPE_SIGNED_32BIT ||
           type == EEC_SIGNAL_TYPE_SIGNED_64BIT;
}

static EEC_SignalType_t dbc_type_from_len(uint32_t len, bool is_signed)
{
    if (len <= 1U) {
        return EEC_SIGNAL_TYPE_UNSIGNED_1BIT;
    }
    if (len <= 8U) {
        return is_signed ? EEC_SIGNAL_TYPE_SIGNED_8BIT : EEC_SIGNAL_TYPE_UNSIGNED_8BIT;
    }
    if (len <= 16U) {
        return is_signed ? EEC_SIGNAL_TYPE_SIGNED_16BIT : EEC_SIGNAL_TYPE_UNSIGNED_16BIT;
    }
    if (len <= 32U) {
        return is_signed ? EEC_SIGNAL_TYPE_SIGNED_32BIT : EEC_SIGNAL_TYPE_UNSIGNED_32BIT;
    }
    return is_signed ? EEC_SIGNAL_TYPE_SIGNED_64BIT : EEC_SIGNAL_TYPE_UNSIGNED_64BIT;
}

/** @brief True if @p msg has at least one tx binding on @p bus. */
static bool dbc_msg_on_bus(const EEC_Message_t *msg, const EEC_Bus_t *bus)
{
    uint32_t t;
    for (t = 0U; t < msg->tx_count; ++t) {
        if (msg->tx_ports[t].bus == bus) {
            return true;
        }
    }
    return false;
}

/* ── Export ────────────────────────────────────────────────────────────── */

/* Format a double for DBC output WITHOUT scientific notation, which some DBC
 * parsers and older CANdb+ builds reject. Integer-valued numbers print with no
 * decimal point; fractional numbers print with trailing zeros trimmed. */
static void dbc_fmt_num(char *buf, size_t n, double v)
{
    if (v == (double)(long long)v && fabs(v) < 1e15) {
        snprintf(buf, n, "%lld", (long long)v);
        return;
    }
    snprintf(buf, n, "%.10f", v);
    {
        char *dot = strchr(buf, '.');
        if (dot) {
            char *end = buf + strlen(buf) - 1;
            while (end > dot && *end == '0') { *end-- = '\0'; }
            if (end == dot) { *end = '\0'; }
        }
    }
}

/* Cycle time (ms) of a message on a given bus, 0 if event-driven/not found. */
static uint32_t dbc_msg_cycle_ms(const EEC_Message_t *msg, const EEC_Bus_t *bus)
{
    uint32_t t;
    for (t = 0U; t < msg->tx_count; ++t) {
        if (msg->tx_ports[t].bus == bus) {
            return msg->tx_ports[t].cycle_time_ms;
        }
    }
    return 0U;
}

static void dbc_write_header(FILE *f, const EEC_Bus_t *bus)
{
    uint32_t n;

    fprintf(f, "VERSION \"\"\n\n\n");
    fprintf(f, "NS_ :\n\tNS_DESC_\n\tCM_\n\tBA_DEF_\n\tBA_\n\tVAL_\n"
               "\tCAT_DEF_\n\tCAT_\n\tFILTER\n\tBA_DEF_DEF_\n\tEV_DATA_\n"
               "\tENVVAR_DATA_\n\tSGTYPE_\n\tSGTYPE_VAL_\n\tBA_DEF_SGTYPE_\n"
               "\tSIG_GROUP_\n\tSIG_VALTYPE_\n\tSIGTYPE_VALTYPE_\n\tBO_TX_BU_\n"
               "\tBA_DEF_REL_\n\tBA_REL_\n\tBA_DEF_DEF_REL_\n\tBU_SG_REL_\n"
               "\tBU_EV_REL_\n\tBU_BO_REL_\n\tSG_MUL_VAL_\n\n");
    fprintf(f, "BS_:\n\n");

    /* BU_ node list = ECUs physically present on this bus. */
    fprintf(f, "BU_:");
    for (n = 0U; n < bus->node_count; ++n) {
        if (bus->nodes[n].ecu) {
            fprintf(f, " %s", bus->nodes[n].ecu->name);
        }
    }
    fprintf(f, "\n\n");
}

int EEC_Export_dbc_bus(const EEC_Architecture_t *arch, const EEC_Bus_t *bus,
                       const char *filename)
{
    FILE *f;
    uint32_t i, s, m, e, r;
    int written = 0;

    if (!arch || !bus || !filename) {
        return -1;
    }

    f = fopen(filename, "w");
    if (!f) {
        return -1;
    }

    dbc_write_header(f, bus);

    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *sys = arch->systems[i];
        if (!sys) {
            continue;
        }
        for (s = 0U; s < sys->swc_count; ++s) {
            const EEC_Swc_t *swc = sys->swcs[s];
            if (!swc) {
                continue;
            }
            for (m = 0U; m < swc->message_count; ++m) {
                const EEC_Message_t *msg = swc->messages[m];
                uint32_t dbc_id;
                const char *sender;

                if (!msg || !dbc_msg_on_bus(msg, bus)) {
                    continue;
                }

                dbc_id = msg->is_extended
                       ? ((msg->frame_id & EEC_DBC_EXT_MASK) | EEC_DBC_EXT_FLAG)
                       : (msg->frame_id & EEC_DBC_STD_MASK);
                sender = (swc->allocated_ecu && swc->allocated_ecu->name[0] != '\0')
                       ? swc->allocated_ecu->name : "Vector__XXX";

                fprintf(f, "BO_ %u %s: %u %s\n",
                        dbc_id,
                        (msg->name[0] != '\0') ? msg->name : "UnnamedMsg",
                        (unsigned)msg->dlc, sender);

                for (e = 0U; e < msg->entry_count; ++e) {
                    const EEC_MessageSignal_t *ms = &msg->entries[e];
                    const EEC_Signal_t *sig = ms->signal;
                    char sign_char;
                    bool has_rx = false;

                    if (!sig) {
                        continue;
                    }
                    sign_char = dbc_type_is_signed(sig->type) ? '-' : '+';

                    {
                        char sc[32], of[32], mn[32], mx[32];
                        dbc_fmt_num(sc, sizeof(sc), (double)ms->scale);
                        dbc_fmt_num(of, sizeof(of), (double)ms->offset);
                        dbc_fmt_num(mn, sizeof(mn), (double)sig->min_value);
                        dbc_fmt_num(mx, sizeof(mx), (double)sig->max_value);
                        fprintf(f, " SG_ %s : %u|%u@%d%c (%s,%s) [%s|%s] \"%s\"",
                                (sig->name[0] != '\0') ? sig->name : "UnnamedSig",
                                (unsigned)ms->start_bit,
                                (unsigned)ms->length,
                                ms->little_endian ? 1 : 0,
                                sign_char,
                                sc, of, mn, mx,
                                dbc_unit_str(sig->unit));
                    }

                    for (r = 0U; r < ms->receiver_count; ++r) {
                        if (ms->receivers[r]) {
                            has_rx = true;
                            fprintf(f, " %s", ms->receivers[r]->name);
                        }
                    }
                    if (!has_rx) {
                        fprintf(f, " Vector__XXX");
                    }
                    fprintf(f, "\n");
                }
                fprintf(f, "\n");
                ++written;
            }
        }
    }

    /* Attribute definitions (Vector standard). Placed after all BO_ records.
     * GenMsgCycleTime carries the message period so CANoe/CANalyzer can run a
     * residual-bus simulation; VFrameFormat marks extended messages as J1939 PG
     * so CANdb+ recognizes them as J1939 rather than generic extended CAN. */
    fprintf(f, "BA_DEF_ BO_  \"GenMsgCycleTime\" INT 0 65535;\n");
    fprintf(f, "BA_DEF_ BO_  \"VFrameFormat\" ENUM  \"StandardCAN\",\"ExtendedCAN\",\"reserved\",\"J1939PG\";\n");
    fprintf(f, "BA_DEF_DEF_  \"GenMsgCycleTime\" 0;\n");
    fprintf(f, "BA_DEF_DEF_  \"VFrameFormat\" \"StandardCAN\";\n");

    /* Second pass: per-message attribute values. */
    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *sys = arch->systems[i];
        if (!sys) continue;
        for (s = 0U; s < sys->swc_count; ++s) {
            const EEC_Swc_t *swc = sys->swcs[s];
            if (!swc) continue;
            for (m = 0U; m < swc->message_count; ++m) {
                const EEC_Message_t *msg = swc->messages[m];
                uint32_t dbc_id, cycle;
                if (!msg || !dbc_msg_on_bus(msg, bus)) continue;
                dbc_id = msg->is_extended
                       ? ((msg->frame_id & EEC_DBC_EXT_MASK) | EEC_DBC_EXT_FLAG)
                       : (msg->frame_id & EEC_DBC_STD_MASK);
                cycle = dbc_msg_cycle_ms(msg, bus);
                if (cycle > 0U) {
                    fprintf(f, "BA_ \"GenMsgCycleTime\" BO_ %u %u;\n",
                            dbc_id, cycle);
                }
                /* VFrameFormat: 1 = ExtendedCAN, 3 = J1939PG, 0 = StandardCAN.
                 * Extended IDs in this ag domain are J1939 PGs. */
                fprintf(f, "BA_ \"VFrameFormat\" BO_ %u %d;\n",
                        dbc_id, msg->is_extended ? 3 : 0);
            }
        }
    }

    fclose(f);
    EEC_Log_Printf(EEC_LOG_INFO, "DBC export: %d message(s) → %s", written, filename);
    return written;
}

/* ── Validation ────────────────────────────────────────────────────────── */

/* Is an ECU a node on this bus (i.e. present in BU_)? */
static bool dbc_node_on_bus(const EEC_Bus_t *bus, const EEC_Ecu_t *ecu)
{
    uint32_t n;
    if (!ecu) return false;
    for (n = 0U; n < bus->node_count; ++n) {
        if (bus->nodes[n].ecu == ecu) return true;
    }
    return false;
}

/* Validate the DBC that would be exported for one bus and report DBC-level
 * errors (the kind CANdb+ would reject or that corrupt decoding). Returns the
 * number of errors found. Checks: D1 frame overflow, D2 signal overlap,
 * D3 duplicate frame-id, D4 duplicate signal name in a message, D5 DLC range,
 * D6 zero-length signal, D7 min>max, D8 sender/receiver not in BU_. */
int EEC_Dbc_Validate_bus(const EEC_Architecture_t *arch, const EEC_Bus_t *bus,
                         FILE *report)
{
    int errors = 0;
    uint32_t i, s, m, e, e2, r;

    if (!arch || !bus) return -1;

    /* D3: duplicate frame-id across all messages on the bus. */
    for (i = 0U; i < arch->system_count; ++i) {
        const EEC_System_t *sys = arch->systems[i];
        if (!sys) continue;
        for (s = 0U; s < sys->swc_count; ++s) {
            const EEC_Swc_t *swc = sys->swcs[s];
            if (!swc) continue;
            for (m = 0U; m < swc->message_count; ++m) {
                const EEC_Message_t *msg = swc->messages[m];
                uint64_t bits = 0U;   /* occupied-bit mask, Intel layout */
                uint32_t frame_bits;
                if (!msg || !dbc_msg_on_bus(msg, bus)) continue;
                frame_bits = 8U * (uint32_t)msg->dlc;

                /* D5: DLC range (classic CAN). */
                if (msg->dlc == 0U || msg->dlc > 8U) {
                    ++errors;
                    if (report) fprintf(report, "  [FAIL] D5 msg '%s': DLC %u out of range (1..8)\n",
                                        msg->name, (unsigned)msg->dlc);
                }
                /* D8: sender must be a node on the bus. */
                if (swc->allocated_ecu && !dbc_node_on_bus(bus, swc->allocated_ecu)) {
                    ++errors;
                    if (report) fprintf(report, "  [FAIL] D8 msg '%s': transmitter '%s' not in BU_ (not on bus)\n",
                                        msg->name, swc->allocated_ecu->name);
                }

                for (e = 0U; e < msg->entry_count; ++e) {
                    const EEC_MessageSignal_t *ms = &msg->entries[e];
                    const EEC_Signal_t *sig = ms->signal;
                    if (!sig) continue;

                    /* D6: zero length. */
                    if (ms->length == 0U) {
                        ++errors;
                        if (report) fprintf(report, "  [FAIL] D6 msg '%s' sig '%s': zero length\n",
                                            msg->name, sig->name);
                        continue;
                    }
                    /* D1: frame overflow (Intel layout). */
                    if (ms->little_endian &&
                        (ms->start_bit + ms->length) > frame_bits) {
                        ++errors;
                        if (report) fprintf(report, "  [FAIL] D1 msg '%s' sig '%s': bits %u..%u exceed frame (%u bits)\n",
                                            msg->name, sig->name,
                                            (unsigned)ms->start_bit,
                                            (unsigned)(ms->start_bit + ms->length - 1U),
                                            frame_bits);
                    }
                    /* D2: overlap (Intel layout, up to 64 bits). */
                    if (ms->little_endian && frame_bits <= 64U) {
                        uint32_t bpos;
                        for (bpos = ms->start_bit;
                             bpos < ms->start_bit + ms->length && bpos < 64U; ++bpos) {
                            uint64_t mask = (uint64_t)1U << bpos;
                            if (bits & mask) {
                                ++errors;
                                if (report) fprintf(report, "  [FAIL] D2 msg '%s' sig '%s': overlaps bit %u\n",
                                                    msg->name, sig->name, bpos);
                                break;
                            }
                            bits |= mask;
                        }
                    }
                    /* D7: min > max. */
                    if (sig->min_value > sig->max_value) {
                        ++errors;
                        if (report) fprintf(report, "  [FAIL] D7 msg '%s' sig '%s': min %g > max %g\n",
                                            msg->name, sig->name,
                                            (double)sig->min_value, (double)sig->max_value);
                    }
                    /* D4: duplicate signal name within the message. */
                    for (e2 = e + 1U; e2 < msg->entry_count; ++e2) {
                        const EEC_Signal_t *o = msg->entries[e2].signal;
                        if (o && o->name[0] && strcmp(o->name, sig->name) == 0) {
                            ++errors;
                            if (report) fprintf(report, "  [FAIL] D4 msg '%s': duplicate signal name '%s'\n",
                                                msg->name, sig->name);
                        }
                    }
                    /* D8: each receiver must be a node on the bus. */
                    for (r = 0U; r < ms->receiver_count; ++r) {
                        if (ms->receivers[r] && !dbc_node_on_bus(bus, ms->receivers[r])) {
                            ++errors;
                            if (report) fprintf(report, "  [FAIL] D8 msg '%s' sig '%s': receiver '%s' not in BU_\n",
                                                msg->name, sig->name, ms->receivers[r]->name);
                        }
                    }
                }
            }
        }
    }

    /* D3: duplicate frame-id — O(n^2) over messages on this bus. */
    {
        uint32_t i2, s2, m2;
        for (i = 0U; i < arch->system_count; ++i) {
            const EEC_System_t *sysa = arch->systems[i];
            if (!sysa) continue;
            for (s = 0U; s < sysa->swc_count; ++s) {
                const EEC_Swc_t *swca = sysa->swcs[s];
                if (!swca) continue;
                for (m = 0U; m < swca->message_count; ++m) {
                    const EEC_Message_t *ma = swca->messages[m];
                    if (!ma || !dbc_msg_on_bus(ma, bus)) continue;
                    for (i2 = i; i2 < arch->system_count; ++i2) {
                        const EEC_System_t *sysb = arch->systems[i2];
                        if (!sysb) continue;
                        for (s2 = (i2 == i ? s : 0U); s2 < sysb->swc_count; ++s2) {
                            const EEC_Swc_t *swcb = sysb->swcs[s2];
                            if (!swcb) continue;
                            for (m2 = (i2 == i && s2 == s ? m + 1U : 0U);
                                 m2 < swcb->message_count; ++m2) {
                                const EEC_Message_t *mb = swcb->messages[m2];
                                if (!mb || !dbc_msg_on_bus(mb, bus)) continue;
                                if (ma->frame_id == mb->frame_id &&
                                    ma->is_extended == mb->is_extended) {
                                    ++errors;
                                    if (report) fprintf(report, "  [FAIL] D3 duplicate frame-id 0x%X ('%s' and '%s')\n",
                                                        ma->frame_id, ma->name, mb->name);
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (report) {
        fprintf(report, "[DBC:%s] %d error(s).\n", bus->name, errors);
    }
    return errors;
}

int EEC_Dbc_Validate_all(const EEC_Architecture_t *arch, FILE *report)
{
    uint32_t b;
    int total = 0;
    if (!arch) return -1;
    for (b = 0U; b < arch->bus_count; ++b) {
        const EEC_Bus_t *bus = arch->buses[b];
        if (!bus) continue;
        if (bus->type == EEC_BUS_TYPE_CAN || bus->type == EEC_BUS_TYPE_ISOBUS) {
            total += EEC_Dbc_Validate_bus(arch, bus, report);
        }
    }
    return total;
}

int EEC_Export_dbc_all(const EEC_Architecture_t *arch, const char *dir)
{
    uint32_t b;
    int files = 0;

    if (!arch || !dir) {
        return -1;
    }

    for (b = 0U; b < arch->bus_count; ++b) {
        const EEC_Bus_t *bus = arch->buses[b];
        char path[1024];

        if (!bus) {
            continue;
        }
        if (bus->type != EEC_BUS_TYPE_CAN && bus->type != EEC_BUS_TYPE_ISOBUS) {
            continue;
        }
        (void)snprintf(path, sizeof(path), "%s/%s.dbc", dir, bus->name);
        if (EEC_Export_dbc_bus(arch, bus, path) >= 0) {
            ++files;
        }
    }
    return files;
}

/* ── Import ────────────────────────────────────────────────────────────── */

int EEC_Import_dbc(EEC_Architecture_t *arch, EEC_Swc_t *swc, const char *filename)
{
    FILE *f;
    char line[1024];
    EEC_Message_t *current = NULL;
    int imported = 0;

    if (!arch || !swc || !filename) {
        return -1;
    }

    f = fopen(filename, "r");
    if (!f) {
        return -1;
    }

    while (fgets(line, sizeof(line), f)) {
        /* Message record. */
        if (strncmp(line, "BO_ ", 4) == 0) {
            unsigned int id = 0U;
            unsigned int dlc = 0U;
            char name[64] = {0};
            char sender[64] = {0};

            if (sscanf(line, "BO_ %u %63[^:]: %u %63s",
                       &id, name, &dlc, sender) >= 3) {
                bool ext = (id & EEC_DBC_EXT_FLAG) != 0U;
                uint32_t frame_id = ext ? (id & EEC_DBC_EXT_MASK)
                                        : (id & EEC_DBC_STD_MASK);
                /* Trim trailing spaces from the name. */
                size_t len = strlen(name);
                while (len > 0U && (name[len - 1U] == ' ' || name[len - 1U] == '\t')) {
                    name[--len] = '\0';
                }
                current = EEC_Swc_CreateMessage(swc, name, frame_id, ext, (uint8_t)dlc);
                if (current) {
                    ++imported;
                }
            }
            continue;
        }

        /* Signal record (belongs to the current message). */
        {
            char signame[64] = {0};
            unsigned int start = 0U;
            unsigned int len = 0U;
            int byteorder = 1;
            char sign = '+';
            float scale = 1.0f;
            float offset = 0.0f;
            float mn = 0.0f;
            float mx = 0.0f;
            char unit[32] = {0};
            int n;

            n = sscanf(line, " SG_ %63s : %u|%u@%d%c (%f,%f) [%f|%f] \"%31[^\"]\"",
                       signame, &start, &len, &byteorder, &sign,
                       &scale, &offset, &mn, &mx, unit);
            if (n >= 7 && current) {
                bool is_signed = (sign == '-');
                EEC_Signal_t *sig = EEC_Architecture_CreateSignalEx(
                    arch, signame,
                    dbc_type_from_len(len, is_signed),
                    EEC_SIGNAL_INTERFACE_CAN,
                    EEC_SIGNAL_UNIT_NONE,
                    mn, mx, scale, scale);
                if (sig) {
                    (void)EEC_Message_AddSignal(current, sig,
                                                (uint16_t)start, (uint16_t)len,
                                                (byteorder == 1), scale, offset);
                }
            }
        }
    }

    fclose(f);
    EEC_Log_Printf(EEC_LOG_INFO, "DBC import: %d message(s) from %s", imported, filename);
    return imported;
}
