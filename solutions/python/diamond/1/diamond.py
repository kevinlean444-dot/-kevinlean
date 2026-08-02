def una_fila(i, max_i):
    letra = chr(ord('A')+ i)
    anchoTotal = 2 * max_i + 1
    if i == 0:
        return letra.center(anchoTotal)
    else:
        espacio = letra + " " * (2*i - 1) + letra
        return espacio.center(anchoTotal)
        
def rows(letter):
    resultado = []
    max_i = ord(letter) - 65
    for i in range(max_i + 1):
        resultado.append(una_fila(i, max_i))

    resultado += resultado[:-1][::-1]
    
    return resultado
    
        
        
    
    



