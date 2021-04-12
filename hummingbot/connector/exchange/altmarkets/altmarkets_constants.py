# A single source of truth for constant variables related to the exchange
class Constants:
    EXCHANGE_NAME = "altmarkets"
    REST_URL = "https://v2.altmarkets.io/api/v2/peatio"
    # WS_PRIVATE_URL = "wss://stream.crypto.com/v2/user"
    WS_PRIVATE_URL = "wss://v2.altmarkets.io/api/v2/ranger/private"
    # WS_PUBLIC_URL = "wss://stream.crypto.com/v2/market"
    WS_PUBLIC_URL = "wss://v2.altmarkets.io/api/v2/ranger/public"

    HBOT_BROKER_ID = "HBOT"

    ENDPOINT = {
        # Public Endpoints
        "TIMESTAMP": "public/timestamp",
        "TICKER": "public/markets/tickers",
        "TICKER_SINGLE": "public/markets/{trading_pair}/tickers",
        "SYMBOL": "public/markets",
        "ORDER_BOOK": "public/markets/{trading_pair}/depth",
        "ORDER_CREATE": "market/orders",
        "ORDER_DELETE": "market/orders/{id}/cancel",
        "ORDER_STATUS": "market/orders/{id}",
        "USER_ORDERS": "market/orders",
        "USER_BALANCES": "account/balances",
    }

    WS_SUB = {
        "TRADES": "{trading_pair}.trades",
        "ORDERS": "{trading_pair}.ob-inc",
        "USER_ORDERS_TRADES": ['balance', 'order', 'trade'],

    }

    WS_METHODS = {
        "ORDERS_SNAPSHOT": ".ob-snap",
        "ORDERS_UPDATE": ".ob-inc",
        "TRADES_UPDATE": ".trades",
        "USER_BALANCES": "balance",
        "USER_ORDERS": "order",
        "USER_TRADES": "trade",
    }

    ORDER_STATES = {
        "DONE": {"done", "cancel", "partial-canceled"},
        "FAIL": {"cancel", "reject"},
        "OPEN": {"submitted", "wait", "pending"},
        "CANCEL": {"partial-canceled", "cancel"},
        "CANCEL_WAIT": {'wait', 'cancel', 'done', 'reject'},
    }

    # Timeouts
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    API_CALL_TIMEOUT = 10.0
    API_MAX_RETRIES = 4

    # Intervals
    # Only used when nothing is received from WS
    SHORT_POLL_INTERVAL = 5.0
    # One minute should be fine since we request balance updates on order updates
    LONG_POLL_INTERVAL = 60.0
    # Two minutes should be fine for order status since we get these via WS
    UPDATE_ORDER_STATUS_INTERVAL = 120.0
    # 10 minute interval to update trading rules, these would likely never change whilst running.
    INTERVAL_TRADING_RULES = 600

    # Trading pair splitter regex
    TRADING_PAIR_SPLITTER = r"^(\w+)(btc|ltc|altm|doge|eth|bnb|usdt|usdc|usds|tusd|cro|roger)$"
