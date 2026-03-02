import hmac
import json
import requests
import hashlib
import time
import uuid
import threading
from config import Cfg
from loguru import logger

TRXX_BASE_URL = "https://trxx.io/api/v1/frontend"

# Period mapping: frontend format -> TRXX API format
PERIOD_MAP = {
    "1H": "1H",
    "1D": "1D",
    "3D": "3D",
    "30D": "30D",
}
VALID_PERIODS = list(PERIOD_MAP.keys())


# ============================================================
# Signing & Verification
# ============================================================

def _get_credentials():
    """Get TRXX API credentials from config"""
    api_key = Cfg.TRXX_API_KEY
    api_secret = Cfg.TRXX_API_SECRET
    if not api_key or not api_secret:
        raise ValueError("TRXX_API_KEY or TRXX_API_SECRET is not configured")
    return api_key, api_secret


def _sort_object(obj):
    """Recursively sort object keys (equivalent to TS sortObject)"""
    if isinstance(obj, dict):
        return {k: _sort_object(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sort_object(item) for item in obj]
    return obj


def _canonical(obj):
    """Convert object to canonical JSON string (sorted keys, compact, no spaces)"""
    sorted_obj = _sort_object(obj)
    return json.dumps(sorted_obj, separators=(',', ':'), ensure_ascii=False)


def _generate_signature(api_secret: str, timestamp: str, body_str: str = "") -> str:
    """
    Generate HMAC-SHA256 signature for TRXX API.
    message = '{timestamp}&{canonical_json_body}'
    Returns hex string.
    """
    message = f'{timestamp}&{body_str}'
    signature = hmac.new(api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return signature


def _build_signed_headers(api_key: str, api_secret: str, timestamp: str, body_str: str) -> dict:
    """Build request headers with HMAC-SHA256 signature for POST requests"""
    signature = _generate_signature(api_secret, timestamp, body_str)
    return {
        "API-KEY": api_key,
        "TIMESTAMP": timestamp,
        "SIGNATURE": signature,
        "Content-Type": "application/json",
    }


def _build_get_headers(api_key: str) -> dict:
    """Build request headers for GET requests (API-KEY only, no signature)"""
    return {
        "API-KEY": api_key,
    }


def verify_trxx_webhook_signature(timestamp: str, payload: dict, received_signature: str, window_seconds: int = 120):
    """
    Verify TRXX webhook callback signature.
    Returns (valid: bool, error: str or None)
    """
    # Validate timestamp window
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False, "Invalid timestamp format"

    now = int(time.time())
    if abs(now - ts) > window_seconds:
        return False, "Timestamp out of window"

    # Compute expected signature
    _, api_secret = _get_credentials()
    body_str = _canonical(payload)
    expected = _generate_signature(api_secret, timestamp, body_str)

    if expected != received_signature:
        return False, "Invalid signature"

    return True, None


def verify_frontend_signature(timestamp: str, payload: dict, received_signature: str, window_seconds: int = 300):
    """
    Verify frontend request signature using FRONTEND_API_SECRET.
    Returns (valid: bool, error: str or None)
    """
    frontend_secret = Cfg.FRONTEND_API_SECRET
    if not frontend_secret:
        return False, "FRONTEND_API_SECRET is not configured"

    # Validate timestamp window
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False, "Invalid timestamp format"

    now = int(time.time())
    if abs(now - ts) > window_seconds:
        return False, "Timestamp out of window"

    # Compute expected signature
    body_str = _canonical(payload)
    expected = _generate_signature(frontend_secret, timestamp, body_str)

    if expected != received_signature:
        return False, "Invalid signature"

    return True, None


# ============================================================
# TRXX API Client (Low-level)
# ============================================================

def _trxx_post(path: str, body: dict) -> dict:
    """
    TRXX POST request (with signature).
    Returns parsed JSON response.
    """
    api_key, api_secret = _get_credentials()
    timestamp = str(int(time.time()))
    body_str = _canonical(body)
    headers = _build_signed_headers(api_key, api_secret, timestamp, body_str)

    url = f"{TRXX_BASE_URL}{path}"
    response = requests.post(url, data=body_str, headers=headers)
    response.raise_for_status()
    return response.json()


def _trxx_get(path: str, params: dict = None) -> dict:
    """
    TRXX GET request (API-KEY only, no signature).
    Returns parsed JSON response.
    """
    api_key, _ = _get_credentials()
    headers = _build_get_headers(api_key)

    url = f"{TRXX_BASE_URL}{path}"
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()


def _parse_trxx_response(raw_json: dict) -> dict:
    """
    Normalize TRXX API response to standard format: {errno, message, data}.
    TRXX may return:
      1. {"errno": 0, "data": {...}}
      2. {"errno": 0, "serial": "...", "amount": ...}  (no data wrapper)
      3. {"period": "1D", "price": 400, ...}  (direct format, no errno)
    """
    if isinstance(raw_json, dict) and "errno" in raw_json:
        if "data" in raw_json:
            return {
                "errno": raw_json.get("errno", 0),
                "message": raw_json.get("message"),
                "data": raw_json["data"],
            }
        else:
            return {
                "errno": raw_json.get("errno", 0),
                "message": raw_json.get("message"),
                "data": raw_json,
            }
    else:
        return {
            "errno": 0,
            "data": raw_json,
        }


# ============================================================
# TRXX API Endpoints (High-level)
# ============================================================

def trxx_get_index_data() -> dict:
    """GET /index-data - Public parameters / pricing tiers"""
    raw = _trxx_get("/index-data")
    return _parse_trxx_response(raw)


def trxx_estimate_price(period: str, energy_amount: int) -> dict:
    """GET /order/price - Estimate price for energy rental"""
    raw = _trxx_get("/order/price", {
        "period": period,
        "energy_amount": str(energy_amount),
    })
    return _parse_trxx_response(raw)


def trxx_create_order(data: dict) -> dict:
    """
    POST /order - Create an energy rental order.
    data should contain: receive_address, period, energy_amount, out_trade_no (optional)
    """
    raw = _trxx_post("/order", data)
    return _parse_trxx_response(raw)


def trxx_query_order(serial: str) -> dict:
    """GET /order/query - Query order by serial"""
    raw = _trxx_get("/order/query", {"serial": serial})
    return _parse_trxx_response(raw)


def trxx_reclaim_order(serial: str) -> dict:
    """POST /order/reclaim - Reclaim (return early) an order"""
    raw = _trxx_post("/order/reclaim", {"serial": serial})
    return _parse_trxx_response(raw)


def trxx_transfer_activate(receive_address: str, amount: float = 0.5) -> dict:
    """POST /order/transfer - Transfer small TRX to activate address"""
    raw = _trxx_post("/order/transfer", {
        "receive_address": receive_address,
        "amount": amount,
    })
    return _parse_trxx_response(raw)


# ============================================================
# Pending Order Polling Scheduler
# ============================================================

_scheduler_running = False
_scheduler_lock = threading.Lock()


def _poll_pending_orders():
    """Poll pending orders and sync status from TRXX (cron job equivalent)"""
    from db_provider import get_pending_trxx_orders, update_trxx_order_status, get_trxx_order_by_serial

    try:
        pending_orders = get_pending_trxx_orders(Cfg.NETWORK_ID, older_than_seconds=120)
        if not pending_orders:
            return

        logger.info(f"[TRXX Scheduler] Found {len(pending_orders)} pending orders to check")

        for order in pending_orders:
            serial = order.get("serial")
            if not serial:
                continue

            try:
                result = trxx_query_order(serial)
                if result.get("errno") != 0:
                    logger.error(f"[TRXX Scheduler] Failed to query order {serial}: {result.get('message')}")
                    continue

                trxx_data = result.get("data")
                if not trxx_data:
                    continue

                trxx_status = int(trxx_data.get("status", 0))
                if trxx_status == 40:
                    new_status = "delegated"
                elif trxx_status == 41:
                    new_status = "failed"
                else:
                    new_status = "pending"

                if new_status != order.get("status"):
                    update_trxx_order_status(
                        Cfg.NETWORK_ID, serial, new_status,
                        trxx_status=trxx_status,
                        txid=trxx_data.get("txid"),
                        bandwidth_hash=trxx_data.get("bandwidth_hash"),
                        active_hash=trxx_data.get("active_hash"),
                    )
                    logger.info(f"[TRXX Scheduler] Updated order {serial}: {order.get('status')} -> {new_status}")

                    # Notify third party if delegated
                    if new_status == "delegated" and Cfg.THIRDPARTY_WEBHOOK_URL:
                        _notify_third_party(order, serial, trxx_data, source="cron")

            except Exception as e:
                logger.error(f"[TRXX Scheduler] Error processing order {serial}: {e}")

    except Exception as e:
        logger.error(f"[TRXX Scheduler] Cron tick error: {e}")


def _notify_third_party(order: dict, serial: str, trxx_data: dict, source: str = "webhook"):
    """Send async notification to third party webhook"""
    def _do_notify():
        try:
            payload = {
                "orderId": order.get("id"),
                "serial": serial,
                "receiveAddress": trxx_data.get("receive_address") or order.get("receive_address"),
                "status": "delegated",
                "txid": trxx_data.get("txid"),
                "energyAmount": trxx_data.get("energy_amount") or order.get("energy_amount"),
                "source": source,
            }
            resp = requests.post(
                Cfg.THIRDPARTY_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            logger.info(f"[TRXX Notify] Sent to third party, status={resp.status_code}, serial={serial}")
        except Exception as e:
            logger.error(f"[TRXX Notify] Failed to notify third party for serial={serial}: {e}")

    t = threading.Thread(target=_do_notify, daemon=True)
    t.start()


def _scheduler_loop():
    """Background loop that runs every 2 minutes"""
    while _scheduler_running:
        try:
            _poll_pending_orders()
        except Exception as e:
            logger.error(f"[TRXX Scheduler] Unexpected error: {e}")
        time.sleep(120)  # 2 minutes


def start_trxx_scheduler():
    """Start the background scheduler for polling pending orders"""
    global _scheduler_running
    with _scheduler_lock:
        if _scheduler_running:
            return
        _scheduler_running = True
        t = threading.Thread(target=_scheduler_loop, daemon=True, name="trxx-scheduler")
        t.start()
        logger.info("[TRXX Scheduler] Started (polling every 2 minutes)")


def stop_trxx_scheduler():
    """Stop the background scheduler"""
    global _scheduler_running
    with _scheduler_lock:
        _scheduler_running = False
        logger.info("[TRXX Scheduler] Stopped")
