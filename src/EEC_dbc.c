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

                    fprintf(f, " SG_ %s : %u|%u@%d%c (%g,%g) [%g|%g] \"%s\"",
                            (sig->name[0] != '\0') ? sig->name : "UnnamedSig",
                            (unsigned)ms->start_bit,
                            (unsigned)ms->length,
                            ms->little_endian ? 1 : 0,
                            sign_char,
                            (double)ms->scale,
                            (double)ms->offset,
                            (double)sig->min_value,
                            (double)sig->max_value,
                            dbc_unit_str(sig->unit));

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

    fclose(f);
    EEC_Log_Printf(EEC_LOG_INFO, "DBC export: %d message(s) → %s", written, filename);
    return written;
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
