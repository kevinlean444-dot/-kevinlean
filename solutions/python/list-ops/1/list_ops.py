def append(list1, list2):
    return list1 + list2
        

def concat(lists):
    resultado = []
    for sublist in lists:
        resultado += sublist
    return resultado


def filter(function, list):
    resultado = []
    for item in list:
        if function(item):
            resultado.append(item)
    return resultado


def length(list):
    resultado = len(list)
    return resultado


def map(function, list):
    resultado = []
    for item in list:
        resultado.append(function(item))
    return resultado
    


def foldl(function, list, initial):
    acumulador = initial
    for i in list:
        acumulador = function(acumulador, i)
    return acumulador

def foldr(function, list, initial):
    list = list[::-1]
    acumulador = initial
    for i in list:
        acumulador = function(acumulador, i)
    return acumulador


def reverse(list):
    list = list[::-1]
    return list
