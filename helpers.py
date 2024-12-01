"""
Вспомогательные функции для торговли на Bybit

Этот модуль содержит вспомогательные функции для взаимодействия с API Bybit,
включая функции для получения информации об аккаунте, логирования переводов
и мониторинга лимитов API.
"""

import pandas as pd
from pandas import DataFrame
from pybit.unified_trading import HTTP


class BybitHelper:
    """
    Класс-помощник для работы с Bybit API
    """

    def __init__(self, client: HTTP = None):
        """
        Инициализация помощника

        Args:
            client (HTTP, optional): HTTP клиент Bybit. По умолчанию None
        """
        self.client = client

    @staticmethod
    def log_limits(headers: dict):
        """
        Логирование лимитов API запросов.

        Аргументы:
            headers (dict): Заголовки ответа API, содержащие информацию о лимитах
        """
        print(
            f"Лимиты  {headers.get('X-Bapi-Limit-Status')} / {headers.get('X-Bapi-Limit')}"
        )

    def assets(self):
        """
        Получение балансов для UNIFIED торгового аккаунта.

        Примечание: Этот метод показывает балансы только для UNIFIED аккаунта и не
        отображает полные балансы кошелька. Детали копи-трейдинга, фандинга и
        инверсных аккаунтов не включены.

        Возвращает:
            dict: Информация об активах аккаунта
        """
        if not self.client:
            raise ValueError("HTTP клиент не инициализирован")

        r, _, h = self.client.get_wallet_balance(accountType="UNIFIED")
        r = r.get("result", {}).get("list", [])[0]

        total_balance = float(r.get("totalWalletBalance", "0.0"))
        coins = [
            f"{float(c.get('walletBalance', '0.0')):>12.6f} {c.get('coin'):>12}"
            for c in r.get("coin", [])
        ]

        print("\n".join(coins))
        print(f"---\nTotal: {total_balance:>18.2f}\n")

        self.log_limits(h)

    def get_transfers(self):
        """
        Получение и логирование записей о переводах средств для аккаунта.

        Эта функция получает транзакции переводов без пагинации.
        Создает DataFrame с информацией о переводах и сортирует
        транзакции по временной метке в порядке убывания.

        Возвращает:
            pandas.DataFrame: DataFrame, содержащий детали транзакций переводов
        """
        if not self.client:
            raise ValueError("HTTP клиент не инициализирован")

        r, _, h = self.client.get_transaction_log()

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

        self.log_limits(h)

    def get_assets(self, coin: str) -> float:
        """
        Получение доступного баланса конкретной монеты на аккаунте

        Args:
            coin (str): Название монеты (например, "BTC", "ETH", "USDT")

        Returns:
            float: Доступный баланс монеты для вывода

        Raises:
            ValueError: Если клиент не инициализирован или название монеты пустое
            RuntimeError: Если ответ API имеет неожиданный формат
        """
        if not self.client:
            raise ValueError("HTTP клиент не инициализирован")
        if not coin:
            raise ValueError("Не указано название монеты")

        try:
            # API возвращает кортеж (response, cursor, headers)
            response, _, headers = self.client.get_wallet_balance(accountType="UNIFIED")
            if not response:
                raise RuntimeError("Пустой ответ от API")

            # Получаем список монет из ответа
            account_data = response.get("result", {}).get("list", [])
            if not account_data:
                return 0.0

            # Получаем информацию о монетах
            coins_data = account_data[0].get("coin", [])
            if not coins_data:
                return 0.0

            # Создаем словарь с балансами монет
            balances = {
                asset.get("coin"): float(asset.get("availableToWithdraw", "0.0"))
                for asset in coins_data
                if asset.get("coin")  # Проверяем, что название монеты существует
            }

            # Логируем лимиты API
            self.log_limits(headers)

            # Возвращаем баланс запрошенной монеты или 0.0, если монета не найдена
            return self.round_down(balances.get(coin, 0.0), 3)

        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Неожиданный формат ответа API: {str(e)}")
        except ValueError as e:
            raise RuntimeError(f"Ошибка преобразования значения: {str(e)}")

    def place_order(
        self,
        category: str,
        symbol: str,
        side: str,
        order_type: str,
        qty: float,
        market_unit: str = "quoteCoin",
    ) -> dict:
        """
        Размещение ордера на бирже

        Args:
            category (str): Категория торговли (например, "linear", "spot")
            symbol (str): Торговая пара (например, "BTCUSDT")
            side (str): Сторона ордера ("Buy" или "Sell")
            order_type (str): Тип ордера (например, "Market", "Limit")
            qty (float): Количество для торговли
            market_unit (str, optional): Единица измерения. По умолчанию "quoteCoin"

        Returns:
            dict: Информация о размещенном ордере

        Raises:
            ValueError: Если клиент не инициализирован или параметры некорректны
            RuntimeError: Если возникла ошибка при размещении ордера
        """
        if not self.client:
            raise ValueError("HTTP клиент не инициализирован")
        if not all([category, symbol, side, order_type]):
            raise ValueError("Не указаны обязательные параметры ордера")
        if qty <= 0:
            raise ValueError("Количество должно быть больше 0")
        if side not in ["Buy", "Sell"]:
            raise ValueError(
                'Некорректная сторона ордера. Используйте "Buy" или "Sell"'
            )

        try:
            # Получаем информацию о минимальном размере ордера
            instrument_info, _, _ = self.client.get_instruments_info(
                category=category, symbol=symbol
            )
            lot_size_filter = (
                instrument_info.get("result", {})
                .get("list", [])[0]
                .get("lotSizeFilter", {})
            )
            min_order_qty = float(lot_size_filter.get("minOrderQty", "0.0"))

            # Проверяем минимальный размер ордера
            if qty < min_order_qty:
                raise ValueError(
                    f"Количество {qty} меньше минимально допустимого {min_order_qty}"
                )

            response, _, headers = self.client.place_order(
                category=category,
                symbol=symbol,
                side=side,
                orderType=order_type,
                qty=qty,
                marketUnit=market_unit,
            )

            self.log_limits(headers)
            return response

        except Exception as e:
            raise RuntimeError(f"Ошибка размещения ордера: {str(e)}")

    @staticmethod
    def float_trunc(f: float, prec: int) -> float:
        """
        Ещё один способ отбросить от float лишнее без округлений

        Args:
            f (float): Число для обработки
            prec (int): Количество знаков после запятой

        Returns:
            float: Обработанное число
        """
        l, r = f"{float(f):.12f}".split(".")  # 12 дб достаточно для всех монет
        return float(f"{l}.{r[:prec]}")

    @staticmethod
    def round_down(value: float, decimals: int) -> float:
        """
        Ещё один способ отбросить от float лишнее без округлений

        Args:
            value (float): Число для обработки
            decimals (int): Количество знаков после запятой

        Returns:
            float: Обработанное число
        """
        factor = 1 / (10**decimals)
        return (value // factor) * factor
