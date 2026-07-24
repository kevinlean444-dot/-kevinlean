"""Functions for tracking poker hands and assorted card tasks.

Python list documentation: https://docs.python.org/3/tutorial/datastructures.html
"""


def get_rounds(number):
    """Create a list containing the current and next two round numbers.

    Parameters:
        number (int): The current round number.

    Returns:
        list: The current round number and the two that follow.
    """
    # Creamos y retornamos la lista directamente con los tres elementos consecuentes
    return [number, number + 1, number + 2]


def concatenate_rounds(rounds_1, rounds_2):
    """Concatenate two lists of round numbers.

    Parameters:
        rounds_1 (list): The first rounds played.
        rounds_2 (list): The second group of rounds played.

    Returns:
        list:  All rounds played.
    """
    # En Python, concatenar dos listas es tan sencillo como sumarlas con el operador '+'
    return rounds_1 + rounds_2


def list_contains_round(rounds, number):
    """Check if the list of rounds contains the specified number.

    Parameters:
        rounds (list): The rounds played.
        number (int): The round number.

    Returns:
        bool: Was the round played?
    """
    # El operador 'in' verifica directamente si un elemento existe dentro de la lista
    return number in rounds


def card_average(hand):
    """Calculate and returns the average card value from the list.

    Parameters:
        hand (list): The cards in the hand.

    Returns:
        float: The average value of the cards in the hand.
    """
    # Evitamos redefinir 'hand' para no perder los datos de entrada
    return sum(hand) / len(hand)


def approx_average_is_average(hand):
    """Return if the (average of first and last card values) OR ('middle' card) == calculated average.

    Parameters:
        hand (list): The cards in the hand.

    Returns:
        bool: Does one of the approximate averages equal the `true average`?
    """
    promedio_real = sum(hand) / len(hand)
    
    # Aproximación 1: Promedio de la primera y última carta
    promedio_extremos = (hand[0] + hand[-1]) / 2
    
    # Aproximación 2: La carta del medio (usamos división entera '//' para el índice)
    carta_medio = hand[len(hand) // 2]
    
    return promedio_real == promedio_extremos or promedio_real == carta_medio


def average_even_is_average_odd(hand):
    """Return if the (average of even indexed card values) == (average of odd indexed card values).

    Parameters:
        hand (list): The cards in the hand.

    Returns:
        bool: Are the even and odd averages equal?
    """
    # Usamos "slicing" [inicio:fin:paso] para separar las cartas rápidamente
    cartas_pares = hand[0::2]  # Índices 0, 2, 4...
    cartas_impares = hand[1::2] # Índices 1, 3, 5...
    
    promedio_pares = sum(cartas_pares) / len(cartas_pares)
    promedio_impares = sum(cartas_impares) / len(cartas_impares)
    
    return promedio_pares == promedio_impares


def maybe_double_last(hand):
    """Multiply a Jack card value in the last index position by 2.

    Parameters:
        hand (list): The cards in the hand.

    Returns:
        list: The hand with Jacks (if present) value doubled.
    """
    # Verificamos si la última carta (índice -1) es un Jack (11)
    if hand[-1] == 11:
        hand[-1] = 22  # Duplicamos su valor directamente en la lista
        
    return hand
