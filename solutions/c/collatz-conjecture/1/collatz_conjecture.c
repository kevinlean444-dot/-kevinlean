#include "collatz_conjecture.h"


int steps(int start) {
    int pasos = 0;
    if (start >= 1) {
    for(; start != 1; pasos++) {
        if (start % 2 == 0) {
            start = start / 2;
            
        }
        else {
            start = (start * 3) +1;
        }
    }
    return pasos;
    }
    else {
        return -1;
    }
}
        
