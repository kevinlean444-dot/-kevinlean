def steps(number):
    if number == 0 or number < 0:
        raise ValueError("Only positive integers are allowed")
    contador = 0
    while number != 1:
        if (number % 2) == 0:
            number = number // 2
            contador += 1
        elif(number %2 ) != 0:
            number = (number * 3) +1
            contador += 1
    return contador
