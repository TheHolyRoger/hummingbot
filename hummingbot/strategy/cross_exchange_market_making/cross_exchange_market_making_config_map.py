from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_decimal,
    validate_bool
)
from hummingbot.client.settings import required_exchanges, EXAMPLE_PAIRS
from decimal import Decimal
from hummingbot.client.config.config_helpers import (
    minimum_order_amount
)
from typing import Optional


def maker_trading_pair_prompt():
    maker_market = cross_exchange_market_making_config_map.get("maker_market").value
    example = EXAMPLE_PAIRS.get(maker_market)
    return "Enter the token trading pair you would like to trade on maker market: %s%s >>> " % (
        maker_market,
        f" (e.g. {example})" if example else "",
    )


def taker_trading_pair_prompt():
    taker_market = cross_exchange_market_making_config_map.get("taker_market").value
    example = EXAMPLE_PAIRS.get(taker_market)
    return "Enter the token trading pair you would like to trade on taker market: %s%s >>> " % (
        taker_market,
        f" (e.g. {example})" if example else "",
    )


def top_depth_tolerance_prompt() -> str:
    maker_market = cross_exchange_market_making_config_map["maker_market_trading_pair"].value
    base_asset, quote_asset = maker_market.split("-")
    return f"What is your top depth tolerance? (in {base_asset}) >>> "


# strategy specific validators
def validate_maker_market_trading_pair(value: str) -> Optional[str]:
    maker_market = cross_exchange_market_making_config_map.get("maker_market").value
    return validate_market_trading_pair(maker_market, value)


def validate_taker_market_trading_pair(value: str) -> Optional[str]:
    taker_market = cross_exchange_market_making_config_map.get("taker_market").value
    return validate_market_trading_pair(taker_market, value)


def order_amount_prompt() -> str:
    maker_exchange = cross_exchange_market_making_config_map["maker_market"].value
    trading_pair = cross_exchange_market_making_config_map["maker_market_trading_pair"].value
    base_asset, quote_asset = trading_pair.split("-")
    min_amount = minimum_order_amount(maker_exchange, trading_pair)
    return f"What is the amount of {base_asset} per order? (minimum {min_amount}) >>> "


def validate_order_amount(value: str) -> Optional[str]:
    try:
        maker_exchange = cross_exchange_market_making_config_map.get("maker_market").value
        trading_pair = cross_exchange_market_making_config_map["maker_market_trading_pair"].value
        min_amount = minimum_order_amount(maker_exchange, trading_pair)
        if Decimal(value) < min_amount:
            return f"Order amount must be at least {min_amount}."
    except Exception:
        return "Invalid order amount."


def taker_market_on_validated(value: str):
    required_exchanges.append(value)


def validate_price_source(value: str) -> Optional[str]:
    if value not in {"config_rate", "external_market", "custom_api"}:
        return "Invalid price source type."


def validate_price_source_exchange(value: str) -> Optional[str]:
    return validate_exchange(value)


def on_validate_base_price_source(value: str):
    if value != "external_market":
        cross_exchange_market_making_config_map["base_price_source_exchange"].value = None
        cross_exchange_market_making_config_map["base_price_source_market"].value = None
    if value != "custom_api":
        cross_exchange_market_making_config_map["base_price_source_custom_api"].value = None
    else:
        cross_exchange_market_making_config_map["base_price_source_type"].value = None


def base_price_source_market_prompt() -> str:
    external_market = cross_exchange_market_making_config_map.get("base_price_source_exchange").value
    return f'Enter the base token trading pair on {external_market} >>> '


def on_validated_base_price_source_exchange(value: str):
    if value is None:
        cross_exchange_market_making_config_map["base_price_source_exchange"].value = None


def validate_base_price_source_market(value: str) -> Optional[str]:
    market = cross_exchange_market_making_config_map.get("base_price_source_exchange").value
    return validate_market_trading_pair(market, value)


def on_validate_quote_price_source(value: str):
    if value != "external_market":
        cross_exchange_market_making_config_map["quote_price_source_exchange"].value = None
        cross_exchange_market_making_config_map["quote_price_source_market"].value = None
    if value != "custom_api":
        cross_exchange_market_making_config_map["quote_price_source_custom_api"].value = None
    else:
        cross_exchange_market_making_config_map["quote_price_source_type"].value = None


def quote_price_source_market_prompt() -> str:
    external_market = cross_exchange_market_making_config_map.get("quote_price_source_exchange").value
    return f'Enter the quote token trading pair on {external_market} >>> '


