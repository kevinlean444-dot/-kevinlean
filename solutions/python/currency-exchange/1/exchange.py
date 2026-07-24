def exchange_money(budget, exchange_rate):
    """Calculate estimated value after exchange."""
    return budget / exchange_rate


def get_change(budget, exchanging_value):
    """Calculate currency left after an exchange."""
    return budget - exchanging_value


def get_value_of_bills(denomination, number_of_bills):
    """Calculate the total value of currency at current denomination."""
    return denomination * number_of_bills
    

def get_number_of_bills(amount, denomination):
    """Calculate the number of currency units (bills) within the amount."""
    return amount // denomination


def get_leftover_of_bills(amount, denomination):
    """Calculate leftover amount after exchanging into bills."""
    return amount % denomination


def exchangeable_value(budget, exchange_rate, spread, denomination):
    """Calculate the maximum value of the new currency.

    Parameters:
        budget (float): The amount of your money you are planning to exchange.
        exchange_rate (float): The unit value of the foreign currency.
        spread (int): The percentage that is taken as an exchange fee.
        denomination (int) The value of a single unit (bill).

    Returns:
        int: The maximum value you can get in the new currency.
    """
    # 1. Aplicar el recargo (spread) a la tasa de cambio
    actual_rate = exchange_rate * (1 + spread / 100)
    
    # 2. Calcular el total de dinero extranjero que recibirías
    total_foreign_currency = budget / actual_rate
    
    # 3. Calcular cuántos billetes enteros obtienes y su valor total
    number_of_bills = total_foreign_currency // denomination
    
    return int(number_of_bills * denomination)
