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


s_decimal_zero = Decimal(0)


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


def valid_empty(value):
    return (value == s_decimal_zero or value is None)


def validate_amount_min(value: str):
    valid_dec = validate_decimal(value, 0, inclusive=False)
    decimal_value = Decimal(value) if valid_dec is None else s_decimal_zero
    amount_max = random_loop_trade_config_map.get("order_amount_max").value
    if not valid_empty(amount_max):
        if valid_empty(value):
            return "order_amount_min can't be 0 if order_amount_max is set"
        elif valid_dec is None and not amount_max > decimal_value:
            return "order_amount_min must be lower than order_amount_max"
        else:
            return valid_dec


def validate_amount_max(value: str):
    valid_dec = validate_decimal(value, 0, inclusive=False)
    decimal_value = Decimal(value) if valid_dec is None else s_decimal_zero
    amount_min = random_loop_trade_config_map.get("order_amount_min").value
    if not valid_empty(amount_min):
        if valid_empty(value):
            return "order_amount_max can't be 0 if order_amount_min is set"
        elif valid_dec is None and not amount_min < decimal_value:
            return "order_amount_min must be lower than order_amount_max"
        else:
            return valid_dec


def validate_price(value: str):
    valid_dec = validate_decimal(value, 0, inclusive=False)
    # decimal_value = Decimal(value) if valid_dec is None else s_decimal_zero
    enabled_rand = random_loop_trade_config_map.get("order_pricetype_random").value
    enabled_spread = random_loop_trade_config_map.get("order_pricetype_spread").value
    if not enabled_rand and not enabled_spread:
        if valid_empty(value):
            return "order_price can't be 0 if not using random/spread"
        else:
            return valid_dec


def validate_price_min(value: str):
    valid_dec = validate_decimal(value, 0, inclusive=False)
    decimal_value = Decimal(value) if valid_dec is None else s_decimal_zero
    price_max = random_loop_trade_config_map.get("order_price_max").value
    enabled_rand = random_loop_trade_config_map.get("order_pricetype_random").value
    if enabled_rand:
        if valid_empty(value):
            return "order_price_min can't be 0 if random is enabled"
        elif valid_dec is None and not valid_empty(price_max) and not price_max > decimal_value:
            return "order_price_min must be lower than order_price_max"
        else:
            return valid_dec


def validate_price_max(value: str):
    valid_dec = validate_decimal(value, 0, inclusive=False)
    decimal_value = Decimal(value) if valid_dec is None else s_decimal_zero
    price_min = random_loop_trade_config_map.get("order_price_min").value
    enabled_rand = random_loop_trade_config_map.get("order_pricetype_random").value
    if enabled_rand:
        if valid_empty(value):
            return "order_price_max can't be 0 if random is enabled"
        elif valid_dec is None and not valid_empty(price_min) and not price_min < decimal_value:
            return "order_price_min must be lower than order_price_max"
        else:
            return valid_dec


def validate_spread(value: str):
    valid_dec = validate_decimal(value, 0, inclusive=False)
    # decimal_value = Decimal(value) if valid_dec is None else s_decimal_zero
    enabled_rand = random_loop_trade_config_map.get("order_pricetype_random").value
    enabled_spread = random_loop_trade_config_map.get("order_pricetype_spread").value
    if enabled_spread and not enabled_rand:
        if valid_empty(value):
            return "order_spread can't be 0 if not using random"
        else:
            return valid_dec


def validate_spread_min(value: str):
    valid_dec = validate_decimal(value, 0, 100, inclusive=False)
    decimal_value = Decimal(value) if valid_dec is None else s_decimal_zero
    spread_max = random_loop_trade_config_map.get("order_spread_max").value
    enabled_rand = random_loop_trade_config_map.get("order_pricetype_random").value
    enabled_spread = random_loop_trade_config_map.get("order_pricetype_spread").value
    if enabled_rand and enabled_spread:
        if valid_empty(value):
            return "order_spread_min can't be 0 if random spread is enabled"
        elif valid_dec is None and not valid_empty(spread_max) and not spread_max > decimal_value:
            return "order_spread_min must be lower than order_spread_max"
        else:
            return valid_dec


