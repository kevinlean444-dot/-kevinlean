def resistor_label(colors):
    
    colores = {'black': 0, 'brown': 1, 'red': 2, 'orange': 3, 'yellow': 4, 'green': 5, 'blue': 6, 'violet': 7, 'grey': 8, 'white': 9}
    mainValue = 0

    tolerance = {'grey': 0.05, 'violet': 0.1, 'blue': 0.25, 'green': 0.5, 'brown': 1, 'red': 2, 'gold': 5, 'silver':10}
    cantidadDijitos = len(colors) - 2
    if len(colors) == 1: 
        return "0 ohms"
    for color in colors[:cantidadDijitos]:
        digito = colores.get(color)
        mainValue = mainValue * 10 + digito
            
    ceros = colores.get(colors[-2])
    tolerancia = tolerance.get(colors[-1])
    
    
    total = mainValue * (10 ** ceros)
    numeroKm = 0
    numeroGm = 0
    numeroMg = 0
    
    if total >= 1000000000:
        numeroGm = total / 1000000000
        if numeroGm == int(numeroGm):
            return f"{int(numeroGm)} gigaohms ±{tolerancia}%"
        else:
            return f"{numeroGm} gigaohms ±{tolerancia}%"
    elif total >= 1000000:
        numeroMg = total / 1000000
        if numeroMg == int(numeroMg):
            return f"{int(numeroMg)} megaohms ±{tolerancia}%"
        else:
            return f"{numeroMg} megaohms ±{tolerancia}%"
    elif total >= 1000:
        numeroKm = total / 1000
        if numeroKm == int(numeroKm):
            return f"{int(numeroKm)} kiloohms ±{tolerancia}%"
        else:
            return f"{numeroKm} kiloohms ±{tolerancia}%"

    else:
        return f"{total} ohms ±{tolerancia}%"

    