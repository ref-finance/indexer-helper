import sys
sys.path.append('../')
from near_multinode_rpc_provider import MultiNodeJsonProviderError,  MultiNodeJsonProvider
from redis_provider import RedisProvider, list_token_metadata
from config import Cfg
import json
import time
import sys

    
def internal_update_token_metadata(conn, contract_id, metadata):
    ret = False
    try:
        ret = conn.view_call(contract_id, "ft_metadata", b'')
        if "result" in ret:
            json_str = "".join([chr(x) for x in ret["result"]])
            metadata_obj = json.loads(json_str)
            ret = True
        else:
            print("Does not got token metadata  %s" % contract_id)
            ret = False

    except MultiNodeJsonProviderError as e:
        print("RPC Error: ", e)

    # print(metadata_obj)
    
    if ret is True:
        if metadata != metadata_obj:
            redis_conn = RedisProvider()
            redis_conn.add_token_metadata(network_id, contract_id, json.dumps(metadata_obj))
            redis_conn.close()
            print("Update metadata to Redis: %s" % contract_id)
    return ret


def update(network_id):
    token_metadata = {}
    try:
        token_metadata = list_token_metadata(network_id)
    except Exception as e:
        print("Error occurred when fetch token_metadata from Redis. Error is: ", e)

    try:
        conn = MultiNodeJsonProvider(network_id)
        for token, metadata in token_metadata.items():
            internal_update_token_metadata(conn, token, metadata)
            time.sleep(0.1)
    except MultiNodeJsonProviderError as e:
        print("RPC Error: ", e)
    except Exception as e:
        print("Error: ", e)


def init_token_metadata_to_redis(network_id):
    whitelist_tokens = []
    metadata_obj = {
        "spec":"", 
        "name": "", 
        "symbol": "", 
        "icon":"",
        "reference": "",
        "reference_hash": "",
        "decimals": 0
    }  
    contract = Cfg.NETWORK[network_id]["REF_CONTRACT"]
    try:
        conn = MultiNodeJsonProvider(network_id)
        ret = conn.view_call(contract,  "get_whitelisted_tokens", b'')
        json_str = "".join([chr(x) for x in ret["result"]])
        # print(json_str)
        whitelist_tokens = json.loads(json_str)
        for token in whitelist_tokens:
            internal_update_token_metadata(conn, token, metadata_obj)
            time.sleep(0.1)
    except MultiNodeJsonProviderError as e:
        print("RPC Error: ", e)
    except Exception as e:
        print("Error: ", e)


if __name__ == "__main__":

    if len(sys.argv) == 2:
        network_id = str(sys.argv[1]).upper()
        if network_id in ["MAINNET", "TESTNET"]:
            print("Staring update metadata ...")
            # init_token_metadata_to_redis(network_id)
            update(network_id)
            print("Done.")
        else:
            print("Error, network_id should be MAINNET or TESTNET")
            exit(1)
    else:
        print("Error, must put NETWORK_ID as arg")
        exit(1)
