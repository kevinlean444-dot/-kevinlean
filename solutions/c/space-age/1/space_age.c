#include "space_age.h"


double age(planet_t planet, uint64_t seconds) {
    double resultado = 0;
    double periodos[] = { 0.2406467, 0.61519726, 1.0, 1.8808158, 11.862615, 29.447498, 84.016846, 164.79132};

    if(planet < 0 || planet > 7) {
        return -1;
    }
    else {
        resultado = seconds / (31557600 * periodos[planet]);
    }
    return resultado;
}