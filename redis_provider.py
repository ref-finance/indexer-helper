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
            # removed = self.review_farmid()
            # print("Remove farmid: %s" % removed)
            return True
        else:
            return False
    
    def review_farmid(self, network_id):
        old = set(self.r.hkeys(Cfg.NETWORK[network_id]["REDIS_KEY"]))
        expired = list(old - self.farmids)
        self.r.hdel(Cfg.NETWORK[network_id]["REDIS_KEY"], *expired)
        return expired


    def add_farm(self, network_id, farm_id, farm_str):
        self.farmids.add(farm_id)
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_KEY"], farm_id, farm_str)

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


    # r=redis.StrictRedis(connection_pool=pool)
    # r.hset(KEY, "aaa", "AAA")
    # r.hset(KEY, "bbb", "BBB")
    # r.close()

