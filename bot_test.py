from pybit.unified_trading import HTTP

cl = HTTP()

r = cl.get_orderbook(category="spot", symbol="BTCUSDT")
print(r)
