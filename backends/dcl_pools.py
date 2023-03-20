import sys

sys.path.append('../')
from near_multinode_rpc_provider import MultiNodeJsonProviderError, MultiNodeJsonProvider
from config import Cfg
import json
import time
import sys
from db_provider import handle_dcl_pools


def update_dcl_pools(network_id):
    dcl_pools_data = []
    try:
        conn = MultiNodeJsonProvider(network_id)
        ret = conn.view_call(Cfg.NETWORK[network_id]["DCL_POOL_CONTRACT"], "list_pools", b'{"from_index": 0,"limit":10000}')
        b = "".join([chr(x) for x in ret["result"]])
        dcl_pools = json.loads(b)
        for pool in dcl_pools:
            pool_date = {
                "pool_id": pool["pool_id"],
                "token_x": pool["token_x"],
                "token_y": pool["token_y"],
                "volume_x_in": pool["volume_x_in"],
                "volume_y_in": pool["volume_y_in"],
                "volume_x_out": pool["volume_x_out"],
                "volume_y_out": pool["volume_y_out"],
                "total_order_x": pool["total_order_x"],
                "total_order_y": pool["total_order_y"],
                "total_x": pool["total_x"],
                "total_y": pool["total_y"],
                "total_fee_x_charged": pool["total_fee_x_charged"],
                "total_fee_y_charged": pool["total_fee_y_charged"],
                "volume_x_in_grow": "0",
                "volume_y_in_grow": "0",
                "volume_x_out_grow": "0",
                "volume_y_out_grow": "0",
                "total_order_x_grow": "0",
                "total_order_y_grow": "0",
            }
            dcl_pools_data.append(pool_date)

    except MultiNodeJsonProviderError as e:
        print("RPC Error: ", e)
    except Exception as e:
        print("Error: ", e)

    try:
        if len(dcl_pools_data) > 0:
            handle_dcl_pools(dcl_pools_data, network_id)
    except Exception as e:
        print("insert dcl_pools to db error. Error is: ", e)


if __name__ == "__main__":

    if len(sys.argv) == 2:
        start_time = int(time.time())
        network_id = str(sys.argv[1]).upper()
        if network_id in ["MAINNET", "TESTNET", "DEVNET"]:
            print("Staring update_dcl_pools ...")
            update_dcl_pools(network_id)
            end_time = int(time.time())
            print("update_dcl_pools consuming time:{}", start_time - end_time)
        else:
            print("Error, network_id should be MAINNET, TESTNET or DEVNET")
            exit(1)
    else:
        print("Error, must put NETWORK_ID as arg")
        exit(1)
