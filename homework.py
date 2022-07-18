import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

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


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
handler = StreamHandler()
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s - %(funcName)s - %(lineno)s'
)
handler.setFormatter(formatter)

def send_message(bot: telegram.Bot, message: str):
    """Отправить сообщение."""
    text = str(message)
    try:
        logger.info('Отправляем сообщение')
        bot.send_message(TELEGRAM_CHAT_ID, text)
        logger.info('Сообщение отправлено')
    except telegram.error.TelegramError:
        raise exceptions.TelegramException('Ошибка отправки сообщения')


def get_api_answer(current_timestamp: int):
    """Сделать API запрос."""
    params = {'from_date': current_timestamp}
    try:
        logger.info('Делаем запрос к API')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise exceptions.WrongStatusCodeException('Неудовлетворительный '
                                                      'статус ответа')
        logger.info('Запрос к API прошел успешно')
        return response.json()
    except requests.exceptions.RequestException:
        raise exceptions.EndpointIsNotAvailable('Эндпоинт не доступен')


def check_response(response: requests.models.Response):
    """Проверить ответ API."""
    logger.info('Проверяем ответ сервера')
    if not isinstance(response, dict):
        raise TypeError('Неверный формат ответа')
    if 'homeworks' not in response or 'current_date' not in response:
        raise KeyError('Один из ключей отсутствует')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Неверный формат ответа')
    return homeworks


def parse_status(homework: dict):
    """Получить статус работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status is None:
        raise KeyError('Неправильный ключ')
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError:
        raise KeyError(f'Статус домашней работы "{homework_status}" '
                       f'отсутствует в списке')


def check_tokens():
    """Проверить наличие токенов."""
    envs = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    return all(globals()[name] for name in envs)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют необходимые токены')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    prev_report = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date', current_timestamp)
            homework = check_response(response)
            if len(homework) != 0:
                current_report = parse_status(homework[0])
                if current_report != prev_report:
                    send_message(bot, current_report)
                    prev_report = current_report
            else:
                logger.info('Обновлений не произошло')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            bot.send_message(TELEGRAM_CHAT_ID, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s, %(levelname)s, %(message)s',
        filename='info.log'
    )


    main()
