import sys

sys.path.append('../')
from near_multinode_rpc_provider import MultiNodeJsonProviderError, MultiNodeJsonProvider
from redis_provider import RedisProvider, list_token_metadata, list_farms, list_pools
from config import Cfg
import json
import time
import sys


def count_data(network_id):
    print(network_id)


if __name__ == "__main__":
    print("###############START CRM DATA COUNT###############")
    if len(sys.argv) == 2:
        start_time = int(time.time())
        network_id = str(sys.argv[1]).upper()
        if network_id in ["MAINNET", "TESTNET", "DEVNET"]:
            count_data(network_id)
            end_time = int(time.time())
            print("crm count data consuming time:{}", start_time - end_time)
        else:
            print("Error, network_id should be MAINNET, TESTNET or DEVNET")
            exit(1)
    else:
        print("Error, must put NETWORK_ID as arg")
        exit(1)
