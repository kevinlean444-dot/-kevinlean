def is_paired(input_string):
    pares = {')': '(', ']': '[', '}': '{'}
    stack = []
    for i in input_string:
        if i == "[" or i == "{" or i == "(":
            stack.append(i)
        elif  i== "]" or i == "}" or i == ")":
            if not stack:
                return False
            ultimo = stack.pop()
            if ultimo != pares[i]:
                return False
    if not stack:
        return True
    elif len(stack) >= 1:
        return False
    return True