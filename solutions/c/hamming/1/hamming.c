#include "hamming.h"
#include <stdint.h>
#include <string.h>

int compute (const char *strand1, const char *strand2) {
    int largo1 = strlen(strand1);
    int largo2 = strlen(strand2);
    int diferencias = 0;
    if (largo1 != largo2) {
        return -1;
    }
    else{
        for(int contador = 0; contador < largo1; contador++) {
            if (strand1[contador] != strand2[contador]) {
                diferencias += 1;
            }
        }
        return diferencias;
    }
        
}
