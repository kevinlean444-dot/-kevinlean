def recite(start_verse, end_verse):
    partes = [
    "the house that Jack built.",
    "the malt",
    "the rat",
    "the cat",
    "the dog",
    "the cow with the crumpled horn",
    "the maiden all forlorn",
    "the man all tattered and torn",
    "the priest all shaven and shorn",
    "the rooster that crowed in the morn",
    "the farmer sowing his corn",
    "the horse and the hound and the horn",
]
    conexiones = [
    "",  # la casa no tiene conexión
    "that lay in",
    "that ate",
    "that killed",
    "that worried",
    "that tossed",
    "that milked",
    "that kissed",
    "that married",
    "that woke",
    "that kept",
    "that belonged to",
]
    union = []
    def un_verso(n, partes, conexiones):
        resultado = 'This is ' + partes[n -1]
        for i in range(n-2, -1, -1):
            resultado += " " + conexiones[i+1] + " " + partes[i]
        return resultado
        


    for n in range(start_verse, end_verse +1):
        union.append(un_verso(n, partes, conexiones))
        
    return union

        
        