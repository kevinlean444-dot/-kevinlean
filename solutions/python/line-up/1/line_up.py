def line_up(name, number):
    if number % 10 == 1 and number not in (11, 12, 13) and number % 100 != 11:
        return f"{name}, you are the {number}st customer we serve today. Thank you!"

    elif number % 10 == 2 and number not in (11, 12, 13) and number % 100 != 12:
        return f"{name}, you are the {number}nd customer we serve today. Thank you!"
    elif number % 10 == 3 and number not in (11, 12, 13) and number % 100 != 13:
        return f"{name}, you are the {number}rd customer we serve today. Thank you!"
    else: 
        return f"{name}, you are the {number}th customer we serve today. Thank you!"
