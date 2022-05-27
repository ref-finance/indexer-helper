import sys
sys.path.append('../')
from near_multinode_rpc_provider import MultiNodeJsonProviderError,  MultiNodeJsonProvider
from redis_provider import RedisProvider
import http.client
from config import Cfg
import json
import time
import sys
from db_provider import add_token_price_to_db

def pool_price(network_id, tokens):
    # tokens = [{"SYMBOL": "ref", "NEAR_ID": "rft.tokenfactory.testnet", "MD_ID": "ref-finance.testnet|24|wrap.testnet", "DECIMAL": 8}, ...]
    # return [{"NEAR_ID": "rft.tokenfactory.testnet", "BASE_ID": "wrap.testnet", "price": "nnnnnn"}, ...]
    pool_tokens_price = []
    try:
        conn = MultiNodeJsonProvider(network_id)
        for token in tokens:
            src, pool_id, base = token["MD_ID"].split("|")
            time.sleep(0.1)
            ret = conn.view_call(
                src, 
                "get_return", 
                ('{"pool_id": %s, "token_in": "%s", "amount_in": "1%s", "token_out": "%s"}' 
                % (pool_id, token["NEAR_ID"], '0'*token["DECIMAL"], base))
                .encode(encoding='utf-8')
            )
            json_str = "".join([chr(x) for x in ret["result"]])
            price = json.loads(json_str)
            if token["NEAR_ID"] == "token.v2.ref-finance.near":
                debug_price = int(price) / 1000000000000000000000000.0
                print('[debug][%s]REF-wNEAR:%.08f' % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), debug_price))
            pool_tokens_price.append({"NEAR_ID": token["NEAR_ID"], "BASE_ID": base, "price": price})

    except MultiNodeJsonProviderError as e:
        print("RPC Error: ", e)
        pool_tokens_price.clear()
    except Exception as e:
        print("Error: ", e)
        pool_tokens_price.clear()
    return pool_tokens_price


def market_price(network_id, tokens):
    # tokens = [{"SYMBOL": "ref", "NEAR_ID": "rft.tokenfactory.testnet", "MD_ID": "ref-finance.testnet|24|wrap.testnet", "DECIMAL": 8}, ...]
    # return [{"NEAR_ID": "rft.tokenfactory.testnet", "BASE_ID": "", "price": "nnnnnn"}, ...]
    market_tokens_price = []
    md_ids = []
    obj = None
    try:
        conn = http.client.HTTPSConnection(Cfg.MARKET_URL, port=443)
        headers = {"Content-type": "application/json; charset=utf-8",
                "cache-control": "no-cache"}
        
        for token in tokens:
            md_ids.append(token["MD_ID"])

        token_str = ",".join(md_ids)
        # print(token_str)
        conn.request("GET", "/api/v3/simple/price?ids=%s&vs_currencies=usd" % token_str, headers=headers)
        res = conn.getresponse()
        print(res.status, res.reason)
        data = res.read()
        conn.close()
        obj = json.loads(data.decode("utf-8"))
        # {'tether': {'usd': 1.0}, 'near': {'usd': 3.29}, 'dai': {'usd': 1.0}}
        print('[debug][%s]%s' % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), obj))
    except Exception as e:
        print("Error: ", e)

    if obj and len(obj) > 0:
        for token in tokens:
            md_id = token["MD_ID"]
            if md_id in obj:
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
    tokens_price = market_price(network_id, market_tokens)
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
                    if token["BASE_ID"] in price_ref:
                        # print(int(token["price"]) / int("1"*decimals[token["BASE_ID"]]))
                        price = int(token["price"]) / int("1"+"0"*decimals[token["BASE_ID"]]) * float(price_ref[token["BASE_ID"]])
                        # print(token["NEAR_ID"], "%.08f" % price)
                        conn.add_token_price(network_id, token["NEAR_ID"], "%.08f" % price)
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
                    if token["BASE_ID"] in price_ref:
                        price = int(token["price"]) / int("1"+"0"*decimals[token["BASE_ID"]]) * float(price_ref[token["BASE_ID"]])
                        add_token_price_to_db(token["NEAR_ID"], token["BASE_ID"], "%.08f" % price, decimals[token["NEAR_ID"]])
                    else:
                        print("%s has no ref price %s/usd" % (token["NEAR_ID"], token["BASE_ID"]))
                else:
                    add_token_price_to_db(token["NEAR_ID"], token["BASE_ID"], token["price"], decimals[token["NEAR_ID"]])
    except Exception as e:
        print("Error occurred when update to db, Error is: ", e)


if __name__ == '__main__':
    # update_price("TESTNET")
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