/**
 * @file    EEC_zone.h
 * @brief   E/E Architect Design — Zonal/Central architecture distribution.
 * @author  Anadack Temtching Dassi
 * @date    2026
 *
 * A zone groups a subset of ECUs. Systems can be assigned to exactly one zone.
 * In ZONAL mode the auto-mapper routes each assigned system only onto its
 * zone's ECUs; in CENTRAL mode (default) systems may use every ECU.
 *
 * Zones can be defined programmatically (CreateZone / Zone_AddEcu /
 * AssignSystemToZone) or loaded from a JSON file (LoadZones).
 */
#ifndef EEC_ZONE_H
#define EEC_ZONE_H

#include "EEC_architecture.h"
#include <stdio.h>

#ifdef __cplusplus
extern "C" {
#endif

/** @brief Set the architecture distribution mode. */
void EEC_Architecture_SetMode(EEC_Architecture_t *arch, EEC_ArchMode_t mode);

/** @brief Canonical mode name ("CENTRAL"|"ZONAL"). */
const char *EEC_ArchMode_ToString(EEC_ArchMode_t mode);

/** @brief Parse a mode name (case-insensitive); unknown/NULL -> CENTRAL. */
EEC_ArchMode_t EEC_ArchMode_FromString(const char *name);

/** @brief Create and register a zone.
 *  @return New zone, or an existing zone with the same name, or NULL on error.
 */
EEC_Zone_t *EEC_Architecture_CreateZone(EEC_Architecture_t *arch, const char *name);

/** @brief Find a zone by name, or NULL. */
EEC_Zone_t *EEC_Architecture_FindZone(EEC_Architecture_t *arch, const char *name);

/** @brief Add an ECU to a zone (ignored if already present).
 *  @return 0 on success, -1 on invalid input or allocation failure.
 */
int EEC_Zone_AddEcu(EEC_Zone_t *zone, EEC_Ecu_t *ecu);

/** @brief Assign a system to exactly one zone (replaces any previous zone).
 *  @return 0 on success, -1 on invalid input.
 */
int EEC_Architecture_AssignSystemToZone(EEC_System_t *system, EEC_Zone_t *zone);

/** @brief Find a registered ECU by instance name, or NULL. */
EEC_Ecu_t *EEC_Architecture_FindEcu(EEC_Architecture_t *arch, const char *name);

/** @brief Find a registered system by name, or NULL. */
EEC_System_t *EEC_Architecture_FindSystem(EEC_Architecture_t *arch, const char *name);

/** @brief Load mode + zones + system assignments from a JSON file.
 *
 *  Schema:
 *  {
 *    "mode": "ZONAL",
 *    "zones": [
 *      { "name": "Cabin", "ecus": ["AEC_CABIN_01"], "systems": ["Cabin_..."] }
 *    ]
 *  }
 *  ECU and system names are resolved against the already-built architecture;
 *  unresolved names are reported to the log and skipped.
 *  @return Number of zones created, or -1 on invalid input or file failure.
 */
int EEC_Architecture_LoadZones(EEC_Architecture_t *arch, const char *path);

/** @brief Export mode, zones, ECUs and assigned systems to a JSON file.
 *  @return 0 on success, -1 on invalid input or file failure.
 */
int EEC_Export_zones_json(const EEC_Architecture_t *arch, const char *path);

/** @brief Verify zone consistency and write results to @p report.
 *  In ZONAL mode: every auto-mappable system must be assigned to exactly one
 *  zone, and every zone must have at least one ECU.
 *  @return Number of errors found (0 = OK).
 */
int EEC_Verify_zones(const EEC_Architecture_t *arch, FILE *report);

#ifdef __cplusplus
}
#endif
#endif
