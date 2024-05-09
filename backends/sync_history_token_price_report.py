import sys

sys.path.append('../')
import json
from config import Cfg
import time
from redis_provider import RedisProvider, get_history_token_price_report
from db_provider import get_token_price_history


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


def handle_token_price_ratio_report(network_id, token_pair, token_price_data, now_time):
    symbols_data = get_token_symbol(network_id)
    token_pair_one = token_pair.split("->")[0]
    token_pair_two = token_pair.split("->")[1]
    redis_key = token_pair
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


def handle_token_price_report_to_redis(network_id, token_price_data, now_time):
    token_pairs = Cfg.NETWORK[network_id]["HISTORY_TOKEN_PRICE_REPORT_PAIR"]
    for token_pair in token_pairs:
        handle_token_price_ratio_report(network_id, token_pair, token_price_data, now_time)


def handel_redis_data(token_pairs):
    ret_redis_data_list = {}
    symbols_data = get_token_symbol("MAINNET")
    for token_pair in token_pairs:
        token_pair_one = token_pair.split("->")[0]
        redis_key = token_pair
        price_list = []
        redis_values = {
            "symbol": symbols_data[token_pair_one],
            "contract_address": token_pair_one,
            "price_list": price_list
        }
        ret_redis_data_list[redis_key] = redis_values
    return ret_redis_data_list


def handle_token_price_data(token_pair, token_price_data, now_time, redis_values):
    token_pair_one = token_pair.split("->")[0]
    token_pair_two = token_pair.split("->")[1]
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
    price_list = redis_values["price_list"]
    price_list.append(price_data)
    if len(price_list) > 2880:
        price_list.pop(0)
    redis_values["price_list"] = price_list


def write_json_file(data, file_path):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)


def read_json_file(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data


if __name__ == "__main__":
    print("#########TOKEN PRICE RATIO START###########")
    start_time = int(time.time())
    all_token_pairs = Cfg.NETWORK["MAINNET"]["HISTORY_TOKEN_PRICE_REPORT_PAIR"]
    redis_data_list = handel_redis_data(all_token_pairs)
    data_start_time = 1712592000
    for i in range(0, 10000):
        s_time = data_start_time + i * 900
        if s_time >= int(time.time()):
            break
        start_time1 = int(time.time())
        print("-----------i:", i)
        db_token_price_data = get_token_price_history(s_time, s_time + 900)
        if db_token_price_data is None:
            continue
        end_time1 = int(time.time())
        time_consuming1 = end_time1 - start_time1
        print("get_token_price_history consuming:", time_consuming1)
        # print("db_token_price_data:", db_token_price_data)
        for all_token_pair in all_token_pairs:
            handle_token_price_data(all_token_pair, db_token_price_data, s_time, redis_data_list[all_token_pair])
        end_time2 = int(time.time())
        time_consuming2 = end_time2 - end_time1
        print("handle_token_price_data time consuming:", time_consuming2)
    end_time = int(time.time())
    time_consuming = end_time - start_time
    print("all time consuming:", time_consuming)
    write_json_file(redis_data_list, "redis_data.json")

    redis_token_report_data = read_json_file("redis_data.json")
    for key, values in redis_token_report_data.items():
        redis_conn = RedisProvider()
        redis_conn.begin_pipe()
        redis_conn.add_history_token_price_report("MAINNET", key, json.dumps(values))
        redis_conn.end_pipe()
        redis_conn.close()
    print("#########LAST TOKEN PRICE END###########")

