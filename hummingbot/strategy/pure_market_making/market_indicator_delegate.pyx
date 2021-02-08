from hummingbot.data_feed.market_indicator_data_feed import MarketIndicatorDataFeed, NetworkStatus

cdef class MarketIndicatorDelegate:
    def __init__(self, api_url: str, api_key: str, update_interval: float = None):
        super().__init__()
        update_interval = 30.0 if (update_interval is None or update_interval < 1) else update_interval
        self._market_indicator_feed = MarketIndicatorDataFeed(api_url=api_url,
                                                              api_key=api_key,
                                                              update_interval=update_interval)
        self._market_indicator_feed.start()

    def trend_is_up(self) -> bool:
        return self.c_trend_is_up()

    def trend_is_down(self) -> bool:
        return self.c_trend_is_down()

    cdef object c_trend_is_up(self):
        return self._market_indicator_feed.trend_is_up()

    cdef object c_trend_is_down(self):
        return self._market_indicator_feed.trend_is_down()

    @property
    def ready(self) -> bool:
        return self._market_indicator_feed.network_status == NetworkStatus.CONNECTED

    @property
    def market_indicator_feed(self) -> MarketIndicatorDataFeed:
        return self._market_indicator_feed
