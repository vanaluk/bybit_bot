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

import pandas as pd
from dotenv import load_dotenv
from pybit import exceptions
from pybit.unified_trading import HTTP
from helpers import BybitHelper

pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 500)
pd.set_option("display.width", 1000)

load_dotenv()
API_KEY = os.getenv("BB_API_KEY")
SECRET_KEY = os.getenv("BB_SECRET_KEY")


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

        print("1. Get all balance")
        helper.assets()
        print("----------------")
        # helper.get_transfers()

        print("2. Get availible coin balance (XRP)")
        avbl = helper.get_assets("XRP")
        print(
            avbl,
            round(avbl, 3),
            helper.round_down(avbl, 3),
            helper.float_trunc(avbl, 3),
        )
        print("----------------")

        print("3. Get price (XRPUSDT)")
        r = client.get_instruments_info(category="spot", symbol="XRPUSDT")
        print(r)
        print("----------------")

    except exceptions.InvalidRequestError as e:
        print("Ошибка запроса ByBit", e.status_code, e.message, sep=" | ")
    except exceptions.FailedRequestError as e:
        print("Ошибка выполнения запроса ByBit", e.status_code, e.message, sep=" | ")
    except exceptions.UnauthorizedExceptionError as e:
        print("Ошибка авторизации ByBit", str(e), sep=" | ")
    except exceptions.InvalidChannelTypeError as e:
        print("Ошибка канала ByBit", str(e), sep=" | ")
    except exceptions.TopicMismatchError as e:
        print("Ошибка темы ByBit", str(e), sep=" | ")
    except (KeyError, ValueError, TypeError) as e:
        print("Ошибка обработки данных", str(e), sep=" | ")
    except (ConnectionError, TimeoutError) as e:
        print("Ошибка сети", str(e), sep=" | ")
    except (OSError, IOError) as e:
        print("Ошибка операции с файлом", str(e), sep=" | ")
    except RuntimeError as e:
        print("Ошибка выполнения", str(e), sep=" | ")
    except AttributeError as e:
        print("Ошибка ответа API", str(e), sep=" | ")
    # trunk-ignore(pylint/W0718)
    except Exception as e:
        print("Неизвестная ошибка", str(e), sep=" | ")


if __name__ == "__main__":
    main()
