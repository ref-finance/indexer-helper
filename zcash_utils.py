import json
import requests
import hashlib
import base58
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
from config import Cfg
from near_multinode_rpc_provider import MultiNodeJsonProvider
from db_provider import add_multichain_lending_zcash_data

# Try to use hashlib for RIPEMD160, fallback to pycryptodome if not available
try:
    # Try to use hashlib's ripemd160 if available (depends on OpenSSL)
    hashlib.new('ripemd160')
    _has_ripemd160 = True
    _RIPEMD160 = None
except (ValueError, AttributeError):
    # If not available, use pycryptodome
    try:
        from Crypto.Hash import RIPEMD160 as _RIPEMD160
        _has_ripemd160 = False
    except ImportError:
        raise ImportError("RIPEMD160 not available. Please install pycryptodome: pip install pycryptodome")


DEFAULT_ZCASH_RPC_URL = "https://go.getblock.io/88e3cf13488c4b63959f67ebc83b3211/"


def get_deposit_address(network_id, am_id, path_data, type_data, near_number, deposit_uuid):
    deposit_address = ""
    try:
        request_data = {"am_id": am_id, "path": json.dumps(path_data)}
        conn = MultiNodeJsonProvider(network_id)
        deposit_address_ret = conn.view_call(Cfg.NETWORK[network_id]["ZCASH_VERIFY_CONTRACT"], "get_deposit_address", json.dumps(request_data).encode(encoding='utf-8'))
        if "result" in deposit_address_ret:
            json_str = "".join([chr(x) for x in deposit_address_ret["result"]])
            deposit_address = json.loads(json_str)
            add_multichain_lending_zcash_data(network_id, am_id, deposit_address, json.dumps(request_data), type_data, near_number, deposit_uuid)
    except Exception as e:
        print("get_deposit_address error:", e)
        raise
    return deposit_address


def verify_mca_creation(network_id, am_id, hax_data, prevs):
    try:
        path = {"am_id": am_id}
        request_data = {"msg": json.dumps(path), "tx": hax_data, "prevs": prevs}
        print("verify_mca_creation request_data:", json.dumps(request_data))
        conn = MultiNodeJsonProvider(network_id)
        res_data = conn.view_call(Cfg.NETWORK[network_id]["ZCASH_VERIFY_CONTRACT"], "verify_mca_creation", json.dumps(request_data).encode(encoding='utf-8'))
        print("verify_mca_creation res_data:", res_data)
        if "result" in res_data:
            json_str = "".join([chr(x) for x in res_data["result"]])
            ret = json.loads(json_str)
            print("verify_mca_creation ret:", ret)
            return ret
    except Exception as e:
        print("verify_mca_creation error:", e)
        raise


def verify_business(network_id, path_data, hax_data, prevs, near_number):
    try:
        request_data = {"msg": json.dumps(path_data), "tx": hax_data, "prevs": prevs}
        if near_number is not None and near_number != 0:
            request_data["amount"] = str(near_number)
        print("verify_business request_data:", json.dumps(request_data))
        conn = MultiNodeJsonProvider(network_id)
        res_data = conn.view_call(Cfg.NETWORK[network_id]["ZCASH_VERIFY_CONTRACT"], "verify_business",
                                  json.dumps(request_data).encode(encoding='utf-8'))
        print("verify_business res_data:", res_data)
        if "result" in res_data:
            json_str = "".join([chr(x) for x in res_data["result"]])
            ret = json.loads(json_str)
            print("verify_mca_creation ret:", ret)
            return ret
    except Exception as e:
        print("verify_business error:", e)
        raise


def verify_add_zcash(network_id, application, signer_wallet, signer_signature):
    try:
        request_data = {"application": application, "signer_wallet": signer_wallet, "signer_signature": signer_signature}
        print("verify_add_zcash request_data:", json.dumps(request_data))
        conn = MultiNodeJsonProvider(network_id)
        res_data = conn.view_call(Cfg.NETWORK[network_id]["ZCASH_VERIFY_CONTRACT"], "verify_add_zcash", json.dumps(request_data).encode(encoding='utf-8'))
        print("verify_add_zcash res_data:", res_data)
        if "result" in res_data:
            json_str = "".join([chr(x) for x in res_data["result"]])
            ret = json.loads(json_str)
            print("create_mca_from_zcash ret:", ret)
    except Exception as e:
        print("verify_add_zcash error:", e)
        raise


