class CheckResponseException(Exception):
    """Неверный формат ответа API."""
    pass


class UnknownStatusException(Exception):
    """Исключение неизвестного статуса домашки."""
    pass


class MissingTokenException(Exception):
    """Нет нужных переменных среды."""
    pass


class IncorrectAPIResponseException(Exception):
    """Исключение некорректного ответа API."""
    pass
