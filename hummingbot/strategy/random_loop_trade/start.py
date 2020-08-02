from typing import (
    List,
    Tuple,
)
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.random_loop_trade import RandomLoopTrade
from hummingbot.strategy.random_loop_trade.random_loop_trade_config_map import random_loop_trade_config_map


def start(self):
    try:
        order_amount = random_loop_trade_config_map.get("order_amount").value
        order_amount_min = random_loop_trade_config_map.get("order_amount_min").value
        order_amount_max = random_loop_trade_config_map.get("order_amount_max").value
        order_type = random_loop_trade_config_map.get("order_type").value
        is_buy = random_loop_trade_config_map.get("is_buy").value
        ping_pong_enabled = random_loop_trade_config_map.get("ping_pong_enabled").value
        time_delay = random_loop_trade_config_map.get("time_delay").value
        market = random_loop_trade_config_map.get("market").value.lower()
        raw_market_trading_pair = random_loop_trade_config_map.get("market_trading_pair_tuple").value
        order_price = None
        order_price_min = None
        order_price_max = None
        cancel_order_wait_time = None

        if order_type == "limit":
            order_price = random_loop_trade_config_map.get("order_price").value
            order_price_min = random_loop_trade_config_map.get("order_price_min").value
            order_price_max = random_loop_trade_config_map.get("order_price_max").value
            cancel_order_wait_time = random_loop_trade_config_map.get("cancel_order_wait_time").value

        try:
            trading_pair: str = raw_market_trading_pair
            assets: Tuple[str, str] = self._initialize_market_assets(market, [trading_pair])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(market, [trading_pair])]

        self._initialize_wallet(token_trading_pairs=list(set(assets)))
        self._initialize_markets(market_names)
        self.assets = set(assets)

        maker_data = [self.markets[market], trading_pair] + list(assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        strategy_logging_options = RandomLoopTrade.OPTION_LOG_ALL

        self.strategy = RandomLoopTrade(market_infos=[MarketTradingPairTuple(*maker_data)],
                                        order_type=order_type,
                                        order_price=order_price if order_price else None,
                                        order_price_min=order_price_min if order_price_min else None,
                                        order_price_max=order_price_max if order_price_max else None,
                                        cancel_order_wait_time=cancel_order_wait_time,
                                        is_buy=is_buy,
                                        ping_pong_enabled=ping_pong_enabled,
                                        time_delay=time_delay,
                                        order_amount=order_amount,
                                        order_amount_min=order_amount_min,
                                        order_amount_max=order_amount_max,
                                        logging_options=strategy_logging_options)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
