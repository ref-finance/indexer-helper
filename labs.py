from redis_provider import list_pools


def all_top1():
    ret = {}
    pools = list_pools("MAINNET")
    for id, pool in pools.items():
        key = "{%s}-{%s}" % (pool["token_account_ids"][0], pool["token_account_ids"][1])
        pool["id"] = id
        if int(pool["amounts"][1]) == 0:
            continue
        if key in ret:
            if int(ret[key]["amounts"][1]) < int(pool["amounts"][1]):
                ret[key] = pool
        else:
            ret[key] = pool

    for pool in ret.values():
        print(pool)
    
    print(len(ret))


if __name__ == '__main__':
    # {"pool_kind": "SIMPLE_POOL", "token_account_ids": ["berryclub.ek.near", "wrap.near"], 
    # "amounts": ["10781805299861938750618", "1038658988795550292193714729"], 
    # "total_fee": 30, "shares_total_supply": "104544652275134335110148000"}

    tokens = set()
    pools = list_pools("MAINNET")
    print(len(pools))
    for id, pool in pools.items():
        tokens.add(pool["token_account_ids"][0])
        tokens.add(pool["token_account_ids"][1])
    for token in tokens:
        print(token)
    print(len(tokens))

    all_top1()
