"""
Тестовые функции для проверки работы Bybit API

Этот модуль содержит функции для тестирования подключения
и основных операций с Bybit API.
"""

from helpers import BybitHelper


def test_connection(helper: BybitHelper):
    """
    Проверка подключения и вывод информации о балансах и ценах

    Args:
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


def test_place_order(helper: BybitHelper):
    """
    Тестирование размещения ордера
    
    Args:
        helper: экземпляр BybitHelper
    """
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
