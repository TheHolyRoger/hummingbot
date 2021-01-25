import hashlib
import hmac
from typing import Any, Dict
from datetime import datetime, timezone, timedelta


class AltmarketsAuth:
    """
    Auth class required by AltMarkets.io API
    Learn more at https://altmarkets.io
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.signature = None
        self.nonce = None
        # POSIX epoch for nonce
        self.date_epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def generate_signature(self) -> (Dict[str, Any]):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """
        # Must use UTC timestamps for nonce
        date_now = datetime.now(timezone.utc)
        posix_timestamp_millis = int(((date_now - self.date_epoch) // timedelta(microseconds=1)) // 1000)
        self.nonce = str(posix_timestamp_millis)
        auth_payload = self.nonce + self.api_key
        # Build the HS256 signature
        self.signature = hmac.new(
            bytes(self.secret_key, 'latin-1'),
            msg=bytes(auth_payload, 'latin-1'),
            digestmod=hashlib.sha256).hexdigest()

        return True

    def get_headers(self) -> (Dict[str, Any]):
        self.generate_signature()
        return {
            "X-Auth-Apikey": self.api_key,
            "X-Auth-Nonce": self.nonce,
            "X-Auth-Signature": self.signature,
            "Content-Type": "application/json"
        }
