"""Functions to help play and score a game of blackjack.

How to play blackjack:    https://bicyclecards.com/how-to-play/blackjack/
"Standard" playing cards: https://en.wikipedia.org/wiki/Standard_52-card_deck
"""


def value_of_card(card):
    """Determine the scoring value of a card."""
    if card in ['J', 'Q', 'K']:
        return 10
    if card == 'A':
        return 1
    return int(card)


def higher_card(card_one, card_two):
    """Determine which card has a higher value in the hand."""
    val_one = value_of_card(card_one)
    val_two = value_of_card(card_two)
    
    if val_one > val_two:
        return card_one
    elif val_two > val_one:
        return card_two
    else:
        return card_one, card_two


def value_of_ace(card_one, card_two):
    """Calculate the most advantageous value for an upcoming ace card."""
    val_one = value_of_card(card_one)
    val_two = value_of_card(card_two)
    
    # Si alguna de las cartas ya es un As, su valor en mano cuenta como 11
    if card_one == 'A':
        val_one = 11
    if card_two == 'A':
        val_two = 11
        
    if val_one + val_two + 11 <= 21:
        return 11
    else:
        return 1


def is_blackjack(card_one, card_two):
    """Determine if the hand is a 'natural' or 'blackjack'."""
    # Un blackjack natural requiere estrictamente un As (11) y una carta de valor 10
    has_ace = card_one == 'A' or card_two == 'A'
    has_ten = value_of_card(card_one) == 10 or value_of_card(card_two) == 10
    
    return has_ace and has_ten


def can_split_pairs(card_one, card_two):
    """Determine if a player can split their hand into two hands."""
    return value_of_card(card_one) == value_of_card(card_two)


def can_double_down(card_one, card_two):
    """Determine if a blackjack player can place a double down bet."""
    total = value_of_card(card_one) + value_of_card(card_two)
    return total in [9, 10, 11]