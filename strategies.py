"""
Торговые стратегии для Bybit бота

Этот модуль содержит различные торговые стратегии,
которые могут быть использованы с Bybit API.
"""

import time
from datetime import datetime
from helpers import BybitHelper


def run_trailing_stop_strategy(
    helper: BybitHelper, coin: str, buy_amount: float, check_interval: int = 10
):
    """
    Запуск торгового алгоритма

    Args:
        helper: экземпляр BybitHelper
        coin: название монеты (например, "XRP")
        buy_amount: сумма в USDT для покупки
        check_interval: интервал проверки цены в секундах
    """
    symbol = f"{coin}USDT"
    category = "spot"
    price_drop_threshold = -3  # порог падения цены для покупки
    price_rise_threshold = 5  # порог роста цены для продажи
    stop_loss_threshold = -10  # стоп-лосс (процент от точки входа)
    quick_rise_threshold = 2  # порог быстрого роста цены для покупки
    entry_price = None  # цена входа в позицию
    trailing_price = None  # цена для трейлинг-стопа
    hours_period = 3  # период для отслеживания изменения цены
    quick_period = 2  # период для отслеживания быстрого роста

    print(f"Запуск алгоритма для {symbol}")
    print(
        f"Вход в позицию при:\n"
        f"1) Падении на {abs(price_drop_threshold)}% за {hours_period} часа\n"
        f"2) Быстром росте на {quick_rise_threshold}% за {quick_period} час"
    )

    while True:
        try:
            # Получаем текущую цену и изменения за разные периоды
            current_price = helper.get_price(category, symbol)
            price_change = helper.get_price_change(category, symbol, hours=hours_period)
            quick_price_change = helper.get_price_change(
                category, symbol, hours=quick_period
            )

            # Форматируем время для вывода
            current_time = datetime.now().strftime("%H:%M:%S")

            if entry_price is None:
                # Если мы не в позиции, ищем возможность для входа
                print(
                    f"[{current_time}] Цена {symbol}: {current_price:.4f} USDT "
                    f"(Изменение за {hours_period}ч: {price_change:.2f}%, "
                    f"за {quick_period}ч: {quick_price_change:.2f}%)",
                    end="",
                )

                # Проверяем условия входа
                if quick_price_change >= quick_rise_threshold:
                    print(
                        f"\nБыстрый рост! Цена выросла на {quick_price_change:.2f}% за последний час. Размещаем ордер на покупку."
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
                    trailing_price = current_price
                    print(f"Вошли в позицию по цене: {entry_price:.4f} USDT")

                elif price_change <= price_drop_threshold:
                    print(
                        f"\nЦена упала на {abs(price_change):.2f}% за {hours_period} часа. Размещаем ордер на покупку."
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
                    trailing_price = current_price
                    print(f"Вошли в позицию по цене: {entry_price:.4f} USDT")
                else:
                    print(f" (Ждем сигнала)")
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
