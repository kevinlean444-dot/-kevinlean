def score(x, y):
    distancia = (x**2 + y**2) ** 0.5
    if distancia <= 1:
        return 10
    elif distancia <= 5:
        return 5
    elif distancia <= 10:
        return 1
    else:
        return 0