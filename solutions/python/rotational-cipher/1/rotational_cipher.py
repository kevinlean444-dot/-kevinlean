def rotate(text, key):
    textoRotado = []
    for i in text:
        if i.islower():
            posicion = ord(i) - ord('a')
            nuevaPosicion = (posicion + key) % 26
            letraRotada = chr(nuevaPosicion + ord('a'))
            textoRotado.append(letraRotada)
        elif i.isupper():
            posicion = ord(i) - ord('A')
            nuevaPosicion = (posicion + key) % 26
            letraRotada = chr(nuevaPosicion + ord('A'))
            textoRotado.append(letraRotada)

        elif not i.isalpha():
            letraRotada = i 
            textoRotado.append(letraRotada)
        else:
            letraRotada = i
            textoRotado.append(letraRotada)
            
            
        
    final = "".join(textoRotado)
    return final
        
        
