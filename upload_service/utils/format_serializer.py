def format_serializer_errors(errors) -> str:
    if isinstance(errors, dict):
        formatted = {}
        for field, value in errors.items():
            formatted[field] = format_serializer_errors(value)
        return "</br>".join(f"{val}" for _, val in formatted.items())

    if isinstance(errors, list):
        if all(isinstance(item, str) for item in errors):
            return "</br>".join(errors)
        return "</br>".join(error for error in errors)

    return str(errors)
