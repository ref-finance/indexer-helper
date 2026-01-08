import json

from config import Cfg
import redis
from data_utils import get_redis_data, batch_get_redis_data
from cachetools import TTLCache

pool = redis.ConnectionPool(host=Cfg.REDIS["REDIS_HOST"], port=int(Cfg.REDIS["REDIS_PORT"]), decode_responses=True)
cache = TTLCache(maxsize=10000, ttl=20)


def list_pools_by_id_list(network_id: str, id_list: list) -> list:
    pool_list = []
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hmget(Cfg.NETWORK[network_id]["REDIS_POOL_KEY"], id_list)
    r.close()
    try:
        pool_list = [json.loads(x) for x in ret if x is not None]
    except Exception as e:
        print(e)
    return pool_list


def list_pools_by_tokens(network_id: str, token1: str, token2: str) -> list:
    list_pools_data = []
    id_list = [token1, token2]
    sorted_tp = sorted(id_list)
    key = "{%s}-{%s}" % (sorted_tp[0], sorted_tp[1])
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_POOL_BY_TOKEN_KEY"], key)
    r.close()
    try:
        list_pools_data = json.loads(ret)
    except Exception as e:
        print(e)
    return list_pools_data


def list_farms(network_id):
    cache_key = 'list_farms'
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_KEY"])
        r.close()
        farm_data = [json.loads(x) for x in ret.values()]
        cache_value = farm_data
        cache[cache_key] = farm_data
    return cache_value


def list_pools(network_id):
    cache_key = 'list_pools'
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_POOL_KEY"])
        r.close()
        pools = []
        for id, value in ret.items():
            single_pool = json.loads(value)
            single_pool["id"] = id
            pools.append(single_pool)
        cache_value = pools
        cache[cache_key] = pools
    return cache_value


def get_pool(network_id, pool_id):
    cache_key = 'get_pool_' + str(pool_id)
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hget(Cfg.NETWORK[network_id]["REDIS_POOL_KEY"], pool_id)
        r.close()
        single_pool = {}
        if ret:
            single_pool = json.loads(ret)
            single_pool["id"] = pool_id
        cache_value = single_pool
        cache[cache_key] = single_pool
    return cache_value


def list_top_pools(network_id):
    cache_key = 'list_top_pools'
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_TOP_POOL_KEY"])
        r.close()
        pools = []
        for key, value in ret.items():
            pools.append(json.loads(value))
        cache_value = pools
        cache[cache_key] = pools
    return cache_value


def list_token_price(network_id):
    cache_key = 'list_token_price'
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_KEY"])
        r.close()
        cache_value = ret
        cache[cache_key] = ret
    return cache_value


def list_base_token_price(network_id):
    cache_key = 'list_base_token_price'
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_BASE_TOKEN_PRICE_KEY"])
        r.close()
        cache_value = ret
        cache[cache_key] = ret
    return cache_value