def validate_spread_max(value: str):
    valid_dec = validate_decimal(value, 0, 100, inclusive=False)
    decimal_value = Decimal(value) if valid_dec is None else s_decimal_zero
    spread_min = random_loop_trade_config_map.get("order_spread_min").value
    enabled_rand = random_loop_trade_config_map.get("order_pricetype_random").value
    enabled_spread = random_loop_trade_config_map.get("order_pricetype_spread").value
    if enabled_rand and enabled_spread:
        if valid_empty(value):
            return "order_spread_max can't be 0 if random/spread is enabled"
        elif valid_dec is None and not valid_empty(spread_min) and not spread_min < decimal_value:
            return "order_spread_min must be lower than order_spread_max"
        else:
            return valid_dec


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
                  required_if=lambda: (random_loop_trade_config_map.get("order_type").value == "limit"),
                  validator=validate_amount_min,
                  default=s_decimal_zero,
                  type_str="decimal"),
    "order_amount_max":
        ConfigVar(key="order_amount_max",
                  prompt="What is your preferred max quantity per order (denominated in the base asset, default is 0)? "
                         ">>> ",
                  required_if=lambda: (random_loop_trade_config_map.get("order_type").value == "limit"),
                  validator=validate_amount_max,
                  default=s_decimal_zero,
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
    "order_pricetype_random":
        ConfigVar(key="order_pricetype_random",
                  prompt="Enable random price? >>> ",
                  required_if=lambda: (random_loop_trade_config_map.get("order_type").value == "limit"),
                  type_str="bool",
                  validator=validate_bool,
                  default=False,
                  prompt_on_new=True),
    "order_pricetype_spread":
        ConfigVar(key="order_pricetype_spread",
                  prompt="Use spreads instead of hard prices? >>> ",
                  required_if=lambda: (random_loop_trade_config_map.get("order_type").value == "limit"),
                  type_str="bool",
                  validator=validate_bool,
                  default=False,
                  prompt_on_new=True),
    "order_price":
        ConfigVar(key="order_price",
                  prompt="What is the price of the limit order ? >>> ",
                  required_if=lambda: (random_loop_trade_config_map.get("order_type").value == "limit" and
                                       not random_loop_trade_config_map.get("order_pricetype_random").value and
                                       not random_loop_trade_config_map.get("order_pricetype_spread").value),
                  type_str="decimal",
                  validator=validate_price,
                  prompt_on_new=True),
    "order_price_min":
        ConfigVar(key="order_price_min",
                  prompt="What is the min price of the limit order ? >>> ",
                  required_if=lambda: (random_loop_trade_config_map.get("order_type").value == "limit" and
                                       random_loop_trade_config_map.get("order_pricetype_random").value and
                                       not random_loop_trade_config_map.get("order_pricetype_spread").value),
                  type_str="decimal",
                  validator=validate_price_min,
                  prompt_on_new=True),
    "order_price_max":
        ConfigVar(key="order_price_max",
                  prompt="What is the max price of the limit order ? >>> ",
                  required_if=lambda: (random_loop_trade_config_map.get("order_type").value == "limit" and
                                       random_loop_trade_config_map.get("order_pricetype_random").value and
                                       not random_loop_trade_config_map.get("order_pricetype_spread").value),
                  type_str="decimal",
                  validator=validate_price_max,
                  prompt_on_new=True),
    "order_spread":
        ConfigVar(key="order_spread",
                  prompt="How far away from the mid price do you want your price to be?"
                         " (Enter 1 to indicate 1%) >>> ",
                  required_if=lambda: (random_loop_trade_config_map.get("order_type").value == "limit" and
                                       not random_loop_trade_config_map.get("order_pricetype_random").value and
                                       random_loop_trade_config_map.get("order_pricetype_spread").value),
                  type_str="decimal",
                  validator=validate_spread,
                  prompt_on_new=True),
    "order_spread_min":
        ConfigVar(key="order_spread_min",
                  prompt="How far away from the mid price do you want your minimum price to be?"
                         " (Enter 1 to indicate 1%) >>> ",
                  required_if=lambda: (random_loop_trade_config_map.get("order_type").value == "limit" and
                                       random_loop_trade_config_map.get("order_pricetype_random").value and
                                       random_loop_trade_config_map.get("order_pricetype_spread").value),
                  type_str="decimal",
                  validator=validate_spread_min,
                  prompt_on_new=True),
    "order_spread_max":
        ConfigVar(key="order_spread_max",
                  prompt="How far away from the mid price do you want your maximum price to be?"
                         " (Enter 1 to indicate 1%) >>> ",
                  required_if=lambda: (random_loop_trade_config_map.get("order_type").value == "limit" and
                                       random_loop_trade_config_map.get("order_pricetype_random").value and
                                       random_loop_trade_config_map.get("order_pricetype_spread").value),
                  type_str="decimal",
                  validator=validate_spread_max,
                  prompt_on_new=True),
    "order_spread_pricetype":
        ConfigVar(key="order_spread_pricetype",
                  prompt="Which price type to calculate spread from? ("
                         "mid_price/last_price/best_bid/best_ask) >>> ",
                  type_str="str",
                  required_if=lambda: (random_loop_trade_config_map.get("order_type").value == "limit" and
                                       random_loop_trade_config_map.get("order_pricetype_spread").value),
                  default="mid_price",
                  validator=lambda s: None if s in {"mid_price",
                                                    "last_price",
                                                    "best_bid",
                                                    "best_ask",
                                                    } else
                  "Invalid price type."),
    "cancel_order_wait_time":
        ConfigVar(key="cancel_order_wait_time",
                  prompt="How long do you want to wait before cancelling your limit order (in seconds). "
                         "(Default is 60 seconds) ? >>> ",
                  required_if=lambda: random_loop_trade_config_map.get("order_type").value == "limit",
                  type_str="float",
                  default=60),
}
