def encode(plain_text):
    letra_opuesta = []
    for char in plain_text.lower():
        if char.isalpha():
            posicion = ord(char) - ord('a')
            posicionOpuesta = 25 - posicion
            letra_opuesta.append(chr(posicionOpuesta + ord('a')))
        elif char.isnumeric():
            letra_opuesta.append(char)
    grupoFinal = []
    for i in range(0, len(letra_opuesta), 5):
        
        grupoFinal.append("".join(letra_opuesta[i:i+5]))
    return " ".join(grupoFinal)
            
    
         
    

def decode(ciphered_text):
    letra_opuesta = []
    for char in ciphered_text:
        if char.isalpha():
            posicion = ord(char) - ord('a')
            posicionOpuesta = 25 - posicion
            letra_opuesta.append(chr(posicionOpuesta + ord('a')))
        elif char.isnumeric():
            letra_opuesta.append(char)
    return "".join(letra_opuesta)
    
    
