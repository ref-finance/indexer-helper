import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode
import requests
from config import Cfg

BITGET_BASE_URL = "https://bopenapi.bgwapi.io"
OKX_BASE_URL = "https://web3.okx.com"


def _sorted_json_str(data: Dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _build_body_str(body: Optional[Dict[str, Any]]) -> str:
    if not body:
        return ""
    if not isinstance(body, dict):
        raise ValueError("body must be a JSON object")
    return _sorted_json_str(body)


def _build_signature(
    api_path: str,
    body_str: str,
    api_key: str,
    api_secret: str,
    timestamp_ms: str,
    query: Optional[Dict[str, Any]] = None,
) -> str:
    sign_payload = {
        "apiPath": api_path,
        "body": body_str,
        "x-api-key": api_key,
        "x-api-timestamp": timestamp_ms,
    }
    if query:
        for key, value in query.items():
            sign_payload[str(key)] = "" if value is None else str(value)
    sign_str = _sorted_json_str(sign_payload)
    signature = hmac.new(api_secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(signature).decode("utf-8")


def _get_env_credentials() -> Tuple[str, str, str]:
    api_key = Cfg.BITGET_API_KEY
    api_secret = Cfg.BITGET_API_SECRET
    partner_code = Cfg.BITGET_PARTNER_CODE
    if not api_key or not api_secret or not partner_code:
        raise ValueError("BITGET_API_KEY, BITGET_API_SECRET, BITGET_PARTNER_CODE must be set")
    return api_key, api_secret, partner_code


def _get_okx_env_credentials() -> Tuple[str, str, str, str]:
    api_key = Cfg.OKX_API_KEY
    api_secret = Cfg.OKX_API_SECRET
    api_passphrase = Cfg.OKX_API_PASSPHRASE
    project_id = Cfg.OKX_PROJECT_ID
    if not api_key or not api_secret or not project_id:
        raise ValueError("OKX_API_KEY, OKX_API_SECRET, PROJECT_ID must be set")
    return api_key, api_secret, api_passphrase, project_id


def _build_okx_signature(timestamp: str, method: str, request_path: str, body_str: str, api_secret: str) -> str:
    prehash = timestamp + method.upper() + request_path + body_str
    signature = hmac.new(
        api_secret.encode("utf-8"),
        prehash.encode("utf-8"),
        hashlib.sha256
    ).digest()
    return base64.b64encode(signature).decode("utf-8")


def proxy_bitget_request(
    api_path: str,
    method: str = "POST",
    body: Optional[Dict[str, Any]] = None,
    query: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    api_key, api_secret, partner_code = _get_env_credentials()
    timestamp_ms = str(int(time.time() * 1000))
    body_str = _build_body_str(body)
    signature = _build_signature(api_path, body_str, api_key, api_secret, timestamp_ms, query)

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "x-api-timestamp": timestamp_ms,
        "x-api-signature": signature,
        "Partner-Code": partner_code,
    }

    url = f"{BITGET_BASE_URL}{api_path}"
    request_kwargs = {
        "method": method.upper(),
        "url": url,
        "headers": headers,
        "params": query,
        "timeout": timeout,
    }
    if body_str:
        request_kwargs["data"] = body_str
    response = requests.request(
        **request_kwargs,
    )
    response.raise_for_status()
    return response.json()


def proxy_okx_request(
    api_path: str,
    method: str = "POST",
    body: Optional[Dict[str, Any]] = None,
    query: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    api_key, api_secret, api_passphrase, project_id = _get_okx_env_credentials()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
                f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"

    method_upper = method.upper()

    body_str = ""
    if method_upper != "GET" and body:
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)

    request_path = api_path
    if query:
        query_string = urlencode(query)
        request_path = f"{api_path}?{query_string}"

    signature = _build_okx_signature(timestamp, method_upper, request_path, body_str, api_secret)

    headers = {
        "Content-Type": "application/json",
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": api_passphrase,
    }
    if project_id:
        headers["OK-ACCESS-PROJECT"] = project_id

    url = f"{OKX_BASE_URL}{request_path}"
    request_kwargs = {
        "method": method_upper,
        "url": url,
        "headers": headers,
        "timeout": timeout,
    }
    if body_str:
        request_kwargs["data"] = body_str
    response = requests.request(**request_kwargs)
    response.raise_for_status()
    return response.json()
