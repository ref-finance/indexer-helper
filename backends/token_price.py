import sys
sys.path.append('../')
from near_multinode_rpc_provider import MultiNodeJsonProviderError,  MultiNodeJsonProvider
from redis_provider import RedisProvider
import requests
from config import Cfg
import json
import time
from db_provider import add_history_token_price


def pool_price(network_id, tokens):
    # tokens = [{"SYMBOL": "ref", "NEAR_ID": "rft.tokenfactory.testnet", "MD_ID": "ref-finance.testnet|24|wrap.testnet", "DECIMAL": 8}, ...]
    # return [{"NEAR_ID": "rft.tokenfactory.testnet", "BASE_ID": "wrap.testnet", "price": "nnnnnn"}, ...]
    pool_tokens_price = []
    # print("pool_price tokens:", tokens)
    try:
        conn = MultiNodeJsonProvider(network_id)
        for token in tokens:
            src, pool_id, base = token["MD_ID"].split("|")
            time.sleep(0.1)
            if token["NEAR_ID"] == "meta-pool.near" or token["NEAR_ID"] == "linear-protocol.near":
                try:
                    ret = conn.view_call(src, "get_rated_pool", ('{"pool_id": %s}' % pool_id)
                                         .encode(encoding='utf-8'))
                    json_str = "".join([chr(x) for x in ret["result"]])
                    result_obj = json.loads(json_str)
                    rates = result_obj["rates"]
                    price = int(rates[0])
                except Exception as e:
                    print("get_rated_pool error:", e)
                    continue
            elif token["NEAR_ID"] == "nearx.stader-labs.near" or token["NEAR_ID"] == "v2-nearx.stader-labs.near":
                try:
                    ret = conn.view_call(src, "get_nearx_price", "NA".encode(encoding='utf-8'))
                    json_str = "".join([chr(x) for x in ret["result"]])
                    price = json.loads(json_str)
                except Exception as e:
                    print("get_nearx_price error:", e)
                    continue
            elif token["NEAR_ID"] == "xtoken.ref-finance.near":
                try:
                    # print("statr get_virtual_price")
                    ret = conn.view_call(src, "get_virtual_price", "NA".encode(encoding='utf-8'))
                    # print("get_virtual_price ret:", ret)
                    json_str = "".join([chr(x) for x in ret["result"]])
                    # print("get_virtual_price ret result:", json_str)
                    price = json.loads(json_str)
                    # print("get_virtual_price price:", price)
                except Exception as e:
                    print("get_virtual_price error:", e)
                    continue
            else:
                ret = conn.view_call(
                    src,
                    "get_return",
                    ('{"pool_id": %s, "token_in": "%s", "amount_in": "1%s", "token_out": "%s"}'
                     % (pool_id, token["NEAR_ID"], '0' * token["DECIMAL"], base))
                        .encode(encoding='utf-8')
                )
                json_str = "".join([chr(x) for x in ret["result"]])
                price = json.loads(json_str)
            if token["NEAR_ID"] == "token.v2.ref-finance.near":
                debug_price = int(price) / 1000000000000000000000000.0
                print('[debug][%s]REF-wNEAR:%.12f' % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), debug_price))
            pool_tokens_price.append({"NEAR_ID": token["NEAR_ID"], "BASE_ID": base, "price": price})

    except MultiNodeJsonProviderError as e:
        print("RPC Error: ", e)
        pool_tokens_price.clear()
    except Exception as e:
        print("Error: ", e)
        pool_tokens_price.clear()
    return pool_tokens_price


def market_price(network_id, tokens, base_tokens):
    market_tokens_price = []
    obj = None
    try:
        response = requests.get(Cfg.MARKET_URL)
        data = response.text
        obj = json.loads(data)
        handel_base_token_price(network_id, base_tokens, obj)
        print('[debug][%s]%s' % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), obj))
    except Exception as e:
        print("Error: ", e)

    if obj and len(obj) > 0:
        for token in tokens:
            md_id = token["MD_ID"]
            if md_id in obj and "usd" in obj[md_id]:
                market_tokens_price.append({
                    "NEAR_ID": token["NEAR_ID"], 
                    "BASE_ID": "", 
                    "price": str(obj[md_id]["usd"])
                })

    return market_tokens_price


