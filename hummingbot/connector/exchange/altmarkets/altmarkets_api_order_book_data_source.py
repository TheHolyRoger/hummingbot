#!/usr/bin/env python

import aiohttp
import asyncio
import json
import logging
import pandas as pd
import time
from decimal import Decimal
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.altmarkets.altmarkets_order_book import AltmarketsOrderBook
from hummingbot.connector.exchange.altmarkets.altmarkets_constants import Constants
from hummingbot.connector.exchange.altmarkets.altmarkets_utils import (
    convert_to_exchange_trading_pair,
    generic_api_request,
)


class AltmarketsAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _haobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._haobds_logger is None:
            cls._haobds_logger = logging.getLogger(__name__)
        return cls._haobds_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, Decimal]:
        results = dict()
        # Altmarkets rate limit is 100 https requests per 10 seconds
        if len(trading_pairs) == 1:
            for trading_pair in trading_pairs:
                ex_pair = convert_to_exchange_trading_pair(trading_pair)
                resp_json = await generic_api_request("get", Constants.TICKER_SINGLE_URI.format(trading_pair=ex_pair))
                results[trading_pair] = Decimal(str(resp_json['ticker']["last"]))
        else:
            resp_json = await generic_api_request("get", Constants.TICKER_URI)
            for trading_pair in trading_pairs:
                ex_pair = convert_to_exchange_trading_pair(trading_pair)
                results[trading_pair] = Decimal(str(resp_json[ex_pair]["ticker"]["last"]))
        return results

    # Deprecated get_mid_price function - mid price is pulled from order book now.
    # @staticmethod
    # @cachetools.func.ttl_cache(ttl=10)
    # def get_mid_price(trading_pair: str) -> Optional[Decimal]:
    #     resp = requests.get(url=Constants.EXCHANGE_ROOT_API + Constants.TICKER_URI)
    #     records = resp.json()
    #     result = None
    #     for tag in list(records.keys()):
    #         record = records[tag]
    #         pair = convert_from_exchange_trading_pair(tag)
    #         if trading_pair == pair and record["ticker"]["open"] is not None and record["ticker"]["last"] is not None:
    #             result = ((Decimal(record["ticker"]["open"]) * Decimal('1')) + (Decimal(record["ticker"]["last"]) * Decimal('3'))) / Decimal("4")
    #             if result <= 0:
    #                 result = Decimal('0.00000001')
    #             break
    #     return result

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            products: List[Dict[str, Any]] = await generic_api_request("get", Constants.SYMBOLS_URI)
            return [
                product["name"].replace("/", "-") for product in products
                if product['state'] == "enabled"
            ]

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for huobi trading pairs
            pass

        return []

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        # when type is set to "step0", the default value of "depth" is 150
        # params: Dict = {"symbol": trading_pair, "type": "step0"}
        # Altmarkets rate limit is 100 https requests per 10 seconds
        depth_url = Constants.DEPTH_URI.format(trading_pair=convert_to_exchange_trading_pair(trading_pair))
        try:
            data: Dict[str, Any] = await generic_api_request("get", depth_url, shared_client=client)
            return data
        except Exception:
            raise IOError(f"Error fetching Altmarkets market snapshot for {trading_pair}.")

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
            snapshot_msg: OrderBookMessage = AltmarketsOrderBook.snapshot_message_from_exchange(
                snapshot,
                metadata={"trading_pair": trading_pair}
            )
            order_book: OrderBook = self.order_book_create_function()
            order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
            return order_book

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=Constants.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    pong_waiter = await ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=Constants.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(Constants.EXCHANGE_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "event": Constants.WS_PUSHER_SUBSCRIBE_EVENT,
                            "streams": [stream.format(trading_pair=convert_to_exchange_trading_pair(trading_pair)) for stream in Constants.WS_TRADE_SUBSCRIBE_STREAMS]
                        }
                        await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        # Altmarkets's data value for id is a large int too big for ujson to parse
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        if "ping" in raw_msg:
                            await ws.send(f'{{"op":"pong","timestamp": {str(msg["ping"])}}}')
                        elif "subscribed" in raw_msg:
                            pass
                        elif ".trades" in raw_msg:
                            trading_pair = list(msg.keys())[0].split(".")[0]
                            for trade in msg[f"{trading_pair}.trades"]["trades"]:
                                trade_message: OrderBookMessage = AltmarketsOrderBook.trade_message_from_exchange(
                                    trade,
                                    metadata={"trading_pair": trading_pair}
                                )
                                output.put_nowait(trade_message)
                        else:
                            # Debug log output for pub WS messages
                            self.logger().info(f"Unrecognized message received from Altmarkets websocket: {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Trades: Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(Constants.MESSAGE_TIMEOUT)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(Constants.EXCHANGE_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "event": "subscribe",
                            "streams": [stream.format(trading_pair=convert_to_exchange_trading_pair(trading_pair)) for stream in Constants.WS_OB_SUBSCRIBE_STREAMS]
                        }
                        await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        # Altmarkets's data value for id is a large int too big for ujson to parse
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        if "ping" in raw_msg:
                            await ws.send(f'{{"op":"pong","timestamp": {str(msg["ping"])}}}')
                        elif "subscribed" in raw_msg:
                            pass
                        elif ".ob-inc" in raw_msg:
                            # msg_key = list(msg.keys())[0]
                            trading_pair = list(msg.keys())[0].split(".")[0]
                            order_book_message: OrderBookMessage = AltmarketsOrderBook.diff_message_from_exchange(
                                msg[f"{trading_pair}.ob-inc"],
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(order_book_message)
                        elif ".ob-snap" in raw_msg:
                            # msg_key = list(msg.keys())[0]
                            trading_pair = list(msg.keys())[0].split(".")[0]
                            order_book_message: OrderBookMessage = AltmarketsOrderBook.snapshot_message_from_exchange(
                                msg[f"{trading_pair}.ob-snap"],
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(order_book_message)
                        else:
                            # Debug log output for pub WS messages
                            self.logger().info(f"OB: Unrecognized message received from Altmarkets websocket: {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(Constants.MESSAGE_TIMEOUT)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_message: OrderBookMessage = AltmarketsOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_message)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error.", exc_info=True)
                            await asyncio.sleep(5.0)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
