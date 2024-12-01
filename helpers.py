"""
Вспомогательные функции для торговли на Bybit

Этот модуль содержит вспомогательные функции для взаимодействия с API Bybit,
включая функции для получения информации об аккаунте, логирования переводов
и мониторинга лимитов API.
"""

import pandas as pd
from pandas import DataFrame
from pybit.unified_trading import HTTP


def log_limits(headers: dict):
    """
    Логирование лимитов API запросов.

    Аргументы:
        headers (dict): Заголовки ответа API, содержащие информацию о лимитах
    """
    print(
        f"Лимиты  {headers.get('X-Bapi-Limit-Status')} / {headers.get('X-Bapi-Limit')}"
    )


def assets(cl: HTTP):
    """
    Получение балансов для UNIFIED торгового аккаунта.

    Примечание: Этот метод показывает балансы только для UNIFIED аккаунта и не
    отображает полные балансы кошелька. Детали копи-трейдинга, фандинга и
    инверсных аккаунтов не включены.

    Аргументы:
        cl (HTTP): HTTP клиент Bybit с учетными данными для аутентификации

    Возвращает:
        dict: Информация об активах аккаунта
    """
    r, _, h = cl.get_wallet_balance(accountType="UNIFIED")
    r = r.get("result", {}).get("list", [])[0]

    total_balance = float(r.get("totalWalletBalance", "0.0"))
    coins = [
        f"{float(c.get('walletBalance', '0.0')):>12.6f} {c.get('coin'):>12}"
        for c in r.get("coin", [])
    ]

    print("\n".join(coins))
    print(f"---\nTotal: {total_balance:>18.2f}\n")

    log_limits(h)


def get_transfers(cl: HTTP):
    """
    Получение и логирование записей о переводах средств для аккаунта.

    Эта функция получает транзакции переводов без пагинации.
    Создает DataFrame с информацией о переводах и сортирует
    транзакции по временной метке в порядке убывания.

    Аргументы:
        cl (HTTP): HTTP клиент Bybit с учетными данными для аутентификации

    Возвращает:
        pandas.DataFrame: DataFrame, содержащий детали транзакций переводов
    """
    r, _, h = cl.get_transaction_log()

    df = DataFrame(
        [
            {
                "currency": e.get("currency"),
                "type": e.get("type"),
                "change": e.get("change"),
                "cashBalance": e.get("cashBalance"),
                "transactionTime": int(e.get("transactionTime")),
            }
            for e in r.get("result", {}).get("list", [])
            if e.get("type").startswith("TRANSFER")
        ]
    )

    df["transactionTime"] = pd.to_datetime(df["transactionTime"], unit="ms")
    df.sort_values(by=["transactionTime"], inplace=True, ascending=False)
    print(df)

    log_limits(h)