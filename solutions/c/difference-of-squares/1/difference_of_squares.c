#include "difference_of_squares.h"


unsigned int square_of_sum(unsigned int n) {
    unsigned int valor1 = 0;
    for (unsigned int calculo = 1; calculo <= n; calculo++) {
        valor1 += calculo;
    }
    return valor1 * valor1;
}
unsigned int sum_of_squares(unsigned int n){
    unsigned int valor2 = 0;
    for (unsigned int calculo = 1; calculo <= n; calculo++) {
        valor2 += calculo * calculo;
        
    }
    return valor2 ;
}

unsigned int difference_of_squares(unsigned int n) {
    unsigned int calculo1 = square_of_sum(n);
    unsigned int calculo2 = sum_of_squares(n);
    return calculo1 - calculo2;
    }



