from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import os

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем API ключи из переменных окружения
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")

# Инициализируем клиент Bybit
# Для тестового API используйте: "https://api-testnet.bybit.com"
# Для реального API используйте: "https://api.bybit.com"
session = HTTP(
    testnet=False,  # Измените на False для реального API
    api_key=api_key,
    api_secret=api_secret,
)


# Пример получения баланса аккаунта
def get_wallet_balance():
    return session.get_wallet_balance(accountType="UNIFIED")


# Пример получения текущей цены
def get_current_price(symbol="BTCUSDT"):
    return session.get_tickers(category="spot", symbol=symbol)


# Получаем и выводим баланс кошелька
balance = get_wallet_balance()
print("Баланс кошелька:")
print(balance)

# Получаем и выводим текущую цену
price = get_current_price()
print("Текущая цена:")
print(price)
