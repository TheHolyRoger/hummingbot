import aiohttp
from aiohttp.test_utils import TestClient
import asyncio
from async_timeout import timeout
import conf
from datetime import datetime
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
import random
import pandas as pd
import re
import time
from typing import (
    Any,
    AsyncIterable,
    Coroutine,
    Dict,
    List,
    Optional,
    Tuple
)
import ujson

import hummingbot
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketTransactionFailureEvent,
    MarketOrderFailureEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.asyncio_throttle import Throttler
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.altmarkets.altmarkets_api_order_book_data_source import AltmarketsAPIOrderBookDataSource
from hummingbot.connector.exchange.altmarkets.altmarkets_auth import AltmarketsAuth
from hummingbot.connector.exchange.altmarkets.altmarkets_in_flight_order import AltmarketsInFlightOrder
from hummingbot.connector.exchange.altmarkets.altmarkets_order_book_tracker import AltmarketsOrderBookTracker
from hummingbot.connector.exchange.altmarkets.altmarkets_user_stream_tracker import AltmarketsUserStreamTracker
from hummingbot.connector.exchange.altmarkets.altmarkets_constants import Constants
from hummingbot.connector.exchange.altmarkets.altmarkets_utils import (
    convert_to_exchange_trading_pair,
    convert_from_exchange_trading_pair,
    retry_sleep_time,
    AltmarketsAPIError,
)
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee

hm_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("NaN")
BROKER_ID = "HBOT"


cdef str get_client_order_id(str order_side, object trading_pair):
    cdef:
        int64_t nonce = <int64_t> get_tracking_nonce()
        object symbols = trading_pair.split("-")
        str base = symbols[0].lower()
        str quote = symbols[1].lower()
    return f"{BROKER_ID}-{order_side.upper()}-{base}{quote}-{nonce}"


