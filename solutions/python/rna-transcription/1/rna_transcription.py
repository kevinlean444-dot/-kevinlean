def to_rna(dna_strand):
    resultado = []
    for i in dna_strand:
        if i == 'G':
            resultado.append('C')
        elif i == 'C':
            resultado.append('G')
        elif i =='T':
            resultado.append('A')
        elif i == 'A':
            resultado.append('U')
        elif not i.isalpha():
            raise ValueError('No valido')
    return ''.join(resultado)
            
        
            
