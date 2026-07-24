"""Functions for creating, transforming, and adding prefixes to strings."""


def add_prefix_un(word):
    """Take the given word and add the 'un' prefix.

    Parameters:
        word (str): The root word.

    Returns:
        str: Root word prepended with 'un'.
    """
    # CORRECTO: Usamos f-strings o simple concatenación con '+'. 
    # 'un'.join(word) intercalaba "un" entre cada letra de la palabra.
    return f"un{word}"


def make_word_groups(vocab_words):
    """Transform a list containing a prefix and words.

    Parameters:
        vocab_words (list[str]): Vocabulary words with prefix at first index.

    Returns:
        str: Prefix followed by vocabulary words with prefix applied.
    """
    # CORRECTO: Extraemos el prefijo (primer elemento) y luego aplicamos
    # ese prefijo a cada palabra restante de la lista usando una list comprehension.
    prefix = vocab_words[0]
    words = vocab_words[1:]
    
    applied_words = [prefix + word for word in words]
    
    # Insertamos el prefijo al inicio de nuestra nueva lista y unimos con ' :: '
    return ' :: '.join([prefix] + applied_words)


def remove_suffix_ness(word):
    """Remove the suffix from the word while keeping spelling in mind.

    Parameters:
        word (str): Word to remove suffix from.

    Returns:
        str: Word with suffix removed & spelling adjusted.
    """
    # CORRECTO: Quitamos los últimos 4 caracteres ('ness') usando slicing [:-4].
    # Cuidado con .strip('ness'), porque removería letras de más si la palabra base termina en n, e o s.
    base_word = word[:-4]
    
    # Si la raíz termina en 'i', la regla ortográfica en inglés dice que originalmente era 'y' (e.g., heavi -> heavy).
    if base_word.endswith('i'):
        return base_word[:-1] + 'y'
        
    return base_word


def adjective_to_verb(sentence, index):
    """Change the adjective within the sentence to a verb.

    Parameters:
        sentence (str): The word used in a sentence as an adjective.
        index (int): Index of the adjective to remove and transform.

    Returns:
        str: The extracted adjective in verb form.
    """
    # CORRECTO: Separamos la oración en palabras.
    words = sentence.split()
    
    # Extraemos la palabra objetivo usando el índice.
    target_word = words[index]
    
    # Limpiamos posibles signos de puntuación al final de la palabra (como el punto '.') usando .strip()
    clean_word = target_word.strip('.,?!;')
    
    # Retornamos el adjetivo transformado en verbo agregando 'en'
    return f"{clean_word}en"