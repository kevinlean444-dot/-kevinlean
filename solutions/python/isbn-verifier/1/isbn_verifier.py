def is_valid(isbn):
    isbn = isbn.replace('-', '')
    if len(isbn) != 10:
        return False
    numeros = []


    for idx, i in enumerate(list(isbn.lower())):
        if i == 'x' and  idx == 9:
            numeros.append(10)
        elif i.isnumeric():
            numeros.append(int(i))
        else: 
            return False
   
  
    test = (numeros[0] * 10 + numeros[1] * 9 + numeros[2] * 8 + numeros[3] * 7 + numeros[4] * 6 + numeros[5] * 5 + numeros[6] * 4 + numeros[7] * 3 + numeros[8] * 2 + numeros[9] * 1)
    if test % 11 == 0:
        return True
    else: 
        return False
        
