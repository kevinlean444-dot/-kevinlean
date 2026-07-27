def transform(legacy_data):
    newLetters = {}
    for k, v in legacy_data.items():
        for value in v:
            newLetters[value.lower()] = k
    return newLetters
            
        