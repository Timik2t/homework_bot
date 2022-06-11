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

SEND_MSG_INFO = 'Сообщение: "{message}" отправлено в чат'


def send_message(bot, message):
    """Отправка сообщения в чат."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logger.info(SEND_MSG_INFO.format(message=message))


SERVER_ERROR_INFORMATION = ['code', 'error']
RESPONSE_ERROR_MSG = (
    'Cбой запроса статус: {response}, '
    'параметры запроса: {endpoint}, {params}'
)
SERVER_ERROR_MSG = (
    'Cбой запроса статус: {response}, '
    'параметры запроса: {endpoint}, {params}, '
    'ошибка: {error}'
)


def get_api_answer(current_timestamp):
    """Запрос к API."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        # response.raise_for_status()
    except requests.exceptions.RequestException as error:
        raise error(RESPONSE_ERROR_MSG.format(
            response=response,
            endpoint=ENDPOINT,
            params=params)
        )
    if response.status_code != OK:
        raise requests.ConnectionError(RESPONSE_ERROR_MSG.format(
            response=response,
            endpoint=ENDPOINT,
            params=params)
        )
    api_answer = response.json()
    for key in SERVER_ERROR_INFORMATION:
        if key in api_answer:
            raise exceptions.InternalServerError(SERVER_ERROR_MSG.format(
                response=response,
                endpoint=ENDPOINT,
                params=params,
                error=api_answer[str(key)]
            ))
    return api_answer


ENDPOINT_RESOURCE = 'homeworks'
NOT_DICT_MSG = 'API вернул {response}, тип {type} не являющемся обьектом dict'
NOT_LIST_MSG = 'API вернул {homeworks}, тип {type} не являющемся обьектом list'
ENDPOINT_MISSING_ERROR_MSG = f'В ответе API нет ключа {ENDPOINT_RESOURCE}'


def check_response(response):
    """Проверяет ответ API."""
    if not isinstance(response, dict):
        raise TypeError(NOT_DICT_MSG.format(
            response=response,
            type=type(response)
        ))
    if ENDPOINT_RESOURCE not in response:
        raise KeyError(ENDPOINT_MISSING_ERROR_MSG)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(NOT_LIST_MSG.format(
            homeworks=homeworks,
            type=type(homeworks)
        ))
    return homeworks


HW_STATUS_MISSING_MSG = (
    'Ожидались статусы: {status}, '
    'пришел: {response_ststus}'
)
PARSE_STATUS_MSG = (
    'Изменился статус проверки работы "{homework_name}". '
    '{status}')


def parse_status(homework):
    """Извлечение статуса домашки."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in VERDICTS:
        raise KeyError(HW_STATUS_MISSING_MSG.format(
            status=VERDICTS.keys(),
            response_ststus=homework_status
        ))
    return (PARSE_STATUS_MSG.format(
            homework_name=homework_name,
            status=VERDICTS[homework_status]
            ))


TOKENS_MISSING_MSG = 'Отсутствует необходимая переменная среды {name}'
TOKENS = ['TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID', 'PRACTICUM_TOKEN']


def check_tokens():
    """Проверка переменных окружения."""
    for name in TOKENS:
        if not globals()[name]:
            logger.error(TOKENS_MISSING_MSG.format(name=name))
            return False
    return True


HW_MISSING_MSG = 'За последнее время нет домашек'


def is_homework(homeworks):
    """Проверка есть ли домашка."""
    if len(homeworks) == 0:
        raise exceptions.NotNewHomeworksError(HW_MISSING_MSG)


PRE_HW_STATUS_LOG_MSG = 'Статус проверки домашки прежний'
CHECK_TOKENS_MISSING_MSG = 'Отсутствует необходимая переменная среды'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError(CHECK_TOKENS_MISSING_MSG)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    pre_status = None
    pre_error = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            is_homework(homeworks)
            current_timestamp = response.get('current_date')
            homework_status = homeworks[0].get('status')
            if homework_status != pre_status:
                pre_status = homework_status
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logger.debug(PRE_HW_STATUS_LOG_MSG)

        except Exception as error:
            message = str(error)
            if str(error) != pre_error:
                pre_error = str(error)
                send_message(bot, message)
            logger.error(error)
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
