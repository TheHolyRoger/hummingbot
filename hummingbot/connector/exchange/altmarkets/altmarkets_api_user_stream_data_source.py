#!/usr/bin/env python

import time
import asyncio
import logging
from typing import (
    Any,
    AsyncIterable,
    List,
    Optional,
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from .altmarkets_constants import Constants
from .altmarkets_auth import AltmarketsAuth
from .altmarkets_websocket import AltmarketsWebsocket


class AltmarketsAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, altmarkets_auth: AltmarketsAuth, trading_pairs: Optional[List[str]] = []):
        self._altmarkets_auth: AltmarketsAuth = altmarkets_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _listen_to_orders_trades_balances(self) -> AsyncIterable[Any]:
        """
        Subscribe to active orders via web socket
        """

        try:
            ws = AltmarketsWebsocket(self._altmarkets_auth)

            await ws.connect()

            await ws.subscribe(Constants.WS_SUB["USER_ORDERS_TRADES"])

            async for msg in ws.on_message():
                self._last_recv_time = time.time()
                if msg is not None:
                    yield msg

        except Exception as e:
            raise e
        finally:
            await ws.disconnect()
            await asyncio.sleep(5)

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue) -> AsyncIterable[Any]:
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """

        while True:
            try:
                async for msg in self._listen_to_orders_trades_balances():
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    f"Unexpected error with {Constants.EXCHANGE_NAME} WebSocket connection. "
                    "Retrying after 30 seconds...", exc_info=True)
                await asyncio.sleep(30.0)