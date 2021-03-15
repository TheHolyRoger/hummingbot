#!/usr/bin/env python
import sys
import asyncio
import unittest
import aiohttp
import conf
import logging
from async_timeout import timeout
from os.path import join, realpath
from typing import Dict, Any
from hummingbot.connector.exchange.altmarkets.altmarkets_auth import AltmarketsAuth
from hummingbot.connector.exchange.altmarkets.altmarkets_websocket import AltmarketsWebsocket
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.exchange.altmarkets.altmarkets_constants import Constants

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.altmarkets_api_key
        secret_key = conf.altmarkets_secret_key
        cls.auth = AltmarketsAuth(api_key, secret_key)

    async def rest_auth(self) -> Dict[Any, Any]:
        endpoint = Constants.ENDPOINT['USER_BALANCES']
        headers = self.auth.get_headers()
        http_client = aiohttp.ClientSession()
        response = await http_client.get(f"{Constants.REST_URL}/{endpoint}", headers=headers)
        await http_client.close()
        return await response.json()

    async def ws_auth(self) -> Dict[Any, Any]:
        ws = AltmarketsWebsocket(self.auth)
        await ws.connect()
        async with timeout(30):
            await ws.subscribe(Constants.WS_SUB["USER_ORDERS_TRADES"])
            async for response in ws.on_message():
                if ws.is_subscribed:
                    return True
        return False

    def test_rest_auth(self):
        result = self.ev_loop.run_until_complete(self.rest_auth())
        if len(result) == 0 or "currency" not in result[0].keys():
            print(f"Unexpected response for API call: {result}")
        assert "currency" in result[0].keys()

    def test_ws_auth(self):
        try:
            subscribed = self.ev_loop.run_until_complete(self.ws_auth())
            no_errors = True
        except Exception:
            no_errors = False
        assert no_errors is True
        assert subscribed is True
