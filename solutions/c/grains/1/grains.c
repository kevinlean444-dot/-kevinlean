#include "grains.h"
#include <stdint.h>
uint64_t square(uint8_t index) {
    uint64_t iResultadoTotal = 0;
    
    if(index<= 64 && index >= 1) {
    
        iResultadoTotal =  1ull << (index - 1); 
    }
     else {
        return 0;
    }
    
    return iResultadoTotal;
}
uint64_t total(void) {
    uint64_t totalResultado = 0;
    for(uint8_t calculo = 0; calculo <= 64; calculo++) {
        totalResultado += square(calculo);
    }
    return totalResultado;
}
