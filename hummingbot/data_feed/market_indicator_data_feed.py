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

    def __init__(self, api_url, api_key: str = "", update_interval: float = 30.0):
        super().__init__()
        self._ready_event = asyncio.Event()
        self._shared_client: Optional[aiohttp.ClientSession] = None
        self._api_url = api_url
        self._api_name = urlparse(api_url).netloc
        self._api_auth_params = {'api_key': api_key}
        self._check_network_interval = 120.0
        self._ev_loop = asyncio.get_event_loop()
        self._price: Decimal = 0
        self._update_interval: float = update_interval
        self._fetch_trend_task: Optional[asyncio.Task] = None
        self._market_trend = None
        self._last_check = 0
        self._check_expiry = 300  # Seconds

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
        return (True if self._last_check > int(time.time() - self._check_expiry) and self._market_trend is True
                else False)

    def trend_is_down(self) -> bool:
        return (True if self._last_check > int(time.time() - self._check_expiry) and self._market_trend is False
                else False)

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
        client = self._http_client()
        async with client.request("GET",
                                  self._api_url,
                                  params=self._api_auth_params) as resp:
            if resp.status != 200:
                resp_text = await resp.text()
                raise Exception(f"Custom API Feed {self.name} server error: {resp_text}")
            rjson = await resp.json()
            self._market_trend = True if rjson['market_indicator'] == 'up' else False
            self._last_check = int(time.time())
        self._ready_event.set()

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
