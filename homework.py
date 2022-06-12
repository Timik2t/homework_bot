import logging
import os
import time
from http.client import OK

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)

SEND_INFO = 'Сообщение: "{message}" отправлено в чат'


def send_message(bot, message):
    """Отправка сообщения в чат."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logger.info(SEND_INFO.format(message=message))


SERVER_ERROR_INFORMATION = ['code', 'error']
RESPONSE_ERROR = (
    'Cбой запроса: {error}, '
    'параметры запроса: {url}, {params}, {headers}'
)
SERVER_ERROR = (
    'Ошибка сервера: {error}, {key}, '
    'параметры запроса: {url}, {params}, {headers} '
)


def get_api_answer(current_timestamp):
    """Запрос к API."""
    request_params = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': current_timestamp}
    )
    try:
        response = requests.get(**request_params)
    except requests.exceptions.RequestException as error:
        raise ConnectionError(RESPONSE_ERROR.format(
            error=error,
            **request_params)
        )
    if response.status_code != OK:
        raise ConnectionError(RESPONSE_ERROR.format(
            error=response.status_code,
            **request_params)
        )
    api_answer = response.json()
    for key in SERVER_ERROR_INFORMATION:
        if key in api_answer:
            raise exceptions.InternalServerError(SERVER_ERROR.format(
                key=key,
                error=api_answer[key],
                **request_params
            ))
    return api_answer


NOT_DICT = 'API вернул {type} не являющемся обьектом dict'
NOT_LIST = 'API вернул список домашек тип {type} не являющийся обьектом list'
ENDPOINT_MISSING_ERROR = 'В ответе API нет ключа "homeworks"'


def check_response(response):
    """Проверяет ответ API."""
    if not isinstance(response, dict):
        raise TypeError(NOT_DICT.format(
            type=type(response)
        ))
    if "homeworks" not in response:
        raise KeyError(ENDPOINT_MISSING_ERROR)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(NOT_LIST.format(
            type=type(homeworks)
        ))
    return homeworks


STATUS_MISSING = 'Неизвестный статус проверки: {response_status}'
PARSE_STATUS = (
    'Изменился статус проверки работы "{name}". '
    '{status}')


def parse_status(homework):
    """Извлечение статуса домашки."""
    name = homework['homework_name']
    status = homework['status']
    if status not in VERDICTS:
        raise ValueError(
            STATUS_MISSING.format(response_status=status)
        )
    return PARSE_STATUS.format(
        name=name,
        status=VERDICTS[status]
    )


TOKENS_MISSING = 'Отсутствуют необходимые переменные среды {names}'
TOKENS = ['TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID', 'PRACTICUM_TOKEN']


def check_tokens():
    """Проверка переменных окружения."""
    missing_tokens = [name for name in TOKENS if not globals()[name]]
    if missing_tokens:
        logger.error(TOKENS_MISSING.format(names=missing_tokens))
        return False
    return True


CHECK_TOKENS_MISSING = 'Отсутствуют необходимые переменные среды'
ERROR_MESSAGE = 'Сбой в работе: {error}'
BOT_ERROR = 'Ошибка отправки сообщения в телеграмм'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError(CHECK_TOKENS_MISSING)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    pre_status = None
    pre_message = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if not homeworks:
                continue
            homework_status = homeworks[0].get('status')
            if homework_status != pre_status:
                send_message(bot, parse_status(homeworks[0]))
                pre_status = homework_status
                current_timestamp = response.get('current_date',
                                                 current_timestamp)
        except Exception as error:
            message = ERROR_MESSAGE.format(error=error)
            if message != pre_message:
                logger.error(message)
                try:
                    send_message(bot, message)
                    pre_message = message
                except exceptions.BotSendMessageError:
                    logger.error(BOT_ERROR)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        level=logging.INFO,
        handlers=[logging.FileHandler(__file__ + ".log"),
                  logging.StreamHandler()]
    )
    main()
