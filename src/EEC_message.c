/**
 * @file    EEC_message.c
 * @brief   E/E Architect Design — SWC and CAN message model implementation.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */

#include <stdio.h>
#include "EEC_message.h"
#include "EEC_log.h"

#include <stdlib.h>
#include <string.h>

/* ── Local array helpers (mirror EEC_architecture.c growth policy) ─────── */

static int msg_reserve_value_array(void **array, uint32_t *capacity,
                                   uint32_t needed, size_t elem_size)
{
    void *tmp;
    uint32_t new_capacity = (*capacity == 0U) ? 4U : *capacity;
    while (new_capacity < needed) {
        new_capacity *= 2U;
    }
    tmp = realloc(*array, (size_t)new_capacity * elem_size);
    if (!tmp) {
        return -1;
    }
    *array = tmp;
    *capacity = new_capacity;
    return 0;
}

static int msg_reserve_ptr_array(void ***array, uint32_t *capacity, uint32_t needed)
{
    return msg_reserve_value_array((void **)array, capacity, needed, sizeof(void *));
}

static void msg_copy_string(char *dest, size_t dest_size, const char *src)
{
    if (!dest || dest_size == 0U) {
        return;
    }
    if (!src) {
        dest[0] = '\0';
        return;
    }
    snprintf(dest, dest_size, "%s", src);
}

/* ── SWC lifecycle ─────────────────────────────────────────────────────── */

EEC_Swc_t *EEC_System_CreateSwc(EEC_System_t *system, const char *name)
{
    EEC_Swc_t *swc;
    EEC_Architecture_t *arch;

    if (!system || !system->owner_architecture) {
        return NULL;
    }
    arch = system->owner_architecture;

    swc = (EEC_Swc_t *)calloc(1U, sizeof(EEC_Swc_t));
    if (!swc) {
        return NULL;
    }

    swc->id = EEC_ID_MAKE(arch->ids.next_swc_id++, 0U);
    msg_copy_string(swc->name, sizeof(swc->name),
                    (name && name[0] != '\0') ? name : system->name);
    swc->owner_system = system;
    swc->owner_architecture = arch;
    swc->allocated_ecu = NULL;

    if (msg_reserve_ptr_array((void ***)&system->swcs, &system->swc_capacity,
                              system->swc_count + 1U) != 0) {
        free(swc);
        return NULL;
    }

    system->swcs[system->swc_count++] = swc;
    EEC_Log_Printf(EEC_LOG_TRACE, "Created SWC #%u '%s' for system '%s'",
                   swc->id, swc->name, system->name);
    return swc;
}

void EEC_Swc_AllocateToEcu(EEC_Swc_t *swc, EEC_Ecu_t *ecu)
{
    if (!swc) {
        return;
    }
    swc->allocated_ecu = ecu;
}

int EEC_Swc_AddVariable(EEC_Swc_t *swc, EEC_Signal_t *signal)
{
    uint32_t i;

    if (!swc || !signal) {
        return -1;
    }

    /* Idempotent: do not register the same variable twice. */
    for (i = 0U; i < swc->variable_count; ++i) {
        if (swc->variables[i] == signal) {
            return 0;
        }
    }

    if (msg_reserve_ptr_array((void ***)&swc->variables, &swc->variable_capacity,
                              swc->variable_count + 1U) != 0) {
        return -1;
    }

    swc->variables[swc->variable_count++] = signal;
    signal->producer_swc = swc;
    EEC_Log_Printf(EEC_LOG_TRACE, "SWC '%s' produces variable '%s'",
                   swc->name, signal->name);
    return 0;
}

EEC_Signal_t *EEC_Swc_CreateVariable(EEC_Swc_t *swc, const char *name,
                                     EEC_SignalType_t type,
                                     EEC_SignalInterface_t interface_type,
                                     EEC_SignalUnit_t unit,
                                     float min_value, float max_value,
                                     float resolution, float scaling)
{
    EEC_Signal_t *signal;

    if (!swc || !swc->owner_architecture || !name) {
        return NULL;
    }

    signal = EEC_Architecture_CreateSignalEx(swc->owner_architecture, name, type,
                                             interface_type, unit,
                                             min_value, max_value,
                                             resolution, scaling);
    if (!signal) {
        return NULL;
    }

    if (EEC_Swc_AddVariable(swc, signal) != 0) {
        /* Signal stays registered in the architecture; only the SWC link failed. */
        return NULL;
    }
    return signal;
}

