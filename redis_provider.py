from config import Cfg
import redis

pool = redis.ConnectionPool(host='127.0.0.1',port=6379,decode_responses=True)



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
    
    def add_pool(self, network_id, pool_id, pool_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_POOL_KEY"], pool_id, pool_str)
    
    def add_top_pool(self, network_id, pool_id, pool_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_TOP_POOL_KEY"], pool_id, pool_str)
    
    def add_token_price(self, network_id, contract_id, price_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_KEY"], contract_id, price_str)

    def list_farms(self, network_id):
        return self.r.hgetall(Cfg.NETWORK[network_id]["REDIS_KEY"])


if __name__ == '__main__':
    conn = RedisProvider()
    # conn.begin_pipe()
    # conn.add_farm("farm_id_1", "farm_value_1")
    # conn.add_farm("farm_id_2", "farm_value_2")
    # conn.add_farm("farm_id_3", "farm_value_3")
    # conn.end_pipe()
    p = list_farms("TESTNET")
    print(p)
    # list_pools("MAINNET")
    print(list_token_price("MAINNET"))


    # r=redis.StrictRedis(connection_pool=pool)
    # r.hset(KEY, "aaa", "AAA")
    # r.hset(KEY, "bbb", "BBB")
    # r.close()

