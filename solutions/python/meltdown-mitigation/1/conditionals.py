"""Functions to prevent a nuclear meltdown."""


def is_criticality_balanced(temperature, neutrons_emitted):
    """Verify criticality is balanced.

    Parameters:
        temperature (int or float): The temperature value in kelvin.
        neutrons_emitted (int or float): The number of neutrons emitted per second.

    Returns:
        bool: Is criticality balanced?
    """
    # Condición 1: Temperatura menor a 800 K
    # Condición 2: Neutrones emitidos mayor a 500
    # Condición 3: El producto de ambos menor a 500,000
    if temperature < 800 and neutrons_emitted > 500 and (temperature * neutrons_emitted) < 500000:
        return True
    
    return False


def reactor_efficiency(voltage, current, theoretical_max_power):
    """Assess reactor efficiency zone.

    Parameters:
        voltage (int or float): Voltage value.
        current (int or float): Current value.
        theoretical_max_power (int or float): The power level that corresponds to a 100% efficiency.

    Returns:
        str: One of ('green', 'orange', 'red', or 'black').
    """
    generated_power = voltage * current
    efficiency = (generated_power / theoretical_max_power) * 100

    if efficiency >= 80:
        return 'green'
    elif efficiency >= 60:  # Al usar 'elif', ya sabemos que es menor a 80
        return 'orange'
    elif efficiency >= 30:  # Ya sabemos que es menor a 60
        return 'red'
    else:
        return 'black'


def fail_safe(temperature, neutrons_produced_per_second, threshold):
    """Assess and return status code for the reactor.

    Parameters:
        temperature (int or float): The value of the temperature in kelvin.
        neutrons_produced_per_second (int or float): The neutron flux.
        threshold (int or float): The threshold for the category.

    Returns:
        str: One of ('LOW', 'NORMAL', 'DANGER').
    """
    product = temperature * neutrons_produced_per_second
    
    # 'LOW' -> producto < 90% del umbral
    if product < (threshold * 0.90):
        return 'LOW'
    
    # 'NORMAL' -> producto está dentro del +/- 10% del umbral
    # Como el caso menor al 90% ya se evaluó arriba, basta con verificar que no pase del 110%
    elif product <= (threshold * 1.10):
        return 'NORMAL'
    
    # 'DANGER' -> cualquier otro caso
    else:
        return 'DANGER'
