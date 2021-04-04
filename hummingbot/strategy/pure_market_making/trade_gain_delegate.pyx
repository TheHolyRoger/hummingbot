import time
from decimal import Decimal
from hummingbot.core.data_type.trade import Trade
from hummingbot.core.event.events import TradeType
from hummingbot.strategy.pure_market_making.pure_market_making import PureMarketMakingStrategy


s_decimal_zero = Decimal(0)


cdef class TradeGainDelegate():
    def __init__(self,
                 strategy: PureMarketMakingStrategy = None):
        self._strat: PureMarketMakingStrategy = strategy
        self._filtered_trades = {}
        self._recent_buys = 0
        self._recent_buys_cf = 0
        self._recent_sells = 0
        self._recent_sells_cf = 0
        self._highest_buy_price = s_decimal_zero
        self._lowest_buy_price = s_decimal_zero
        self._highest_sell_price = s_decimal_zero
        self._lowest_sell_price = s_decimal_zero

    # Get Filtered trades list
    cdef c_refresh_filtered_trades(self):
        cdef:
            int accept_time_buys = int(time.time() - int((self._strat.trade_gain_hours_buys * (60 * 60))))
            int accept_time_sells = int(time.time() - int((self._strat.trade_gain_hours_sells * (60 * 60))))
            list trades = self._strat.trades
            list trades_history = self._strat.trades_history
        # Order by TS
        all_trades = trades + trades_history if len(trades) < 1000 else trades
        for trade in all_trades:
            trade_ts = int(trade.timestamp) if type(trade) == Trade else int(trade.timestamp / 1000)
            trade_side = trade.side.name if type(trade) == Trade else trade.trade_type
            if trade_side == TradeType.SELL.name:
                if trade_ts > accept_time_sells:
                    self._filtered_trades[trade_ts] = trade
            if trade_side == TradeType.BUY.name:
                if trade_ts > accept_time_buys:
                    self._filtered_trades[trade_ts] = trade

    # Populate Trade Vars
    cdef c_populate_trade_vars(self):
        cdef:
            int accept_time_buys = int(time.time() - int((self._strat.trade_gain_hours_buys * (60 * 60))))
            int accept_time_sells = int(time.time() - int((self._strat.trade_gain_hours_sells * (60 * 60))))
            int accept_time_careful = int(time.time() - int((self._strat.trade_gain_careful_hours * (60 * 60))))
            int recent_trades_limit = self._strat.trade_gain_trades

        # Filter and find trade vals
        for trade_ts in sorted(list(self._filtered_trades.keys()), reverse=True):
            trade = self._filtered_trades[trade_ts]
            trade_side = trade.side.name if type(trade) == Trade else trade.trade_type
            trade_price = Decimal(str(trade.price))
            if trade_ts > accept_time_careful:
                if trade_side == TradeType.SELL.name:
                    self._recent_sells_cf += 1
                elif trade_side == TradeType.BUY.name:
                    self._recent_buys_cf += 1
            if trade_side == TradeType.SELL.name:
                if trade_ts > accept_time_sells:
                    self._recent_sells += 1
                    if self._recent_sells <= recent_trades_limit:
                        if self._lowest_sell_price == s_decimal_zero or trade_price < self._lowest_sell_price:
                            self._lowest_sell_price = trade_price
                        if self._highest_sell_price == s_decimal_zero or trade_price > self._highest_sell_price:
                            self._highest_sell_price = trade_price
            elif trade_side == TradeType.BUY.name:
                if trade_ts > accept_time_buys:
                    self._recent_buys += 1
                    if self._recent_buys <= recent_trades_limit:
                        if self._lowest_buy_price == s_decimal_zero or trade_price < self._lowest_buy_price:
                            self._lowest_buy_price = trade_price
                        if self._highest_buy_price == s_decimal_zero or trade_price > self._highest_buy_price:
                            self._highest_buy_price = trade_price

    cdef c_check_inventory_ratio(self, double base_ratio, double quote_ratio):
        if quote_ratio >= 0.986:
            self._lowest_sell_price = s_decimal_zero

    cdef c_set_buy_sell_thresholds(self):
        cdef:
            object buy_margin = self._strat.trade_gain_allowed_loss + Decimal('1')
            object sell_margin = Decimal('1') - self._strat.trade_gain_allowed_loss

        if not self._strat._trade_gain_dump_it or self._strat.trade_gain_profit_buyin == s_decimal_zero:
            if self._lowest_sell_price != s_decimal_zero:
                self._strat.trade_gain_pricethresh_buy = Decimal(self._lowest_sell_price * buy_margin)
                self._strat.trade_gain_initial_max_buy = s_decimal_zero
            elif self._strat.trade_gain_initial_max_buy > s_decimal_zero:
                self._strat.trade_gain_pricethresh_buy = self._strat.trade_gain_initial_max_buy

        if self._highest_buy_price != s_decimal_zero:
            self._strat.trade_gain_pricethresh_sell = Decimal(self._highest_buy_price * sell_margin)
            self._strat.trade_gain_initial_min_sell = s_decimal_zero
        elif self._strat.trade_gain_initial_min_sell > s_decimal_zero:
            self._strat.trade_gain_pricethresh_sell = self._strat.trade_gain_initial_min_sell

    cdef c_set_same_side_thresholds(self):
        cdef:
            object buy_margin_on_self = self._strat.trade_gain_ownside_allowedloss + Decimal('1')
            object sell_margin_on_self = Decimal('1') - self._strat.trade_gain_ownside_allowedloss

        if self._strat.trade_gain_ownside_enabled:
            chk_ownside_buy = ((not self._strat._trade_gain_dump_it or
                                self._strat.trade_gain_profit_buyin == s_decimal_zero) and
                               self._lowest_buy_price != s_decimal_zero and
                               self._strat.trade_gain_initial_max_buy == s_decimal_zero and
                               (self._lowest_sell_price == s_decimal_zero or
                                (self._lowest_buy_price * buy_margin_on_self) < self._strat.trade_gain_pricethresh_buy))
            if chk_ownside_buy:
                self._strat.trade_gain_pricethresh_buy = Decimal(self._lowest_buy_price * buy_margin_on_self)

            chk_ownside_sell = (self._highest_sell_price != s_decimal_zero and
                                self._strat.trade_gain_initial_min_sell == s_decimal_zero and
                                (self._highest_buy_price == s_decimal_zero or
                                 (self._highest_sell_price * sell_margin_on_self) > self._strat.trade_gain_pricethresh_sell))
            if chk_ownside_sell:
                self._strat.trade_gain_pricethresh_sell = Decimal(self._highest_sell_price * sell_margin_on_self)

    cdef bint c_should_cancel_buys(self):
        return (self._strat._trade_gain_dump_it or (self._strat.trade_gain_careful_enabled and
                                                    self._recent_sells_cf < 1 and
                                                    self._recent_buys_cf >= self._strat.trade_gain_careful_limittrades))

    cdef bint c_should_cancel_sells(self):
        return (self._strat.trade_gain_careful_enabled and
                self._recent_buys_cf < 1 and
                self._recent_sells_cf >= self._strat.trade_gain_careful_limittrades)
