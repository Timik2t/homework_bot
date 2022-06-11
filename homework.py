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
    'параметры запроса: {endpoint}, {params}, {headers}'
)
SERVER_ERROR = (
    'Cбой запроса: {error}, {key}, '
    'параметры запроса: {endpoint}, {params}, {headers} '
)


def get_api_answer(current_timestamp):
    """Запрос к API."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        # response.raise_for_status()
    except requests.exceptions.RequestException as error:
        raise ValueError(RESPONSE_ERROR.format(
            error=error,
            endpoint=ENDPOINT,
            headers=HEADERS,
            params=params)
        )
    if response.status_code != OK:
        raise ValueError(RESPONSE_ERROR.format(
            error=response.status_code,
            endpoint=ENDPOINT,
            headers=HEADERS,
            params=params)
        )
    api_answer = response.json()
    for key in SERVER_ERROR_INFORMATION:
        if key in api_answer:
            raise exceptions.InternalServerError(SERVER_ERROR.format(
                key=key,
                endpoint=ENDPOINT,
                headers=HEADERS,
                params=params,
                error=api_answer[key]
            ))
    return api_answer


NOT_DICT = 'API вернул {response}, тип {type} не являющемся обьектом dict'
NOT_LIST = 'API вернул {homeworks}, тип {type} не являющемся обьектом list'
ENDPOINT_MISSING_ERROR = 'В ответе API нет ключа "homeworks"'


def check_response(response):
    """Проверяет ответ API."""
    if not isinstance(response, dict):
        raise TypeError(NOT_DICT.format(
            response=response,
            type=type(response)
        ))
    if "homeworks" not in response:
        raise KeyError(ENDPOINT_MISSING_ERROR)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(NOT_LIST.format(
            homeworks=homeworks,
            type=type(homeworks)
        ))
    return homeworks


HW_STATUS_MISSING = 'Неизвестный статус проверки: {response_ststus}'
PARSE_STATUS = (
    'Изменился статус проверки работы "{homework_name}". '
    '{status}')


def parse_status(homework):
    """Извлечение статуса домашки."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in VERDICTS:
        raise ValueError(
            HW_STATUS_MISSING.format(response_ststus=homework_status)
        )
    return PARSE_STATUS.format(
        homework_name=homework_name,
        status=VERDICTS[homework_status]
    )


TOKENS_MISSING = 'Отсутствует необходимая переменная среды {name}'
TOKENS = ['TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID', 'PRACTICUM_TOKEN']


def check_tokens():
    """Проверка переменных окружения."""
    missing_tokens = []
    for name in TOKENS:
        if not globals()[name]:
            missing_tokens.append(name)
    if len(missing_tokens) != 0:
        logger.error(TOKENS_MISSING.format(name=missing_tokens))
        return False
    return True


HW_MISSING = 'За последнее время нет домашек'


def is_homework(homeworks):
    """Проверка есть ли домашка."""
    if len(homeworks) == 0:
        return False
    return homeworks[0].get('status')


CHECK_TOKENS_MISSING = 'Отсутствует необходимая переменная среды'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError(CHECK_TOKENS_MISSING)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    pre_status = None
    pre_error = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            homework_status = is_homework(homeworks)
            if not homework_status:
                send_message(bot, HW_MISSING)
            elif homework_status != pre_status:
                send_message(bot, parse_status(homeworks[0]))
                pre_status = homework_status
                current_timestamp = response.get('current_date',
                                                 current_timestamp)
        except Exception as error:
            message = str(error)
            if str(error) != pre_error:
                try:
                    send_message(bot, message)
                    pre_error = str(error)
                except exceptions.BotSendMessageError as bot_error:
                    logger.error(bot_error)
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
