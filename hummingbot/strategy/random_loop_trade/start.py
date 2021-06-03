from typing import (
    List,
    Tuple,
)
from decimal import Decimal
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
        cancel_order_wait_time = random_loop_trade_config_map.get("cancel_order_wait_time").value

        order_pricetype_random = random_loop_trade_config_map.get("order_pricetype_random").value
        order_pricetype_spread = random_loop_trade_config_map.get("order_pricetype_spread").value
        order_price = None
        order_price_min = None
        order_price_max = None
        order_spread = None
        order_spread_min = None
        order_spread_max = None
        order_spread_pricetype = random_loop_trade_config_map.get("order_spread_pricetype").value

        if order_type == "limit":
            if not order_pricetype_spread:
                order_price = random_loop_trade_config_map.get("order_price").value
                if order_pricetype_random:
                    order_price_min = random_loop_trade_config_map.get("order_price_min").value
                    order_price_max = random_loop_trade_config_map.get("order_price_max").value
            else:
                order_spread = random_loop_trade_config_map.get("order_spread").value

                if order_pricetype_random:
                    order_spread_min = random_loop_trade_config_map.get("order_spread_min").value / Decimal('100')
                    order_spread_max = random_loop_trade_config_map.get("order_spread_max").value / Decimal('100')

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
                                        cancel_order_wait_time=cancel_order_wait_time,
                                        order_pricetype_random=order_pricetype_random,
                                        order_pricetype_spread=order_pricetype_spread,
                                        order_price=order_price,
                                        order_price_min=order_price_min,
                                        order_price_max=order_price_max,
                                        order_spread=order_spread,
                                        order_spread_min=order_spread_min,
                                        order_spread_max=order_spread_max,
                                        order_spread_pricetype=order_spread_pricetype,
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
