import sys
sys.path.append('../')
from near_rpc_provider import JsonProviderError,  JsonProvider
from redis_provider import RedisProvider
from config import Cfg
import json
import time
import sys

def update_farms(network_id):

    farms = []

    try:
        conn = JsonProvider(Cfg.NETWORK[network_id]["NEAR_RPC_URL"])
        ret = conn.view_call(Cfg.NETWORK[network_id]["FARMING_CONTRACT"], 
            "list_seeds", b'{"from_index": 0, "limit": 100}')
        json_str = "".join([chr(x) for x in ret["result"]])
        seeds = json.loads(json_str)

        for seed in seeds.keys():
            time.sleep(0.1)
            ret = conn.view_call(Cfg.NETWORK[network_id]["FARMING_CONTRACT"], 
                "list_farms_by_seed", ('{"seed_id": "%s"}' % seed).encode(encoding='utf-8'))
            json_str = "".join([chr(x) for x in ret["result"]])
            seed_farms = json.loads(json_str)
            for farm in seed_farms:
                farms.append(farm)
    except JsonProviderError as e:
        print("RPC Error: ", e)
    except Exception as e:
        print("Error: ", e)

    try:
        if len(farms) > 0:
            conn = RedisProvider()
            conn.begin_pipe()
            for farm in farms:
                conn.add_farm(network_id, farm["farm_id"], json.dumps(farm))
            conn.end_pipe()
    except Exception as e:
        print("Error occurred when update to Redis, cancel pipe. Error is: ", e)
        



def update_pools(network_id):

    pools = []

    try:
        conn = JsonProvider(Cfg.NETWORK[network_id]["NEAR_RPC_URL"])
        ret = conn.view_call(Cfg.NETWORK[network_id]["REF_CONTRACT"], "get_number_of_pools", b'')
        pool_num = int("".join([chr(x) for x in ret["result"]]))
        print(pool_num)

        base_index = 0

        while base_index < pool_num :
            time.sleep(0.1)
            ret = conn.view_call(Cfg.NETWORK[network_id]["REF_CONTRACT"], 
                "get_pools", ('{"from_index": %s, "limit": 300}' % base_index).encode(encoding='utf-8'))
            json_str = "".join([chr(x) for x in ret["result"]])
            batch_pools = json.loads(json_str)
            base_index += len(batch_pools)
            for pool in batch_pools:
                pools.append(pool)
        
        print("Update total %s pools" % len(pools))

    except JsonProviderError as e:
        print("RPC Error: ", e)
        pools.clear()
    except Exception as e:
        print("Error: ", e)
        pools.clear()
    
    try:
        if len(pools) > 0:
            conn = RedisProvider()
            conn.begin_pipe()
            for i in range(0,len(pools)):
                conn.add_pool(network_id, "%s" % i, json.dumps(pools[i]))
            conn.end_pipe()
            print("Import Pools to Redis OK.")

            tops = {}
            for i in range(0,len(pools)):
                pool = pools[i]
                key = "{%s}-{%s}" % (pool["token_account_ids"][0], pool["token_account_ids"][1])
                pool["id"] = "%s" % i
                if int(pool["amounts"][1]) == 0:
                    continue
                if key in tops:
                    if int(tops[key]["amounts"][1]) < int(pool["amounts"][1]):
                        tops[key] = pool
                else:
                    tops[key] = pool
            conn.begin_pipe()
            for key, top_pool in tops.items():
                conn.add_top_pool(network_id, key, json.dumps(top_pool))
                # print("%s" % (top_pool,))
            conn.end_pipe()
            print("Import Top-Pools to Redis OK.")

    except Exception as e:
        print("Error occurred when update Pools to Redis, cancel pipe. Error is: ", e)



if __name__ == "__main__":

    if len(sys.argv) == 2:
        network_id = str(sys.argv[1]).upper()
        if network_id in ["MAINNET", "TESTNET"]:
            update_farms(network_id)
            update_pools(network_id)
        else:
            print("Error, network_id should be MAINNET or TESTNET")
            exit(1)
    else:
        print("Error, must put NETWORK_ID as arg")
        exit(1)
