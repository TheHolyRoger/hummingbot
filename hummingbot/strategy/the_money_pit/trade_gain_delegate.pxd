from hummingbot.strategy.the_money_pit.the_money_pit import TheMoneyPitStrategy
from hummingbot.strategy.the_money_pit.the_money_pit cimport TheMoneyPitStrategy


cdef class TradeGainDelegate:
    cdef:
        TheMoneyPitStrategy _strat
        dict _filtered_trades
        int _recent_buys
        int _recent_buys_cf
        int _recent_sells
        int _recent_sells_cf
        object _highest_buy_price
        object _lowest_buy_price
        object _highest_sell_price
        object _lowest_sell_price

    cdef c_refresh_filtered_trades(self)
    cdef c_populate_trade_vars(self)
    cdef c_check_inventory_ratio(self, double base_ratio, double quote_ratio)
    cdef c_set_buy_sell_thresholds(self)
    cdef c_set_same_side_thresholds(self)
    cdef bint c_should_cancel_buys(self)
    cdef bint c_should_cancel_sells(self)
