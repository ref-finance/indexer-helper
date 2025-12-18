import json
import requests
import hashlib
import base58
import base64
import time
from dataclasses import dataclass
from typing import List, Tuple, Union, Dict, Any, Optional
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import utils as asym_utils
from config import Cfg
from near_multinode_rpc_provider import MultiNodeJsonProvider
from db_provider import add_multichain_lending_zcash_data
from near_api.account import Account
from near_api.providers import JsonProvider as NearJsonProvider
from loguru import logger


class CustomZcashJsonProvider(NearJsonProvider):
    def __init__(self, rpc_addr, tx_timeout=30, query_timeout=10):
        super().__init__(rpc_addr)
        self._tx_timeout = tx_timeout
        self._query_timeout = query_timeout
    
    def send_tx_and_wait(self, signed_tx, timeout=None):
        return self.json_rpc('broadcast_tx_commit', [base64.b64encode(signed_tx).decode('utf8')], timeout=self._tx_timeout)
    
    def json_rpc(self, method, params, timeout=None):
        if timeout is None:
            timeout = self._query_timeout
        return super().json_rpc(method, params, timeout=timeout)
    
    def get_status(self):
        return self.json_rpc('status', [None])


from near_api.signer import Signer, KeyPair

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


DEFAULT_FUNCTION_CALL_GAS = 300000000000000
DEFAULT_FUNCTION_CALL_DEPOSIT = 1  # yoctoNEAR

ZCASH_HEADERS_HASH_PERSONALIZATION = b"ZTxIdHeadersHash"
ZCASH_TRANSPARENT_HASH_PERSONALIZATION = b"ZTxIdTranspaHash"
ZCASH_PREVOUTS_HASH_PERSONALIZATION = b"ZTxIdPrevoutHash"
ZCASH_SEQUENCE_HASH_PERSONALIZATION = b"ZTxIdSequencHash"
ZCASH_OUTPUTS_HASH_PERSONALIZATION = b"ZTxIdOutputsHash"
ZCASH_SAPLING_DIGEST_PERSONALIZATION = b"ZTxIdSaplingHash"
ZCASH_ORCHARD_DIGEST_PERSONALIZATION = b"ZTxIdOrchardHash"
ZCASH_TRANSPARENT_INPUT_HASH_PERSONALIZATION = b"Zcash___TxInHash"
ZCASH_TRANSPARENT_AMOUNTS_HASH_PERSONALIZATION = b"ZTxTrAmountsHash"
ZCASH_TRANSPARENT_SCRIPTS_HASH_PERSONALIZATION = b"ZTxTrScriptsHash"
ZCASH_TX_PERSONALIZATION_PREFIX = b"ZcashTxHash_"


@dataclass
class TxInput:
    prev_tx_hash: bytes
    prev_tx_index: int
    script: bytes
    sequence: int


@dataclass
class TxOutput:
    value: int
    script: bytes


@dataclass
class PreviousOutput:
    value: int
    script: bytes


def _blake2b_personal(data: bytes, personalization: bytes) -> bytes:
    return hashlib.blake2b(data, digest_size=32, person=personalization).digest()


class Blake2b32(hashes.HashAlgorithm):
    name = "blake2b32"
    digest_size = 32
    block_size = 128


def _read_compact_size(data: bytes, offset: int) -> Tuple[int, int]:
    first = data[offset]
    offset += 1
    if first < 0xFD:
        return first, offset
    if first == 0xFD:
        val = int.from_bytes(data[offset:offset + 2], "little")
        return val, offset + 2
    if first == 0xFE:
        val = int.from_bytes(data[offset:offset + 4], "little")
        return val, offset + 4
    val = int.from_bytes(data[offset:offset + 8], "little")
    return val, offset + 8


def _read_bytes(data: bytes, offset: int, length: int) -> Tuple[bytes, int]:
    return data[offset:offset + length], offset + length


