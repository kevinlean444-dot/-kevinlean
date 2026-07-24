def commands(binary_str):
    acciones = []
    if binary_str[-1] == '1':
        acciones.append('wink')
    if binary_str[-2] == '1':
        acciones.append('double blink')
    if binary_str[-3] == '1':
        acciones.append('close your eyes')
    if binary_str[-4] == '1':
        acciones.append('jump')
    if binary_str[-5] == '1':
        acciones.reverse()
    return acciones
    
