def traducir_palabra(word):
    vowels = ('a', 'e', 'i', 'o', 'u')
    
    if word[0] in vowels or word.startswith(('xr', 'yt')):
        indice = 0
    else:
        indice = 0
        for i in range(len(word)):
            if word[i] == 'q' and word[i + 1] == 'u':
                indice = i + 2
                break
            elif word[i] == 'y' and i != 0:
                indice = i
                break
            elif word[i] in vowels:
                indice = i
                break
    
    return word[indice:] + word[:indice] + "ay"


def translate(text):
    palabras = text.split()
    resultado = []
    for palabra in palabras:
        resultado.append(traducir_palabra(palabra))
    return " ".join(resultado)
                
                
        
