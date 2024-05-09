import sys

sys.path.append('../')
import json
from config import Cfg
import time
from redis_provider import RedisProvider, get_history_token_price_report
from db_provider import get_token_price


def handle_token_pair(network_id):
    token_pair_list = []
    token_list = []
    for token in Cfg.TOKENS[network_id]:
        token_list.append(token["NEAR_ID"])
    for token_one in token_list:
        for token_two in token_list:
            if token_one != token_two:
                token_pair_list.append(token_one + "->" + token_two)
    return token_pair_list


def get_token_decimal(network_id):
    decimals = {}
    for token in Cfg.TOKENS[network_id]:
        decimals[token["NEAR_ID"]] = token["DECIMAL"]
    return decimals


def get_token_symbol(network_id):
    symbols = {}
    for token in Cfg.TOKENS[network_id]:
        symbols[token["NEAR_ID"]] = token["SYMBOL"]
    return symbols


def handle_date_to_time_stamp(date_time):
    if date_time == "":
        return 0
    time_stamp = time.strptime(date_time, "%Y-%m-%d %H:%M:%S")
    timestamp = int(time.mktime(time_stamp))
    return timestamp


def get_ratio(amount_in, amount_out):
    ratio = 0.000000
    try:
        ratio = float(float(amount_in) / float(amount_out))
    except Exception as e:
        print("get ratio error:", e)
        return ratio
    return '%.12f' % ratio


def handle_token_price_ratio_report_m(network_id, token_pair, token_price_data, now_time):
    symbols_data = get_token_symbol(network_id)
    token_pair_one = token_pair.split("->")[0]
    token_pair_two = token_pair.split("->")[1]
    redis_key = token_pair + "_m"
    token_pair_one_price = 0.00
    token_pair_two_price = 0.00
    if token_pair_one in token_price_data:
        token_pair_one_price = token_price_data[token_pair_one]["price"]
    if token_pair_two in token_price_data:
        token_pair_two_price = token_price_data[token_pair_two]["price"]
    if token_pair_one_price == 0.00 or token_pair_two_price == 0.00:
        return
    ratio = get_ratio(token_pair_one_price, token_pair_two_price)
    price_data = {
        "price": ratio,
        "date_time": now_time
    }
    ret = get_history_token_price_report(network_id, redis_key)
    if ret is None:
        price_list = []
        redis_values = {
            "symbol": symbols_data[token_pair_one],
            "contract_address": token_pair_one,
            "price_list": ""
        }
        price_list.append(price_data)
        redis_values["price_list"] = price_list
    else:
        redis_values = json.loads(ret)
        price_list = redis_values["price_list"]
        price_list.append(price_data)
        if len(price_list) > 2880:
            price_list.pop(0)
        redis_values["price_list"] = price_list
    add_token_price_ratio_to_redis(network_id, redis_key, redis_values)


def add_token_price_ratio_to_redis(network_id, key, values):
    redis_conn = RedisProvider()
    redis_conn.begin_pipe()
    redis_conn.add_history_token_price_report(network_id, key, json.dumps(values))
    redis_conn.end_pipe()
    redis_conn.close()


def handle_token_price_report_to_redis(network_id, token_price_data):
    token_pairs = handle_token_pair(network_id)
    now_time = int(time.time())
    for token_pair in token_pairs:
        handle_token_price_ratio_report_m(network_id, token_pair, token_price_data, now_time)


if __name__ == "__main__":
    print("#########TOKEN PRICE RATIO START###########")
    if len(sys.argv) == 2:
        start_time = int(time.time())
        network_id = str(sys.argv[1]).upper()
        if network_id in ["MAINNET", "TESTNET", "DEVNET"]:
            start_time = int(time.time())
            token_price_data = get_token_price()
            handle_token_price_report_to_redis(network_id, token_price_data)
            end_time = int(time.time())
            time_consuming = end_time - start_time
            print("handle_token_price_report_to_redis time consuming:", time_consuming)
        else:
            print("Error, network_id should be MAINNET, TESTNET or DEVNET")
            exit(1)
    else:
        print("Error, must put NETWORK_ID as arg")
        exit(1)
    print("#########TOKEN PRICE RATIO END###########")

    # start_time = int(time.time())
    # token_price_data = get_token_price()
    # handle_token_price_report_to_redis("MAINNET", token_price_data)
    # end_time = int(time.time())
    # time_consuming = end_time - start_time
    # print("time consuming:", time_consuming)
    # print("#########LAST TOKEN PRICE END###########")

