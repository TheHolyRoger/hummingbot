#!/usr/bin/env python

import asyncio
import logging
from typing import (
    Any,
    AsyncIterable,
    Dict,
    Optional,
    List,
)
import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.connector.exchange.altmarkets.altmarkets_constants import Constants
from hummingbot.connector.exchange.altmarkets.altmarkets_auth import AltmarketsAuth


class AltmarketsAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _lausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._lausds_logger is None:
            cls._lausds_logger = logging.getLogger(__name__)
        return cls._lausds_logger

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

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                auth_headers = self._altmarkets_auth.get_headers()
                async with websockets.connect(Constants.EXCHANGE_WS_AUTH_URI, extra_headers=auth_headers) as ws:
                    ws: websockets.WebSocketClientProtocol = ws

                    # # We don't need an auth request since token is sent in headers.
                    # auth_request: Dict[str, Any] = {
                    #     "event": Constants.WS_AUTH_REQUEST_EVENT,
                    #     "data": "empty"
                    # }
                    # await ws.send(ujson.dumps(auth_request))

                    for trading_pair in self._trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "event": Constants.WS_PUSHER_SUBSCRIBE_EVENT,
                            "streams": Constants.WS_USER_SUBSCRIBE_STREAMS
                        }
                        await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        diff_msg: Dict[str, Any] = ujson.loads(raw_msg)
                        # Debug printing.
                        # self.logger().info(f"PrvWS msg: {diff_msg}")
                        if "ping" in raw_msg:
                            await ws.send(f'{{"op":"pong","timestamp": {str(diff_msg["ping"])}}}')
                        elif "subscribed" in raw_msg:
                            pass
                        elif "order" in raw_msg or "trade" in raw_msg:
                            output.put_nowait(diff_msg)
                        else:
                            # Debug log output for pub WS messages
                            self.logger().info(f"Unrecognized message received from Altmarkets websocket: {diff_msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with Altmarkets WebSocket connection. "
                                    "Retrying after 30 seconds...", exc_info=True)
                await asyncio.sleep(30.0)

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=Constants.MESSAGE_TIMEOUT)
                    self._last_recv_time = time.time()
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await ws.ping()
                        self._last_recv_time = time.time()
                        await asyncio.wait_for(pong_waiter, timeout=Constants.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()
