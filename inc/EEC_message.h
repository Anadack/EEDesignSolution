/**
 * @file    EEC_message.h
 * @brief   E/E Architect Design — SWC and CAN message model.
 * @author  Anadack Temtching Dassi
 * @date    2026
 *
 * Ownership model:
 *   System ──1..n──▶ SWC ──0..n──▶ Message ──1..n──▶ tx port (ECU CAN port on a bus)
 *
 * A SWC (software component) carries the logical behaviour of a system and is
 * allocated to exactly one ECU. Messages are owned by the SWC, so re-allocating
 * a SWC to another ECU moves its messages with it. The transport bindings
 * (which ECU port / which bus a message is transmitted on) are recomputed at
 * mapping time and are therefore treated as derivable data.
 */
#ifndef EEC_MESSAGE_H
#define EEC_MESSAGE_H

#include "EEC_architecture.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ── SWC lifecycle ─────────────────────────────────────────────────────── */

/** @brief Create and register one SWC inside a system.
 *  @param system Owning system.
 *  @param name   SWC name (may be NULL to use a default).
 *  @return Newly created SWC, or NULL on invalid input or allocation failure.
 */
EEC_Swc_t *EEC_System_CreateSwc(EEC_System_t *system, const char *name);

/** @brief Allocate a SWC to an ECU (authoritative deployment link).
 *  @param swc SWC to allocate.
 *  @param ecu Target ECU, or NULL to unallocate.
 */
void EEC_Swc_AllocateToEcu(EEC_Swc_t *swc, EEC_Ecu_t *ecu);

/** @brief Register an existing architecture signal as a software variable
 *  produced by this SWC. Sets the signal's producer_swc back-reference.
 *  A software variable has no physical device pin but may feed a CAN message.
 *  @param swc    Producing SWC.
 *  @param signal Architecture signal computed by the SWC.
 *  @return 0 on success, -1 on invalid input or allocation failure.
 */
int EEC_Swc_AddVariable(EEC_Swc_t *swc, EEC_Signal_t *signal);

/** @brief Declarative definition of one SWC software variable, used for batch import. */
typedef struct EEC_SwcVariableDef_s {
    const char           *name;           /**< Variable/signal name. */
    EEC_SignalType_t      type;           /**< Payload representation. */
    EEC_SignalInterface_t interface_type; /**< Interface (typically CAN for network variables). */
    EEC_SignalUnit_t      unit;           /**< Engineering unit. */
    float                 min_value;      /**< Minimum engineering value. */
    float                 max_value;      /**< Maximum engineering value. */
    float                 resolution;     /**< Resolution / LSB. */
    float                 scaling;        /**< Scaling factor. */
} EEC_SwcVariableDef_t;

/** @brief Create a new architecture signal and register it as a SWC variable.
 *  Convenience wrapper over EEC_Architecture_CreateSignalEx + EEC_Swc_AddVariable.
 *  @param swc            Producing SWC (its owner architecture receives the signal).
 *  @param name           Variable/signal name.
 *  @param type           Payload representation.
 *  @param interface_type Interface (typically CAN for network variables).
 *  @param unit           Engineering unit.
 *  @param min_value      Minimum engineering value.
 *  @param max_value      Maximum engineering value.
 *  @param resolution     Resolution / LSB.
 *  @param scaling        Scaling factor.
 *  @return The created signal, or NULL on invalid input or allocation failure.
 */
EEC_Signal_t *EEC_Swc_CreateVariable(EEC_Swc_t *swc, const char *name,
                                     EEC_SignalType_t type,
                                     EEC_SignalInterface_t interface_type,
                                     EEC_SignalUnit_t unit,
                                     float min_value, float max_value,
                                     float resolution, float scaling);

/** @brief Batch-create a list of SWC software variables.
 *  @param swc   Producing SWC.
 *  @param defs  Array of variable definitions.
 *  @param count Number of definitions.
 *  @return Number of variables successfully created.
 */
uint32_t EEC_Swc_ImportVariables(EEC_Swc_t *swc,
                                 const EEC_SwcVariableDef_t *defs, uint32_t count);

/** @brief Destroy every SWC owned by a system (and their messages).
 *  Used by EEC_Architecture_Destroy; frees the system's swcs[] array too.
 *  @param system System whose SWCs are released. NULL is accepted.
 */
