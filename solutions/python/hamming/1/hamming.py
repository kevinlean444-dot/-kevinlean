def distance(strand_a, strand_b):
    if len(strand_a) != len(strand_b):
        raise ValueError("Strands must be of equal length.")
    counter = 0
    for i, k in zip(strand_a, strand_b):
        if i != k:
            counter += 1
    return counter
