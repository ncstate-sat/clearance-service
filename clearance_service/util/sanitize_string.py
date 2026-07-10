def sanitize_string(input_string):
    """Remove asterisks and parenthesis from a string."""
    translation_table = str.maketrans("", "", "()*?[].")
    sanitized_string = input_string.translate(translation_table)
    return sanitized_string