def on_validated_quote_price_source_exchange(value: str):
    if value is None:
        cross_exchange_market_making_config_map["quote_price_source_exchange"].value = None


def validate_quote_price_source_market(value: str) -> Optional[str]:
    market = cross_exchange_market_making_config_map.get("quote_price_source_exchange").value
    return validate_market_trading_pair(market, value)


cross_exchange_market_making_config_map = {
    "strategy": ConfigVar(key="strategy",
                          prompt="",
                          default="cross_exchange_market_making"
                          ),
    "maker_market": ConfigVar(
        key="maker_market",
        prompt="Enter your maker exchange name >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=lambda value: required_exchanges.append(value),
    ),
    "taker_market": ConfigVar(
        key="taker_market",
        prompt="Enter your taker exchange name >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=taker_market_on_validated,
    ),
    "maker_market_trading_pair": ConfigVar(
        key="maker_market_trading_pair",
        prompt=maker_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_maker_market_trading_pair
    ),
    "taker_market_trading_pair": ConfigVar(
        key="taker_market_trading_pair",
        prompt=taker_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_taker_market_trading_pair
    ),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        validator=lambda v: validate_decimal(v, Decimal(-100), Decimal("100"), inclusive=True),
        type_str="decimal",
    ),
    "order_amount": ConfigVar(
        key="order_amount",
        prompt=order_amount_prompt,
        prompt_on_new=True,
        type_str="decimal",
        validator=validate_order_amount,
    ),
    "adjust_order_enabled": ConfigVar(
        key="adjust_order_enabled",
        prompt="Do you want to enable adjust order? (Yes/No) >>> ",
        default=True,
        type_str="bool",
        validator=validate_bool,
        required_if=lambda: False,
    ),
    "active_order_canceling": ConfigVar(
        key="active_order_canceling",
        prompt="Do you want to enable active order canceling? (Yes/No) >>> ",
        type_str="bool",
        default=True,
        required_if=lambda: False,
        validator=validate_bool,
    ),
    # Setting the default threshold to 0.05 when to active_order_canceling is disabled
    # prevent canceling orders after it has expired
    "cancel_order_threshold": ConfigVar(
        key="cancel_order_threshold",
        prompt="What is the threshold of profitability to cancel a trade? (Enter 1 to indicate 1%) >>> ",
        default=5,
        type_str="decimal",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, min_value=Decimal(-100), max_value=Decimal(100), inclusive=False),
    ),
    "limit_order_min_expiration": ConfigVar(
        key="limit_order_min_expiration",
        prompt="How often do you want limit orders to expire (in seconds)? >>> ",
        default=130.0,
        type_str="float",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, min_value=0, inclusive=False)
    ),
    "top_depth_tolerance": ConfigVar(
        key="top_depth_tolerance",
        prompt=top_depth_tolerance_prompt,
        default=0,
        type_str="decimal",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, min_value=0, inclusive=True)
    ),
    "anti_hysteresis_duration": ConfigVar(
        key="anti_hysteresis_duration",
        prompt="What is the minimum time interval you want limit orders to be adjusted? (in seconds) >>> ",
        default=60,
        type_str="float",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, min_value=0, inclusive=False)
    ),
    "order_size_taker_volume_factor": ConfigVar(
        key="order_size_taker_volume_factor",
        prompt="What percentage of hedge-able volume would you like to be traded on the taker market? "
               "(Enter 1 to indicate 1%) >>> ",
        default=25,
        type_str="decimal",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal(100), inclusive=False)
    ),
    "order_size_taker_balance_factor": ConfigVar(
        key="order_size_taker_balance_factor",
        prompt="What percentage of asset balance would you like to use for hedging trades on the taker market? "
               "(Enter 1 to indicate 1%) >>> ",
        default=Decimal("99.5"),
        type_str="decimal",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal(100), inclusive=False)
    ),
    "order_size_portfolio_ratio_limit": ConfigVar(
        key="order_size_portfolio_ratio_limit",
        prompt="What ratio of your total portfolio value would you like to trade on the maker and taker markets? "
               "Enter 50 for 50% >>> ",
        default=Decimal("16.67"),
        type_str="decimal",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal(100), inclusive=False)
    ),
    "base_price_source":
        ConfigVar(key="base_price_source",
                  prompt="Which base price source to use? (config_rate/external_market/custom_api) >>> ",
                  prompt_on_new=True,
                  type_str="str",
                  default="config_rate",
                  validator=validate_price_source,
                  on_validated=on_validate_base_price_source),
    "quote_price_source":
        ConfigVar(key="quote_price_source",
                  prompt="Which quote price source to use? (config_rate/external_market/custom_api) >>> ",
                  prompt_on_new=True,
                  type_str="str",
                  default="config_rate",
                  validator=validate_price_source,
                  on_validated=on_validate_quote_price_source),
    "taker_to_maker_base_conversion_rate": ConfigVar(
        key="taker_to_maker_base_conversion_rate",
        prompt="Enter conversion rate for taker base asset value to maker base asset value, e.g. "
               "if maker base asset is USD, taker is DAI and 1 USD is worth 1.25 DAI, "
               "the conversion rate is 0.8 (1 / 1.25) >>> ",
        prompt_on_new=True,
        required_if=lambda: cross_exchange_market_making_config_map.get("base_price_source").value == "config_rate",
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal("100"), inclusive=False),
        type_str="decimal"
    ),
    "taker_to_maker_quote_conversion_rate": ConfigVar(
        key="taker_to_maker_quote_conversion_rate",
        prompt="Enter conversion rate for taker quote asset value to maker quote asset value, e.g. "
               "if taker quote asset is USD, maker is DAI and 1 USD is worth 1.25 DAI, "
               "the conversion rate is 0.8 (1 / 1.25) >>> ",
        prompt_on_new=True,
        required_if=lambda: cross_exchange_market_making_config_map.get("quote_price_source").value == "config_rate",
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal("100"), inclusive=False),
        type_str="decimal"
    ),
    "base_price_source_exchange":
        ConfigVar(key="base_price_source_exchange",
                  prompt="Enter external base price source exchange name >>> ",
                  prompt_on_new=True,
                  required_if=lambda: cross_exchange_market_making_config_map.get("base_price_source").value == "external_market",
                  type_str="str",
                  validator=validate_price_source_exchange,
                  on_validated=on_validated_base_price_source_exchange),
    "base_price_source_market":
        ConfigVar(key="base_price_source_market",
                  prompt=base_price_source_market_prompt,
                  prompt_on_new=True,
                  required_if=lambda: cross_exchange_market_making_config_map.get("base_price_source").value == "external_market",
                  type_str="str",
                  validator=validate_base_price_source_market),
    "base_price_source_custom_api":
        ConfigVar(key="base_price_source_custom_api",
                  prompt="Enter base pricing API URL >>> ",
                  prompt_on_new=True,
                  required_if=lambda: cross_exchange_market_making_config_map.get("base_price_source").value == "custom_api",
                  type_str="str"),
    "base_price_source_type":
        ConfigVar(key="base_price_source_type",
                  prompt="Which base price type to use? (mid_price/last_price/best_bid/best_ask) >>> ",
                  type_str="str",
                  required_if=lambda: cross_exchange_market_making_config_map.get("base_price_source").value != "custom_api",
                  default="mid_price",
                  validator=lambda s: None if s in {"mid_price",
                                                    "last_price",
                                                    "best_bid",
                                                    "best_ask"} else
                  "Invalid price type."),
    "quote_price_source_exchange":
        ConfigVar(key="quote_price_source_exchange",
                  prompt="Enter quote external price source exchange name >>> ",
                  prompt_on_new=True,
                  required_if=lambda: cross_exchange_market_making_config_map.get("quote_price_source").value == "external_market",
                  type_str="str",
                  validator=validate_price_source_exchange,
                  on_validated=on_validated_quote_price_source_exchange),
    "quote_price_source_market":
        ConfigVar(key="quote_price_source_market",
                  prompt=quote_price_source_market_prompt,
                  prompt_on_new=True,
                  required_if=lambda: cross_exchange_market_making_config_map.get("quote_price_source").value == "external_market",
                  type_str="str",
                  validator=validate_quote_price_source_market),
    "quote_price_source_custom_api":
        ConfigVar(key="quote_price_source_custom_api",
                  prompt="Enter quote pricing API URL >>> ",
                  prompt_on_new=True,
                  required_if=lambda: cross_exchange_market_making_config_map.get("quote_price_source").value == "custom_api",
                  type_str="str"),
    "quote_price_source_type":
        ConfigVar(key="quote_price_source_type",
                  prompt="Which quote price type to use? (mid_price/last_price/best_bid/best_ask) >>> ",
                  type_str="str",
                  required_if=lambda: cross_exchange_market_making_config_map.get("quote_price_source").value != "custom_api",
                  default="mid_price",
                  validator=lambda s: None if s in {"mid_price",
                                                    "last_price",
                                                    "best_bid",
                                                    "best_ask"} else
                  "Invalid price type."),
}
