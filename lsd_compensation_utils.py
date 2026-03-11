#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
LSD Bridge Fee Compensation - Background Scheduler & Core Logic

Flow:
  1. Frontend submits depositAddress → stored in DB (status=0)
  2. Scheduler polls every 60s:
     a. Query 1Click /v0/status for each pending record
     b. On SUCCESS: extract amountIn, amountOut, refundTo
     c. Calculate fee difference → convert to Burrow shares → convert to LSD amount
     d. Send LSD token to user's BSC address
     e. Update DB with tx_hash (status=1)
  3. Records older than 24h without SUCCESS are expired (status=-2)
"""

import json
import time
import threading
import base64
import requests
from loguru import logger
from config import Cfg
from web3 import Web3


# ============================================================
# Constants
# ============================================================

ONECLICK_STATUS_URL = "https://1click.chaindefuser.com/v0/status"
BURROW_CONTRACT = "contract.main.burrow.near"
BURROW_USDT_TOKEN_ID = "usdt.tether-token.near"

# ERC20 transfer function signature: transfer(address,uint256)
ERC20_TRANSFER_SIG = "0xa9059cbb"

# Max retry count for sending LSD
MAX_RETRY_COUNT = 3


# ============================================================
# 1Click Status Query
# ============================================================

def query_oneclick_status(deposit_address):
    """
    Query 1Click swap status by depositAddress.
    Returns the full response JSON or None on error.
    """
    try:
        resp = requests.get(
            ONECLICK_STATUS_URL,
            params={"depositAddress": deposit_address},
            timeout=15
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"[LSD Compensation] Failed to query 1Click status for {deposit_address}: {e}")
        return None


# ============================================================
# NEAR Contract Queries (Burrow)
# ============================================================

def _near_view_call(account_id, method_name, args_json="{}"):
    """Call NEAR view function via RPC, returns parsed JSON result."""
    rpc_urls = Cfg.NETWORK[Cfg.NETWORK_ID]["NEAR_RPC_URL"]
    args_b64 = base64.b64encode(args_json.encode("utf-8")).decode("utf-8")

    for rpc_url in rpc_urls:
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "query",
                "params": {
                    "request_type": "call_function",
                    "account_id": account_id,
                    "method_name": method_name,
                    "args_base64": args_b64,
                    "finality": "optimistic"
                }
            }
            resp = requests.post(rpc_url, json=payload, timeout=10)
            resp.raise_for_status()
            result = resp.json()

            if "error" in result:
                logger.warning(f"NEAR RPC error from {rpc_url}: {result['error']}")
                continue

            raw_result = result.get("result", {}).get("result", [])
            json_str = "".join([chr(x) for x in raw_result])
            return json.loads(json_str)
        except Exception as e:
            logger.warning(f"NEAR view_call {method_name} failed on {rpc_url}: {e}")
            continue

    raise Exception(f"All NEAR RPC nodes failed for {account_id}.{method_name}")


def query_burrow_asset():
    """
    Query Burrow get_asset for USDT.
    Returns dict with supplied.shares, supplied.balance, config.extra_decimals.
    """
    args = json.dumps({"token_id": BURROW_USDT_TOKEN_ID})
    return _near_view_call(BURROW_CONTRACT, "get_asset", args)


def query_lsd_metadata():
    """
    Query get_metadata on Burrow contract for LSD.
    Returns dict with underlying_burrowland_shares etc.
    """
    return _near_view_call(BURROW_CONTRACT, "get_metadata")


def query_lsd_total_supply():
    """
    Query ft_total_supply on Burrow contract for LSD.
    Returns total supply as string.
    """
    return _near_view_call(BURROW_CONTRACT, "ft_total_supply")


# ============================================================
# LSD Amount Calculation
# ============================================================

def calculate_lsd_amount(fee_difference_str, burrow_asset, lsd_metadata, lsd_total_supply_str):
    """
    Calculate LSD token amount from fee difference.

    Formula:
      burrow_shares = fee_difference * 10^(extra_decimals) * supplied.shares / supplied.balance
      lsd_amount = burrow_shares * total_supply / underlying_burrowland_shares

    All calculations use integer arithmetic to avoid precision loss.

    Args:
        fee_difference_str: string, amountIn - amountOut (smallest unit)
        burrow_asset: dict from get_asset
        lsd_metadata: dict from get_metadata
        lsd_total_supply_str: string from ft_total_supply

    Returns:
        string: LSD amount in smallest unit
    """
    fee_difference = int(fee_difference_str)
    if fee_difference <= 0:
        return "0"

    # Burrow asset data
    extra_decimals = int(burrow_asset["config"]["extra_decimals"])
    supplied_shares = int(burrow_asset["supplied"]["shares"])
    supplied_balance = int(burrow_asset["supplied"]["balance"])

    if supplied_balance == 0:
        raise ValueError("Burrow supplied balance is zero")

    # LSD metadata
    underlying_shares = int(lsd_metadata["underlying_burrowland_shares"])
    total_supply = int(lsd_total_supply_str)

    if underlying_shares == 0:
        raise ValueError("LSD underlying_burrowland_shares is zero")

    # Step 1: Convert fee difference to Burrow shares
    burrow_shares = fee_difference * (10 ** extra_decimals) * supplied_shares // supplied_balance

    # Step 2: Convert Burrow shares to LSD tokens
    lsd_amount = burrow_shares * total_supply // underlying_shares

    return str(lsd_amount)


# ============================================================
# BSC ERC20 Token Transfer
# ============================================================

def send_lsd_token_bsc(to_address, amount_str):
    """
    Send LSD ERC20 token on BSC chain.

    Args:
        to_address: recipient BSC address (0x...)
        amount_str: token amount in smallest unit (string)

    Returns:
        tx_hash: string, transaction hash on BSC
    """

    rpc_url = Cfg.BSC_RPC_URL
    private_key = Cfg.BSC_WALLET_PRIVATE_KEY
    token_address = Cfg.BSC_LSD_TOKEN_ADDRESS

    if not rpc_url or not private_key or not token_address:
        raise ValueError("BSC_RPC_URL, BSC_WALLET_PRIVATE_KEY, BSC_LSD_TOKEN_ADDRESS must be configured")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to BSC RPC: {rpc_url}")

    account = w3.eth.account.from_key(private_key)
    sender_address = account.address

    # ERC20 transfer ABI
    erc20_abi = [
        {
            "constant": False,
            "inputs": [
                {"name": "_to", "type": "address"},
                {"name": "_value", "type": "uint256"}
            ],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        }
    ]

    token_contract = w3.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=erc20_abi
    )

    amount = int(amount_str)
    nonce = w3.eth.get_transaction_count(sender_address)
    gas_price = w3.eth.gas_price

    tx = token_contract.functions.transfer(
        Web3.to_checksum_address(to_address),
        amount
    ).build_transaction({
        "from": sender_address,
        "nonce": nonce,
        "gasPrice": gas_price,
        "gas": 100000,  # ERC20 transfer typically needs ~60k gas
        "chainId": 56,  # BSC mainnet
    })

    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    logger.info(f"[LSD Compensation] Sent LSD on BSC: to={to_address}, amount={amount_str}, tx={tx_hash.hex()}")
    return tx_hash.hex()


# ============================================================
# Core Processing Logic
# ============================================================

def _process_pending_record(record):
    """Process a single pending LSD compensation record."""
    from db_provider import update_lsd_compensation

    record_id = record["id"]
    deposit_address = record["deposit_address"]

    try:
        # Step 1: Query 1Click status
        status_data = query_oneclick_status(deposit_address)
        if not status_data:
            return

        oneclick_status = status_data.get("status", "")

        # Store status response for audit
        update_lsd_compensation(
            Cfg.NETWORK_ID, record_id,
            oneclick_status=oneclick_status,
            status_response=status_data
        )

        # Only process SUCCESS
        if oneclick_status != "SUCCESS":
            if oneclick_status in ("FAILED", "REFUNDED"):
                update_lsd_compensation(
                    Cfg.NETWORK_ID, record_id,
                    status=-1,
                    error_msg=f"1Click status: {oneclick_status}"
                )
                logger.info(f"[LSD Compensation] Record {record_id} marked failed: 1Click {oneclick_status}")
            return

        # Step 2: Extract amountIn, amountOut, refundTo from quoteResponse
        quote_response = status_data.get("quoteResponse", {})
        quote = quote_response.get("quote", {})
        quote_request = quote_response.get("quoteRequest", {})

        amount_in = quote.get("amountIn", "0")
        amount_out = quote.get("amountOut", "0")
        refund_to = quote_request.get("refundTo", "")

        if not refund_to:
            update_lsd_compensation(
                Cfg.NETWORK_ID, record_id,
                status=-1,
                error_msg="No refundTo address found in quoteResponse"
            )
            return

        # Step 3: Calculate fee difference
        fee_difference = int(amount_in) - int(amount_out)
        if fee_difference <= 0:
            update_lsd_compensation(
                Cfg.NETWORK_ID, record_id,
                status=1,
                user_address=refund_to,
                amount_in=amount_in,
                amount_out=amount_out,
                fee_difference="0",
                lsd_amount="0",
                error_msg="No fee difference (amountIn <= amountOut)"
            )
            logger.info(f"[LSD Compensation] Record {record_id}: no fee difference, skipped")
            return

        fee_difference_str = str(fee_difference)

        # Step 4: Query Burrow and calculate LSD amount
        burrow_asset = query_burrow_asset()
        lsd_metadata = query_lsd_metadata()
        lsd_total_supply = query_lsd_total_supply()

        lsd_amount = calculate_lsd_amount(fee_difference_str, burrow_asset, lsd_metadata, lsd_total_supply)

        logger.info(
            f"[LSD Compensation] Record {record_id}: amountIn={amount_in}, amountOut={amount_out}, "
            f"feeDiff={fee_difference_str}, lsdAmount={lsd_amount}"
        )

        # Step 5: Send LSD token on BSC
        tx_hash = send_lsd_token_bsc(refund_to, lsd_amount)

        # Step 6: Update record as completed
        update_lsd_compensation(
            Cfg.NETWORK_ID, record_id,
            status=1,
            user_address=refund_to,
            amount_in=amount_in,
            amount_out=amount_out,
            fee_difference=fee_difference_str,
            lsd_amount=lsd_amount,
            lsd_tx_hash=tx_hash
        )
        logger.info(f"[LSD Compensation] Record {record_id} completed: tx={tx_hash}")

    except Exception as e:
        retry_count = record.get("retry_count", 0) + 1
        new_status = -1 if retry_count >= MAX_RETRY_COUNT else 0
        update_lsd_compensation(
            Cfg.NETWORK_ID, record_id,
            status=new_status,
            retry_count=retry_count,
            error_msg=str(e)
        )
        logger.error(f"[LSD Compensation] Record {record_id} error (retry {retry_count}): {e}")


# ============================================================
# Scheduler
# ============================================================

_scheduler_running = False
_scheduler_lock = threading.Lock()


def _poll_lsd_compensations():
    """Poll pending LSD compensation records and process them."""
    from db_provider import get_pending_lsd_compensations, expire_old_lsd_compensations

    try:
        # First, expire old records
        expired_count = expire_old_lsd_compensations(Cfg.NETWORK_ID)
        if expired_count > 0:
            logger.info(f"[LSD Compensation] Expired {expired_count} old records")

        # Get pending records (status=0, within 24h)
        pending = get_pending_lsd_compensations(Cfg.NETWORK_ID)
        if not pending:
            return

        logger.info(f"[LSD Compensation] Found {len(pending)} pending records to process")

        for record in pending:
            try:
                _process_pending_record(record)
            except Exception as e:
                logger.error(f"[LSD Compensation] Unexpected error processing record {record.get('id')}: {e}")

    except Exception as e:
        logger.error(f"[LSD Compensation] Poll tick error: {e}")


def _scheduler_loop():
    """Background loop that runs every 60 seconds."""
    while _scheduler_running:
        try:
            _poll_lsd_compensations()
        except Exception as e:
            logger.error(f"[LSD Compensation] Scheduler unexpected error: {e}")
        time.sleep(60)


def start_lsd_compensation_scheduler():
    """Start the background scheduler for LSD compensation."""
    global _scheduler_running
    with _scheduler_lock:
        if _scheduler_running:
            return
        _scheduler_running = True
        t = threading.Thread(target=_scheduler_loop, daemon=True, name="lsd-compensation-scheduler")
        t.start()
        logger.info("[LSD Compensation] Scheduler started (polling every 60 seconds)")


def stop_lsd_compensation_scheduler():
    """Stop the background scheduler."""
    global _scheduler_running
    with _scheduler_lock:
        _scheduler_running = False
        logger.info("[LSD Compensation] Scheduler stopped")


