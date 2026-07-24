def flatten(iterable):
    lista = []
    for i in iterable:
        if i is not None:
            if not isinstance(i, list):
                lista.append(i)
            elif isinstance(i, list):
                lista += flatten(i)
        
    return lista
        
            
        
    
