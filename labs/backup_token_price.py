import sys
sys.path.append('../')
from near_rpc_provider import JsonProviderError,  JsonProvider
from redis_provider import RedisProvider
import http.client
from config import Cfg
import json
import time
import sys

def update_market_price(network_id):
    obj = None
    tokens = []
    md2contract = {}

    try:
        conn = http.client.HTTPSConnection(Cfg.MARKET_URL, port=443)
        headers = {"Content-type": "application/json; charset=utf-8",
                "cache-control": "no-cache"}
        
        for token in Cfg.TOKENS[network_id]:
            tokens.append(token["MD_ID"])
            md2contract[token["MD_ID"]] = token["NEAR_ID"]
        token_str = ",".join(tokens)
        # print(token_str)
        conn.request("GET", "/api/v3/simple/price?ids=%s&vs_currencies=usd" % token_str, headers=headers)
        res = conn.getresponse()
        print(res.status, res.reason)
        data = res.read()
        conn.close()
        obj = json.loads(data.decode("utf-8"))
        # print(obj)  # {'tether': {'usd': 1.0}, 'near': {'usd': 3.29}, 'dai': {'usd': 1.0}}
    except Exception as e:
        print("Error: ", e)

    try:
        if obj and len(obj) > 0:
            conn = RedisProvider()
            conn.begin_pipe()
            for md_id, value in obj.items():
                # print(md2contract[md_id], str(value["usd"]))
                conn.add_token_price(network_id, md2contract[md_id], str(value["usd"]))
            conn.end_pipe()
            conn.close()
    except Exception as e:
        print("Error occurred when update to Redis, cancel pipe. Error is: ", e)


if __name__ == '__main__':
    # update_market_price("TESTNET")
    if len(sys.argv) == 2:
        network_id = str(sys.argv[1]).upper()
        if network_id in ["MAINNET", "TESTNET"]:
            update_market_price(network_id)
        else:
            print("Error, network_id should be MAINNET or TESTNET")
            exit(1)
    else:
        print("Error, must put NETWORK_ID as arg")
        exit(1)