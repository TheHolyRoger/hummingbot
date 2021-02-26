from typing import (
    List,
    Tuple
)
from decimal import Decimal
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.paper_trade import create_paper_trade_market
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_pair import CrossExchangeMarketPair
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making import (
    CrossExchangeMarketMakingStrategy,
    AssetPriceDelegate,
    OrderBookAssetPriceDelegate,
    APIAssetPriceDelegate,
)
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making_config_map import \
    cross_exchange_market_making_config_map as xemm_map


def start(self):
    maker_market = xemm_map.get("maker_market").value.lower()
    taker_market = xemm_map.get("taker_market").value.lower()
    raw_maker_trading_pair = xemm_map.get("maker_market_trading_pair").value
    raw_taker_trading_pair = xemm_map.get("taker_market_trading_pair").value
    min_profitability = xemm_map.get("min_profitability").value / Decimal("100")
    order_amount = xemm_map.get("order_amount").value
    strategy_report_interval = global_config_map.get("strategy_report_interval").value
    limit_order_min_expiration = xemm_map.get("limit_order_min_expiration").value
    cancel_order_threshold = xemm_map.get("cancel_order_threshold").value / Decimal("100")
    active_order_canceling = xemm_map.get("active_order_canceling").value
    adjust_order_enabled = xemm_map.get("adjust_order_enabled").value
    top_depth_tolerance = xemm_map.get("top_depth_tolerance").value
    order_size_taker_volume_factor = xemm_map.get("order_size_taker_volume_factor").value / Decimal("100")
    order_size_taker_balance_factor = xemm_map.get("order_size_taker_balance_factor").value / Decimal("100")
    order_size_portfolio_ratio_limit = xemm_map.get("order_size_portfolio_ratio_limit").value / Decimal("100")
    anti_hysteresis_duration = xemm_map.get("anti_hysteresis_duration").value
    taker_to_maker_base_conversion_rate = xemm_map.get("taker_to_maker_base_conversion_rate").value
    taker_to_maker_quote_conversion_rate = xemm_map.get("taker_to_maker_quote_conversion_rate").value
    price_source_types = {
        'base': xemm_map.get("base_price_source_type").value,
        'quote': xemm_map.get("quote_price_source_type").value,
    }
    price_sources = {
        'base': xemm_map.get("base_price_source").value,
        'quote': xemm_map.get("quote_price_source").value,
    }
    price_source_markets = {
        'base': xemm_map.get("base_price_source_market").value,
        'quote': xemm_map.get("quote_price_source_market").value,
    }
    price_source_exchanges = {
        'base': xemm_map.get("base_price_source_exchange").value,
        'quote': xemm_map.get("quote_price_source_exchange").value,
    }
    price_source_custom_apis = {
        'base': xemm_map.get("base_price_source_custom_api").value,
        'quote': xemm_map.get("quote_price_source_custom_api").value,
    }

    # check if top depth tolerance is a list or if trade size override exists
    if isinstance(top_depth_tolerance, list) or "trade_size_override" in xemm_map:
        self._notify("Current config is not compatible with cross exchange market making strategy. Please reconfigure")
        return

    try:
        maker_trading_pair: str = raw_maker_trading_pair
        taker_trading_pair: str = raw_taker_trading_pair
        maker_assets: Tuple[str, str] = self._initialize_market_assets(maker_market, [maker_trading_pair])[0]
        taker_assets: Tuple[str, str] = self._initialize_market_assets(taker_market, [taker_trading_pair])[0]
    except ValueError as e:
        self._notify(str(e))
        return

    market_names: List[Tuple[str, List[str]]] = [
        (maker_market, [maker_trading_pair]),
        (taker_market, [taker_trading_pair]),
    ]

    # Add Asset Price Delegate markets to main markets if already using the exchange.
    for asset_type in ['base', 'quote']:
        if price_sources[asset_type] == "external_market":
            ext_exchange: str = price_source_exchanges[asset_type]
            if ext_exchange in [maker_market, taker_market]:
                asset_pair: str = price_source_markets[asset_type]
                market_names.append((ext_exchange, [asset_pair]))

    self._initialize_wallet(token_trading_pairs=list(set(maker_assets + taker_assets)))
    self._initialize_markets(market_names)
    self.assets = set(maker_assets + taker_assets)
    maker_data = [self.markets[maker_market], maker_trading_pair] + list(maker_assets)
    taker_data = [self.markets[taker_market], taker_trading_pair] + list(taker_assets)
    maker_market_trading_pair_tuple = MarketTradingPairTuple(*maker_data)
    taker_market_trading_pair_tuple = MarketTradingPairTuple(*taker_data)
    self.market_trading_pair_tuples = [maker_market_trading_pair_tuple, taker_market_trading_pair_tuple]
    self.market_pair = CrossExchangeMarketPair(maker=maker_market_trading_pair_tuple, taker=taker_market_trading_pair_tuple)

    # Asset Price Feed Delegates
    price_delegates = {'base': None, 'quote': None}
    shared_ext_mkt = None
    # Initialize price delegates as needed for defined price sources.
    for asset_type in ['base', 'quote']:
        price_source: str = price_sources[asset_type]
        if price_source == "external_market":
            # For price feeds using other connectors
            ext_exchange: str = price_source_exchanges[asset_type]
            asset_pair: str = price_source_markets[asset_type]
            if ext_exchange in list(self.markets.keys()):
                # Use existing market if Exchange is already in markets
                ext_market = self.markets[ext_exchange]
            else:
                # Create markets otherwise
                UseSharedSource = (price_sources['quote'] == price_sources['base'] and
                                   price_source_exchanges['quote'] == price_source_exchanges['base'])
                # Use shared paper trade market if both price feeds are on the same exchange.
                if UseSharedSource and shared_ext_mkt is None and asset_type == 'base':
                    # Create Shared paper trade if not existing
                    shared_ext_mkt = create_paper_trade_market(price_source_exchanges['base'],
                                                               [price_source_markets['base'], price_source_markets['quote']])
                ext_market = shared_ext_mkt if UseSharedSource else create_paper_trade_market(ext_exchange, [asset_pair])
                if ext_exchange not in list(self.markets.keys()):
                    self.markets[ext_exchange]: ExchangeBase = ext_market
            price_delegates[asset_type]: AssetPriceDelegate = OrderBookAssetPriceDelegate(ext_market, asset_pair)
        elif price_source == "custom_api":
            # For price feeds using custom APIs
            custom_api: str = price_source_custom_apis[asset_type]
            price_delegates[asset_type]: AssetPriceDelegate = APIAssetPriceDelegate(custom_api)

    strategy_logging_options = (
        CrossExchangeMarketMakingStrategy.OPTION_LOG_CREATE_ORDER
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_ADJUST_ORDER
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_MAKER_ORDER_FILLED
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_REMOVING_ORDER
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_STATUS_REPORT
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_MAKER_ORDER_HEDGED
    )
    self.strategy = CrossExchangeMarketMakingStrategy(
        market_pairs=[self.market_pair],
        min_profitability=min_profitability,
        status_report_interval=strategy_report_interval,
        logging_options=strategy_logging_options,
        order_amount=order_amount,
        limit_order_min_expiration=limit_order_min_expiration,
        cancel_order_threshold=cancel_order_threshold,
        active_order_canceling=active_order_canceling,
        adjust_order_enabled=adjust_order_enabled,
        top_depth_tolerance=top_depth_tolerance,
        order_size_taker_volume_factor=order_size_taker_volume_factor,
        order_size_taker_balance_factor=order_size_taker_balance_factor,
        order_size_portfolio_ratio_limit=order_size_portfolio_ratio_limit,
        anti_hysteresis_duration=anti_hysteresis_duration,
        taker_to_maker_base_conversion_rate=taker_to_maker_base_conversion_rate,
        taker_to_maker_quote_conversion_rate=taker_to_maker_quote_conversion_rate,
        base_asset_price_delegate=price_delegates['base'],
        quote_asset_price_delegate=price_delegates['quote'],
        base_price_source_type=price_source_types['base'],
        quote_price_source_type=price_source_types['quote'],
        hb_app_notification=True,
    )
