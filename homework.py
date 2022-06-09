import logging
import os
import time

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

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=logging.INFO,
)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщения в чат."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logger.info('Отправка сообщения в чат')


def get_api_answer(current_timestamp):
    """Запрос к API."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        response.raise_for_status()
    except requests.HTTPError as error:
        logger.error(f'Ошибка запроса к API {error}')
    return response.json()


def check_response(response):
    """Проверяет ответ API."""
    try:
        homeworks_list = response['homeworks']
    except KeyError as error:
        error_msg = f'Ошибка доступа по ключу homeworks: {error}'
        logger.error(error_msg)
        raise exceptions.CheckResponseException(error_msg)
    if homeworks_list is None:
        error_msg = 'В ответе API нет словаря с домашками'
        logger.error(error_msg)
        raise exceptions.CheckResponseException(error_msg)
    if len(homeworks_list) == 0:
        error_msg = 'За последнее время нет домашек'
        logger.error(error_msg)
        raise exceptions.CheckResponseException(error_msg)
    return homeworks_list


def parse_status(homework):
    """Извлечение статуса домашки."""
    try:
        homework_name = homework.get('homework_name')
    except KeyError as error:
        logger.error(f'Ошибка доступа по ключу homework_name: {error}')
    try:
        homework_status = homework.get('status')
    except KeyError as error:
        logger.error(f'Ошибка доступа по ключу status: {error}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    if verdict is None:
        msg = 'Неизвестный статус домашки'
        logger.error(msg)
        raise exceptions.UnknownStatusException(msg)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка переменных окружения."""
    return all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_msg = 'Отсутствует необходимая переменная среды'
        logger.critical(error_msg)
        raise exceptions.MissingTokenException(error_msg)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    pre_status = None
    pre_error = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
        except exceptions.IncorrectAPIResponseException as error:
            if str(error) != pre_error:
                pre_error = str(error)
                send_message(bot, error)
            logger.error(error)
            time.sleep(RETRY_TIME)
            continue
        try:
            homeworks = check_response(response)
            homework_status = homeworks[0].get('status')
            if homework_status != pre_status:
                pre_status = homework_status
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logger.debug('Статус проверки домашки прежний')
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if pre_error != str(error):
                pre_error = str(error)
                send_message(bot, message)
            logger.error(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
