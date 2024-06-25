import sys
sys.path.append('../')
from near_multinode_rpc_provider import MultiNodeJsonProviderError,  MultiNodeJsonProvider
from redis_provider import RedisProvider
import requests
from config import Cfg
import json
import time
from db_provider import add_history_token_price, batch_add_history_token_price
import traceback


def get_now_millisecond():
    millisecond = int(time.time_ns()) // 1000000
    return millisecond


def pool_price(network_id, tokens):
    pool_tokens_price = []
    try:
        decimal_data = get_decimals()
        simple_pool_list, stable_pool_list, stable_pool_detail_list = get_all_pool_data()
        conn = MultiNodeJsonProvider(network_id)
        for token in tokens:
            src, pool_id, base = token["MD_ID"].split("|")
            if token["NEAR_ID"] == "meta-pool.near" or token["NEAR_ID"] == "linear-protocol.near":
                try:
                    ret = conn.view_call(src, "get_rated_pool", ('{"pool_id": %s}' % pool_id)
                                         .encode(encoding='utf-8'))
                    json_str = "".join([chr(x) for x in ret["result"]])
                    result_obj = json.loads(json_str)
                    rates = result_obj["rates"]
                    price = int(rates[0]) / int("1" + "0" * decimal_data[token["NEAR_ID"]])
                except Exception as e:
                    print("get_rated_pool error:", e)
                    continue
            elif token["NEAR_ID"] == "nearx.stader-labs.near" or token["NEAR_ID"] == "v2-nearx.stader-labs.near":
                try:
                    ret = conn.view_call(src, "get_nearx_price", "NA".encode(encoding='utf-8'))
                    json_str = "".join([chr(x) for x in ret["result"]])
                    price = json.loads(json_str)
                    price = int(price) / int("1" + "0" * decimal_data[token["NEAR_ID"]])
                except Exception as e:
                    print("get_nearx_price error:", e)
                    continue
            elif token["NEAR_ID"] == "xtoken.ref-finance.near":
                try:
                    ret = conn.view_call(src, "get_virtual_price", "NA".encode(encoding='utf-8'))
                    json_str = "".join([chr(x) for x in ret["result"]])
                    price = json.loads(json_str)
                    price = int(price) / int("1" + "0" * decimal_data[token["NEAR_ID"]])
                except Exception as e:
                    print("get_virtual_price error:", e)
                    continue
            else:
                token_in = {
                    "id": token["NEAR_ID"],
                    "decimals": decimal_data[token["NEAR_ID"]]
                }
                token_out = {
                    "id": base,
                    "decimals": decimal_data[base]
                }
                price = 0
                sdk_price_data = get_price_by_sdk(simple_pool_list, stable_pool_list, stable_pool_detail_list, token_in,
                                                  token_out)
                for sdk_price in sdk_price_data:
                    price = price + float(sdk_price["estimate"])
            pool_tokens_price.append({"NEAR_ID": token["NEAR_ID"], "BASE_ID": base, "price": price})

    except MultiNodeJsonProviderError as e:
        print("RPC Error: ", e)
        pool_tokens_price.clear()
    except Exception as e:
        print("Error: ", e)
        traceback.print_exc()
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
    start_time1 = get_now_millisecond()
    pool_tokens = []
    market_tokens = []
    decimals = {}
    price_ref = {}
    for token in Cfg.TOKENS[network_id]:
        decimals[token["NEAR_ID"]] = token["DECIMAL"]
        if len(token["MD_ID"].split("|")) == 3:
            pool_tokens.append(token)
        else:
            market_tokens.append(token)

    tokens_price = market_price(network_id, market_tokens, Cfg.TOKENS["BASE_MAINNET"])
    for token in tokens_price:
        price_ref[token["NEAR_ID"]] = token["price"]
    tokens_price += pool_price(network_id, pool_tokens)

    try:
        if len(tokens_price) > 0:
            conn = RedisProvider()
            conn.begin_pipe()
            for token in tokens_price:
                if token["BASE_ID"] != "":
                    if token["NEAR_ID"] == "xtoken.ref-finance.near":
                        ref_token_price = get_base_id_price(tokens_price, price_ref, decimals, token["BASE_ID"])
                        if ref_token_price > 0:
                            price = int(token["price"]) / 100000000 * ref_token_price
                            conn.add_token_price(network_id, token["NEAR_ID"], "%.12f" % price)
                    elif token["BASE_ID"] in price_ref:
                        price = float(token["price"]) * float(price_ref[token["BASE_ID"]])
                        if token["NEAR_ID"] not in price_ref:
                            price_ref[token["NEAR_ID"]] = price
                        conn.add_token_price(network_id, token["NEAR_ID"], "%.12f" % price)
                    else:
                        print("%s has no ref price %s/usd" % (token["NEAR_ID"], token["BASE_ID"]))
                else:
                    conn.add_token_price(network_id, token["NEAR_ID"], token["price"])
            conn.end_pipe()
            conn.close()
    except Exception as e:
        print("Error occurred when update to Redis, cancel pipe. Error is: ", e)
    end_time1 = get_now_millisecond()
    if end_time1 - start_time1 > 10:
        print("update_price time:", end_time1 - start_time1)
    try:
        if len(tokens_price) > 0:
            insert_data_list = []
            for token in tokens_price:
                if token["BASE_ID"] != "":
                    if token["NEAR_ID"] == "xtoken.ref-finance.near":
                        ref_token_price = get_base_id_price(tokens_price, price_ref, decimals, token["BASE_ID"])
                        if ref_token_price > 0:
                            price = int(token["price"]) / 100000000 * ref_token_price
                            insert_data_list.append({"contract_address": token["NEAR_ID"], "symbol": get_symbol(token["NEAR_ID"]), "price": "%.12f" % price, "decimal": decimals[token["NEAR_ID"]]})
                    elif token["BASE_ID"] in price_ref:
                        price = float(token["price"]) * float(price_ref[token["BASE_ID"]])
                        insert_data_list.append({"contract_address": token["NEAR_ID"], "symbol": get_symbol(token["NEAR_ID"]), "price": "%.12f" % price, "decimal": decimals[token["NEAR_ID"]]})
                    else:
                        print("%s has no ref price %s/usd" % (token["NEAR_ID"], token["BASE_ID"]))
                else:
                    insert_data_list.append({"contract_address": token["NEAR_ID"], "symbol": get_symbol(token["NEAR_ID"]), "price": token["price"], "decimal": decimals[token["NEAR_ID"]]})
                if len(insert_data_list) >= 500:
                    batch_add_history_token_price(insert_data_list, network_id)
                    insert_data_list.clear()
            if len(insert_data_list) > 0:
                batch_add_history_token_price(insert_data_list, network_id)
    except Exception as e:
        print("Error occurred when update to db, Error is: ", e)
    end_time2 = get_now_millisecond()
    if end_time2 - end_time1 > 10:
        print("insert data time:", end_time2 - end_time1)


