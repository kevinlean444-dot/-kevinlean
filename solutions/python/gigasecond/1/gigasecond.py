from datetime import timedelta
def add(moment):
    nuevaFecha = moment + timedelta(seconds= 1_000_000_000)
    return nuevaFecha
