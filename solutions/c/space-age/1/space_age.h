#ifndef SPACE_AGE_H
#define SPACE_AGE_H
#include <stdint.h>

typedef enum {MERCURY, VENUS, EARTH, MARS, JUPITER, SATURN, URANUS, NEPTUNE} planet_t;

double age(planet_t planet, uint64_t seconds);



#endif
