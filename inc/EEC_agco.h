/**
 * @file    EEC_agco.h
 * @brief   E/E Architect Design — AGCO ECU factory presets.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#ifndef EEC_AGCO_H
#define EEC_AGCO_H

#include "EEC_architecture.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @brief Create one pre-populated SMALL AEC ECU variant.
 *  @param arch Owning architecture.
 *  @param ecu_name ECU name.
 *  @param can_address_count Number of CAN addresses that follow in the variadic argument list.
 *  @return Newly created ECU, or NULL on invalid input or allocation failure.
 */
EEC_Ecu_t *EEC_Agco_CreateEcuSmall(EEC_Architecture_t *arch, const char *ecu_name, uint8_t can_address_count, ...);

/** @brief Create one pre-populated MEDIUM AEC ECU variant.
 *  @param arch Owning architecture.
 *  @param ecu_name ECU name.
 *  @param can_address_count Number of CAN addresses that follow in the variadic argument list.
 *  @return Newly created ECU, or NULL on invalid input or allocation failure.
 */
EEC_Ecu_t *EEC_Agco_CreateEcuMedium(EEC_Architecture_t *arch, const char *ecu_name, uint8_t can_address_count, ...);

/** @brief Create one pre-populated LARGE AEC ECU variant.
 *  @param arch Owning architecture.
 *  @param ecu_name ECU name.
 *  @param can_address_count Number of CAN addresses that follow in the variadic argument list.
 *  @return Newly created ECU, or NULL on invalid input or allocation failure.
 */
EEC_Ecu_t *EEC_Agco_CreateEcuLarge(EEC_Architecture_t *arch, const char *ecu_name, uint8_t can_address_count, ...);

#ifdef __cplusplus
}
#endif
#endif
