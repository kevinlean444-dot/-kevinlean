def sum_of_multiples(limit, multiples):
    multiplos = set()
    for n in multiples:
        if n == 0:
            continue
        for i in range(n, limit, n):
            multiplos.add(i)
    total = 0
    for v in multiplos:
        total += v
        
    return total
            