@dataclass
class TransactionV5:
    version: int
    version_group_id: int
    consensus_branch_id: int
    lock_time: int
    expiry_height: int
    inputs: List[TxInput]
    outputs: List[TxOutput]

    @classmethod
    def parse(cls, tx_hex: str) -> "TransactionV5":
        tx_bytes = bytes.fromhex(tx_hex)
        offset = 0

        header_bytes, offset = _read_bytes(tx_bytes, offset, 4)
        header = int.from_bytes(header_bytes, "little")
        version = header & ((1 << 31) - 1)
        overwintered = (header >> 31) != 0
        if version != 5 or not overwintered:
            raise ValueError(f"Expected overwintered v5 transaction, got header {version}")

        vg_id_bytes, offset = _read_bytes(tx_bytes, offset, 4)
        version_group_id = int.from_bytes(vg_id_bytes, "little")

        branch_id_bytes, offset = _read_bytes(tx_bytes, offset, 4)
        consensus_branch_id = int.from_bytes(branch_id_bytes, "little")

        lock_time_bytes, offset = _read_bytes(tx_bytes, offset, 4)
        lock_time = int.from_bytes(lock_time_bytes, "little")

        expiry_height_bytes, offset = _read_bytes(tx_bytes, offset, 4)
        expiry_height = int.from_bytes(expiry_height_bytes, "little")

        input_count, offset = _read_compact_size(tx_bytes, offset)
        inputs: List[TxInput] = []
        for _ in range(input_count):
            prev_hash, offset = _read_bytes(tx_bytes, offset, 32)
            prev_index_bytes, offset = _read_bytes(tx_bytes, offset, 4)
            prev_index = int.from_bytes(prev_index_bytes, "little")
            script_len, offset = _read_compact_size(tx_bytes, offset)
            script, offset = _read_bytes(tx_bytes, offset, script_len)
            sequence_bytes, offset = _read_bytes(tx_bytes, offset, 4)
            sequence = int.from_bytes(sequence_bytes, "little")
            inputs.append(TxInput(prev_hash, prev_index, script, sequence))

        output_count, offset = _read_compact_size(tx_bytes, offset)
        outputs: List[TxOutput] = []
        for _ in range(output_count):
            value_bytes, offset = _read_bytes(tx_bytes, offset, 8)
            value = int.from_bytes(value_bytes, "little", signed=True)
            script_len, offset = _read_compact_size(tx_bytes, offset)
            script, offset = _read_bytes(tx_bytes, offset, script_len)
            outputs.append(TxOutput(value, script))

        return cls(
            version, version_group_id, consensus_branch_id,
            lock_time, expiry_height, inputs, outputs
        )

    def header_digest(self) -> bytes:
        header = 0x80000005
        data = bytearray()
        data.extend(header.to_bytes(4, "little"))
        data.extend(self.version_group_id.to_bytes(4, "little"))
        data.extend(self.consensus_branch_id.to_bytes(4, "little"))
        data.extend(self.lock_time.to_bytes(4, "little"))
        data.extend(self.expiry_height.to_bytes(4, "little"))
        return _blake2b_personal(bytes(data), ZCASH_HEADERS_HASH_PERSONALIZATION)

    def prevouts_hash(self) -> bytes:
        data = bytearray()
        for txin in self.inputs:
            data.extend(txin.prev_tx_hash)
            data.extend(txin.prev_tx_index.to_bytes(4, "little"))
        return _blake2b_personal(bytes(data), ZCASH_PREVOUTS_HASH_PERSONALIZATION)

    def amounts_hash(self, previous_outputs: List[PreviousOutput]) -> bytes:
        data = bytearray()
        for prev_out in previous_outputs:
            data.extend(prev_out.value.to_bytes(8, "little", signed=True))
        return _blake2b_personal(bytes(data), ZCASH_TRANSPARENT_AMOUNTS_HASH_PERSONALIZATION)

    def scripts_hash(self, previous_outputs: List[PreviousOutput]) -> bytes:
        data = bytearray()
        for prev_out in previous_outputs:
            script = prev_out.script
            data.append(len(script) & 0xFF)
            data.extend(script)
        return _blake2b_personal(bytes(data), ZCASH_TRANSPARENT_SCRIPTS_HASH_PERSONALIZATION)

    def sequence_hash(self) -> bytes:
        data = bytearray()
        for txin in self.inputs:
            data.extend(txin.sequence.to_bytes(4, "little"))
        return _blake2b_personal(bytes(data), ZCASH_SEQUENCE_HASH_PERSONALIZATION)

    def outputs_hash(self) -> bytes:
        data = bytearray()
        for txout in self.outputs:
            data.extend(txout.value.to_bytes(8, "little", signed=True))
            data.append(len(txout.script) & 0xFF)
            data.extend(txout.script)
        return _blake2b_personal(bytes(data), ZCASH_OUTPUTS_HASH_PERSONALIZATION)

    def transparent_sig_digest(
        self,
        input_index: int,
        previous_outputs: List[PreviousOutput],
        hash_type: int,
    ) -> bytes:
        data = bytearray()
        data.append(hash_type)
        data.extend(self.prevouts_hash())
        data.extend(self.amounts_hash(previous_outputs))
        data.extend(self.scripts_hash(previous_outputs))
        data.extend(self.sequence_hash())
        data.extend(self.outputs_hash())

        txin = self.inputs[input_index]
        prev_out = previous_outputs[input_index]
        txin_data = bytearray()
        txin_data.extend(txin.prev_tx_hash)
        txin_data.extend(txin.prev_tx_index.to_bytes(4, "little"))
        txin_data.extend(prev_out.value.to_bytes(8, "little", signed=True))
        txin_data.append(len(prev_out.script) & 0xFF)
        txin_data.extend(prev_out.script)
        txin_data.extend(txin.sequence.to_bytes(4, "little"))
        txin_digest = _blake2b_personal(bytes(txin_data), ZCASH_TRANSPARENT_INPUT_HASH_PERSONALIZATION)
        data.extend(txin_digest)

        return _blake2b_personal(bytes(data), ZCASH_TRANSPARENT_HASH_PERSONALIZATION)

    @staticmethod
    def sapling_digest_empty() -> bytes:
        return _blake2b_personal(b"", ZCASH_SAPLING_DIGEST_PERSONALIZATION)

    @staticmethod
    def orchard_digest_empty() -> bytes:
        return _blake2b_personal(b"", ZCASH_ORCHARD_DIGEST_PERSONALIZATION)

    def calculate_sighash(
        self,
        input_index: int,
        previous_outputs: List[PreviousOutput],
        hash_type: int,
    ) -> bytes:
        data = bytearray()
        data.extend(self.header_digest())
        data.extend(self.transparent_sig_digest(input_index, previous_outputs, hash_type))
        data.extend(self.sapling_digest_empty())
        data.extend(self.orchard_digest_empty())
        personalization = bytearray(16)
        personalization[:12] = ZCASH_TX_PERSONALIZATION_PREFIX
        personalization[12:] = self.consensus_branch_id.to_bytes(4, "little")
        return _blake2b_personal(bytes(data), bytes(personalization))


