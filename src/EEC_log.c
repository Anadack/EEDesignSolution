/**
 * @file    EEC_log.c
 * @brief   E/E Architect Design — Logging utilities implementation.
 * @author  Anadack Temtching Dassi
 * @date    2026
 */
#include "EEC_log.h"
#include <stdarg.h>

/** @brief Current log file handle shared by the logger. */
static FILE *g_log_file = NULL;

int EEC_Log_Init(const char *filename)
{
    if (!filename) {
        return 0;
    }
    g_log_file = fopen(filename, "w");
    return g_log_file ? 0 : -1;
}

void EEC_Log_Close(void)
{
    if (g_log_file) {
        fclose(g_log_file);
        g_log_file = NULL;
    }
}

void EEC_Log_Write(const char *level, const char *message)
{
    const char *lvl = level ? level : EEC_LOG_INFO;
    const char *msg = message ? message : "";
    fprintf(stdout, "[%s] %s\n", lvl, msg);
    if (g_log_file) {
        fprintf(g_log_file, "[%s] %s\n", lvl, msg);
        fflush(g_log_file);
    }
}

void EEC_Log_Printf(const char *level, const char *fmt, ...)
{
    char buffer[512];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt ? fmt : "", args);
    va_end(args);
    EEC_Log_Write(level, buffer);
}
