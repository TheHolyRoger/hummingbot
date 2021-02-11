# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t

cdef class RandomLoopTrade(StrategyBase):
    cdef:
        dict _market_infos
        bint _all_markets_ready
        bint _place_orders
        bint _is_buy
        bint _ping_pong_enabled
        str _order_type

        double _cancel_order_wait_time
        double _status_report_interval
        double _last_timestamp
        double _start_timestamp
        double _time_delay

        bint _order_pricetype_random
        bint _order_pricetype_spread
        object _order_price
        object _order_price_min
        object _order_price_max
        object _order_amount
        object _order_amount_min
        object _order_amount_max
        object _order_spread
        object _order_spread_min
        object _order_spread_max
        object _order_spread_pricetype

        dict _tracked_orders
        dict _time_to_cancel
        dict _order_id_to_market_info
        dict _in_flight_cancels

        int64_t _logging_options

    cdef c_process_market(self, object market_info)
    cdef c_place_orders(self, object market_info)
    cdef c_has_enough_balance(self, object market_info)
    cdef c_process_market(self, object market_info)
