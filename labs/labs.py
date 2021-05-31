import sys
sys.path.append('../')
from redis_provider import list_token_price, list_top_pools, list_pools, list_farms
from config import Cfg


def farm_seeds():
    farms = list_farms("TESTNET")
    seeds = set()
    for farm in farms:
        status = farm["farm_status"]
        total_reward = int(farm["total_reward"])
        claimed_reward = int(farm["claimed_reward"])
        unclaimed_reward = int(farm["unclaimed_reward"])
        if status == "Running" and total_reward > claimed_reward + unclaimed_reward :
            seeds.add(farm["seed_id"])
    return seeds

def all_top1():
    precisions = {}
    for token in Cfg.TOKENS["TESTNET"]:
        precisions[token["NEAR_ID"]] = token["DECIMAL"]
    pools = list_top_pools("TESTNET")
    prices = list_token_price("TESTNET")
    for pool in pools:
        # print(pool)
        tvl0 = 0
        tvl1 = 0
        if pool['token_account_ids'][0] in prices:
            tvl0 = float(prices[pool['token_account_ids'][0]]) * int(pool['amounts'][0]) / (10 ** precisions[pool['token_account_ids'][0]])
        if pool['token_account_ids'][1] in prices:
            tvl1 = float(prices[pool['token_account_ids'][1]]) * int(pool['amounts'][1]) / (10 ** precisions[pool['token_account_ids'][1]])
        print("TVL0", tvl0)
        print("TVL1", tvl1)
        if tvl0 > 0 and tvl1 > 0:
            pool["TVL"] = str(tvl0 + tvl1)
        elif tvl0 > 0:
            pool["TVL"] = str(tvl0 * 2)
        elif tvl1 > 0:
            pool["TVL"] = str(tvl1 * 2)
        else:
            pool["TVL"] = "0"
        # key = "{%s}-{%s}" % (pool["token_account_ids"][0], pool["token_account_ids"][1])
        # pool["id"] = id
        # if int(pool["amounts"][1]) == 0:
        #     continue
        # if key in ret:
        #     if int(ret[key]["amounts"][1]) < int(pool["amounts"][1]):
        #         ret[key] = pool
        # else:
        #     ret[key] = pool

    for pool in pools:
        print(pool)
    
    print(len(pools))


if __name__ == '__main__':
    # {"pool_kind": "SIMPLE_POOL", "token_account_ids": ["berryclub.ek.near", "wrap.near"], 
    # "amounts": ["10781805299861938750618", "1038658988795550292193714729"], 
    # "total_fee": 30, "shares_total_supply": "104544652275134335110148000"}

    # tokens = set()
    # pools = list_pools("MAINNET")
    # print(len(pools))
    # for id, pool in pools.items():
    #     tokens.add(pool["token_account_ids"][0])
    #     tokens.add(pool["token_account_ids"][1])
    # for token in tokens:
    #     print(token)
    # print(len(tokens))

    # all_top1()
    print(farm_seeds())
