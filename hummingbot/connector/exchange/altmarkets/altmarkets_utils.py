import re
from hummingbot.connector.exchange.altmarkets.altmarkets_constants import Constants
from typing import (
    Optional,
    Tuple)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


TRADING_PAIR_SPLITTER = re.compile(Constants.TRADING_PAIR_SPLITTER)

CENTRALIZED = True

EXAMPLE_PAIR = "ALTM-BTC"

DEFAULT_FEES = [0.1, 0.2]


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = TRADING_PAIR_SPLITTER.match(trading_pair)
        return m.group(1), m.group(2)
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    if split_trading_pair(exchange_trading_pair) is None:
        return None
    # Altmarkets uses lowercase (btcusdt)
    base_asset, quote_asset = split_trading_pair(exchange_trading_pair)
    return f"{base_asset.upper()}-{quote_asset.upper()}"


def convert_to_exchange_trading_pair(am_trading_pair: str) -> str:
    # Altmarkets uses lowercase (btcusdt)
    return am_trading_pair.replace("-", "").lower()


KEYS = {
    "altmarkets_api_key":
        ConfigVar(key="altmarkets_api_key",
                  prompt="Enter your Altmarkets API key >>> ",
                  required_if=using_exchange("altmarkets"),
                  is_secure=True,
                  is_connect_key=True),
    "altmarkets_secret_key":
        ConfigVar(key="altmarkets_secret_key",
                  prompt="Enter your Altmarkets secret key >>> ",
                  required_if=using_exchange("altmarkets"),
                  is_secure=True,
                  is_connect_key=True),
}
