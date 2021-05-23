from near_rpc_provider import JsonProviderError,  JsonProvider
from redis_provider import RedisProvider
from config import Cfg
import json

def update_farms(network_id):

    farms = []

    try:
        conn = JsonProvider(Cfg.NETWORK[network_id]["NEAR_RPC_URL"])
        ret = conn.view_call(Cfg.NETWORK[network_id]["FARMING_CONTRACT"], 
            "list_seeds", b'{"from_index": 0, "limit": 100}')
        json_str = "".join([chr(x) for x in ret["result"]])
        seeds = json.loads(json_str)

        for seed in seeds.keys():
            print(seed)
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
        



if __name__ == "__main__":
    update_farms("TESTNET")