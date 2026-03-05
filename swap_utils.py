#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
EVM DEX Aggregation - Quote and Transaction Building

Supports Bitget and OKX DEX aggregators.
Architecture: Backend builds quotes + transaction data, frontend signs and sends via wallet.

API Endpoints:
  - /api/swap/quote        : Aggregated quote from Bitget/OKX (best price selection)
  - /api/swap/build-tx     : Build swap transaction calldata for wallet signing
  - /api/swap/approve-tx   : Build ERC20 approve transaction data
  - /api/swap/supported-routers : Get supported router info per chain
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional

from loguru import logger
from bitget_utils import proxy_bitget_request, proxy_okx_request


# ============================================================
# Constants
# ============================================================

# Bitget chain ID -> chain name mapping
BITGET_CHAIN_MAP = {
    1: "eth",
    56: "bnb",
    137: "matic",
    8453: "base",
}

# OKX native token sentinel address
OKX_NATIVE_TOKEN_ADDRESS = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"

# EIP-1559 supported chain IDs
EIP1559_CHAINS = [8453, 1, 42161, 10, 137]

# Bluechip tokens per chain (for intermediate token selection in pre-swap)
BLUECHIP_TOKENS = {
    1: {  # Ethereum
        "USDT": {"address": "0xdAC17F958D2ee523a2206206994597C13D831ec7", "symbol": "USDT", "decimals": 6},
        "USDC": {"address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "symbol": "USDC", "decimals": 6},
        "WETH": {"address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "symbol": "WETH", "decimals": 18},
    },
    56: {  # BSC
        "USDT": {"address": "0x55d398326f99059fF775485246999027B3197955", "symbol": "USDT", "decimals": 18},
        "USDC": {"address": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", "symbol": "USDC", "decimals": 18},
    },
    8453: {  # Base
        "USDC": {"address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "symbol": "USDC", "decimals": 6},
        "WETH": {"address": "0x4200000000000000000000000000000000000006", "symbol": "WETH", "decimals": 18},
    },
    42161: {  # Arbitrum
        "USDT": {"address": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", "symbol": "USDT", "decimals": 6},
        "USDC": {"address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", "symbol": "USDC", "decimals": 6},
        "WETH": {"address": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", "symbol": "WETH", "decimals": 18},
    },
    137: {  # Polygon
        "USDT": {"address": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", "symbol": "USDT", "decimals": 6},
        "USDC": {"address": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", "symbol": "USDC", "decimals": 6},
    },
    10: {  # Optimism
        "USDT": {"address": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58", "symbol": "USDT", "decimals": 6},
        "USDC": {"address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85", "symbol": "USDC", "decimals": 6},
        "WETH": {"address": "0x4200000000000000000000000000000000000006", "symbol": "WETH", "decimals": 18},
    },
    143: {  # Monad
        "USDT": {"address": "", "symbol": "USDT", "decimals": 6},
        "USDC": {"address": "", "symbol": "USDC", "decimals": 6},
        "WETH": {"address": "0x4200000000000000000000000000000000000006", "symbol": "WETH", "decimals": 18},
    },
}

# Standard ERC20 approve function selector: approve(address,uint256)
ERC20_APPROVE_SELECTOR = "0x095ea7b3"
# Max uint256 for unlimited approval
MAX_UINT256 = "0x" + "f" * 64


# ============================================================
# Helper Functions
# ============================================================

def is_native_token(address: str) -> bool:
    """Check if address represents native token (ETH/BNB etc.)"""
    if not address or address == "":
        return True
    normalized = address.lower().replace("0x", "")
    return (
        normalized == "0"
        or normalized == "0" * 40
        or address.lower() == OKX_NATIVE_TOKEN_ADDRESS.lower()
    )


def normalize_evm_address(address: str) -> str:
    """Normalize EVM address to lowercase with 0x prefix"""
    if not address:
        return ""
    addr = address.lower()
    return addr if addr.startswith("0x") else f"0x{addr}"


def get_bitget_chain_name(chain_id: int) -> str:
    """Convert chain ID to Bitget chain name"""
    return BITGET_CHAIN_MAP.get(chain_id, "eth")


def shrink_token(amount: str, decimals: int) -> str:
    """Convert smallest-unit amount to human-readable decimal string"""
    try:
        d = Decimal(str(amount)) / Decimal(10 ** decimals)
        # Use quantize to get proper decimal representation without trailing zeros
        result = format(d, 'f')
        # Remove trailing zeros but keep at least one decimal for readability
        if '.' in result:
            result = result.rstrip('0').rstrip('.')
        return result if result else "0"
    except (InvalidOperation, ValueError):
        return "0"


def expand_token(amount: str, decimals: int) -> str:
    """Convert human-readable amount to smallest-unit integer string"""
    try:
        d = Decimal(str(amount)) * Decimal(10 ** decimals)
        return str(int(d))
    except (InvalidOperation, ValueError):
        return "0"


def convert_slippage_to_decimal(slippage: float) -> float:
    """
    Convert slippage input to decimal form.
    - >= 1: bps (e.g., 50 -> 0.005)
    - [0.01, 1): percent (e.g., 0.5 -> 0.005)
    - (0, 0.01): already decimal (e.g., 0.005)
    """
    if slippage >= 1:
        return slippage / 10000
    elif slippage >= 0.01:
        return slippage / 100
    else:
        return slippage


def get_bluechip_tokens(chain_id: int) -> Dict[str, Dict]:
    """Get bluechip tokens config for a specific chain"""
    return BLUECHIP_TOKENS.get(chain_id, {})


def find_best_bluechip_token(chain_id: int) -> Optional[Dict]:
    """Find best intermediate bluechip token (priority: USDT > USDC > WETH)"""
    tokens = get_bluechip_tokens(chain_id)
    for symbol in ["USDT", "USDC", "WETH"]:
        if symbol in tokens and tokens[symbol].get("address"):
            return tokens[symbol]
    return None


def is_bluechip_token(chain_id: int, token_address: str) -> bool:
    """Check if a token is a bluechip token on the given chain"""
    if is_native_token(token_address):
        return True
    tokens = get_bluechip_tokens(chain_id)
    normalized = normalize_evm_address(token_address)
    for config in tokens.values():
        if config.get("address") and normalize_evm_address(config["address"]) == normalized:
            return True
    return False


def _is_bitget_response_success(response: Dict) -> bool:
    """Check if Bitget API response indicates success"""
    return (
        response.get("code") == "00000"
        or response.get("error_code") == 0
        or response.get("status") == 0
    )


def _build_erc20_approve_calldata(spender: str, amount: str = None) -> str:
    """
    Build ERC20 approve(address,uint256) calldata.
    spender: the address to approve
    amount: the amount to approve (default: MaxUint256 for unlimited)
    """
    if amount is None:
        amount = MAX_UINT256

    # Pad spender to 32 bytes (remove 0x, pad left to 64 hex chars)
    spender_hex = spender.lower().replace("0x", "").zfill(64)

    # Pad amount to 32 bytes
    if amount.startswith("0x"):
        amount_hex = amount[2:].zfill(64)
    else:
        amount_hex = hex(int(amount))[2:].zfill(64)

    return f"{ERC20_APPROVE_SELECTOR}{spender_hex}{amount_hex}"


# ============================================================
# Bitget DEX API
# ============================================================

def bitget_quote(
    chain_id: int,
    token_in: Dict,
    token_out: Dict,
    amount_in: str,
    slippage: float,
    user_address: str,
) -> Dict:
    """
    Call Bitget quote API.

    Args:
        amount_in: smallest unit (e.g., wei for ETH, or 1000000 for 1 USDT)
        slippage: decimal (e.g., 0.005 for 0.5%)
    Returns:
        {"success": True/False, "router": "bitget", "data": ..., "error": ...}
    """
    try:
        chain_name = get_bitget_chain_name(chain_id)
        token_in_decimals = token_in.get("decimals", 18)
        readable_amount = shrink_token(amount_in, token_in_decimals)

        normalized_in = "" if is_native_token(token_in.get("address", "")) else normalize_evm_address(token_in["address"])
        normalized_out = "" if is_native_token(token_out.get("address", "")) else normalize_evm_address(token_out["address"])
        normalized_user = normalize_evm_address(user_address)

        body = {
            "fromSymbol": token_in.get("symbol", ""),
            "fromAmount": readable_amount,
            "fromChain": chain_name,
            "fromAddress": normalized_user,
            "toSymbol": token_out.get("symbol", ""),
            "toChain": chain_name,
            "toAddress": normalized_user,
            "estimateGas": True,
            "skipCache": True,
        }
        if normalized_in:
            body["fromContract"] = normalized_in
        if normalized_out:
            body["toContract"] = normalized_out
        if slippage is not None:
            body["slippage"] = slippage * 100  # Bitget uses percentage (e.g., 0.5 for 0.5%)

        result = proxy_bitget_request(
            api_path="/bgw-pro/swapx/pro/quote",
            method="POST",
            body=body,
        )
        return {"success": True, "router": "bitget", "data": result}
    except Exception as e:
        logger.error(f"bitget_quote error: {e}")
        return {"success": False, "router": "bitget", "error": str(e)}


def bitget_swap(
    chain_id: int,
    token_in: Dict,
    token_out: Dict,
    amount_in: str,
    slippage: float,
    from_address: str,
    to_address: str,
    market: str,
) -> Dict:
    """
    Call Bitget swap API to get calldata.

    Args:
        market: market/channel from quote response (required)
    Returns:
        {"success": True/False, "router": "bitget", "data": ..., "error": ...}
    """
    try:
        chain_name = get_bitget_chain_name(chain_id)
        token_in_decimals = token_in.get("decimals", 18)
        readable_amount = shrink_token(amount_in, token_in_decimals)

        normalized_in = "" if is_native_token(token_in.get("address", "")) else normalize_evm_address(token_in["address"])
        normalized_out = "" if is_native_token(token_out.get("address", "")) else normalize_evm_address(token_out["address"])
        normalized_from = normalize_evm_address(from_address)
        normalized_to = normalize_evm_address(to_address)

        body = {
            "fromSymbol": token_in.get("symbol", ""),
            "fromAmount": readable_amount,
            "fromChain": chain_name,
            "fromAddress": normalized_from,
            "toSymbol": token_out.get("symbol", ""),
            "toChain": chain_name,
            "toAddress": normalized_to,
            "slippage": slippage * 100,
            "market": market,
            "feeRate": 0,
        }
        if normalized_in:
            body["fromContract"] = normalized_in
        if normalized_out:
            body["toContract"] = normalized_out

        result = proxy_bitget_request(
            api_path="/bgw-pro/swapx/pro/swap",
            method="POST",
            body=body,
        )
        return {"success": True, "router": "bitget", "data": result}
    except Exception as e:
        logger.error(f"bitget_swap error: {e}")
        return {"success": False, "router": "bitget", "error": str(e)}


# ============================================================
# OKX DEX API
# ============================================================

def okx_quote(
    chain_id: int,
    token_in: Dict,
    token_out: Dict,
    amount_in: str,
    slippage: float,
    user_address: str,
) -> Dict:
    """
    Call OKX quote API.

    Args:
        amount_in: smallest unit
        slippage: decimal (e.g., 0.005 for 0.5%)
    """
    try:
        normalized_in = OKX_NATIVE_TOKEN_ADDRESS if is_native_token(token_in.get("address", "")) \
            else normalize_evm_address(token_in["address"])
        normalized_out = OKX_NATIVE_TOKEN_ADDRESS if is_native_token(token_out.get("address", "")) \
            else normalize_evm_address(token_out["address"])

        query = {
            "chainIndex": str(chain_id),
            "fromTokenAddress": normalized_in,
            "toTokenAddress": normalized_out,
            "amount": str(amount_in),
            "swapMode": "exactIn",
            "slippage": str(slippage),
        }
        if user_address:
            query["userWalletAddress"] = user_address

        result = proxy_okx_request(
            api_path="/api/v6/dex/aggregator/quote",
            method="GET",
            query=query,
        )
        return {"success": True, "router": "okx", "data": result}
    except Exception as e:
        logger.error(f"okx_quote error: {e}")
        return {"success": False, "router": "okx", "error": str(e)}


def okx_swap(
    chain_id: int,
    token_in: Dict,
    token_out: Dict,
    amount_in: str,
    slippage: float,
    from_address: str,
    to_address: str,
) -> Dict:
    """Call OKX swap API to get calldata."""
    try:
        normalized_in = OKX_NATIVE_TOKEN_ADDRESS if is_native_token(token_in.get("address", "")) \
            else normalize_evm_address(token_in["address"])
        normalized_out = OKX_NATIVE_TOKEN_ADDRESS if is_native_token(token_out.get("address", "")) \
            else normalize_evm_address(token_out["address"])

        query = {
            "chainIndex": str(chain_id),
            "fromTokenAddress": normalized_in,
            "toTokenAddress": normalized_out,
            "amount": str(amount_in),
            "swapMode": "exactIn",
            "slippagePercent": str(slippage),
            "userWalletAddress": from_address,
        }
        if to_address and to_address.lower() != from_address.lower():
            query["swapReceiverAddress"] = to_address

        result = proxy_okx_request(
            api_path="/api/v6/dex/aggregator/swap",
            method="GET",
            query=query,
        )
        return {"success": True, "router": "okx", "data": result}
    except Exception as e:
        logger.error(f"okx_swap error: {e}")
        return {"success": False, "router": "okx", "error": str(e)}


def okx_approve_transaction(
    chain_id: int,
    token_address: str,
    approve_amount: str,
) -> Dict:
    """Get OKX approve transaction data (includes dexContractAddress)."""
    try:
        normalized_token = normalize_evm_address(token_address)
        query = {
            "chainIndex": str(chain_id),
            "tokenContractAddress": normalized_token,
            "approveAmount": str(approve_amount),
        }

        result = proxy_okx_request(
            api_path="/api/v6/dex/aggregator/approve-transaction",
            method="GET",
            query=query,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"okx_approve_transaction error: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# Parse Quote Responses
# ============================================================

def _parse_bitget_quote(data: Dict, token_out: Dict) -> Optional[Dict]:
    """Parse Bitget quote response into unified format."""
    if not _is_bitget_response_success(data) or not data.get("data"):
        return None

    bd = data["data"]
    raw_out = bd.get("outAmount") or bd.get("toAmount") or "0"
    raw_min_out = bd.get("minOutAmount") or bd.get("toMinAmount") or raw_out
    token_out_decimals = token_out.get("decimals", 18)

    try:
        amount_out = Decimal(raw_out) * Decimal(10 ** token_out_decimals)
        min_amount_out = Decimal(raw_min_out) * Decimal(10 ** token_out_decimals)
    except (InvalidOperation, ValueError):
        return None

    if amount_out <= 0:
        return None

    return {
        "router": "bitget",
        "amountOut": str(int(amount_out)),
        "amountOutReadable": raw_out,
        "minAmountOut": str(int(min_amount_out)),
        "market": bd.get("market", ""),
        "gasEstimate": bd.get("gas", ""),
        "estimateRevert": bd.get("estimateRevert", False),
        "_amountOutDecimal": amount_out,
    }


def _parse_okx_quote(data: Dict, token_out: Dict, slippage_decimal: float) -> Optional[Dict]:
    """Parse OKX quote response into unified format."""
    code = data.get("code")
    if str(code) != "0" or not data.get("data") or len(data["data"]) == 0:
        return None

    od = data["data"][0]
    raw_out = od.get("toTokenAmount") or od.get("toAmount") or "0"

    try:
        amount_out = Decimal(raw_out)
    except (InvalidOperation, ValueError):
        return None

    if amount_out <= 0:
        return None

    # Calculate minAmountOut
    min_amount_out = int(amount_out * (Decimal("1") - Decimal(str(slippage_decimal))))
    token_out_decimals = token_out.get("decimals", 18)

    return {
        "router": "okx",
        "amountOut": str(int(amount_out)),
        "amountOutReadable": shrink_token(str(int(amount_out)), token_out_decimals),
        "minAmountOut": str(min_amount_out),
        "gasEstimate": od.get("estimateGasFee") or od.get("estimatedGas") or "",
        "_amountOutDecimal": amount_out,
    }


# ============================================================
# Aggregated Quote
# ============================================================

def aggregate_quote(
    chain_id: int,
    token_in: Dict,
    token_out: Dict,
    amount_in: str,
    slippage: float,
    sender: str,
    recipient: str = None,
) -> Dict:
    """
    Call Bitget and OKX quote APIs in parallel, select best quote by amountOut.

    Args:
        chain_id: EVM chain ID
        token_in: {"address": "0x...", "symbol": "USDT", "decimals": 6}
        token_out: {"address": "0x...", "symbol": "USDC", "decimals": 6}
        amount_in: smallest unit string (e.g., "1000000" for 1 USDT)
        slippage: flexible input (bps, percent, or decimal)
        sender: user wallet address
        recipient: optional recipient address (defaults to sender)
    Returns:
        Unified quote result with best route info.
    """
    if not recipient:
        recipient = sender

    slippage_decimal = convert_slippage_to_decimal(slippage)

    # Determine which routers to query based on chain support
    routers_to_query = []
    if chain_id in BITGET_CHAIN_MAP:
        routers_to_query.append(("bitget", bitget_quote))
    # OKX supports many chains, always try
    routers_to_query.append(("okx", okx_quote))

    if not routers_to_query:
        return {
            "success": False,
            "error": f"No DEX router supports chain ID {chain_id}",
        }

    quotes = []
    errors = []

    # Parallel query using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(routers_to_query)) as executor:
        futures = {}
        for router_name, quote_fn in routers_to_query:
            future = executor.submit(
                quote_fn,
                chain_id=chain_id,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                slippage=slippage_decimal,
                user_address=sender,
            )
            futures[future] = router_name

        for future in as_completed(futures):
            router_name = futures[future]
            try:
                result = future.result()
                if result.get("success"):
                    quotes.append(result)
                else:
                    errors.append({"router": router_name, "error": result.get("error", "Unknown error")})
            except Exception as e:
                errors.append({"router": router_name, "error": str(e)})

    if not quotes:
        return {
            "success": False,
            "error": "All DEX routers failed to return quotes",
            "details": errors,
        }

    # Parse and compare quotes, select best by amountOut
    parsed_quotes = []

    for q in quotes:
        router = q["router"]
        data = q["data"]
        parsed = None

        if router == "bitget":
            parsed = _parse_bitget_quote(data, token_out)
        elif router == "okx":
            parsed = _parse_okx_quote(data, token_out, slippage_decimal)

        if parsed:
            parsed_quotes.append(parsed)
        else:
            # Quote returned but could not be parsed (API error or empty data)
            error_msg = data.get("msg", "") if isinstance(data, dict) else str(data)
            errors.append({"router": router, "error": f"Invalid quote response: {error_msg}"})

    if not parsed_quotes:
        return {
            "success": False,
            "error": "No valid quote received from any DEX router",
            "details": errors,
        }

    # Select best quote by highest amountOut
    best = max(parsed_quotes, key=lambda q: q["_amountOutDecimal"])
    # Remove internal field
    best.pop("_amountOutDecimal", None)

    # Build all_quotes for comparison
    all_quotes_summary = []
    for pq in parsed_quotes:
        summary = {k: v for k, v in pq.items() if not k.startswith("_")}
        all_quotes_summary.append(summary)

    return {
        "success": True,
        "quote": {
            **best,
            "chainId": chain_id,
            "tokenIn": token_in,
            "tokenOut": token_out,
            "amountIn": amount_in,
            "slippage": slippage_decimal,
            "sender": sender,
            "recipient": recipient,
            "isBluechipIn": is_bluechip_token(chain_id, token_in.get("address", "")),
            "isBluechipOut": is_bluechip_token(chain_id, token_out.get("address", "")),
        },
        "allQuotes": all_quotes_summary,
        "errors": errors if errors else None,
    }


# ============================================================
# Build Swap Transaction
# ============================================================

def build_swap_tx(
    chain_id: int,
    router: str,
    token_in: Dict,
    token_out: Dict,
    amount_in: str,
    slippage: float,
    sender: str,
    recipient: str,
    market: str = None,
) -> Dict:
    """
    Build swap transaction parameters.
    Calls the appropriate DEX swap API and returns transaction params
    ready for frontend wallet signing.

    Args:
        router: "bitget" or "okx"
        market: required for Bitget (from quote response)
    Returns:
        {"success": True, "tx": {"to", "data", "value", "gasLimit", "chainId"}, "router": ...}
    """
    slippage_decimal = convert_slippage_to_decimal(slippage)

    if router == "bitget":
        return _build_bitget_swap_tx(chain_id, token_in, token_out, amount_in, slippage_decimal, sender, recipient, market)
    elif router == "okx":
        return _build_okx_swap_tx(chain_id, token_in, token_out, amount_in, slippage_decimal, sender, recipient)
    else:
        return {"success": False, "error": f"Unknown router: {router}"}


def _build_bitget_swap_tx(chain_id, token_in, token_out, amount_in, slippage, sender, recipient, market):
    """Build Bitget swap transaction."""
    if not market:
        return {"success": False, "error": "market is required for Bitget swap (from quote response)"}

    result = bitget_swap(
        chain_id=chain_id,
        token_in=token_in,
        token_out=token_out,
        amount_in=amount_in,
        slippage=slippage,
        from_address=sender,
        to_address=recipient,
        market=market,
    )

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Bitget swap API call failed")}

    data = result["data"]
    if not _is_bitget_response_success(data) or not data.get("data"):
        return {
            "success": False,
            "error": data.get("msg", "Bitget swap API returned error"),
            "rawResponse": data,
        }

    swap_data = data["data"]

    # Check for estimateRevert
    if swap_data.get("estimateRevert") is True:
        return {
            "success": False,
            "error": "Transaction would revert (slippage or price impact too high)",
        }

    calldata = swap_data.get("calldata") or swap_data.get("data") or ""
    to = swap_data.get("contract") or swap_data.get("to") or ""
    value = swap_data.get("value") or "0"
    gas = swap_data.get("gas") or ""
    if not gas and swap_data.get("computeUnits") is not None:
        gas = str(swap_data["computeUnits"])

    # Ensure calldata starts with 0x
    if calldata and not calldata.startswith("0x"):
        calldata = "0x" + calldata

    # For native token input, value = amountIn
    if is_native_token(token_in.get("address", "")):
        value = amount_in

    # Validation
    if not to or not calldata:
        return {
            "success": False,
            "error": "Bitget swap: missing transaction data or contract address",
            "rawResponse": data,
        }

    return {
        "success": True,
        "tx": {
            "to": to,
            "data": calldata,
            "value": value,
            "gasLimit": gas,
            "chainId": chain_id,
        },
        "router": "bitget",
        # The 'to' address is the spender for ERC20 approval
        "approveSpender": to,
    }


def _build_okx_swap_tx(chain_id, token_in, token_out, amount_in, slippage, sender, recipient):
    """Build OKX swap transaction."""
    result = okx_swap(
        chain_id=chain_id,
        token_in=token_in,
        token_out=token_out,
        amount_in=amount_in,
        slippage=slippage,
        from_address=sender,
        to_address=recipient,
    )

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "OKX swap API call failed")}

    data = result["data"]
    code = data.get("code")

    if str(code) != "0" or not data.get("data"):
        return {
            "success": False,
            "error": data.get("msg", "OKX swap API returned error"),
            "rawResponse": data,
        }

    # Parse OKX response (supports multiple response formats)
    response_data = data["data"]
    tx_data = None

    if isinstance(response_data, list) and len(response_data) > 0:
        tx_data = response_data[0].get("tx") or response_data[0]
    elif isinstance(response_data, dict):
        tx_data = response_data.get("tx") or response_data.get("transaction") or response_data

    if not tx_data:
        return {
            "success": False,
            "error": "OKX swap: no transaction data found in response",
            "rawResponse": data,
        }

    # Check estimateRevert
    if tx_data.get("estimateRevert") is True:
        return {
            "success": False,
            "error": "Transaction would revert (slippage or price impact too high)",
        }

    calldata = tx_data.get("data") or ""
    to = tx_data.get("to") or ""
    value = tx_data.get("value") or "0"
    gas = tx_data.get("gas") or tx_data.get("gasLimit") or ""

    # Ensure calldata starts with 0x
    if calldata and not calldata.startswith("0x"):
        calldata = "0x" + calldata

    # For native token input, value = amountIn
    if is_native_token(token_in.get("address", "")):
        value = amount_in

    # Validation
    if not to or not calldata:
        return {
            "success": False,
            "error": "OKX swap: missing transaction data or contract address",
            "rawResponse": data,
        }

    return {
        "success": True,
        "tx": {
            "to": to,
            "data": calldata,
            "value": value,
            "gasLimit": gas,
            "chainId": chain_id,
        },
        "router": "okx",
    }


# ============================================================
# Build Approve Transaction
# ============================================================

def build_approve_tx(
    chain_id: int,
    router: str,
    token_address: str,
    approve_amount: str,
    spender: str = None,
) -> Dict:
    """
    Build ERC20 approve transaction parameters.

    For OKX: calls OKX API to get approve tx data + dexContractAddress.
    For Bitget: builds standard ERC20 approve calldata (requires spender from build-tx).

    Args:
        chain_id: EVM chain ID
        router: "okx" or "bitget"
        token_address: ERC20 token contract address
        approve_amount: amount to approve (smallest unit, or "max" for unlimited)
        spender: spender address (required for Bitget, optional for OKX)
    """
    if is_native_token(token_address):
        return {"success": False, "error": "Native tokens do not need approval"}

    if router == "okx":
        return _build_okx_approve_tx(chain_id, token_address, approve_amount)
    elif router == "bitget":
        return _build_bitget_approve_tx(chain_id, token_address, approve_amount, spender)
    else:
        return {"success": False, "error": f"Unknown router: {router}"}


def _build_okx_approve_tx(chain_id, token_address, approve_amount):
    """Build OKX approve transaction using OKX API."""
    result = okx_approve_transaction(chain_id, token_address, approve_amount)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "OKX approve API call failed")}

    data = result["data"]
    code = data.get("code")

    if str(code) != "0":
        return {
            "success": False,
            "error": data.get("msg", "OKX approve transaction API returned error"),
        }

    response_data = data.get("data")
    approve_data = None

    if isinstance(response_data, list) and len(response_data) > 0:
        approve_data = response_data[0]
    elif isinstance(response_data, dict):
        approve_data = response_data

    if not approve_data:
        return {
            "success": False,
            "error": "OKX: no approve transaction data in response",
        }

    return {
        "success": True,
        "tx": {
            "to": normalize_evm_address(token_address),
            "data": approve_data.get("data", ""),
            "value": "0",
            "gasLimit": approve_data.get("gasLimit", ""),
            "gasPrice": approve_data.get("gasPrice", ""),
            "chainId": chain_id,
        },
        "dexContractAddress": approve_data.get("dexContractAddress", ""),
        "router": "okx",
    }


def _build_bitget_approve_tx(chain_id, token_address, approve_amount, spender):
    """Build Bitget approve transaction using standard ERC20 approve calldata."""
    if not spender:
        return {
            "success": False,
            "error": "spender address is required for Bitget approve (use 'approveSpender' from build-tx response)",
        }

    # Build standard ERC20 approve calldata
    if approve_amount == "max" or approve_amount == "unlimited":
        calldata = _build_erc20_approve_calldata(spender)
    else:
        calldata = _build_erc20_approve_calldata(spender, approve_amount)

    return {
        "success": True,
        "tx": {
            "to": normalize_evm_address(token_address),
            "data": calldata,
            "value": "0",
            "gasLimit": "60000",  # Standard ERC20 approve gas limit
            "chainId": chain_id,
        },
        "dexContractAddress": spender,
        "router": "bitget",
    }


# ============================================================
# Supported Routers Info
# ============================================================

def get_supported_routers(chain_id: int = None) -> Dict:
    """
    Get supported DEX router information.
    If chain_id is provided, returns routers for that specific chain.
    Otherwise returns all supported chains and routers.
    """
    if chain_id is not None:
        routers = []
        if chain_id in BITGET_CHAIN_MAP:
            routers.append({
                "name": "bitget",
                "chainName": get_bitget_chain_name(chain_id),
                "supported": True,
            })
        routers.append({
            "name": "okx",
            "chainId": str(chain_id),
            "supported": True,
        })

        bluechip = get_bluechip_tokens(chain_id)
        bluechip_list = [
            {"symbol": k, "address": v["address"], "decimals": v["decimals"]}
            for k, v in bluechip.items() if v.get("address")
        ]

        return {
            "chainId": chain_id,
            "routers": routers,
            "bluechipTokens": bluechip_list,
            "isEip1559": chain_id in EIP1559_CHAINS,
        }
    else:
        # Return all supported chains
        all_chains = {}

        # Bitget chains
        for cid, cname in BITGET_CHAIN_MAP.items():
            if cid not in all_chains:
                all_chains[cid] = {"chainId": cid, "routers": [], "bluechipTokens": []}
            all_chains[cid]["routers"].append({"name": "bitget", "chainName": cname})

        # OKX supports many chains, add some common ones
        okx_chains = [1, 56, 137, 8453, 42161, 10, 250, 43114, 324, 59144, 5000, 534352, 146, 130, 143]
        for cid in okx_chains:
            if cid not in all_chains:
                all_chains[cid] = {"chainId": cid, "routers": [], "bluechipTokens": []}
            all_chains[cid]["routers"].append({"name": "okx", "chainId": str(cid)})

        # Add bluechip info
        for cid in all_chains:
            bluechip = get_bluechip_tokens(cid)
            all_chains[cid]["bluechipTokens"] = [
                {"symbol": k, "address": v["address"], "decimals": v["decimals"]}
                for k, v in bluechip.items() if v.get("address")
            ]
            all_chains[cid]["isEip1559"] = cid in EIP1559_CHAINS

        return {"chains": all_chains}

