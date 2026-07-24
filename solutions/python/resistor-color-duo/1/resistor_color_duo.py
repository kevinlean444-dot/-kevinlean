def value(colors):
    colores = {'black':0, 'brown':1, 'red':2, 'orange':3, 'yellow':4, 'green':5, 'blue':6, 'violet':7, 'grey':8, 'white':9}
    total = 0
    for color in colors[:2]:
        color = colores.get(color)
        total = total * 10 + color
    return total
    
