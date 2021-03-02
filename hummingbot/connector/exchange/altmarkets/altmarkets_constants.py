class Constants:
    """
    Constants class stores all of the constants required for Altmarkets connector module
    """

    # Rest API endpoints
    EXCHANGE_ROOT_API = "https://v2.altmarkets.io/api/v2/peatio/"
    EXCHANGE_WS_URI = "wss://v2.altmarkets.io/api/v2/ranger/public/"
    EXCHANGE_WS_AUTH_URI = "wss://v2.altmarkets.io/api/v2/ranger/private/"

    # # GET
    TIMESTAMP_URI = "public/timestamp"
    SYMBOLS_URI = "public/markets"
    TICKER_URI = "public/markets/tickers"
    TICKER_SINGLE_URI = "public/markets/{trading_pair}/tickers"
    DEPTH_URI = "public/markets/{trading_pair}/depth?limit=300"
    # # Private GET
    ACCOUNTS_BALANCE_URI = "account/balances"
    LIST_ORDER_URI = "market/orders/{exchange_order_id}"

    # # POST (Private)
    ORDER_CANCEL_ALL_URI = "market/orders/cancel"
    ORDER_CANCEL_URI = "market/orders/{exchange_order_id}/cancel"
    ORDER_CREATION_URI = "market/orders"

    # Web socket events
    # WS_AUTH_REQUEST_EVENT = 'dummy_auth_request'
    WS_PUSHER_SUBSCRIBE_EVENT = 'subscribe'
    WS_TRADE_SUBSCRIBE_STREAMS = ["{trading_pair}.trades"]
    WS_OB_SUBSCRIBE_STREAMS = ["{trading_pair}.ob-inc"]
    WS_USER_SUBSCRIBE_STREAMS = ['order', 'trade']

    # Timeouts
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    API_CALL_TIMEOUT = 10.0
    UPDATE_ORDERS_INTERVAL = 60.0

    # Trading pair splitter regex
    TRADING_PAIR_SPLITTER = r"^(\w+)(btc|ltc|altm|doge|eth|bnb|usdt|usdc|usds|tusd|cro|roger)$"
