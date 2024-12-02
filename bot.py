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
from dotenv import load_dotenv
from pybit import exceptions
from pybit.unified_trading import HTTP
from helpers import BybitHelper
from tests import test_connection
from strategies import run_trailing_stop_strategy

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")


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
        # Тестирование размещения ордера
        # test_place_order(helper)
        # Запуск торгового алгоритма
        run_trailing_stop_strategy(helper, "XRP")

    except exceptions.InvalidRequestError as e:
        print("Ошибка запроса ByBit", e.status_code, e.message, sep=" | ")
    except exceptions.FailedRequestError as e:
        print("Ошибка выполнения", e.status_code, e.message, sep=" | ")
    except Exception as e:
        print("Ошибка выполнения |", str(e))


if __name__ == "__main__":
    main()
