from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_bool,
    validate_decimal,
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)
from typing import Optional
from decimal import Decimal


def trading_pair_prompt():
    market = random_loop_trade_config_map.get("market").value
    example = EXAMPLE_PAIRS.get(market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (market, f" (e.g. {example})" if example else "")


def str2bool(value: str):
    return str(value).lower() in ("yes", "true", "t", "1")


# checks if the trading pair is valid
def validate_market_trading_pair_tuple(value: str) -> Optional[str]:
    market = random_loop_trade_config_map.get("market").value
    return validate_market_trading_pair(market, value)


random_loop_trade_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="random_loop_trade"),
    "market":
        ConfigVar(key="market",
                  prompt="Enter the name of the exchange >>> ",
                  validator=validate_exchange,
                  on_validated=lambda value: required_exchanges.append(value),
                  prompt_on_new=True),
    "market_trading_pair_tuple":
        ConfigVar(key="market_trading_pair_tuple",
                  prompt=trading_pair_prompt,
                  validator=validate_market_trading_pair_tuple,
                  prompt_on_new=True),
    "order_type":
        ConfigVar(key="order_type",
                  prompt="Enter type of order (limit/market) default is limit >>> ",
                  type_str="str",
                  validator=lambda v: None if v in {"limit", "market", ""} else "Invalid order type.",
                  default="limit",
                  prompt_on_new=True),
    "order_amount":
        ConfigVar(key="order_amount",
                  prompt="What is your preferred quantity per order (denominated in the base asset, default is 1)? "
                         ">>> ",
                  default=Decimal("1.0"),
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True),
    "order_amount_min":
        ConfigVar(key="order_amount_min",
                  prompt="What is your preferred min quantity per order (denominated in the base asset, default is 0)? "
                         ">>> ",
                  default=Decimal("0"),
                  type_str="decimal"),
    "order_amount_max":
        ConfigVar(key="order_amount_max",
                  prompt="What is your preferred max quantity per order (denominated in the base asset, default is 0)? "
                         ">>> ",
                  default=Decimal("0"),
                  type_str="decimal"),
    "is_buy":
        ConfigVar(key="is_buy",
                  prompt="Enter True for Buy order and False for Sell order (default is Buy Order) >>> ",
                  type_str="bool",
                  validator=validate_bool,
                  default=True,
                  prompt_on_new=True),
    "ping_pong_enabled":
        ConfigVar(key="ping_pong_enabled",
                  prompt="Enable Ping Pong (switching between buys and sells - overrides is_buy)? >>> ",
                  type_str="bool",
                  validator=validate_bool,
                  default=False,
                  prompt_on_new=True),
    "time_delay":
        ConfigVar(key="time_delay",
                  prompt="How much do you want to wait between placing orders (Enter 10 to indicate 10 seconds. "
                         "Default is 10)? >>> ",
                  type_str="float",
                  default=10,
                  prompt_on_new=True),
    "order_price":
        ConfigVar(key="order_price",
                  prompt="What is the price of the limit order ? >>> ",
                  required_if=lambda: random_loop_trade_config_map.get("order_type").value == "limit",
                  default=Decimal("0"),
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True),
    "order_price_min":
        ConfigVar(key="order_price_min",
                  prompt="What is the min price of the limit order ? >>> ",
                  required_if=lambda: random_loop_trade_config_map.get("order_type").value == "limit",
                  default=Decimal("0"),
                  type_str="decimal"),
    "order_price_max":
        ConfigVar(key="order_price_max",
                  prompt="What is the max price of the limit order ? >>> ",
                  required_if=lambda: random_loop_trade_config_map.get("order_type").value == "limit",
                  default=Decimal("0"),
                  type_str="decimal"),
    "cancel_order_wait_time":
        ConfigVar(key="cancel_order_wait_time",
                  prompt="How long do you want to wait before cancelling your limit order (in seconds). "
                         "(Default is 60 seconds) ? >>> ",
                  required_if=lambda: random_loop_trade_config_map.get("order_type").value == "limit",
                  type_str="float",
                  default=60),
}