cdef class AltmarketsExchangeTransactionTracker(TransactionTracker):
    cdef:
        AltmarketsExchange _owner

    def __init__(self, owner: AltmarketsExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class AltmarketsExchange(ExchangeBase):
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value
    API_CALL_TIMEOUT = Constants.API_CALL_TIMEOUT
    UPDATE_ORDERS_INTERVAL = Constants.UPDATE_ORDERS_INTERVAL

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hm_logger
        if hm_logger is None:
            hm_logger = logging.getLogger(__name__)
        return hm_logger

    def __init__(self,
                 altmarkets_api_key: str,
                 altmarkets_secret_key: str,
                 poll_interval: float = 5.0,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):

        super().__init__()
        # self._account_id = ""
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._ev_loop = asyncio.get_event_loop()
        self._altmarkets_auth = AltmarketsAuth(api_key=altmarkets_api_key, secret_key=altmarkets_secret_key)
        self._in_flight_orders = {}
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._order_book_tracker = AltmarketsOrderBookTracker(
            trading_pairs=trading_pairs
        )
        self._user_stream_tracker = AltmarketsUserStreamTracker(altmarkets_auth=self._altmarkets_auth, trading_pairs=trading_pairs)
        self._poll_notifier = asyncio.Event()
        self._poll_interval = poll_interval
        self._shared_client = None
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._trading_rules_polling_task = None
        self._tx_tracker = AltmarketsExchangeTransactionTracker(self)
        self._throttler = Throttler(rate_limit = (10.0, 6.5))

    @property
    def name(self) -> str:
        return "altmarkets"

    @property
    def order_book_tracker(self) -> AltmarketsOrderBookTracker:
        return self._order_book_tracker

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, AltmarketsInFlightOrder]:
        return self._in_flight_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, Any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        self._in_flight_orders.update({
            key: AltmarketsInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @property
    def shared_client(self) -> str:
        return self._shared_client

    @shared_client.setter
    def shared_client(self, client: aiohttp.ClientSession):
        self._shared_client = client

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await AltmarketsAPIOrderBookDataSource.get_active_exchange_markets()

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.c_start(self, clock, timestamp)

    cdef c_stop(self, Clock clock):
        ExchangeBase.c_stop(self, clock)
        self._async_scheduler.stop()

    async def start_network(self):
        if self._trading_rules_polling_task is not None:
            self._stop_network()
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            # await self._update_account_id()
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    def _stop_network(self):
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            # self._status_polling_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = \
            self._user_stream_event_listener_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request(method="get", endpoint=Constants.TIMESTAMP_URI)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)
        ExchangeBase.c_tick(self, timestamp)
        self._tx_tracker.c_tick(timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           method,
                           endpoint,
                           params: Optional[Dict[str, Any]] = None,
                           data=None,
                           is_auth_required: bool = False,
                           try_count: int = 0,
                           request_weight: int = 1) -> Dict[str, Any]:
        # Altmarkets rate limit is 100 https requests per 10 seconds
        async with self._throttler.weighted_task(request_weight=request_weight):
            shared_client = await self._http_client()
            # aiohttp TestClient requires path instead of url
            url = (f"/{endpoint}" if isinstance(shared_client, TestClient) else
                   f"{Constants.EXCHANGE_ROOT_API}{endpoint}")
            headers = (self._altmarkets_auth.get_headers() if is_auth_required else
                       {"Content-Type": "application/json"})
            response_coro = shared_client.request(
                method=method.upper(), url=url, headers=headers, params=params,
                data=ujson.dumps(data), timeout=100
            )
            http_status, parsed_response, request_errors = None, None, False
            try:
                async with response_coro as response:
                    http_status = response.status
                    try:
                        parsed_response = await response.json()
                    except Exception:
                        request_errors = True
                        try:
                            parsed_response = str(await response.read())
                            if len(parsed_response) > 100:
                                parsed_response = f"{parsed_response[:100]} ... (truncated)"
                        except Exception:
                            pass
                    if response.status not in [200, 201] or parsed_response is None:
                        request_errors = True
            except Exception:
                request_errors = True
            if request_errors or parsed_response is None:
                if try_count < 4:
                    try_count += 1
                    time_sleep = retry_sleep_time(try_count)
                    print(f"Error fetching data from {url}. HTTP status is {http_status}. "
                          f"Retrying in {time_sleep:.1f}s.")
                    await asyncio.sleep(time_sleep)
                    return await self._api_request(method=method, endpoint=endpoint, params=params,
                                                   data=data, is_auth_required=is_auth_required,
                                                   try_count=try_count, request_weight=request_weight)
                else:
                    print(f"Error fetching data from {url}. HTTP status is {http_status}. "
                          f"Final msg: {parsed_response}.")
                    raise AltmarketsAPIError({"error": parsed_response, "status": http_status})
            return parsed_response

    async def _update_balances(self):
        cdef:
            list data
            list balances
            dict new_available_balances = {}
            dict new_balances = {}
            str asset_name
            object balance

        data = await self._api_request("get", endpoint=Constants.ACCOUNTS_BALANCE_URI, is_auth_required=True)
        balances = data
        if len(balances) > 0:
            for balance_entry in balances:
                asset_name = balance_entry["currency"].upper()
                balance = Decimal(balance_entry["balance"])
                locked_balance = Decimal(balance_entry["locked"])
                # if balance == s_decimal_0:
                #     continue
                new_balances[asset_name] = balance + locked_balance
                # Altmarkets does not use balance categories yet. Just Total Balance & Locked
                new_available_balances[asset_name] = balance

            self._account_available_balances.clear()
            self._account_available_balances = new_available_balances
            self._account_balances.clear()
            self._account_balances = new_balances

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        # There is no API for checking user's fee tier
        # Fee info from https://v2.altmarkets.io/
        """
        if order_type is OrderType.LIMIT and fee_overrides_config_map["altmarkets_maker_fee"].value is not None:
            return TradeFee(percent=fee_overrides_config_map["altmarkets_maker_fee"].value / Decimal("100"))
        if order_type is OrderType.MARKET and fee_overrides_config_map["altmarkets_taker_fee"].value is not None:
            return TradeFee(percent=fee_overrides_config_map["kucoin_taker_fee"].value / Decimal("100"))
        return TradeFee(percent=Decimal("0.001"))
        """
        is_maker = order_type is OrderType.LIMIT
        return estimate_fee("altmarkets", is_maker)

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for trade rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self._api_request("get", endpoint=Constants.SYMBOLS_URI)
            trading_rules_list = self._format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[convert_from_exchange_trading_pair(trading_rule.trading_pair)] = trading_rule

    def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list trading_rules = []

        for info in raw_trading_pair_info:
            try:
                min_amount = Decimal(info["min_amount"])
                min_notional = min(Decimal(info["min_price"]) * min_amount, Decimal("0.00000001"))
                trading_rules.append(
                    TradingRule(trading_pair=info["id"],
                                min_order_size=min_amount,
                                min_price_increment=Decimal(f"1e-{info['price_precision']}"),
                                min_base_amount_increment=Decimal(f"1e-{info['amount_precision']}"),
                                min_notional_size=min_notional)
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def get_order_status(self, exchange_order_id: str) -> Dict[str, Any]:
        """
        Example:
        {
          "id": 23,
          "uuid": "5766053b-1ac8-4b8b-b221-97d396660b5f",
          "side": "buy",
          "ord_type": "limit",
          "price": "0.00000003",
          "avg_price": "0.00000003",
          "state": "done",
          "market": "rogerbtc",
          "created_at": "2020-08-02T15:02:26+02:00",
          "updated_at": "2020-08-02T15:02:26+02:00",
          "origin_volume": "50.0",
          "remaining_volume": "0.0",
          "executed_volume": "50.0",
          "trades_count": 1,
          "trades": [
            {
              "id": 6,
              "price": "0.00000003",
              "amount": "50.0",
              "total": "0.0000015",
              "market": "rogerbtc",
              "created_at": "2020-08-02T15:02:26+02:00",
              "taker_type": "sell",
              "side": "buy"
            }
          ]
        }
        """
        endpoint = Constants.LIST_ORDER_URI.format(exchange_order_id=exchange_order_id)
        return await self._api_request("get", endpoint=endpoint, is_auth_required=True)

    async def _update_order_message(self, exchange_order_id, content, tracked_order):
        order_state = content.get("state")
        # possible order states are "wait", "done", "cancel", "pending"
        if order_state not in ["done", "cancel", "wait", "pending", "reject"]:
            self.logger().info(f"Unrecognized order update response - {content}")

        # Calculate the newly executed amount for this update.
        tracked_order.last_state = order_state
        new_confirmed_amount = Decimal(content.get("executed_volume", '0.0'))
        execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base

        if execute_amount_diff > s_decimal_0:
            execute_price = Decimal(content.get("price", '0.0')
                                    if content.get("price", None) is not None
                                    else content.get("avg_price", '0.0'))
            new_executed_amount_quote = new_confirmed_amount * execute_price
            if content.get("trades", None) is not None:
                new_executed_amount_quote = Decimal('0')
                for one_trade in content.get('trades', []):
                    new_executed_amount_quote += Decimal(one_trade['total'])
            tracked_order.executed_amount_base = new_confirmed_amount
            tracked_order.executed_amount_quote = new_executed_amount_quote
            new_estimated_fee = estimate_fee("altmarkets", tracked_order.order_type is OrderType.LIMIT)
            tracked_order.fee_paid = new_confirmed_amount * new_estimated_fee.percent
            order_filled_event = OrderFilledEvent(
                self._current_timestamp,
                tracked_order.client_order_id,
                tracked_order.trading_pair,
                tracked_order.trade_type,
                tracked_order.order_type,
                execute_price,
                execute_amount_diff,
                self.c_get_fee(
                    tracked_order.base_asset,
                    tracked_order.quote_asset,
                    tracked_order.order_type,
                    tracked_order.trade_type,
                    execute_price,
                    execute_amount_diff,
                ),
                # Unique exchange trade ID not available in client order status
                # But can use validate an order using exchange order ID:
                # https://huobiapi.github.io/docs/spot/v1/en/#query-order-by-order-id
                # Update this comment for AltMarkets ^
                exchange_trade_id=exchange_order_id
            )
            self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                               f"order {tracked_order.client_order_id}.")
            self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

        if tracked_order.is_open:
            return True

        if tracked_order.is_done:
            if not tracked_order.is_cancelled:  # Handles "filled" order
                self.c_stop_tracking_order(tracked_order.client_order_id)
                if tracked_order.trade_type is TradeType.BUY:
                    self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                       f"according to order status API.")
                    self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                         BuyOrderCompletedEvent(self._current_timestamp,
                                                                tracked_order.client_order_id,
                                                                tracked_order.base_asset,
                                                                tracked_order.quote_asset,
                                                                tracked_order.fee_asset or tracked_order.base_asset,
                                                                tracked_order.executed_amount_base,
                                                                tracked_order.executed_amount_quote,
                                                                tracked_order.fee_paid,
                                                                tracked_order.order_type,
                                                                exchange_order_id=tracked_order.exchange_order_id))
                    return True
                else:
                    self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                       f"according to order status API.")
                    self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                         SellOrderCompletedEvent(self._current_timestamp,
                                                                 tracked_order.client_order_id,
                                                                 tracked_order.base_asset,
                                                                 tracked_order.quote_asset,
                                                                 tracked_order.fee_asset or tracked_order.quote_asset,
                                                                 tracked_order.executed_amount_base,
                                                                 tracked_order.executed_amount_quote,
                                                                 tracked_order.fee_paid,
                                                                 tracked_order.order_type,
                                                                 exchange_order_id=tracked_order.exchange_order_id))
                    return True
            else:  # Handles "canceled" or "partial-canceled" order
                self.c_stop_tracking_order(tracked_order.client_order_id)
                self.logger().info(f"The market order {tracked_order.client_order_id} "
                                   f"has been cancelled according to order status API.")
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp,
                                                         tracked_order.client_order_id,
                                                         exchange_order_id=tracked_order.exchange_order_id))
                return True
        else:
            return True

    async def _update_order_status(self):
        cdef:
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            # Debug logging of in-flight orders
            # print(self._in_flight_orders)
            tracked_orders = list(self._in_flight_orders.values())
            for tracked_order in tracked_orders:
                exchange_order_id = await tracked_order.get_exchange_order_id()
                try:
                    order_update = await self.get_order_status(exchange_order_id)
                except (AltmarketsAPIError) as e:
                    # TODO AltM - Handle order error cancel msg
                    err_code = e.error_payload.get("error")
                    try:
                        err_code = err_code.get("err-code")
                    except Exception:
                        pass
                    self.c_stop_tracking_order(tracked_order.client_order_id)
                    self.logger().info(f"The limit order {tracked_order.client_order_id} "
                                       f"has failed according to order status API. - {err_code}")
                    self.c_trigger_event(
                        self.MARKET_ORDER_FAILURE_EVENT_TAG,
                        MarketOrderFailureEvent(
                            self._current_timestamp,
                            tracked_order.client_order_id,
                            tracked_order.order_type
                        )
                    )
                    continue

                if order_update is None:
                    self.logger().network(
                        f"Error fetching status update for the order {tracked_order.client_order_id}: "
                        f"{order_update}.",
                        app_warning_msg=f"Could not fetch updates for the order {tracked_order.client_order_id}. "
                                        f"The order has either been filled or canceled."
                    )
                    continue

                await self._update_order_message(exchange_order_id, order_update, tracked_order)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        """
        Iterator for incoming messages from the user stream.
        """
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 1 seconds.", exc_info=True)
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Update order statuses from incoming messages from the user stream

        Example content:
        {
          "order": {
            "id": 9401,
            "market": "rogerbtc",
            "kind": "ask",
            "side": "sell",
            "ord_type": "limit",
            "price": "0.00000099",
            "avg_price": "0.00000099",
            "state": "wait",
            "origin_volume": "7000.0",
            "remaining_volume": "2810.1",
            "executed_volume": "4189.9",
            "at": 1596481983,
            "created_at": 1596481983,
            "updated_at": 1596553643,
            "trades_count": 272
          }
        }
        {
          "trade": {
            "id": 27243,
            "price": "0.00000099",
            "amount": "35.8",
            "total": "0.000035442",
            "market": "rogerbtc",
            "side": "sell",
            "taker_type": "buy",
            "created_at": 1596553643,
            "order_id": 9401
          }
        }
        """
        async for event_message in self._iter_user_event_queue():
            try:
                # print(f"Evt Msg: {event_message}")
                for event_type in list(event_message.keys()):
                    content = event_message[event_type]
                    if event_type == 'order':
                        # Order id retreived from exchange
                        exchange_order_id = content.get('id')
                        tracked_order = None
                        for order in self._in_flight_orders.values():
                            if order.exchange_order_id == exchange_order_id:
                                tracked_order = order
                                break
                        if tracked_order is None:
                            continue
                        # order_type_description = tracked_order.order_type_description
                        await self._update_order_message(exchange_order_id, content, tracked_order)
                    # When AltMarkets updates to Peatio 2.6 this should start working.
                    elif event_type == 'balance':
                        if len(content) > 0:
                            new_balances = {}
                            new_available_balances = {}
                            for balance_entry in content:
                                asset_name = balance_entry["currency"].upper()
                                balance = Decimal(balance_entry["balance"])
                                locked_balance = Decimal(balance_entry["locked"])
                                # if balance == s_decimal_0:
                                #     continue
                                new_balances[asset_name] = balance + locked_balance
                                new_available_balances[asset_name] = balance

                            self._account_available_balances.clear()
                            self._account_available_balances = new_available_balances
                            self._account_balances.clear()
                            self._account_balances = new_balances
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Altmarkets. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60 * 5)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Altmarkets. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    async def place_order(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          trade_type: TradeType,
                          order_type: OrderType,
                          price: Decimal) -> str:
        endpoint = Constants.ORDER_CREATION_URI
        side = "buy" if trade_type == TradeType.BUY else "sell"
        order_type_str = "limit" if order_type is OrderType.LIMIT else "market"

        params = {
            # "account-id": self._account_id,
            "volume": f"{amount:f}",
            # "client-order-id": order_id,
            "market": convert_to_exchange_trading_pair(trading_pair),
            "side": side,
            "ord_type": order_type_str,
        }
        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            params["price"] = f"{price:f}"
        exchange_order = await self._api_request(
            "post",
            endpoint=endpoint,
            params=params,
            data=params,
            is_auth_required=True
        )
        return str(exchange_order['id'])

    async def create_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Optional[Decimal] = s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object quote_amount
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        if trade_type == TradeType.BUY:
            event_tag, event_cls, side_str = self.MARKET_BUY_ORDER_CREATED_EVENT_TAG, BuyOrderCreatedEvent, "Buy"
        else:
            event_tag, event_cls, side_str = self.MARKET_SELL_ORDER_CREATED_EVENT_TAG, SellOrderCreatedEvent, "Sell"
        try:
            if order_type == OrderType.LIMIT and decimal_price <= s_decimal_0:
                raise ValueError(f"Price of {decimal_price:.8f} is too low.")
            if decimal_amount < trading_rule.min_order_size:
                raise ValueError(f"{side_str} order amount {decimal_amount:.8f} is lower than the minimum order size "
                                 f"{trading_rule.min_order_size:.8f}.")
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount,
                                                       trade_type, order_type, decimal_price)
            self.c_start_tracking_order(
                client_order_id=order_id, exchange_order_id=exchange_order_id, trading_pair=trading_pair,
                order_type=order_type, trade_type=trade_type, price=decimal_price, amount=decimal_amount)
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} {side_str} order {order_id} for {decimal_amount}"
                                   f" {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)
            await asyncio.sleep(0.1)
            self.c_trigger_event(event_tag,
                                 event_cls(
                                     self._current_timestamp, order_type, trading_pair,
                                     decimal_amount, decimal_price, order_id))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting {side_str} {order_type_str} order to AltMarkets for {decimal_amount}"
                f" {trading_pair} {decimal_price if order_type is not OrderType.MARKET else ''}.",
                exc_info=True,
                app_warning_msg=(f"Failed to submit {side_str} order: {e} (Stack trace in logs)"))
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.MARKET,
                   object price=s_decimal_0, dict kwargs={}):
        cdef:
            str order_id = get_client_order_id("buy", trading_pair)

        safe_ensure_future(self.create_order(order_id, trading_pair, amount, TradeType.BUY, order_type, price))
        return order_id

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.MARKET,
                    object price=s_decimal_0, dict kwargs={}):
        cdef:
            str order_id = get_client_order_id("sell", trading_pair)
        safe_ensure_future(self.create_order(order_id, trading_pair, amount, TradeType.SELL, order_type, price))
        return order_id

    async def execute_cancel(self, order_id: str):
        tracked_order = self._in_flight_orders.get(order_id)
        if tracked_order is None:
            raise ValueError(f"Failed to cancel order - {order_id}. Order no longer tracked.")
        endpoint = Constants.ORDER_CANCEL_URI.format(exchange_order_id=tracked_order.exchange_order_id)
        order_state, errors = None, None
        try:
            response = await self._api_request("post", endpoint=endpoint, is_auth_required=True)
            if isinstance(response, dict) and "state" in list(response.keys()):
                order_state = response["state"]
        except (AltmarketsAPIError, Exception) as e:
            errors = e
            if isinstance(e, AltmarketsAPIError) and 'error' in list(e.error_payload.keys()):
                errors = e.error_payload.get("error")
                order_state = e.error_payload.get("error").get("state", None)
        if order_state in ['wait', 'cancel', 'done', 'reject']:
            self.c_stop_tracking_order(tracked_order.client_order_id)
            self.logger().info(f"The order {tracked_order.client_order_id} has been cancelled according"
                               f" to order status API.")
            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp,
                                                     tracked_order.client_order_id))
            return CancellationResult(order_id, True)
        else:
            self.logger().network(
                f"Failed to cancel order: {order_id}, state: {order_state}, errors: {str(errors)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Altmarkets. "
                                f"Check API key and network connection."
            )
            return CancellationResult(order_id, False)

    cdef c_cancel(self, str trading_pair, str order_id):
        safe_ensure_future(self.execute_cancel(order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        open_orders = [o for o in self._in_flight_orders.values() if o.is_open]
        if len(open_orders) == 0:
            return []
        tasks = [self.execute_cancel(o.client_order_id) for o in open_orders]
        order_id_set = set([o.client_order_id for o in open_orders])
        cancellation_results = []
        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
        except Exception as e:
            self.logger().network(
                f"Failed to cancel all orders: {order_id_set}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel all orders on Altmarkets. Check API key and network connection."
            )
        return cancellation_results

    cdef OrderBook c_get_order_book(self, str trading_pair):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            err = f"No order book exists for '{trading_pair}' - {order_books}."
            raise ValueError(err)
        return order_books.get(trading_pair)

    cdef c_did_timeout_tx(self, str tracking_id):
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str exchange_order_id,
                                str trading_pair,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        self._in_flight_orders[client_order_id] = AltmarketsInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_buy(trading_pair, amount, order_type, price, kwargs)

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_sell(trading_pair, amount, order_type, price, kwargs)

    def cancel(self, trading_pair: str, client_order_id: str):
        return self.c_cancel(trading_pair, client_order_id)

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN) -> TradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
