def find_anagrams(word, candidates):
    resultado = []
    for palabras in candidates:
        if sorted(palabras.lower()) == sorted(word.lower()) and palabras.lower() != word.lower():
            resultado.append(palabras)
    return resultado
            
           
        