def equilateral(sides):
    a,b,c = sides
    
    return (a + b >= c and b + c >= a and a + c >= b) and (a != 0 and b != 0 and c != 0) and (a == b == c)

def isosceles(sides):
    a,b,c = sides
    return (a + b >= c and b + c >= a and a + c >= b) and (a != 0 and b != 0 and c != 0) and (a == b or a == c or b == c)


def scalene(sides):
    a,b,c = sides
    return (a + b >= c and b + c >= a and a + c >= b) and (a != 0 and b != 0 and c != 0) and (a != b and a != c and b != c)
