import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s',
    filename='info.log'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = StreamHandler()
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def send_message(bot, message):
    """Отправить сообщение."""
    text = str(message)
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text)
    except telegram.error.TelegramError as error:
        logger.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(current_timestamp):
    """Сделать API запрос."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            logger.error('Неудовлетворительный статус ответа')
            raise Exception('Неудовлетворительный статус ответа')
        return response.json()
    except requests.exceptions.RequestException:
        logger.error('Эндпоинт не доступен')
        raise Exception('Эндпоинт не доступен')
    finally:
        logger.info('Запрос к API прошел успешно')


def check_response(response):
    """Проверить ответ API."""
    if not isinstance(response, dict):
        raise TypeError('Неверный формат ответа')
    if ('homeworks' or 'current_date') not in response.keys():
        raise KeyError('Один из ключей отсутствует')
    homeworks_list = response['homeworks']
    if not isinstance(homeworks_list, list):
        raise TypeError('Неверный формат ответа')
    return homeworks_list


def parse_status(homework):
    """Получить статус работы."""
    try:
        homework_name = homework.get('homework_name')
    except KeyError:
        raise KeyError('Ключ "homework_name" отсутствует')
    try:
        homework_status = homework.get('status')
    except KeyError:
        raise KeyError('Ключ "status" отсутствует')
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError:
        logger.error(f'Статус домашней работы "{homework_status}" '
                     'отсутствует в списке')
        raise KeyError


def check_tokens():
    """Проверить наличие токенов."""
    envs = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    for name in envs:
        if not globals()[name]:
            logger.critical(f'Отсутствует токен: {name}')
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют необходимые токены')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            homework = check_response(response)
            if len(homework) != 0:
                message = parse_status(homework[0])
                bot.send_message(TELEGRAM_CHAT_ID, message)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            bot.send_message(TELEGRAM_CHAT_ID, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
