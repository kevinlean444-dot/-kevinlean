def is_pangram(sentence):
    palabras = set('abcdefghijklmnopqrstuvwxyz')
    nueva = sentence.lower()
    if palabras.issubset(set(nueva)):
        return True
    else:
        return False