void EEC_System_DestroySwcs(EEC_System_t *system);

/* ── Message lifecycle ─────────────────────────────────────────────────── */

/** @brief Create and register one CAN message under a SWC.
 *  @param swc         Owning SWC.
 *  @param name        Message name (DBC BO_), may be NULL.
 *  @param frame_id    CAN identifier (11 or 29 bit).
 *  @param is_extended True for 29-bit identifiers.
 *  @param dlc         Data length code in bytes.
 *  @return Newly created message, or NULL on invalid input or allocation failure.
 */
EEC_Message_t *EEC_Swc_CreateMessage(EEC_Swc_t *swc, const char *name,
                                     uint32_t frame_id, bool is_extended, uint8_t dlc);

/** @brief Derive the J1939 PGN (Parameter Group Number) from a 29-bit CAN frame_id.
 *  Implements SAE J1939-21: extracts Data Page (bit 24), PDU Format (bits 16-23),
 *  and PDU Specific (bits 8-15). For PDU1 format (PF < 240, peer-to-peer/destination
 *  addressed), PS is a destination address and is NOT part of the PGN, so it reads
 *  as 0 in the returned value. For PDU2 format (PF >= 240, broadcast), PS is a group
 *  extension and IS part of the PGN.
 *  @param frame_id 29-bit extended CAN identifier (only bits 0-28 are used).
 *  @return The PGN (0..0x3FFFF), or 0 if frame_id does not look like J1939
 *          (callers needing to distinguish "PGN 0" from "not applicable" should
 *          also check EEC_Message_t.is_extended).
 */
uint32_t EEC_J1939_PgnFromFrameId(uint32_t frame_id);

/** @brief Add a signal placement to a message.
 *  @param msg           Target message.
 *  @param signal        Existing logical signal to reference (not owned).
 *  @param start_bit     Start bit in the frame.
 *  @param length        Signal length in bits.
 *  @param little_endian True = Intel byte order, false = Motorola.
 *  @param scale         DBC scale factor.
 *  @param offset        DBC offset.
 *  @return Pointer to the created placement, or NULL on invalid input/allocation failure.
 */
EEC_MessageSignal_t *EEC_Message_AddSignal(EEC_Message_t *msg, EEC_Signal_t *signal,
                                           uint16_t start_bit, uint16_t length,
                                           bool little_endian, float scale, float offset);

/** @brief Register a receiver ECU on a message signal.
 *  @param ms Message signal placement.
 *  @param rx Receiving ECU.
 *  @return 0 on success, -1 on invalid input or when the receiver table is full.
 */
int EEC_MessageSignal_AddReceiver(EEC_MessageSignal_t *ms, EEC_Ecu_t *rx);

/** @brief Add a transmit binding (ECU CAN port on a bus) to a message.
 *  A message can have several bindings, so the same frame can be broadcast on
 *  several ports of the sending ECU and hence on several buses.
 *  @param msg           Target message.
 *  @param bus           Bus the port transmits on.
 *  @param ecu           ECU owning the CAN port (should equal owner_swc->allocated_ecu).
 *  @param port_index    CAN channel index (1-based).
 *  @param cycle_time_ms Periodicity on this bus (0 = event-driven).
 *  @return Pointer to the created binding, or NULL on invalid input/allocation failure.
 */
EEC_MessageTx_t *EEC_Message_AddTxPort(EEC_Message_t *msg, EEC_Bus_t *bus,
                                       EEC_Ecu_t *ecu, uint8_t port_index,
                                       uint32_t cycle_time_ms);

/* ── Derived-view rebuilders ───────────────────────────────────────────── */

/** @brief Rebuild every ECU's derived hosted_swcs[] list from SWC allocations.
 *  @param arch Architecture to reindex.
 */
void EEC_Architecture_RebuildHostedSwcs(EEC_Architecture_t *arch);

/** @brief Rebuild every bus's derived messages[] list from message tx ports.
 *  @param arch Architecture to reindex.
 */
void EEC_Architecture_RebuildBusMessages(EEC_Architecture_t *arch);

#ifdef __cplusplus
}
#endif
#endif
