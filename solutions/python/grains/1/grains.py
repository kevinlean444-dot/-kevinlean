def square(number):
    
    if number > 64 or number < 1:
        raise ValueError('square must be between 1 and 64')
    else:
        cuadrado = 2**(number - 1)
    return cuadrado
        
        

def total():
    valores = 0
    for casilla in range(1, 65):
        valores += square(casilla)
    return valores
        
        
        
    