def list_token_price_by_id_list(network_id: str, id_list: list) -> list:
    token_list = []
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hmget(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_KEY"], id_list)
    r.close()
    try:
        token_list = [json.loads(x) if x is not None else None for x in ret]
    except Exception as e:
        print(e)
    return token_list


def get_token_price(network_id, token_contract_id):
    cache_key = 'get_token_price_' + token_contract_id
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hget(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_KEY"], token_contract_id)
        r.close()
        cache_value = ret
        cache[cache_key] = ret
    return cache_value


def list_history_token_price(network_id: str, id_list: list) -> list:
    token_list = []
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hmget(Cfg.NETWORK[network_id]["REDIS_HISTORY_TOKEN_PRICE_KEY"], id_list)
    r.close()
    try:
        token_list = [json.loads(x) if x is not None else None for x in ret]
    except Exception as e:
        print(e)
    return token_list


def list_token_metadata(network_id):
    """
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
    """
    cache_key = 'list_token_metadata'
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_TOKEN_METADATA_KEY"])
        r.close()
        metadata_obj = {}
        for key, value in ret.items():
            metadata_obj[key] = json.loads(value)
        cache_value = metadata_obj
        cache[cache_key] = metadata_obj
    return cache_value


def list_burrow_asset_token_metadata(network_id):
    cache_key = 'list_burrow_asset_token_metadata'
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_BURROW_TOKEN_METADATA_KEY"])
        r.close()
        metadata_obj = {}
        for key, value in ret.items():
            metadata_obj[key] = json.loads(value)
        cache_value = metadata_obj
        cache[cache_key] = metadata_obj
    return cache_value


def list_token_metadata_v2(network_id):
    cache_key = 'list_token_metadata_v2'
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_TOKEN_METADATA_KEY"])
        r.close()
        metadata_obj = {}
        for key, value in ret.items():
            token_data = json.loads(value)
            token_data.pop("icon")
            metadata_obj[key] = token_data
        cache_value = metadata_obj
        cache[cache_key] = metadata_obj
    return cache_value


def get_proposal_hash_by_id(network_id: str, id_list: list) -> list:
    proposal_list = []
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hmget(Cfg.NETWORK[network_id]["REDIS_PROPOSAL_ID_HASH_KEY"], id_list)
    r.close()
    try:
        proposal_list = [json.loads(x) if x is not None else None for x in ret]
    except Exception as e:
        print(e)
    return proposal_list


def list_whitelist(network_id):
    """
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
    """
    cache_key = 'list_whitelist'
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_WHITELIST_KEY"])
        r.close()
        whitelist_obj = {}
        for key, value in ret.items():
            whitelist_obj[key] = json.loads(value)
        cache_value = whitelist_obj
        cache[cache_key] = whitelist_obj
    return cache_value


def get_24h_pool_volume(network_id, pool_id):
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_24H_KEY"], pool_id)
    r.close()
    if ret is None:
        ret = get_redis_data(network_id, Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_24H_KEY"], pool_id)
    return json.loads(ret)


def get_dcl_pools_volume_list(network_id, redis_key):
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_LIST_KEY"] + "_" + redis_key)
    r.close()
    if ret is None:
        dcl_pools_volume_list = []
        ret = batch_get_redis_data(network_id,
                                   Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_LIST_KEY"] + "_" + redis_key)
        for d in ret:
            dcl_pools_volume_list.append(d["redis_values"])
    else:
        dcl_pools_volume_list = [json.loads(x) for x in ret.values()]
    return dcl_pools_volume_list


def get_24h_pool_volume_list(network_id):
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_24H_KEY"])
    r.close()
    dcl_pool_list = []
    if ret is None:
        ret = batch_get_redis_data(network_id, Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_24H_KEY"])
        for d in ret:
            dcl_pool = {
                "pool_id": d["redis_key"],
                "volume": d["redis_values"],
            }
            dcl_pool_list.append(dcl_pool)
    else:
        for key, value in ret.items():
            dcl_pool = {
                "pool_id": key,
                "volume": value,
            }
            dcl_pool_list.append(dcl_pool)
    return dcl_pool_list


def get_dcl_pools_tvl_list(network_id, redis_key):
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_TVL_LIST_KEY"] + "_" + redis_key)
    r.close()
    if ret is None:
        dcl_pools_tvl_list = []
        ret = batch_get_redis_data(network_id,
                                   Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_LIST_KEY"] + "_" + redis_key)
        for d in ret:
            dcl_pools_tvl_list.append(d["redis_values"])
    else:
        dcl_pools_tvl_list = [json.loads(x) for x in ret.values()]
    return dcl_pools_tvl_list


def get_account_pool_assets(network_id, key):
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_ACCOUNT_POOL_ASSETS_KEY"], key)
    r.close()
    if ret is None:
        ret = get_redis_data(network_id, Cfg.NETWORK[network_id]["REDIS_ACCOUNT_POOL_ASSETS_KEY"], key)
    return ret


def get_token_price_ratio_report(network_id, key):
    cache_key = 'get_token_price_ratio_report_' + key
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hget(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_RATIO_REPORT_KEY"], key)
        r.close()
        if ret is None:
            ret = get_redis_data(network_id, Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_RATIO_REPORT_KEY"], key)
        cache_value = ret
        cache[cache_key] = ret
    return cache_value


def get_pool_point_24h_by_pool_id(network_id, pool_id):
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_POOL_POINT_24H_DATA_KEY"], pool_id)
    r.close()
    if ret is not None:
        ret = json.loads(ret)
    else:
        ret = get_redis_data(network_id, Cfg.NETWORK[network_id]["REDIS_POOL_POINT_24H_DATA_KEY"], pool_id)
        if ret is not None:
            ret = json.loads(ret)
    return ret


def get_history_token_price_report(network_id, key):
    cache_key = 'get_history_token_price_report_' + key
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.hget(Cfg.NETWORK[network_id]["REDIS_HISTORY_TOKEN_PRICE_REPORT_KEY"], key)
        r.close()
        cache_value = ret
        cache[cache_key] = ret
    return cache_value


def get_market_token_price():
    cache_key = 'get_market_token_price'
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        ret = r.get(Cfg.REDIS_TOKEN_MARKET_PRICE_KEY)
        r.close()
        cache_value = ret
        cache[cache_key] = ret
    return cache_value


def get_burrow_total_fee():
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.get("BURROW_TOTAL_FEE")
    r.close()
    return ret


def get_burrow_total_revenue():
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.get("BURROW_TOTAL_REVENUE")
    r.close()
    return ret


def get_nbtc_total_supply():
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.get("NBTC_TOTAL_SUPPLY")
    r.close()
    return ret


def get_whitelist_tokens():
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.get("WHITELIST_TOKEN_LIST")
    r.close()
    if ret is not None:
        ret = json.loads(ret)
    return ret


def get_rnear_apy(day_number):
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.get("REDIS_KEY_RNEAR_APY" + str(day_number))
    r.close()
    return ret


def add_rnear_apy(value, day_number):
    r = redis.StrictRedis(connection_pool=pool)
    r.set("REDIS_KEY_RNEAR_APY" + str(day_number), value, 600)
    r.close()


def get_dcl_point_data(key):
    cache_key = 'get_dcl_point_data_' + key
    cache_value = cache.get(cache_key, None)
    if cache_value is None:
        r = redis.StrictRedis(connection_pool=pool)
        actual_key = "DCL_POINT_" + key
        pipe = r.pipeline()
        pipe.get(actual_key)
        pipe.ttl(actual_key)
        result = pipe.execute()
        r.close()
        value, ttl = result
        if value is None:
            return None
        cache_value = {
            'value': value,
            'ttl': ttl
        }
        cache[cache_key] = cache_value
    return cache_value


def add_dcl_point_data(key, value):
    cache_key = 'get_dcl_point_data_' + key
    cache_value = {
        'value': value,
        'ttl': 3600
    }
    cache[cache_key] = cache_value
    r = redis.StrictRedis(connection_pool=pool)
    r.set("DCL_POINT_" + key, value, 3600)
    r.close()


def set_dcl_point_ttl(key):
    r = redis.StrictRedis(connection_pool=pool)
    actual_key = "DCL_POINT_" + key
    result = r.expire(actual_key, 3600)
    r.close()
    return result


def add_dcl_bin_point_data(key, value):
    r = redis.StrictRedis(connection_pool=pool)
    r.set("DCL_BIN_POINT_" + key, value, 3600)
    r.close()


def get_dcl_bin_point_data(key):
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.get("DCL_BIN_POINT_" + key)
    r.close()
    return ret


def get_multichain_lending_tokens_data():
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.get("MULTICHAIN_LENDING_TOKENS")
    r.close()
    return ret


def get_multichain_lending_token_icon(token):
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hget("MULTICHAIN_LENDING_TOKENS_ICON", token)
    r.close()
    return ret


def get_lst_total_fee():
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.get("LST_TOTAL_FEE")
    r.close()
    return ret


def get_lst_total_revenue():
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.get("LST_TOTAL_REVENUE")
    r.close()
    return ret


def get_cross_chain_total_fee():
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.get("CROSS_CHAIN_TOTAL_FEE")
    r.close()
    return ret


def get_cross_chain_total_revenue():
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.get("CROSS_CHAIN_TOTAL_REVENUE")
    r.close()
    return ret


class RedisProvider(object):

    def __init__(self):
        self.r = redis.StrictRedis(connection_pool=pool)
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

    def add_base_token_price(self, network_id, contract_id, price_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_BASE_TOKEN_PRICE_KEY"], contract_id, price_str)

    def add_history_token_price(self, network_id, contract_id, price_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_HISTORY_TOKEN_PRICE_KEY"], contract_id, price_str)

    def add_token_metadata(self, network_id, contract_id, metadata_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_TOKEN_METADATA_KEY"], contract_id, metadata_str)

    def add_pools_by_tokens(self, network_id, tokens_str, pool_list_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_POOL_BY_TOKEN_KEY"], tokens_str, pool_list_str)

    def list_farms(self, network_id):
        return self.r.hgetall(Cfg.NETWORK[network_id]["REDIS_KEY"])

    def add_proposal_id_hash(self, network_id, proposal_id, proposal_hash):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_PROPOSAL_ID_HASH_KEY"], proposal_id, proposal_hash)

    def add_twenty_four_hour_pools_data(self, network_id, pool_id, volume):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_24H_KEY"], pool_id, volume)

    def add_dcl_pools_data(self, network_id, pool_id, volume, redis_key):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_LIST_KEY"] + "_" + redis_key, pool_id, volume)

    def add_dcl_pools_tvl_data(self, network_id, redis_key, pool_id, tvl_data):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_TVL_LIST_KEY"] + "_" + redis_key, pool_id, tvl_data)

    def add_account_pool_assets(self, network_id, account_id, value):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_ACCOUNT_POOL_ASSETS_KEY"], account_id, value)

    def add_token_ratio_report(self, network_id, key, value):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_RATIO_REPORT_KEY"], key, value)

    def add_pool_point_24h_assets(self, network_id, pool_id, value):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_POOL_POINT_24H_DATA_KEY"], pool_id, value)

    def add_nbtc_total_supply(self, metadata_str):
        self.r.set("NBTC_TOTAL_SUPPLY", metadata_str, ex=300)

    def add_whitelist_tokens(self, token_list_str):
        self.r.set("WHITELIST_TOKEN_LIST", token_list_str, ex=300)

    def add_multichain_lending_tokens(self, value):
        self.r.set("MULTICHAIN_LENDING_TOKENS", value, ex=600)

    def add_multichain_lending_token_icon(self, token, value):
        self.r.hset("MULTICHAIN_LENDING_TOKENS_ICON", token, value)

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

    a = list_pools_by_id_list("DEVNET", ['79', ])
    print(a)
    # print(get_token_price("MAINNET", "token.v2.ref-finance.near"))

    # r=redis.StrictRedis(connection_pool=pool)
    # r.hset(KEY, "aaa", "AAA")
    # r.hset(KEY, "bbb", "BBB")
    # r.close()

