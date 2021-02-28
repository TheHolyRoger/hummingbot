import aiohttp
import asyncio
import random
import re
from hummingbot.connector.exchange.altmarkets.altmarkets_constants import Constants
from typing import (
    Any,
    Dict,
    Optional,
    Tuple,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


TRADING_PAIR_SPLITTER = re.compile(Constants.TRADING_PAIR_SPLITTER)

CENTRALIZED = True

EXAMPLE_PAIR = "ALTM-BTC"

DEFAULT_FEES = [0.1, 0.2]


class AltmarketsAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = TRADING_PAIR_SPLITTER.match(trading_pair)
        return m.group(1), m.group(2)
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    if split_trading_pair(exchange_trading_pair) is None:
        return None
    # Altmarkets uses lowercase (btcusdt)
    base_asset, quote_asset = split_trading_pair(exchange_trading_pair)
    return f"{base_asset.upper()}-{quote_asset.upper()}"


def convert_to_exchange_trading_pair(am_trading_pair: str) -> str:
    # Altmarkets uses lowercase (btcusdt)
    return am_trading_pair.replace("-", "").lower()


def retry_sleep_time(try_count: int) -> float:
    random.seed()
    randSleep = 1 + float(random.randint(1, 10) / 100)
    return float(5 + float(randSleep * (1 + (try_count ** try_count))))


async def generic_api_request(method,
                              path_url,
                              params: Optional[Dict[str, Any]] = None,
                              client=None,
                              try_count: int = 0) -> Dict[str, Any]:
    url = f"{Constants.EXCHANGE_ROOT_API}{path_url}"
    headers = {"Content-Type": ("application/json" if method == "post"
                                else "application/x-www-form-urlencoded")}
    http_client = client if client is not None else aiohttp.ClientSession()
    response_coro = http_client.request(
        method=method.upper(), url=url, headers=headers, params=params, timeout=Constants.API_CALL_TIMEOUT
    )
    http_status, parsed_response, request_errors = None, None, False
    try:
        async with response_coro as response:
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
                http_status = response.status
    except Exception:
        request_errors = True
    if request_errors or parsed_response is None:
        if try_count < 4:
            try_count += 1
            time_sleep = retry_sleep_time(try_count)
            print(f"Error fetching data from {url}. HTTP status is {http_status}. "
                  f"Retrying in {time_sleep:.1f}s.")
            await asyncio.sleep(time_sleep)
            return await generic_api_request(method=method, path_url=path_url, params=params,
                                             client=client, try_count=try_count)
        else:
            print(f"Error fetching data from {url}. HTTP status is {http_status}. "
                  f"Final msg: {parsed_response}.")
            raise AltmarketsAPIError({"error": parsed_response})
    return parsed_response


KEYS = {
    "altmarkets_api_key":
        ConfigVar(key="altmarkets_api_key",
                  prompt="Enter your Altmarkets API key >>> ",
                  required_if=using_exchange("altmarkets"),
                  is_secure=True,
                  is_connect_key=True),
    "altmarkets_secret_key":
        ConfigVar(key="altmarkets_secret_key",
                  prompt="Enter your Altmarkets secret key >>> ",
                  required_if=using_exchange("altmarkets"),
                  is_secure=True,
                  is_connect_key=True),
}
