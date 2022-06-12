class InternalServerError(Exception):
    """Ошибка ответа сервера."""
    pass


class BotSendMessageError(Exception):
    """Ошибка отправки сообщения ботом."""
    pass
