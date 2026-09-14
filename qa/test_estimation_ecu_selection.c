/* Hermetic integration test for explicit ECU selection in IO estimation. */
#include "EEC_estimation.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int contains(const char *path, const char *needle)
{
    FILE *f = fopen(path, "rb");
    long size;
    char *data;
    int found;
    if (!f) return 0;
    if (fseek(f, 0, SEEK_END) != 0 || (size = ftell(f)) < 0) { fclose(f); return 0; }
    rewind(f);
    data = malloc((size_t)size + 1U);
    if (!data) { fclose(f); return 0; }
    if (fread(data, 1, (size_t)size, f) != (size_t)size) {
        free(data);
        fclose(f);
        return 0;
    }
    data[size] = '\0';
    found = strstr(data, needle) != NULL;
    free(data);
    fclose(f);
    return found;
}

int main(void)
{
    const char *out = "/tmp/eec_estimation_selected_ecu.json";
    int rc = EEC_Estimation_RunWithEcu("library/platform.json", "library",
            "library/ecus/BODAS_RC5_6_40.json", out);
    int ok = rc == 0
          && contains(out, "\"selected_ecu\": {")
          && contains(out, "\"name\": \"BODAS_RC5_6_40\"")
          && contains(out, "\"variant\": \"series 40\"")
          && contains(out, "\"compatible\": true")
          && contains(out, "\"estimate\": {\"ecu_count\":");
    remove(out);
    printf("[%s] selected BODAS ECU is represented in estimation output\n",
           ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
}
