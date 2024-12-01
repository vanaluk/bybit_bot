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
import time
from datetime import datetime

pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 500)
pd.set_option("display.width", 1000)

load_dotenv()

API_KEY = os.getenv("BB_API_KEY")
SECRET_KEY = os.getenv("BB_SECRET_KEY")


def test_connection(helper):
    """
    Проверка подключения и вывод информации о балансах и ценах

    Args:
        client: HTTP клиент Bybit
        helper: экземпляр BybitHelper
    """
    print("1. Get all balance")
    helper.assets()
    print("----------------")

    print("2. Get available coin balance (XRP)")
    avbl = helper.get_assets("XRP")
    print(avbl)
    print("----------------")

    print("3. Get price (XRPUSDT)")
    r = helper.get_instrument_info(category="spot", symbol="XRPUSDT")
    print(r)
    print("----------------")


def test_place_order(helper):
    # Размещение ордера
    qty = 10  # теперь это количество XRP
    print(f"4. Place order XRP - {qty} XRP (XRPUSDT)")
    r = helper.place_order(
        category="spot",
        symbol="XRPUSDT",
        side="Sell",
        order_type="Market",
        qty=qty,
        market_unit="baseCoin",
    )
    print(r)
    print("----------------")


def run_algorithm(helper, coin: str, check_interval: int = 10):
    """
    Запуск торгового алгоритма

    Args:
        helper: экземпляр BybitHelper
        coin: название монеты (например, "XRP")
        check_interval: интервал проверки цены в секундах
    """

    symbol = f"{coin}USDT"
    category = "spot"
    buy_amount = 430  # сумма в USDT для покупки
    price_drop_threshold = -0.5  # порог падения цены для покупки
    price_rise_threshold = 5  # порог роста цены для продажи
    stop_loss_threshold = -10  # стоп-лосс (процент от точки входа)
    entry_price = None  # цена входа в позицию
    trailing_price = None  # цена для трейлинг-стопа
    hours_period = 3  # период для отслеживания изменения цены

    print(f"Запуск алгоритма для {symbol}")
    print(
        f"Ожидание падения цены на {abs(price_drop_threshold)}% за {hours_period} часов"
    )

    while True:
        try:
            # Получаем текущую цену и изменение за указанный период
            current_price = helper.get_price(category, symbol)
            price_change = helper.get_price_change(category, symbol, hours=hours_period)

            # Форматируем время для вывода
            current_time = datetime.now().strftime("%H:%M:%S")

            if entry_price is None:
                # Если мы не в позиции, ищем возможность для входа
                print(
                    f"[{current_time}] Цена {symbol}: {current_price:.4f} USDT (Изменение за {hours_period} часов: {price_change:.2f}%)",
                    end="",
                )

                if price_change <= price_drop_threshold:
                    print(
                        f"\nЦена упала на {abs(price_change):.2f}% за {hours_period} часов. Размещаем ордер на покупку."
                    )
                    r = helper.place_order(
                        category=category,
                        symbol=symbol,
                        side="Buy",
                        order_type="Market",
                        qty=buy_amount,
                        market_unit="quoteCoin",
                    )

                    if r.get("retCode") != 0:
                        print(
                            f"\nОшибка при размещении ордера на покупку: {r.get('retMsg')}"
                        )
                        raise Exception(f"Ошибка размещения ордера: {r.get('retMsg')}")

                    order_id = r.get("result", {}).get("orderId")
                    print(f"Ордер на покупку размещен успешно. ID: {order_id}")

                    entry_price = current_price
                    trailing_price = (
                        current_price  # Устанавливаем начальную цену для трейлинга
                    )
                    print(f"Вошли в позицию по цене: {entry_price:.4f} USDT")
                else:
                    print(f" (Ждем падения цены)")
            else:
                # Если мы в позиции, проверяем условия для трейлинга или выхода
                price_change_from_trailing = (
                    (current_price - trailing_price) / trailing_price
                ) * 100
                total_change_from_entry = (
                    (current_price - entry_price) / entry_price
                ) * 100

                print(
                    f"[{current_time}] Цена {symbol}: {current_price:.4f} USDT",
                    f"(От точки входа: {total_change_from_entry:.2f}%,",
                    f"От трейлинга: {price_change_from_trailing:.2f}%)",
                    end="",
                )

                if total_change_from_entry <= stop_loss_threshold:
                    # Если цена упала ниже стоп-лосса, закрываем позицию
                    print(
                        f"\nСработал стоп-лосс! Цена упала на {abs(total_change_from_entry):.2f}% от точки входа. Размещаем ордер на продажу."
                    )
                    r = helper.place_order(
                        category=category,
                        symbol=symbol,
                        side="Sell",
                        order_type="Market",
                        qty=buy_amount,
                        market_unit="quoteCoin",
                    )

                    if r.get("retCode") != 0:
                        print(
                            f"\nОшибка при размещении ордера на продажу: {r.get('retMsg')}"
                        )
                        raise Exception(f"Ошибка размещения ордера: {r.get('retMsg')}")

                    order_id = r.get("result", {}).get("orderId")
                    print(f"Ордер на продажу размещен успешно. ID: {order_id}")

                    print(f"Закрыли позицию по цене: {current_price:.4f} USDT")
                    print(f"Убыток: {total_change_from_entry:.2f}%")
                    entry_price = None
                    trailing_price = None

                elif price_change_from_trailing >= price_rise_threshold:
                    # Если цена выросла выше порога, обновляем трейлинг
                    old_trailing = trailing_price
                    trailing_price = current_price
                    print(
                        f"\nЦена выросла на {price_change_from_trailing:.2f}% от последней точки трейлинга."
                    )
                    print(
                        f"Обновляем точку трейлинга: {old_trailing:.4f} -> {trailing_price:.4f} USDT"
                    )
                    print(f"Общая прибыль от входа: {total_change_from_entry:.2f}%")

                elif price_change_from_trailing <= price_drop_threshold:
                    # Если цена упала ниже порога от максимума, продаем
                    print(
                        f"\nЦена упала на {abs(price_change_from_trailing):.2f}% от точки трейлинга. Размещаем ордер на продажу."
                    )
                    r = helper.place_order(
                        category=category,
                        symbol=symbol,
                        side="Sell",
                        order_type="Market",
                        qty=buy_amount,
                        market_unit="quoteCoin",
                    )

                    if r.get("retCode") != 0:
                        print(
                            f"\nОшибка при размещении ордера на продажу: {r.get('retMsg')}"
                        )
                        raise Exception(f"Ошибка размещения ордера: {r.get('retMsg')}")

                    order_id = r.get("result", {}).get("orderId")
                    print(f"Ордер на продажу размещен успешно. ID: {order_id}")

                    print(f"Закрыли позицию по цене: {current_price:.4f} USDT")
                    print(f"Итоговая прибыль: {total_change_from_entry:.2f}%")
                    entry_price = None
                    trailing_price = None
                else:
                    print(f" (Следим за ценой)")

            time.sleep(check_interval)

        except Exception as e:
            print(f"\nКритическая ошибка: {str(e)}")
            print("Останавливаем программу...")
            break


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
        run_algorithm(helper, "XRP")

    except exceptions.InvalidRequestError as e:
        print("Ошибка запроса ByBit", e.status_code, e.message, sep=" | ")
    except exceptions.FailedRequestError as e:
        print("Ошибка выполнения", e.status_code, e.message, sep=" | ")
    except Exception as e:
        print("Ошибка выполнения |", str(e))


if __name__ == "__main__":
    main()