uint32_t EEC_Swc_ImportVariables(EEC_Swc_t *swc,
                                 const EEC_SwcVariableDef_t *defs, uint32_t count)
{
    uint32_t i;
    uint32_t created = 0U;

    if (!swc || !defs) {
        return 0U;
    }

    for (i = 0U; i < count; ++i) {
        const EEC_SwcVariableDef_t *d = &defs[i];
        EEC_Signal_t *sig = EEC_Swc_CreateVariable(swc, d->name, d->type,
                                                   d->interface_type, d->unit,
                                                   d->min_value, d->max_value,
                                                   d->resolution, d->scaling);
        if (sig) {
            ++created;
        }
    }

    EEC_Log_Printf(EEC_LOG_TRACE, "SWC '%s' imported %u/%u variable(s)",
                   swc->name, created, count);
    return created;
}

void EEC_System_DestroySwcs(EEC_System_t *system)
{
    uint32_t i, j;

    if (!system) {
        return;
    }

    for (i = 0U; i < system->swc_count; ++i) {
        EEC_Swc_t *swc = system->swcs[i];
        if (!swc) {
            continue;
        }
        for (j = 0U; j < swc->message_count; ++j) {
            EEC_Message_t *msg = swc->messages[j];
            if (!msg) {
                continue;
            }
            free(msg->tx_ports);
            free(msg->entries);
            free(msg);
        }
        free(swc->messages);
        free(swc->variables);
        free(swc);
    }

    free(system->swcs);
    system->swcs = NULL;
    system->swc_count = 0U;
    system->swc_capacity = 0U;
}

/* ── Message lifecycle ─────────────────────────────────────────────────── */

EEC_Message_t *EEC_Swc_CreateMessage(EEC_Swc_t *swc, const char *name,
                                     uint32_t frame_id, bool is_extended, uint8_t dlc)
{
    EEC_Message_t *msg;

    if (!swc || !swc->owner_architecture) {
        return NULL;
    }

    msg = (EEC_Message_t *)calloc(1U, sizeof(EEC_Message_t));
    if (!msg) {
        return NULL;
    }

    msg->id = EEC_ID_MAKE(swc->owner_architecture->ids.next_message_id++, 0U);
    msg_copy_string(msg->name, sizeof(msg->name), name);
    msg->frame_id = frame_id;
    msg->is_extended = is_extended;
    msg->dlc = dlc;
    msg->priority = EEC_PRIORITY_LOW;
    msg->safety = EEC_SAFETY_QM;
    msg->owner_swc = swc;

    if (msg_reserve_ptr_array((void ***)&swc->messages, &swc->message_capacity,
                              swc->message_count + 1U) != 0) {
        free(msg);
        return NULL;
    }

    swc->messages[swc->message_count++] = msg;
    EEC_Log_Printf(EEC_LOG_TRACE, "Created message #%u '%s' (id=0x%X) on SWC '%s'",
                   msg->id, msg->name, frame_id, swc->name);
    return msg;
}

EEC_MessageSignal_t *EEC_Message_AddSignal(EEC_Message_t *msg, EEC_Signal_t *signal,
                                           uint16_t start_bit, uint16_t length,
                                           bool little_endian, float scale, float offset)
{
    EEC_MessageSignal_t *entry;

    if (!msg || !signal) {
        return NULL;
    }

    if (msg_reserve_value_array((void **)&msg->entries, &msg->entry_capacity,
                                msg->entry_count + 1U,
                                sizeof(EEC_MessageSignal_t)) != 0) {
        return NULL;
    }

    entry = &msg->entries[msg->entry_count++];
    memset(entry, 0, sizeof(*entry));
    entry->signal = signal;
    entry->start_bit = start_bit;
    entry->length = length;
    entry->little_endian = little_endian;
    entry->scale = scale;
    entry->offset = offset;
    entry->receiver_count = 0U;
    return entry;
}

int EEC_MessageSignal_AddReceiver(EEC_MessageSignal_t *ms, EEC_Ecu_t *rx)
{
    if (!ms || !rx) {
        return -1;
    }
    if (ms->receiver_count >= EEC_MSG_MAX_RX) {
        return -1;
    }
    ms->receivers[ms->receiver_count++] = rx;
    return 0;
}

