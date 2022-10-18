import sys

sys.path.append('../')
from near_multinode_rpc_provider import MultiNodeJsonProviderError, MultiNodeJsonProvider
from redis_provider import RedisProvider, list_token_metadata, list_farms, list_pools
from config import Cfg
import json
import time
import sys


def internal_farm_seeds(network_id):
    farms = list_farms(network_id)
    seeds = set()
    for farm in farms:
        status = farm["farm_status"]
        total_reward = int(farm["total_reward"])
        claimed_reward = int(farm["claimed_reward"])
        unclaimed_reward = int(farm["unclaimed_reward"])
        if status == "Running" and total_reward > claimed_reward + unclaimed_reward:
            seeds.add(farm["seed_id"])
    return seeds


def update_farms(network_id):
    farms = []

    try:
        conn = MultiNodeJsonProvider(network_id)
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
    except MultiNodeJsonProviderError as e:
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
            conn.close()
    except Exception as e:
        print("Error occurred when update to Redis, cancel pipe. Error is: ", e)


def internal_get_token_metadata(conn, contract_id):
    metadata_obj = {
        "spec": "",
        "name": contract_id,
        "symbol": contract_id,
        "icon": "",
        "reference": "",
        "reference_hash": "",
        "decimals": 0
    }
    try:
        ret = conn.view_call(contract_id, "ft_metadata", b'')
        if "result" in ret:
            json_str = "".join([chr(x) for x in ret["result"]])
            metadata_obj = json.loads(json_str)
            print("Token metadata fetched for %s" % contract_id)
        else:
            print("Token metadata using default for %s" % contract_id)

    except MultiNodeJsonProviderError as e:
        print("RPC Error: ", e)

    redis_conn = RedisProvider()
    redis_conn.add_token_metadata(network_id, contract_id, json.dumps(metadata_obj))
    redis_conn.close()
    print("This metadata has import to Redis")

    return metadata_obj


def internal_get_pools(network_id: str, number: int) -> list:
    pools = []
    token_metadata = {}
    seeds = set()
    contract = Cfg.NETWORK[network_id]["REF_CONTRACT"]

    try:
        token_metadata = list_token_metadata(network_id)
        seeds = internal_farm_seeds(network_id)
    except Exception as e:
        print("Error occurred when fetch token_metadata from Redis. Error is: ", e)

    try:
        conn = MultiNodeJsonProvider(network_id)
        # ret = conn.view_call(contract, "get_number_of_pools", b'')
        # pool_num = int("".join([chr(x) for x in ret["result"]]))
        # print(pool_num)

        base_index = 0
        # while base_index < pool_num :
        #     time.sleep(0.1)
        #     ret = conn.view_call(contract,
        #         "get_pools", ('{"from_index": %s, "limit": 200}' % base_index).encode(encoding='utf-8'))
        #     json_str = "".join([chr(x) for x in ret["result"]])
        #     batch_pools = json.loads(json_str)
        #     base_index += len(batch_pools)
        #     for pool in batch_pools:
        #         pools.append(pool)

        while base_index < 5:
            time.sleep(0.1)
            print("index_number:", number)
            ret = conn.view_call(contract,
                                 "get_pools", ('{"from_index": %s, "limit": 200}' % number).encode(encoding='utf-8'))
            json_str = "".join([chr(x) for x in ret["result"]])
            batch_pools = json.loads(json_str)
            base_index += 1
            number = int(number) + 200
            for pool in batch_pools:
                pools.append(pool)
        print("Update total %s pools" % len(pools))

        # add token info to pools
        # for pool in pools:
        for i in range(0, len(pools)):
            pool = pools[i]
            lpt_id = "%s@%s" % (contract, i)
            if lpt_id in seeds:
                pool["farming"] = True
            else:
                pool["farming"] = False

            pool["token_symbols"] = []
            for x in pool["token_account_ids"]:
                if x in token_metadata:
                    if token_metadata[x] != "":
                        pool["token_symbols"].append(token_metadata[x]["symbol"])
                    # pool["token_symbols"].append(token_metadata[x]["symbol"])
                else:
                    time.sleep(0.1)
                    metadata_obj = internal_get_token_metadata(conn, x)
                    pool["token_symbols"].append(metadata_obj["symbol"])
                    token_metadata[x] = metadata_obj

    except MultiNodeJsonProviderError as e:
        print("RPC Error: ", e)
        pools.clear()
    except Exception as e:
        print("Error: ", e)
        pools.clear()
    return pools


