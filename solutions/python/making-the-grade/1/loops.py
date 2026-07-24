"""Functions for organizing and calculating student exam scores."""


def round_scores(student_scores):
    """Round all provided student scores.

    Parameters:
        student_scores (list[float]): Student exam scores.

    Returns:
        list[int]: Student scores *rounded* to the nearest integer value.
    """
    # Usamos una lista por comprensión para redondear cada nota eficientemente
    return [round(score) for score in student_scores]


def count_failed_students(student_scores):
    """Count the number of failing students out of the group provided.

    Parameters:
        student_scores (list[int]): Student scores as ints.

    Returns:
        int: The count of student scores at or below 40.
    """
    failed_count = 0
    for score in student_scores:
        if score <= 40:
            failed_count += 1
            
    return failed_count


def above_threshold(student_scores, threshold):
    """Determine how many of the provided student scores were 'the best' based on the provided threshold.

    Parameters:
        student_scores (list[int]): Integer scores.
        threshold (int): The threshold to cross to be the "best" score.

    Returns:
        list[int]: Integer scores that are at or above the "best" threshold.
    """
    mejores = []
    for score in student_scores:
        if score >= threshold:
            mejores.append(score)
            
    return mejores


def letter_grades(highest):
    """Create a list of grade thresholds based on the provided highest grade.

    Parameters:
        highest (int): The value of the highest exam score.

    Returns:
        list[int]: Lower threshold scores for each D-A letter grade interval.
    """
    # El rango empieza en 41. Calculamos el tamaño exacto de cada intervalo de nota
    step = (highest - 40) // 4
    
    # Generamos los límites inferiores para D, C, B y A
    # Ej. si highest=100 -> step=15 -> [41, 41+15, 41+30, 41+45] -> [41, 56, 71, 86]
    return [41 + step * i for i in range(4)]


def student_ranking(student_scores, student_names):
    """Organize the student's rank, name, and grade information in descending order.

    Parameters:
        student_scores (list): Scores in descending order.
        student_names (list[str]): Student names by exam score in descending order.

    Returns:
        list[str]: Strings in format ["<rank>. <student name>: <score>"].
    """
    rankings = []
    
    # zip() junta cada nombre con su puntaje correspondiente.
    # enumerate(..., start=1) genera los números de rango comenzando desde el 1.
    for rank, (name, score) in enumerate(zip(student_names, student_scores), start=1):
        rankings.append(f"{rank}. {name}: {score}")
        
    return rankings
    pass


def perfect_score(student_info):
    """Create a list that contains the name and grade of the first student to make a perfect score on the exam.

    Parameters:
        student_info (list[list[str, int]]): List of [<student name>, <score>] lists.

    Returns:
        list: First `[<student name>, 100]` found OR `[]` if no student score of 100 is found.
    """
    best = []
    for name, grade in student_info:
        if grade == 100:
            return [name, grade]
    return []
    pass