def get_raw_transaction(tx_hash, verbose=1, block_hash=None, rpc_url=None, timeout=10, rpc_id="getblock.io"):
    """
    Query the Zcash raw transaction data through the configured RPC endpoint.

    :param tx_hash: Transaction hash to query.
    :param verbose: Verbosity flag (0 or 1) as required by the RPC.
    :param block_hash: Optional block hash to limit the lookup scope.
    :param rpc_url: Optional override for the RPC endpoint.
    :param timeout: Request timeout in seconds.
    :param rpc_id: JSON-RPC id field value.
    :return: The RPC response payload as a Python dict.
    """
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "getrawtransaction",
            "params": [tx_hash, verbose, block_hash],
            "id": rpc_id
        }
        url = rpc_url or DEFAULT_ZCASH_RPC_URL
        response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            print(f"get_raw_transaction error: {data['error']}")
            print(f"request tx_hash:", tx_hash)
            return None
        return data.get("result", data)
    except Exception as e:
        print("get_raw_transaction error:", e)
        raise


def pubkey_to_zcash_address(pubkey_bytes: bytes) -> str:
    """
    Convert public key bytes to Zcash address.

    Args:
        pubkey_bytes: Compressed public key bytes

    Returns:
        Zcash address as base58 string
    """
    # Step 1: Calculate SHA256
    sha256_hash = hashlib.sha256(pubkey_bytes).digest()

    # Step 2: Calculate RIPEMD160 (get hash160)
    if _has_ripemd160:
        # Use hashlib if available
        hash160 = hashlib.new('ripemd160', sha256_hash).digest()
    else:
        # Use pycryptodome
        ripemd160 = _RIPEMD160.new()
        ripemd160.update(sha256_hash)
        hash160 = ripemd160.digest()

    # Step 3: Construct payload with version prefix
    # Zcash mainnet P2PKH version prefix: [0x1C, 0xB8]
    version_bytes = bytes([0x1C, 0xB8])
    versioned_payload = version_bytes + hash160

    # Step 4: Calculate checksum (SHA256(SHA256(payload)))
    checksum_hash1 = hashlib.sha256(versioned_payload).digest()
    checksum_hash2 = hashlib.sha256(checksum_hash1).digest()

    # Step 5: Construct complete payload (including first 4 bytes of checksum)
    full_payload = versioned_payload + checksum_hash2[:4]

    # Step 6: Base58Check encoding
    return base58.b58encode(full_payload).decode('utf-8')


def get_zcash_address_by_pubkey(pubkey_bytes: bytes) -> str:
    """
    Get Zcash address from public key bytes (SEC1 format).

    Args:
        pubkey_bytes: Public key bytes in SEC1 format
                     - Uncompressed: 0x04 + 32 bytes x + 32 bytes y (65 bytes)
                     - Compressed: 0x02/0x03 + 32 bytes x (33 bytes)

    Returns:
        Zcash address as base58 string
    """
    try:
        # Check if already compressed
        if len(pubkey_bytes) == 33 and pubkey_bytes[0] in [0x02, 0x03]:
            return pubkey_to_zcash_address(pubkey_bytes)

        # Parse uncompressed format (0x04 + x + y)
        if len(pubkey_bytes) != 65 or pubkey_bytes[0] != 0x04:
            raise ValueError(f"Invalid pubkey_bytes: expected 65 bytes with 0x04 prefix, got {len(pubkey_bytes)} bytes")

        # Extract x and y coordinates
        x = int.from_bytes(pubkey_bytes[1:33], 'big')
        y = int.from_bytes(pubkey_bytes[33:65], 'big')

        # Verify the point is on the curve by creating the public key
        public_key = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256K1()).public_key(default_backend())

        # Convert to compressed format
        # Compressed format: 0x02 if y is even, 0x03 if y is odd, followed by x coordinate
        x_bytes = x.to_bytes(32, 'big')
        y_is_even = (y % 2 == 0)
        compressed = bytes([0x02 if y_is_even else 0x03]) + x_bytes

        return pubkey_to_zcash_address(compressed)
    except Exception as e:
        raise ValueError(f"Invalid pubkey_bytes: {e}")


if __name__ == '__main__':
    # ret_data = get_raw_transaction("t1Vk9C7swsZv4mTKaPQnJZTsG7j1QLGGFnY")
    # print(ret_data)

    # Convert hex string to bytes
    hex_string = "76a91416020139a3d3c82670ee507261b659da900da23c88ac"
    pubkey_bytes = bytes.fromhex(hex_string)
    ret = get_zcash_address_by_pubkey(pubkey_bytes)
    print(ret)
