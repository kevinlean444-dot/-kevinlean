#include <stdlib.h>
#include "queen_attack.h"

result_t  can_attack (position_t white_queen, position_t black_queen){

if (white_queen.row <= 7 && white_queen.column <= 7 && black_queen.row <= 7 && black_queen.column <= 7 ) {
    if (white_queen.row ==  black_queen.row && white_queen.column == black_queen.column) {
        return INVALID_POSITION;
    }
    else {
        if((white_queen.row ==  black_queen.row || white_queen.column == black_queen.column || abs((int)white_queen.row - (int)black_queen.row) == abs((int)(white_queen.column - (int)black_queen.column)))) {
            return CAN_ATTACK;
        }
    
     else {
            return CAN_NOT_ATTACK;
     }
     }
        
    }
     else {
        return INVALID_POSITION;
     }
}   


   