def _get_near_rpc_url(network_id):
    rpc_urls = Cfg.NETWORK[network_id]["NEAR_RPC_URL"]
    if isinstance(rpc_urls, (list, tuple)) and len(rpc_urls) > 0:
        return rpc_urls[0]
    return rpc_urls


def _build_near_account(network_id):
    signer_id = getattr(Cfg, "ZCASH_SIGNER_ACCOUNT_ID", "")
    signer_private_key = getattr(Cfg, "ZCASH_SIGNER_PRIVATE_KEY", "")
    if not signer_id or not signer_private_key:
        raise ValueError("ZCASH signer credentials are not configured in Cfg")
    rpc_url = _get_near_rpc_url(network_id)
    tx_timeout = getattr(Cfg, "ZCASH_TX_TIMEOUT", 30)
    query_timeout = getattr(Cfg, "ZCASH_QUERY_TIMEOUT", 10)
    provider = CustomZcashJsonProvider(rpc_url, tx_timeout=tx_timeout, query_timeout=query_timeout)
    print(f"Using CustomZcashJsonProvider with tx_timeout={tx_timeout}s, query_timeout={query_timeout}s")
    key_pair = KeyPair(signer_private_key)
    signer = Signer(signer_id, key_pair)
    return Account(provider, signer, signer_id)


