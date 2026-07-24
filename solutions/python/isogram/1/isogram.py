def is_isogram(phrase):
    letras = []
    for c in phrase.lower():
        if c.isalpha():
            letras.append(c)
    
    if len(letras) == len(set(letras)):
        return True
    else: 
        return False
