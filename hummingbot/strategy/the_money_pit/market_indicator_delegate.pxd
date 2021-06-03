cdef class MarketIndicatorDelegate:
    cdef object _market_indicator_feed
    cdef object c_trend_is_up(self)
    cdef object c_trend_is_down(self)