def _decode_success_value(tx_result):
    status = tx_result.get("status")
    if not isinstance(status, dict):
        return None
    success_value = status.get("SuccessValue")
    if success_value is None or success_value == "":
        return None
    padding = "=" * ((4 - len(success_value) % 4) % 4)
    decoded_bytes = base64.b64decode(success_value + padding)
    if not decoded_bytes:
        return None
    try:
        return json.loads(decoded_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        return decoded_bytes.decode("utf-8")


def _call_zcash_contract(network_id, method_name, request_data, gas=None, deposit=None, max_retries=3, retry_delay=2):
    gas_amount = gas if gas is not None else getattr(Cfg, "ZCASH_VERIFY_GAS", DEFAULT_FUNCTION_CALL_GAS)
    deposit_amount = deposit if deposit is not None else getattr(Cfg, "ZCASH_VERIFY_DEPOSIT",
                                                                 DEFAULT_FUNCTION_CALL_DEPOSIT)
    contract_id = Cfg.NETWORK[network_id]["ZCASH_VERIFY_CONTRACT"]
    
    last_exception = None
    for attempt in range(max_retries):
        try:
            # Rebuild account for each retry to ensure fresh connection
            account = _build_near_account(network_id)
            tx_result = account.function_call(
                contract_id,
                method_name,
                request_data,
                gas=gas_amount,
                amount=deposit_amount
            )
            print(f"{method_name} tx_result:", tx_result)
            ret = _decode_success_value(tx_result)
            print(f"{method_name} ret:", ret)
            return ret if ret is not None else tx_result
        except Exception as e:
            last_exception = e
            is_timeout_error = False
            
            # 收集异常链中的所有错误字符串
            error_strings = []
            current_exception = e
            while current_exception:
                error_strings.append(str(current_exception))
                error_strings.append(repr(current_exception))
                if hasattr(current_exception, 'args') and current_exception.args:
                    error_strings.append(str(current_exception.args))
                current_exception = getattr(current_exception, '__cause__', None) or getattr(current_exception, '__context__', None)
            
            # 打印所有收集到的错误字符串用于调试
            print(f"_call_zcash_contract exception type: {type(e).__name__}, error strings: {error_strings[:3]}")
            
            # 检查所有可能的超时关键词（更全面的列表）
            timeout_keywords = [
                "timeout", "timed out", "readtimeout", "connecttimeout", "request timeout",
                "httpconnectionpool", "connection timeout", "read timed out", "connect timed out",
                "408", "504", "503", "502", "gateway timeout", "service unavailable",
                "bad gateway", "request timeout", "client error", "server error"
            ]
            for error_text in error_strings:
                lower_text = error_text.lower()
                for keyword in timeout_keywords:
                    if keyword in lower_text:
                        is_timeout_error = True
                        print(f"_call_zcash_contract detected timeout keyword '{keyword}' in error: {error_text[:200]}")
                        break
                if is_timeout_error:
                    break
            
            # 检查异常类型链中的所有可能的超时/连接异常
            current_exception = e
            exception_chain = []
            while current_exception:
                exception_chain.append(current_exception)
                current_exception = getattr(current_exception, '__cause__', None) or getattr(current_exception, '__context__', None) or getattr(current_exception, 'reason', None)
            
            # 检查 requests 库的异常
            try:
                from requests.exceptions import (
                    ReadTimeout, ConnectTimeout, Timeout, 
                    HTTPError, ConnectionError, RequestException
                )
                for exc in exception_chain:
                    # 所有超时相关的异常
                    if isinstance(exc, (ReadTimeout, ConnectTimeout, Timeout)):
                        is_timeout_error = True
                        print(f"_call_zcash_contract detected timeout exception: {type(exc).__name__}")
                        break
                    # HTTP 错误中的超时状态码
                    if isinstance(exc, HTTPError):
                        response = getattr(exc, 'response', None)
                        if response:
                            status_code = getattr(response, 'status_code', None)
                            # 408 Request Timeout, 504 Gateway Timeout, 503 Service Unavailable, 502 Bad Gateway
                            if status_code in (408, 504, 503, 502):
                                is_timeout_error = True
                                print(f"_call_zcash_contract detected HTTP {status_code} timeout status code")
                                break
                    # 连接错误也可能是超时导致的
                    if isinstance(exc, ConnectionError):
                        # 检查错误信息中是否包含超时相关关键词
                        exc_str = str(exc).lower()
                        if any(kw in exc_str for kw in ["timeout", "timed out", "408", "504"]):
                            is_timeout_error = True
                            print(f"_call_zcash_contract detected ConnectionError with timeout: {type(exc).__name__}")
                            break
            except ImportError:
                pass
            
            # 检查 urllib3 库的异常
            try:
                from urllib3.exceptions import (
                    ReadTimeoutError, ConnectTimeoutError, 
                    TimeoutError as Urllib3TimeoutError,
                    HTTPError as Urllib3HTTPError
                )
                for exc in exception_chain:
                    if isinstance(exc, (ReadTimeoutError, ConnectTimeoutError, Urllib3TimeoutError)):
                        is_timeout_error = True
                        print(f"_call_zcash_contract detected urllib3 timeout exception: {type(exc).__name__}")
                        break
            except ImportError:
                pass
            
            # 检查 socket 异常（连接超时）
            try:
                import socket
                for exc in exception_chain:
                    if isinstance(exc, (socket.timeout, socket.error)):
                        exc_str = str(exc).lower()
                        if "timeout" in exc_str or "timed out" in exc_str:
                            is_timeout_error = True
                            print(f"_call_zcash_contract detected socket timeout: {type(exc).__name__}")
                            break
            except ImportError:
                pass
            
            # 检查 OSError/IOError（可能包含连接超时）
            for exc in exception_chain:
                if isinstance(exc, (OSError, IOError)):
                    exc_str = str(exc).lower()
                    # 检查是否是连接相关的超时错误
                    if any(kw in exc_str for kw in ["timeout", "timed out", "connection", "408", "504"]):
                        is_timeout_error = True
                        print(f"_call_zcash_contract detected OSError/IOError with timeout: {type(exc).__name__}")
                        break
            
            if is_timeout_error and attempt < max_retries - 1:
                print(f"_call_zcash_contract error (attempt {attempt + 1}/{max_retries}): {e.args}, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                continue
            else:
                if not is_timeout_error:
                    print(f"_call_zcash_contract error (not a timeout error): {e.args}")
                else:
                    print(f"_call_zcash_contract error (max retries reached): {e.args}")
                ret = e.args
                tx_result = e.args
                return ret if ret is not None else tx_result
    
    print("_call_zcash_contract error (all retries failed):", last_exception.args if last_exception else "Unknown error")
    if last_exception:
        ret = last_exception.args
        tx_result = last_exception.args
        return ret if ret is not None else tx_result
    return None


def _parse_script_push(script_sig: bytes) -> List[bytes]:
    parts = []
    pos = 0
    length = len(script_sig)
    while pos < length:
        op = script_sig[pos]
        pos += 1
        if op <= 75:
            if pos + op > length:
                break
            parts.append(script_sig[pos:pos + op])
            pos += op
        elif op == 0x4C:
            if pos >= length:
                break
            op_len = script_sig[pos]
            pos += 1
            if pos + op_len > length:
                break
            parts.append(script_sig[pos:pos + op_len])
            pos += op_len
        else:
            break
    return parts


def get_deposit_address(network_id, am_id, path_data, type_data, near_number, deposit_uuid):
    deposit_address = ""
    try:
        request_data = {"am_id": am_id, "path": json.dumps(path_data)}
        contract_id = Cfg.NETWORK[network_id]["ZCASH_VERIFY_CONTRACT"]
        method_name = "get_deposit_address"
        request_data_encoded = json.dumps(request_data).encode(encoding='utf-8')
        
        logger.info(f"get_deposit_address calling view_call: network_id={network_id}, contract_id={contract_id}, method_name={method_name}, request_data={request_data}")
        
        conn = MultiNodeJsonProvider(network_id)
        deposit_address_ret = conn.view_call(contract_id, method_name, request_data_encoded)
        
        logger.info(f"get_deposit_address view_call returned: {deposit_address_ret}")
        
        if "result" in deposit_address_ret:
            json_str = "".join([chr(x) for x in deposit_address_ret["result"]])
            deposit_address = json.loads(json_str)
            logger.info(f"get_deposit_address parsed result: deposit_address={deposit_address}")
            add_multichain_lending_zcash_data(network_id, am_id, deposit_address, json.dumps(request_data), type_data, near_number, deposit_uuid)
        else:
            logger.warning(f"get_deposit_address view_call result missing 'result' key: {deposit_address_ret}")
    except Exception as e:
        logger.error(f"get_deposit_address error: {e}", exc_info=True)
        return
    return deposit_address


def verify_mca_creation(network_id, am_id, hax_data, prevs, deposit_uuid):
    try:
        path = {"am_id": am_id, "uuid": deposit_uuid}
        request_data = {"msg": json.dumps(path), "tx": hax_data, "prevs": prevs}
        print("verify_mca_creation request_data:", json.dumps(request_data))
        return _call_zcash_contract(network_id, "verify_mca_creation", request_data)
    except Exception as e:
        print("verify_mca_creation error:", e)
        return


def verify_business(network_id, path_data, hax_data, prevs, near_number):
    try:
        res_data = json.loads(path_data)
        path_data = res_data["path"]
        request_data = {"msg": path_data, "tx": hax_data, "prevs": prevs}
        print("verify_business request_data:", json.dumps(request_data))
        return _call_zcash_contract(network_id, "verify_business", request_data)
    except Exception as e:
        print("verify_business error:", e)
        return


def verify_add_zcash(network_id, application, signer_wallet, signer_signature):
    try:
        request_data = {"application": application, "signer_wallet": signer_wallet, "signer_signature": signer_signature}
        print("verify_add_zcash request_data:", json.dumps(request_data))
        return _call_zcash_contract(network_id, "verify_add_zcash", request_data)
    except Exception as e:
        print("verify_add_zcash error:", e)
        return


def _normalize_previous_outputs(previous_outputs: List[Union[PreviousOutput, Tuple[Union[str, int], Union[str, bytes]], dict]]) -> List[PreviousOutput]:
    normalized = []
    for item in previous_outputs:
        if isinstance(item, PreviousOutput):
            normalized.append(item)
            continue
        value: Optional[int] = None
        script_bytes: Optional[bytes] = None
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            value = int(item[0])
            script_bytes = bytes.fromhex(item[1]) if isinstance(item[1], str) else item[1]
        elif isinstance(item, dict):
            if "value" in item:
                value = int(item["value"])
            if "script" in item:
                script_field = item["script"]
                script_bytes = bytes.fromhex(script_field) if isinstance(script_field, str) else script_field
        else:
            raise ValueError(f"Unsupported previous output format: {item}")
        if value is None or script_bytes is None:
            raise ValueError(f"Incomplete previous output data: {item}")
        normalized.append(PreviousOutput(value=value, script=script_bytes))
    return normalized


def extract_pubkey_from_v5_tx(
    tx_hex: str,
    input_index: int,
    previous_outputs: List[Union[PreviousOutput, Tuple[Union[str, int], Union[str, bytes]], dict]],
) -> str:
    tx = TransactionV5.parse(tx_hex)
    prev_outs = _normalize_previous_outputs(previous_outputs)
    if input_index >= len(tx.inputs):
        raise ValueError("input_index out of bounds for transaction inputs")
    if input_index >= len(prev_outs):
        raise ValueError("previous_outputs missing data for requested input index")

    script_parts = _parse_script_push(tx.inputs[input_index].script)
    if len(script_parts) < 2:
        raise ValueError("Unable to parse signature and pubkey from input script")
    signature_data = script_parts[0]
    pubkey_data = script_parts[1]
    if not signature_data:
        raise ValueError("Empty signature in scriptSig")
    hash_type = signature_data[-1]
    signature_bytes = signature_data[:-1]

    sighash = tx.calculate_sighash(input_index, prev_outs, hash_type)
    try:
        pubkey = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pubkey_data)
    except ValueError as exc:
        raise ValueError(f"Invalid public key encoding: {exc}") from exc

    try:
        pubkey.verify(
            signature_bytes,
            sighash,
            ec.ECDSA(asym_utils.Prehashed(Blake2b32())),
        )
    except Exception as exc:
        raise ValueError(f"Signature verification failed: {exc}") from exc

    return pubkey_data.hex()


def internal_verify_v5_py(
    tx_hex: str,
    input_index: int,
    previous_outputs: List[Union[PreviousOutput, Tuple[Union[str, int], Union[str, bytes]], dict]],
) -> str:
    return extract_pubkey_from_v5_tx(
        tx_hex=tx_hex,
        input_index=input_index,
        previous_outputs=previous_outputs,
    )


def pubkey_to_zcash_address(pubkey_bytes: bytes) -> str:
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
        ec.EllipticCurvePublicNumbers(x, y, ec.SECP256K1()).public_key(default_backend())

        # Convert to compressed format
        # Compressed format: 0x02 if y is even, 0x03 if y is odd, followed by x coordinate
        x_bytes = x.to_bytes(32, 'big')
        y_is_even = (y % 2 == 0)
        compressed = bytes([0x02 if y_is_even else 0x03]) + x_bytes

        return pubkey_to_zcash_address(compressed)
    except Exception as e:
        raise ValueError(f"Invalid pubkey_bytes: {e}")


def compressed_to_uncompressed_pubkey(compressed_pubkey: str) -> str:
    """
    Convert a compressed secp256k1 public key hex string to its uncompressed form.

    Args:
        compressed_pubkey: Hex-encoded compressed public key (33 bytes, starts with 02/03).

    Returns:
        Hex-encoded uncompressed public key (65 bytes, starts with 04).
    """
    try:
        compressed_bytes = bytes.fromhex(compressed_pubkey)
    except ValueError as exc:
        raise ValueError(f"Invalid hex string for compressed pubkey: {exc}") from exc

    try:
        pubkey = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), compressed_bytes)
    except ValueError as exc:
        raise ValueError(f"Invalid compressed public key: {exc}") from exc

    uncompressed_bytes = pubkey.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return uncompressed_bytes.hex()


