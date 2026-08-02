def proteins(strand):
    proteinas = {
    "AUG": "Methionine",
    "UUU": "Phenylalanine", "UUC": "Phenylalanine",
    "UUA": "Leucine", "UUG": "Leucine",
    "UCU": "Serine", "UCC": "Serine", "UCA": "Serine", "UCG": "Serine",
    "UAU": "Tyrosine", "UAC": "Tyrosine",
    "UGU": "Cysteine", "UGC": "Cysteine",
    "UGG": "Tryptophan",
    "UAA": "STOP", "UAG": "STOP", "UGA": "STOP",
}
    encontradas = []
    for i in range(0, len(strand), 3):
        buscar = proteinas[strand[i:i+3]]
        if buscar == "STOP":
            break
        else:
             encontradas.append(buscar)
    return encontradas
        
            
        
