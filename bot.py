"""
Утилита торгового бота для Bybit

Этот модуль предоставляет утилиты для взаимодействия
с торговой платформой Bybit.
Включает функциональность для:
- Получения информации об активах
- Получения и логирования переводов средств
- Обработки API запросов и аутентификации

Скрипт использует переменные окружения для API ключа и секрета.
Требует библиотеки pybit и python-dotenv для взаимодействия с API и управления окружением.
"""

import os
import sys
from dotenv import load_dotenv
from pybit import exceptions
from pybit.unified_trading import HTTP
from helpers import BybitHelper
from tests import test_connection
from strategies import run_trailing_stop_strategy

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")


def print_usage():
    """Выводит информацию об использовании скрипта"""
    print("Usage: python bot.py <buy_amount> <coin>")
    print("Example: python bot.py 100 XRP")
    sys.exit(1)


def main():
    """
    Основная функция для выполнения операций торгового бота Bybit.

    Эта функция:
    1. Инициализирует HTTP клиент Bybit с учетными данными API
    2. Получает информацию об активах аккаунта
    3. Получает и логирует переводы средств
    4. Обрабатывает возможные ошибки API запросов

    Исключения:
        exceptions.InvalidRequestError: Если произошла ошибка в API запросе
        exceptions.FailedRequestError: Если API запрос не удался
    """
    # Проверяем аргументы командной строки
    if len(sys.argv) != 3:
        print_usage()

    try:
        buy_amount = float(sys.argv[1])
        coin = sys.argv[2].upper()
    except ValueError:
        print("Error: buy_amount must be a number")
        print_usage()

    try:
        if not API_KEY or not SECRET_KEY:
            raise ValueError("API_KEY или SECRET_KEY не найдены в переменных окружения")

        client = HTTP(
            api_key=API_KEY,
            api_secret=SECRET_KEY,
            recv_window=60000,
            return_response_headers=True,
        )

        helper = BybitHelper(client)

        # Тестирование подключения и вывод информации
        test_connection(helper)
        
        # Запуск торгового алгоритма
        run_trailing_stop_strategy(helper, coin, buy_amount)

    except exceptions.InvalidRequestError as e:
        print("Ошибка запроса ByBit", e.status_code, e.message, sep=" | ")
    except exceptions.FailedRequestError as e:
        print("Ошибка выполнения", e.status_code, e.message, sep=" | ")
    except Exception as e:
        print("Ошибка выполнения |", str(e))


if __name__ == "__main__":
    main()
