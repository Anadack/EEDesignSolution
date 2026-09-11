/**
 * @file    EEC_log.h
 * @brief   E/E Architect Design — Logging utilities.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#ifndef EEC_LOG_H
#define EEC_LOG_H

#include <stdio.h>

#ifdef __cplusplus
extern "C" {
#endif

/** @brief String used for information messages. */
#define EEC_LOG_INFO  "INFO"
/** @brief String used for warning messages. */
#define EEC_LOG_WARN  "WARN"
/** @brief String used for error messages. */
#define EEC_LOG_ERROR "ERROR"
/** @brief String used for trace messages. */
#define EEC_LOG_TRACE "TRACE"

/** @brief Open the framework log file.
 *  @param filename Output log path.
 *  @return 0 on success, -1 on error.
 */
int EEC_Log_Init(const char *filename);

/** @brief Close the current log file. */
void EEC_Log_Close(void);

/** @brief Write one formatted log line to stdout and the log file.
 *  @param level Log severity string.
 *  @param message Message text.
 */
void EEC_Log_Write(const char *level, const char *message);

/** @brief printf-style logger.
 *  @param level Log severity string.
 *  @param fmt printf format string.
 */
void EEC_Log_Printf(const char *level, const char *fmt, ...);

#ifdef __cplusplus
}
#endif
#endif
