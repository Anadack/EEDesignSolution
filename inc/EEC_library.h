/**
 * @file    EEC_library.h
 * @brief   E/E Architect Design — Reusable component library (export/import).
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#ifndef EEC_LIBRARY_H
#define EEC_LIBRARY_H

#include "EEC_architecture.h"

#ifdef __cplusplus
extern "C" {
#endif


/* ── Export (save to library) ───────────────────────────────────────────── */

/** @brief Export one system (with its devices and signal definitions) to a JSON file.
 *  @param system  System to serialize.
 *  @param filepath  Output JSON file path.
 *  @return 0 on success, -1 on error.
 */
int EEC_Library_ExportSystem(const EEC_System_t *system, const char *filepath);

/** @brief Export one sensor (with its signal definitions) to a JSON file.
 *  @param sensor   Sensor to serialize.
 *  @param filepath Output JSON file path.
 *  @return 0 on success, -1 on error.
 */
int EEC_Library_ExportSensor(const EEC_Sensor_t *sensor, const char *filepath);

/** @brief Export one actuator (with its signal definitions) to a JSON file.
 *  @param actuator Actuator to serialize.
 *  @param filepath Output JSON file path.
 *  @return 0 on success, -1 on error.
 */
int EEC_Library_ExportActuator(const EEC_Actuator_t *actuator, const char *filepath);

/** @brief Export a flat signal group to a JSON file.
 *
 *  Signals with a shared prefix and consecutive numbering are collapsed into
 *  a single entry with a @c count field, keeping the file compact and human-
 *  readable.
 *
 *  @param signals   Array of signal pointers.
 *  @param count     Number of entries in @p signals.
 *  @param name      Group name written into the JSON.
 *  @param filepath  Output JSON file path.
 *  @return 0 on success, -1 on error.
 */
int EEC_Library_ExportSignalGroup(EEC_Signal_t *const *signals, uint32_t count,
                                  const char *name, const char *filepath);

/** @brief Export an ECU (variant + CAN addresses) to a JSON file.
 *  @param ecu       ECU to serialize (only metadata; physical pins are omitted).
 *  @param filepath  Output JSON file path.
 *  @return 0 on success, -1 on error.
 */
int EEC_Library_ExportEcu(const EEC_Ecu_t *ecu, const char *filepath);

/** @brief Export a full architecture (ECUs + systems) as a reusable bundle.
 *  @param arch      Architecture to serialize.
 *  @param filepath  Output JSON file path.
 *  @return 0 on success, -1 on error.
 */
int EEC_Library_ExportBundle(const EEC_Architecture_t *arch, const char *filepath);

/* ── Import (load from library) ─────────────────────────────────────────── */

/** @brief Import a system from a library JSON file.
 *
 *  Creates the system, its devices, and all embedded signals inside @p arch.
 *
 *  @param arch      Target architecture.
 *  @param filepath  Path to a @c "type":"system" JSON file.
 *  @return The newly created system, or NULL on error.
 */
EEC_System_t *EEC_Library_ImportSystem(EEC_Architecture_t *arch, const char *filepath);

/** @brief Import a sensor from a library JSON file into a component.
 *
 *  Creates the sensor and all embedded signals inside @p arch, attached to @p component.
 *
 *  @param arch      Target architecture.
 *  @param component Target component to attach the sensor to.
 *  @param filepath  Path to a @c "type":"sensor" JSON file.
 *  @return The newly created sensor, or NULL on error.
 */
EEC_Sensor_t *EEC_Library_ImportSensor(EEC_Architecture_t *arch, EEC_Component_t *component, const char *filepath);

/** @brief Import an actuator from a library JSON file into a component.
 *
 *  Creates the actuator and all embedded signals inside @p arch, attached to @p component.
 *
 *  @param arch      Target architecture.
 *  @param component Target component to attach the actuator to.
 *  @param filepath  Path to a @c "type":"actuator" JSON file.
 *  @return The newly created actuator, or NULL on error.
 */
EEC_Actuator_t *EEC_Library_ImportActuator(EEC_Architecture_t *arch, EEC_Component_t *component, const char *filepath);

/** @brief Import a signal group from a library JSON file.
 *
 *  Signals are created inside @p arch and appended as pins on
 *  @p target_sensor (as input pins) or @p target_actuator (as output pins).
 *  Exactly one of the two target pointers must be non-NULL.
 *
 *  @param arch             Target architecture.
 *  @param target_sensor    Sensor to attach pins to, or NULL.
 *  @param target_actuator  Actuator to attach pins to, or NULL.
 *  @param filepath         Path to a @c "type":"signal_group" JSON file.
 *  @return Number of signals imported, or -1 on error.
 */
int EEC_Library_ImportSignalGroup(EEC_Architecture_t *arch,
                                  EEC_Sensor_t *target_sensor,
                                  EEC_Actuator_t *target_actuator,
                                  const char *filepath);

/** @brief Import an ECU preset from a library JSON file.
 *
 *  Creates the ECU using the matching AEC factory (based on @c variant)
 *  and applies stored CAN addresses.
 *
 *  @param arch            Target architecture.
 *  @param filepath        Path to a @c "type":"ecu" JSON file.
 *  @param instance_name   Instance name for the new ECU (overrides the file name).
 *  @return The newly created ECU, or NULL on error.
 */
EEC_Ecu_t *EEC_Library_ImportEcu(EEC_Architecture_t *arch, const char *filepath,
                                const char *instance_name);

/** @brief Import a full bundle into an existing architecture.
 *
 *  Creates all ECUs and systems defined in the bundle and returns the count
 *  of top-level components imported.
 *
 *  @param arch      Target architecture.
 *  @param filepath  Path to a @c "type":"bundle" JSON file.
 *  @return Number of components imported, or -1 on error.
 */
int EEC_Library_ImportBundle(EEC_Architecture_t *arch, const char *filepath);

#ifdef __cplusplus
}
#endif
#endif