def internal_add_volume_info(top_pools: dict):
    contract = Cfg.NETWORK[network_id]["REF_CONTRACT"]
    try:
        conn = MultiNodeJsonProvider(network_id)

        # add vol info to top_pools
        for _, pool in top_pools.items():
            pool["vol01"] = {"input": "0", "output": "0"}
            pool["vol10"] = {"input": "0", "output": "0"}
            ret = conn.view_call(contract, "get_pool_volumes",
                                 ('{"pool_id": %s}' % pool["id"]).encode(encoding='utf-8'))
            if "result" in ret:
                json_str = "".join([chr(x) for x in ret["result"]])
                vol_obj = json.loads(json_str)
                if len(vol_obj) == 2:
                    pool["vol01"] = vol_obj[0]
                    pool["vol10"] = vol_obj[1]

    except MultiNodeJsonProviderError as e:
        print("RPC Error: ", e)
    except Exception as e:
        print("Error: ", e)
    pass


def update_top_pools(network_id: str):
    start_time_1 = int(time.time())
    pools = list_pools(network_id)
    end_time_1 = int(time.time())
    print("list_pools consuming time:{}", start_time_1 - end_time_1)
    pools_by_tokens = {}
    tops = {}
    try:
        if len(pools) > 0:
            start_time_2 = int(time.time())
            conn = RedisProvider()

            # pour pools data to redis
            conn.begin_pipe()
            for i in range(0, len(pools)):
                pool = pools[i]
                # gen tops
                # key = "{%s}-{%s}" % (pool["token_account_ids"][0], pool["token_account_ids"][1])
                sorted_tp = sorted(pool["token_account_ids"])
                key = ""
                for k in range(0, len(sorted_tp)):
                    key = key + "{" + sorted_tp[k] + "}-"
                    if k == len(sorted_tp) - 1:
                        key = key[:-1]
                # key = "{%s}-{%s}" % (sorted_tp[0], sorted_tp[1])
                # pool_id = int(number) + i
                # pool["id"] = "%s" % pool_id
                if key in tops:
                    max_k = int(tops[key]["amounts"][0]) * int(tops[key]["amounts"][1])
                    cur_k = int(pool["amounts"][0]) * int(pool["amounts"][1])
                    if cur_k > max_k:
                        tops[key] = pool
                else:
                    tops[key] = pool
                # gen pools_by_tokens
                if key in pools_by_tokens:
                    pools_by_tokens[key].append(pool)
                else:
                    pools_by_tokens[key] = [pool, ]
                # pour to redis of pools
                # conn.add_pool(network_id, "%s" % pool_id, json.dumps(pools[i]))
            conn.end_pipe()
            end_time_2 = int(time.time())
            print("time_2 consuming time:{}", start_time_2 - end_time_2)
            # print("Import Pools to Redis OK.")

            # add vol info into top-pools
            # start_time_3 = int(time.time())
            # internal_add_volume_info(tops)
            # end_time_3 = int(time.time())
            # print("internal_add_volume_info consuming time:{}", start_time_3 - end_time_3)
            # pour top-pools data to redis
            conn.begin_pipe()
            start_time_4 = int(time.time())
            for key, top_pool in tops.items():
                conn.add_top_pool(network_id, key, json.dumps(top_pool))
                # print("%s" % (top_pool,))
            conn.end_pipe()
            print("Import Top-Pools to Redis OK.")
            end_time_4 = int(time.time())
            print("add_top_pools consuming time:{}", start_time_4 - end_time_4)

            # pour pools_by_tokens data to redis
            conn.begin_pipe()
            start_time_5 = int(time.time())
            for key, pool_list in pools_by_tokens.items():
                conn.add_pools_by_tokens(network_id, key, json.dumps(pool_list))
                # print("%s" % (top_pool,))
            conn.end_pipe()
            end_time_5 = int(time.time())
            print("add_pools_by_tokens consuming time:{}", start_time_5 - end_time_5)
            print("Import pools_by_tokens to Redis OK.")

            conn.close()

    except Exception as e:
        print("Error occurred when update Pools to Redis, cancel pipe. Error is: ", e)


if __name__ == "__main__":

    if len(sys.argv) == 2:
        start_time = int(time.time())
        network_id = str(sys.argv[1]).upper()
        if network_id in ["MAINNET", "TESTNET", "DEVNET"]:
            print("Staring update_top_pools ...")
            update_top_pools(network_id)
            end_time = int(time.time())
            print("update_top_pools consuming time:{}", start_time - end_time)
        else:
            print("Error, network_id should be MAINNET, TESTNET or DEVNET")
            exit(1)
    else:
        print("Error, must put NETWORK_ID as arg")
        exit(1)
