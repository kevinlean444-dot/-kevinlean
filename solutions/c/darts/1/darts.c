#include "darts.h"
#include <math.h>

uint8_t score(coordinate_t landing_position){
    if(sqrt((landing_position.x * landing_position.x) + (landing_position.y * landing_position.y)) <= 1) {
    return  10;
    }
    else if (sqrt((landing_position.x * landing_position.x) + (landing_position.y * landing_position.y)) <=5){
        return 5;
    }
    else if (sqrt((landing_position.x * landing_position.x) + (landing_position.y * landing_position.y)) <=10){
        return 1;
    }
    else {
        return 0;
    }
    
}
    