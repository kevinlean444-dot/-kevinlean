def classify(number):
    """ A perfect number equals the sum of its positive divisors.

    :param number: int a positive integer
    :return: str the classification of the input integer
    """
    if number <= 0:
        raise ValueError ("Classification is only possible for positive integers.")
    aliquot = 0
    
    for i in range(1, number):
        if (number % i) == 0:
            aliquot += i

    
    if aliquot == number:
        return "perfect"
    elif aliquot < number:
        return "deficient"
    else:
        return "abundant"
            
