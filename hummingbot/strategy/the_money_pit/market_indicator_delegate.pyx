from decimal import Decimal
from hummingbot.data_feed.market_indicator_data_feed import MarketIndicatorDataFeed, NetworkStatus


cdef class MarketIndicatorDelegate:
    def __init__(self,
                 api_url: str,
                 api_key: str,
                 update_interval: float = None,
                 check_expiry: bool = False,
                 expire_time: int = None,
                 use_indicator_time: bool = False):
        super().__init__()
        self._market_indicator_feed = MarketIndicatorDataFeed(api_url=api_url,
                                                              api_key=api_key,
                                                              update_interval=update_interval,
                                                              check_expiry=check_expiry,
                                                              expire_time=expire_time,
                                                              use_indicator_time=use_indicator_time)
        self._market_indicator_feed.start()

    def trend_is_up(self) -> bool:
        return self.c_trend_is_up()

    def trend_is_down(self) -> bool:
        return self.c_trend_is_down()

    @property
    def last_timestamp(self) -> int:
        return self._market_indicator_feed.last_timestamp

    @property
    def signal_price_up(self) -> Decimal:
        return self._market_indicator_feed.last_price_up

    @property
    def signal_price_down(self) -> Decimal:
        return self._market_indicator_feed.last_price_down

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