def update_price(network_id):
    pool_tokens = []
    market_tokens = []
    decimals = {}
    price_ref = {}
    for token in Cfg.TOKENS[network_id]:
        # token = {"SYMBOL": "ref", "NEAR_ID": "rft.tokenfactory.testnet", "MD_ID": "ref-finance.testnet|24|wrap.testnet", "DECIMAL": 8}
        decimals[token["NEAR_ID"]] = token["DECIMAL"]
        if len(token["MD_ID"].split("|")) == 3:
            pool_tokens.append(token)
        else:
            market_tokens.append(token)
    
    # [{"NEAR_ID": "rft.tokenfactory.testnet", "BASE_ID": "wrap.testnet", "price": "nnnnnn"}, ...]
    tokens_price = market_price(network_id, market_tokens, Cfg.TOKENS["BASE_MAINNET"])
    for token in tokens_price:
        price_ref[token["NEAR_ID"]] = token["price"]

    tokens_price += pool_price(network_id, pool_tokens)

    try:
        if len(tokens_price) > 0:
            conn = RedisProvider()
            conn.begin_pipe()
            for token in tokens_price:
                # print(md2contract[md_id], str(value["usd"]))
                if token["BASE_ID"] != "":
                    if token["NEAR_ID"] == "xtoken.ref-finance.near":
                        ref_token_price = get_base_id_price(tokens_price, price_ref, decimals, token["BASE_ID"])
                        if ref_token_price > 0:
                            price = int(token["price"]) / 100000000 * ref_token_price
                            conn.add_token_price(network_id, token["NEAR_ID"], "%.12f" % price)
                    elif token["BASE_ID"] in price_ref:
                        # print(int(token["price"]) / int("1"*decimals[token["BASE_ID"]]))
                        price = int(token["price"]) / int("1" + "0" * decimals[token["BASE_ID"]]) * float(price_ref[token["BASE_ID"]])
                        # take those pool token price as ref for other pool token
                        if token["NEAR_ID"] not in price_ref:
                            price_ref[token["NEAR_ID"]] = price
                        # print(token["NEAR_ID"], "%.12f" % price)
                        conn.add_token_price(network_id, token["NEAR_ID"], "%.12f" % price)
                    else:
                        print("%s has no ref price %s/usd" % (token["NEAR_ID"], token["BASE_ID"]))
                else:
                    # print(token["NEAR_ID"], token["price"])
                    conn.add_token_price(network_id, token["NEAR_ID"], token["price"])
            conn.end_pipe()
            conn.close()
    except Exception as e:
        print("Error occurred when update to Redis, cancel pipe. Error is: ", e)

    try:
        if len(tokens_price) > 0:
            for token in tokens_price:
                if token["BASE_ID"] != "":
                    if token["NEAR_ID"] == "xtoken.ref-finance.near":
                        ref_token_price = get_base_id_price(tokens_price, price_ref, decimals, token["BASE_ID"])
                        if ref_token_price > 0:
                            price = int(token["price"]) / 100000000 * ref_token_price
                            add_history_token_price(token["NEAR_ID"], token["BASE_ID"], "%.12f" % price, decimals[token["NEAR_ID"]], network_id)
                    elif token["BASE_ID"] in price_ref:
                        price = int(token["price"]) / int("1" + "0" * decimals[token["BASE_ID"]]) * float(price_ref[token["BASE_ID"]])

                        add_history_token_price(token["NEAR_ID"], token["BASE_ID"], "%.12f" % price, decimals[token["NEAR_ID"]], network_id)
                    else:
                        print("%s has no ref price %s/usd" % (token["NEAR_ID"], token["BASE_ID"]))
                else:
                    add_history_token_price(token["NEAR_ID"], token["BASE_ID"], token["price"], decimals[token["NEAR_ID"]], network_id)
    except Exception as e:
        print("Error occurred when update to db, Error is: ", e)


def get_base_id_price(tokens_price, price_ref, decimals, base_id):
    ref_token_price = 0
    for token in tokens_price:
        if token["BASE_ID"] != "":
            if token["BASE_ID"] in price_ref and token["NEAR_ID"] == base_id:
                ref_token_price = int(token["price"]) / int("1" + "0" * decimals[token["BASE_ID"]]) * float(
                    price_ref[token["BASE_ID"]])
    return ref_token_price


def handel_base_token_price(network_id, base_tokens, base_obj):
    tokens_price = []
    if base_obj and len(base_obj) > 0:
        for base_token in base_tokens:
            md_id = base_token["MD_ID"]
            if md_id in base_obj and "usd" in base_obj[md_id]:
                tokens_price.append({
                    "SYMBOL": base_token["SYMBOL"],
                    "price": '{:.9f}'.format(base_obj[md_id]["usd"])
                })
    try:
        if len(tokens_price) > 0:
            conn = RedisProvider()
            conn.begin_pipe()
            for token in tokens_price:
                conn.add_base_token_price(network_id, token["SYMBOL"], token["price"])
            conn.end_pipe()
            conn.close()
    except Exception as e:
        print("Error occurred when update base token price to Redis, cancel pipe. Error is: ", e)


if __name__ == '__main__':
    # update_price("TESTNET")
    # market_price("MAINNET", [{"SYMBOL": "near", "NEAR_ID": "wrap.near", "MD_ID": "near", "DECIMAL": 24}], Cfg.TOKENS["BASE_MAINNET"])
    if len(sys.argv) == 2:
        network_id = str(sys.argv[1]).upper()
        if network_id in ["MAINNET", "TESTNET", "DEVNET"]:
            update_price(network_id)
        else:
            print("Error, network_id should be MAINNET, TESTNET or DEVNET")
            exit(1)
    else:
        print("Error, must put NETWORK_ID as arg")
        exit(1)
