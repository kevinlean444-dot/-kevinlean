#include "resistor_color_duo.h"


uint16_t color_code(resistor_band_t *bands) {
    resistor_band_t primer_color = bands[0];
    resistor_band_t segundo_color = bands[1];
    uint16_t resultado = (primer_color * 10) + segundo_color;
    return resultado;
}