def get_symbol(contract_address):
    symbol = ""
    for token in Cfg.TOKENS[Cfg.NETWORK_ID]:
        if token["NEAR_ID"] in contract_address:
            symbol = token["SYMBOL"]
            return symbol
    return symbol


def get_decimals():
    decimals = {}
    for token in Cfg.TOKENS[Cfg.NETWORK_ID]:
        decimals[token["NEAR_ID"]] = token["DECIMAL"]
    return decimals


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


def get_price_by_sdk(simple_pool_list, stable_pool_list, stable_pool_detail_list, token_in, token_out):
    simple_pool_list_ = []
    for pool_data in simple_pool_list:
        if token_in["id"] in pool_data["tokenIds"] and token_out["id"] in pool_data["tokenIds"]:
            token_in_quantity = 1
            if token_in["id"] in pool_data["tokenIds"]:
                token_in_decimals = int(token_in["decimals"])
                token_in_amount = int(pool_data["supplies"][token_in["id"]])
                token_in_quantity = token_in_amount / (10 ** token_in_decimals)
            token_out_quantity = 1
            if token_out["id"] in pool_data["tokenIds"]:
                token_out_decimals = int(token_out["decimals"])
                token_out_amount = int(pool_data["supplies"][token_out["id"]])
                token_out_quantity = token_out_amount / (10 ** token_out_decimals)
            if token_out_quantity > 0.1 and token_in_quantity > 0.1:
                simple_pool_list_.append(pool_data)
    query = {
        "method": "estimateSwap",
        "arg1": {
            "tokenIn": token_in,
            "tokenOut": token_out,
            "amountIn": "1",
            "simplePools": simple_pool_list_,
            "options": {
                "enableSmartRouting": True,
                "stablePools": stable_pool_list,
                "stablePoolsDetail": stable_pool_detail_list
            }
        },
        "network": Cfg.NETWORK_ID.lower()
    }
    estimate_ret = requests.post(Cfg.REF_SDK_URL, json=query).content
    estimate_data = json.loads(estimate_ret)
    return estimate_data


def get_all_pool_data():
    response = requests.get(Cfg.REF_URL)
    data = response.text
    all_pool_data = json.loads(data)
    simple_pool_list = all_pool_data["simplePools"]
    stable_pool_list = all_pool_data["unRatedPools"] + all_pool_data["ratedPools"]
    query = {
        "method": "getStablePools",
        "arg1": stable_pool_list,
        "network": Cfg.NETWORK_ID.lower()
    }
    ret = requests.post(Cfg.REF_SDK_URL, json=query).content
    stable_pool_detail_list = json.loads(ret)
    return simple_pool_list, stable_pool_list, stable_pool_detail_list


if __name__ == '__main__':
    print("----------------start_token_price-------------------")
    start_time = get_now_millisecond()
    if len(sys.argv) == 2:
        network_id = str(sys.argv[1]).upper()
        if network_id in ["MAINNET", "TESTNET", "DEVNET"]:
            update_price(network_id)
            end_time = get_now_millisecond()
            if end_time - start_time > 20:
                print("all time:", end_time - start_time)
        else:
            print("Error, network_id should be MAINNET, TESTNET or DEVNET")
            exit(1)
    else:
        print("Error, must put NETWORK_ID as arg")
        exit(1)
