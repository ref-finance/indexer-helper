from config import Cfg
import redis

pool = redis.ConnectionPool(host='127.0.0.1',port=6379,decode_responses=True)

def list_pools_by_id_list(network_id: str, id_list: list) ->list:
    import json
    pool_list = []
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hmget(Cfg.NETWORK[network_id]["REDIS_POOL_KEY"], id_list)
    r.close()
    try:
        pool_list = [json.loads(x) for x in ret if x is not None]
    except Exception as e:
        print(e)
    return pool_list

def list_pools_by_tokens(network_id: str, token1: str, token2: str) ->list:
    import json
    list_pools = []
    token_str = "{%s}-{%s}" % (token1, token2)
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_POOL_BY_TOKEN_KEY"], token_str)
    r.close()
    try:
        list_pools = json.loads(ret)
    except Exception as e:
        print(e)
    return list_pools

def list_farms(network_id):
    import json
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_KEY"])
    r.close()
    list_farms = [json.loads(x) for x in ret.values()]
    print(len(list_farms))
    return list_farms


def list_pools(network_id):
    import json
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_POOL_KEY"])
    r.close()
    pools = []
    for id, value in ret.items():
        single_pool = json.loads(value)
        single_pool["id"] = id
        pools.append(single_pool)
    return pools

def get_pool(network_id, pool_id):
    import json
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_POOL_KEY"], pool_id)
    r.close()
    single_pool = {}
    if ret:
        single_pool = json.loads(ret)
        single_pool["id"] = pool_id
    return single_pool

def list_top_pools(network_id):
    import json
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_TOP_POOL_KEY"])
    r.close()
    pools = []
    for key, value in ret.items():
        pools.append(json.loads(value))
    return pools

def list_token_price(network_id):
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_KEY"])
    r.close()
    return ret

def list_token_price_by_id_list(network_id: str, id_list: list) ->list:
    import json
    token_list = []
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hmget(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_KEY"], id_list)
    r.close()
    try:
        token_list = [json.loads(x) for x in ret if x is not None]
    except Exception as e:
        print(e)
    return token_list

def get_token_price(network_id, token_contract_id):
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_KEY"], token_contract_id)
    r.close()
    return ret

def list_token_metadata(network_id):
    '''
    return:
    {
        'nusdc.ft-fin.testnet': {
            'spec': 'ft-1.0.0', 
            'name': 'NEAR Wrapped USDC', 
            'symbol': 'nUSDC', 
            'icon': 'https://s2.coinmarketcap.com/static/img/coins/64x64/3408.png', 
            'reference': None, 
            'reference_hash': None, 
            'decimals': 2
        },
        ...
    }
    
    '''
    import json
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_TOKEN_METADATA_KEY"])
    r.close()
    metadata_obj = {}
    for key, value in ret.items():
        metadata_obj[key] = json.loads(value)
    return metadata_obj

def list_whitelist(network_id):
    '''
    return:
    {
        'nusdc.ft-fin.testnet': {
            'spec': 'ft-1.0.0', 
            'name': 'NEAR Wrapped USDC', 
            'symbol': 'nUSDC', 
            'icon': 'https://s2.coinmarketcap.com/static/img/coins/64x64/3408.png', 
            'reference': None, 
            'reference_hash': None, 
            'decimals': 2
        },
        ...
    }
    
    '''
    import json
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_WHITELIST_KEY"])
    r.close()
    whitelist_obj = {}
    for key, value in ret.items():
        whitelist_obj[key] = json.loads(value)
    return whitelist_obj


class RedisProvider(object):

    def __init__(self):
        self.r=redis.StrictRedis(connection_pool=pool)
        self.pipe = None
    
    def begin_pipe(self) -> bool:
        if self.pipe is None:
            self.pipe = self.r.pipeline(transaction=True)
            self.farmids = set()
            return True
        else:
            return False
    
    def end_pipe(self) -> bool:
        if self.pipe is not None:
            self.pipe.execute()
            self.pipe = None
            return True
        else:
            return False
    
    # remove farms that not existed in contract
    def review_farmid(self, network_id):
        old = set(self.r.hkeys(Cfg.NETWORK[network_id]["REDIS_KEY"]))
        expired = list(old - self.farmids)
        self.r.hdel(Cfg.NETWORK[network_id]["REDIS_KEY"], *expired)
        return expired


    def add_farm(self, network_id, farm_id, farm_str):
        self.farmids.add(farm_id)
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_KEY"], farm_id, farm_str)
    
    def add_whitelist(self, network_id, whitelist_id, whitelist_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_WHITELIST_KEY"], whitelist_id, whitelist_str)
    
    def add_pool(self, network_id, pool_id, pool_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_POOL_KEY"], pool_id, pool_str)
    
    def add_top_pool(self, network_id, pool_id, pool_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_TOP_POOL_KEY"], pool_id, pool_str)
    
    def add_token_price(self, network_id, contract_id, price_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_KEY"], contract_id, price_str)
    
    def add_token_metadata(self, network_id, contract_id, metadata_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_TOKEN_METADATA_KEY"], contract_id, metadata_str)
    
    def add_pools_by_tokens(self, network_id, tokens_str, pool_list_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_POOL_BY_TOKEN_KEY"], tokens_str, pool_list_str)

    def list_farms(self, network_id):
        return self.r.hgetall(Cfg.NETWORK[network_id]["REDIS_KEY"])
    
    def close(self):
        self.r.close()


if __name__ == '__main__':
    conn = RedisProvider()
    # conn.begin_pipe()
    # conn.add_farm("farm_id_1", "farm_value_1")
    # conn.add_farm("farm_id_2", "farm_value_2")
    # conn.add_farm("farm_id_3", "farm_value_3")
    # conn.end_pipe()
    # p = list_farms("TESTNET")
    # print(p)
    # list_pools("MAINNET")
    # print(list_token_price("MAINNET"))
    # print(list_token_metadata("TESTNET"))
    # a = get_pool("TESTNET", "0")
    # print(a)
    # b = get_pool("TESTNET", "1000")
    # print(b)

    # a = list_pools_by_id_list("MAINNET", ['1346', '1429'])
    # print(a)
    print(get_token_price("MAINNET", "token.v2.ref-finance.near"))



    # r=redis.StrictRedis(connection_pool=pool)
    # r.hset(KEY, "aaa", "AAA")
    # r.hset(KEY, "bbb", "BBB")
    # r.close()

