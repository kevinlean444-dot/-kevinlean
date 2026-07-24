def label(colors):
    
    colores = {'black': 0, 'brown': 1, 'red': 2, 'orange': 3, 'yellow': 4, 'green': 5, 'blue': 6, 'violet': 7, 'grey': 8, 'white': 9}
    mainValue = 0
    total = 0
    for color in colors[:2]:
        digito = colores.get(color)
        mainValue = mainValue * 10 + digito
    ceros = colores.get(colors[2])
    total = mainValue * (10 ** ceros)

    if total >= 1000000000:
        return f"{total // 1000000000} gigaohms"
    
    elif total >= 1000000:
        return f"{total // 1000000} megaohms"
    elif total >= 1000:
        return f"{total // 1000} kiloohms"
        
    else: 
        return f"{total} ohms"
    return total
