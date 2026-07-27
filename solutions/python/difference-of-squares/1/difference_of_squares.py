def square_of_sum(number):
    resultadoSquare = 0
    for i in range(1, number+1):
        resultadoSquare += i
    return resultadoSquare ** 2
        


def sum_of_squares(number):
    resultadoSuma = 0
    for i in range(1, number+1):
        resultadoSuma += i ** 2
    return resultadoSuma

def difference_of_squares(number):
    diferencia = square_of_sum(number) - sum_of_squares(number)
    return diferencia
