
#ifndef QUEEN_ATTACK_H
#define QUEEN_ATTACK_H
#include <stdint.h>

typedef struct { uint8_t column; uint8_t row;} position_t;
typedef enum {INVALID_POSITION, CAN_ATTACK, CAN_NOT_ATTACK} result_t;
result_t  can_attack (position_t white_queen, position_t black_queen);
#endif