def get_pubkey(tx_hex, prev_outputs):
    pubkey_data = internal_verify_v5_py(tx_hex, 0, prev_outputs)
    encryption_pubkey = compressed_to_uncompressed_pubkey(pubkey_data)
    pubkey_bytes = bytes.fromhex(encryption_pubkey)
    t_address = get_zcash_address_by_pubkey(pubkey_bytes)
    return t_address, encryption_pubkey


def get_mca_by_wallet(network_id, encryption_pubkey):
    mca_id = ""
    try:
        request_data = {"wallet": {"Zcash": encryption_pubkey}}
        conn = MultiNodeJsonProvider(network_id)
        mca_ret_data = conn.view_call(Cfg.NETWORK[network_id]["ZCASH_MA_CONTRACT"], "get_mca_by_wallet", json.dumps(request_data).encode(encoding='utf-8'))
        if "result" in mca_ret_data:
            json_str = "".join([chr(x) for x in mca_ret_data["result"]])
            mca_id = json.loads(json_str)
    except Exception as e:
        print("get_mca_by_wallet error:", e)
        return
    return mca_id


class ZcashRPC:

    def __init__(self, user: str = Cfg.ZCASH_RPC_USER, password: str = Cfg.ZCASH_RPC_PWD,
                 host: str = Cfg.ZCASH_RPC_URL, port: int = 8232):
        self.url = f"http://{host}:{port}"
        self.auth = (user, password)
        self.headers = {'content-type': 'application/json'}

    def call(self, method: str, params: Any = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": "python-client",
            "method": method,
            "params": params if params is not None else []
        }

        try:
            response = requests.post(
                self.url,
                data=json.dumps(payload),
                headers=self.headers,
                auth=self.auth,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if 'error' in result and result['error']:
                raise Exception(f"RPC Error: {result['error']}")

            return result.get('result')

        except requests.exceptions.RequestException as e:
            raise Exception(f"Connection error: {e}")

    def getaddresstxids(self, addresses: List[str],
                       start: Optional[int] = None,
                       end: Optional[int] = None) -> List[str]:
        params = {"addresses": addresses}

        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end

        return self.call("getaddresstxids", [params])

    def getaddressbalance(self, addresses: List[str]) -> Dict:
        params = {"addresses": addresses}
        return self.call("getaddressbalance", [params])

    def getrawtransaction(self, txid: str, verbose: int = 1) -> Dict:
        return self.call("getrawtransaction", [txid, verbose])

    def decoderawtransaction(self, hex_data: str) -> Dict:
        return self.call("decoderawtransaction", [hex_data])


if __name__ == '__main__':
    print("-------------------------------------")
    # ret_data = get_raw_transaction("t1Vk9C7swsZv4mTKaPQnJZTsG7j1QLGGFnY")
    # print(ret_data)

    # tx_hex = "050000800a27a7265510e7c80000000027c72f0001a96bcb23ceb4c614bc4cf97eff5f4cf55cb0eacbe207b8cc2f07c6b44471288b000000006a47304402204946fb994962314463bd80c874e784a3299600fb6e6ac9bbe21142db6b38793a02201bada3ac136e76d40842602b6e633fb020ec20838fe8a18e2d778b09b332cacf01210277417aa9c95dd36a05695dc829351215d73621966e4ba33a7f3d44d2ac5ea542ffffffff0240420f00000000001976a91416020139a3d3c82670ee507261b659da900da23c88ac302d8900000000001976a9145ec4d80de0dff42c0cb00c57472424cd7bb428ba88ac000000"
    # prev_outputs = [
    #     {
    #         "value": 10000000,
    #         "script": "76a9145ec4d80de0dff42c0cb00c57472424cd7bb428ba88ac",
    #     }
    # ]
    # result = internal_verify_v5_py(tx_hex, 0, prev_outputs)
    # print("Extracted pubkey:", result)

    # result = compressed_to_uncompressed_pubkey("0277417aa9c95dd36a05695dc829351215d73621966e4ba33a7f3d44d2ac5ea542")
    # print("ret:", result)

    # hex_string = "0477417aa9c95dd36a05695dc829351215d73621966e4ba33a7f3d44d2ac5ea54205da54e5cbe5800d2d8b11c0d57e8f055083010f5bcc902a2e66f20fc4662f2c"
    # pubkey_bytes = bytes.fromhex(hex_string)
    # ret = get_zcash_address_by_pubkey(pubkey_bytes)
    # print("ret", ret)

    # mca_id = get_mca_by_wallet("MAINNET", "04ce305e028aeede9136992d21a479381462586b7d6be1fdc4f07e674777f3faec924ff4e41e04f2f41608cfb5490a31d32428bf9e2489aa6c270603d71cafca0a")
    # print(mca_id)

    rpc = ZcashRPC()
    try:
        # # 获取地址余额
        # print("\n正在查询地址余额...")
        # balance = rpc.getaddressbalance(["t1KsyGrJMo6K6MJc2RSdZKXSuTozJ4M9iJ4"])
        # print(f"余额: {balance['balance'] / 1e8:.8f} ZEC")
        # print(f"已接收总额: {balance.get('received', 0) / 1e8:.8f} ZEC")
        address_ = "t1fT3QoWWwnfPq49Mg2iPK5CcC1LfxeE7iw"
        tx_id_list = rpc.getaddresstxids([address_])
        print("tx_id_list:", tx_id_list)
        if tx_id_list is not None:
            for tx_is in tx_id_list:
                tx_data_ = rpc.getrawtransaction(tx_is)
                print("tx_data_:", tx_data_)

        hex_ = "050000800a27a7265510e7c80000000027c72f0001a96bcb23ceb4c614bc4cf97eff5f4cf55cb0eacbe207b8cc2f07c6b44471288b000000006a47304402204946fb994962314463bd80c874e784a3299600fb6e6ac9bbe21142db6b38793a02201bada3ac136e76d40842602b6e633fb020ec20838fe8a18e2d778b09b332cacf01210277417aa9c95dd36a05695dc829351215d73621966e4ba33a7f3d44d2ac5ea542ffffffff0240420f00000000001976a91416020139a3d3c82670ee507261b659da900da23c88ac302d8900000000001976a9145ec4d80de0dff42c0cb00c57472424cd7bb428ba88ac000000"
        hex_ret = rpc.decoderawtransaction(hex_)
        print("hex_ret:", hex_ret)
    except Exception as e:
        print(f"\n❌ error: {e}")

    import uuid
    am_id = "multica.near"
    deposit_uuid = str(uuid.uuid4())
    path_data = {"am_id": am_id, "uuid": deposit_uuid}
    deposit_address = get_deposit_address(Cfg.NETWORK_ID, am_id, path_data, 1, 0, deposit_uuid)
    print("deposit_address:", deposit_address)
