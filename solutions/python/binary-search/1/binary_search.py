def find(search_list, value):

    alto = len(search_list) -1
    bajo = 0

    while bajo <= alto:
        medio = (bajo + alto) // 2
        if search_list[medio] == value:
            return medio
        elif search_list[medio] < value:
            bajo = medio + 1
        elif search_list[medio] > value:
            alto = medio - 1
        
    raise ValueError('value not in array')
        
        
    
