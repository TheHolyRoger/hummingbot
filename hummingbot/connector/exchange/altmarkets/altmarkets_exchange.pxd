from libc.stdint cimport int64_t

from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class AltmarketsExchange(ExchangeBase):
    cdef:
        str _account_id
        object _user_stream_tracker
        object _async_scheduler
        object _data_source_type
        object _ev_loop
        object _altmarkets_auth
        dict _in_flight_orders
        double _last_poll_timestamp
        double _last_timestamp
        object _poll_notifier
        double _poll_interval
        object _shared_client
        public object _status_polling_task
        public object _user_stream_tracker_task
        public object _user_stream_event_listener_task
        dict _trading_rules
        public object _trading_rules_polling_task
        TransactionTracker _tx_tracker
        object _throttler

    cdef c_did_timeout_tx(self, str tracking_id)
    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str exchange_order_id,
                                str trading_pair,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount)