EEC_MessageTx_t *EEC_Message_AddTxPort(EEC_Message_t *msg, EEC_Bus_t *bus,
                                       EEC_Ecu_t *ecu, uint8_t port_index,
                                       uint32_t cycle_time_ms)
{
    EEC_MessageTx_t *tx;
    uint32_t i;

    if (!msg || !bus || !ecu) {
        return NULL;
    }

    /* Reject duplicate (bus, port) bindings on the same message. */
    for (i = 0U; i < msg->tx_count; ++i) {
        if (msg->tx_ports[i].bus == bus &&
            msg->tx_ports[i].ecu == ecu &&
            msg->tx_ports[i].port_index == port_index) {
            return &msg->tx_ports[i];
        }
    }

    if (msg_reserve_value_array((void **)&msg->tx_ports, &msg->tx_capacity,
                                msg->tx_count + 1U,
                                sizeof(EEC_MessageTx_t)) != 0) {
        return NULL;
    }

    tx = &msg->tx_ports[msg->tx_count++];
    tx->bus = bus;
    tx->ecu = ecu;
    tx->port_index = port_index;
    tx->cycle_time_ms = cycle_time_ms;
    return tx;
}

/* ── Derived-view rebuilders ───────────────────────────────────────────── */

void EEC_Architecture_RebuildHostedSwcs(EEC_Architecture_t *arch)
{
    uint32_t i, s;

    if (!arch) {
        return;
    }

    /* Reset every ECU's derived list (keep capacity for reuse). */
    for (i = 0U; i < arch->ecu_count; ++i) {
        if (arch->ecus[i]) {
            arch->ecus[i]->hosted_swc_count = 0U;
        }
    }

    for (i = 0U; i < arch->system_count; ++i) {
        EEC_System_t *system = arch->systems[i];
        if (!system) {
            continue;
        }
        for (s = 0U; s < system->swc_count; ++s) {
            EEC_Swc_t *swc = system->swcs[s];
            EEC_Ecu_t *ecu;
            if (!swc || !swc->allocated_ecu) {
                continue;
            }
            ecu = swc->allocated_ecu;
            if (msg_reserve_ptr_array((void ***)&ecu->hosted_swcs,
                                      &ecu->hosted_swc_capacity,
                                      ecu->hosted_swc_count + 1U) != 0) {
                continue;
            }
            ecu->hosted_swcs[ecu->hosted_swc_count++] = swc;
        }
    }
}

void EEC_Architecture_RebuildBusMessages(EEC_Architecture_t *arch)
{
    uint32_t i, s, m, t;

    if (!arch) {
        return;
    }

    /* Reset every bus's derived list (keep capacity for reuse). */
    for (i = 0U; i < arch->bus_count; ++i) {
        if (arch->buses[i]) {
            arch->buses[i]->message_count = 0U;
        }
    }

    for (i = 0U; i < arch->system_count; ++i) {
        EEC_System_t *system = arch->systems[i];
        if (!system) {
            continue;
        }
        for (s = 0U; s < system->swc_count; ++s) {
            EEC_Swc_t *swc = system->swcs[s];
            if (!swc) {
                continue;
            }
            for (m = 0U; m < swc->message_count; ++m) {
                EEC_Message_t *msg = swc->messages[m];
                if (!msg) {
                    continue;
                }
                for (t = 0U; t < msg->tx_count; ++t) {
                    EEC_Bus_t *bus = msg->tx_ports[t].bus;
                    uint32_t k;
                    bool already;
                    if (!bus) {
                        continue;
                    }
                    /* A message may bind several ports on the same bus; list it once. */
                    already = false;
                    for (k = 0U; k < bus->message_count; ++k) {
                        if (bus->messages[k] == msg) {
                            already = true;
                            break;
                        }
                    }
                    if (already) {
                        continue;
                    }
                    if (msg_reserve_ptr_array((void ***)&bus->messages,
                                              &bus->message_capacity,
                                              bus->message_count + 1U) != 0) {
                        continue;
                    }
                    bus->messages[bus->message_count++] = msg;
                }
            }
        }
    }
}
