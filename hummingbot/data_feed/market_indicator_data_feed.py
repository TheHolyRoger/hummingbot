import asyncio
import aiohttp
import logging
import time
from typing import Optional
from hummingbot.core.network_base import NetworkBase, NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future
from decimal import Decimal
from urllib.parse import urlparse


class MarketIndicatorDataFeed(NetworkBase):
    cadf_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.cadf_logger is None:
            cls.cadf_logger = logging.getLogger(__name__)
        return cls.cadf_logger

    def __init__(self,
                 api_url,
                 api_key: str = "",
                 update_interval: float = 30.0,
                 check_expiry: bool = False,
                 expire_time: int = 300,
                 use_indicator_time: bool = False):
        super().__init__()
        self._ready_event = asyncio.Event()
        self._shared_client: Optional[aiohttp.ClientSession] = None
        self._api_url = api_url
        self._api_name = urlparse(api_url).netloc
        self._api_auth_params = {'api_key': api_key}
        self._check_network_interval = 120.0
        self._ev_loop = asyncio.get_event_loop()
        self._price: Decimal = 0
        self._update_interval = 30.0 if (update_interval is None or update_interval < 1) else update_interval
        self._fetch_trend_task: Optional[asyncio.Task] = None
        self._market_trend = None
        self._last_check = 0
        self._last_price_up = Decimal('0')
        self._last_price_down = Decimal('0')
        self._check_expiry = check_expiry
        self._expire_time = 300 if (expire_time is None or expire_time < 1) else (expire_time * 60)  # Seconds
        self._use_indicator_time = use_indicator_time

    @property
    def name(self):
        return self._api_name

    @property
    def health_check_endpoint(self):
        return self._api_url

    def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def check_network(self) -> NetworkStatus:
        client = self._http_client()
        async with client.request("GET",
                                  self.health_check_endpoint,
                                  params=self._api_auth_params) as resp:
            status_text = await resp.text()
            if resp.status != 200:
                raise Exception(f"Market Indicator Feed {self.name} server error: {status_text}")
        return NetworkStatus.CONNECTED

    def trend_is_up(self) -> bool:
        if not self._check_expiry or self._last_check > int(time.time() - self._expire_time):
            if self._market_trend is True:
                return True
            return False
        return None

    def trend_is_down(self) -> bool:
        if not self._check_expiry or self._last_check > int(time.time() - self._expire_time):
            if self._market_trend is False:
                return True
            return False
        return None

    @property
    def last_timestamp(self):
        return self._last_check

    @property
    def last_price_up(self):
        return self._last_price_up

    @property
    def last_price_down(self):
        return self._last_price_down

    async def fetch_trend_loop(self):
        while True:
            try:
                await self.fetch_trend()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(f"Error fetching a new price from {self._api_url}.", exc_info=True,
                                      app_warning_msg="Couldn't fetch newest price from CustomAPI. "
                                                      "Check network connection.")

            await asyncio.sleep(self._update_interval)

    async def fetch_trend(self):
        try:
            rjson = {}
            client = self._http_client()
            async with client.request("GET",
                                      self._api_url,
                                      params=self._api_auth_params) as resp:
                if resp.status != 200:
                    resp_text = await resp.text()
                    raise Exception(f"Custom API Feed {self.name} server error: {resp_text}")
                rjson = await resp.json()
            respKeys = list(rjson.keys())
            if 'market_indicator' in respKeys:
                if rjson['market_indicator'] == 'up':
                    self._market_trend = True
                    self._last_price_up = Decimal(str(rjson['price']))
                    self._last_price_down = Decimal('0')
                else:
                    self._market_trend = False
                    self._last_price_up = Decimal('0')
                    self._last_price_down = Decimal(str(rjson['price']))
                time_key = None
                if "timestamp" in respKeys and self._use_indicator_time:
                    time_key = "timestamp"
                elif "time" in respKeys and self._use_indicator_time:
                    time_key = "time"
                self._last_check = int(time.time())
                if time_key is not None:
                    try:
                        self._last_check = int(rjson[time_key])
                    except Exception:
                        pass
                self._ready_event.set()
        except Exception as e:
            raise Exception(f"Custom API Feed {self.name} server error: {e}")

    async def start_network(self):
        await self.stop_network()
        self._fetch_trend_task = safe_ensure_future(self.fetch_trend_loop())

    async def stop_network(self):
        if self._fetch_trend_task is not None:
            self._fetch_trend_task.cancel()
            self._fetch_trend_task = None

    def start(self):
        NetworkBase.start(self)

    def stop(self):
        NetworkBase.stop(self)
