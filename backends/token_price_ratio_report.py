import sys

sys.path.append('../')
import json
from config import Cfg
import time
from redis_provider import RedisProvider, get_token_price_ratio_report
from db_provider import get_token_price


def handle_token_pair(network_id):
    token_pair_list = []
    # token_list = ['pixeltoken.near', 'dbio.near']
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


def handle_hour_stamp(time_stamp):
    unit = 3600
    hour_stamp = time_stamp - (time_stamp % unit)
    return hour_stamp


def handle_day_stamp(time_stamp):
    day_stamp = int(time.mktime(time.strptime(time.strftime("%Y-%m-%d", time.localtime(time_stamp)), "%Y-%m-%d")))
    return day_stamp


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
    return '%.8f' % ratio


def handle_token_price_ratio_report_d(network_id, token_pair, token_price_data, now_time):
    symbols_data = get_token_symbol(network_id)
    token_pair_one = token_pair.split("->")[0]
    token_pair_two = token_pair.split("->")[1]
    redis_key = token_pair + "_d"
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
        "date_time": handle_hour_stamp(now_time)
    }
    ret = get_token_price_ratio_report(network_id, redis_key)
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
        if len(price_list) > 25:
            price_list.pop(0)
        redis_values["price_list"] = price_list
    add_token_price_ratio_to_redis(network_id, redis_key, redis_values)


def handle_token_price_ratio_report_w(network_id, token_pair, token_price_data, now_time):
    symbols_data = get_token_symbol(network_id)
    token_pair_one = token_pair.split("->")[0]
    token_pair_two = token_pair.split("->")[1]
    redis_key = token_pair + "_w"
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
        "date_time": handle_hour_stamp(now_time)
    }
    ret = get_token_price_ratio_report(network_id, redis_key)
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
        if len(price_list) >= 2:
            last_time2 = price_list[-2]["date_time"]
            last_time1 = price_list[-1]["date_time"]
            new_time = last_time2 + 14400
            if new_time != last_time1 or new_time == handle_hour_stamp(now_time):
                price_list.pop(-1)
        price_list.append(price_data)
        if len(price_list) > 42:
            price_list.pop(0)
        redis_values["price_list"] = price_list
    add_token_price_ratio_to_redis(network_id, redis_key, redis_values)


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
        "date_time": handle_day_stamp(now_time)
    }
    ret = get_token_price_ratio_report(network_id, redis_key)
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
        last_time = price_list[-1]["date_time"]
        if last_time == handle_day_stamp(now_time):
            price_list.pop(-1)
        price_list.append(price_data)
        if len(price_list) > 30:
            price_list.pop(0)
        redis_values["price_list"] = price_list
    add_token_price_ratio_to_redis(network_id, redis_key, redis_values)


def handle_token_price_ratio_report_y(network_id, token_pair, token_price_data, now_time):
    symbols_data = get_token_symbol(network_id)
    token_pair_one = token_pair.split("->")[0]
    token_pair_two = token_pair.split("->")[1]
    redis_key = token_pair + "_y"
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
        "date_time": handle_day_stamp(now_time)
    }
    ret = get_token_price_ratio_report(network_id, redis_key)
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
        if len(price_list) >= 2:
            last_time2 = price_list[-2]["date_time"]
            last_time1 = price_list[-1]["date_time"]
            new_time = last_time2 + 259200
            if new_time != last_time1 or new_time == handle_day_stamp(now_time):
                price_list.pop(-1)
        price_list.append(price_data)
        redis_values["price_list"] = price_list
    add_token_price_ratio_to_redis(network_id, redis_key, redis_values)


def handle_token_price_ratio_report_all(network_id, token_pair, token_price_data, now_time):
    symbols_data = get_token_symbol(network_id)
    token_pair_one = token_pair.split("->")[0]
    token_pair_two = token_pair.split("->")[1]
    redis_key = token_pair + "_all"
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
        "date_time": handle_day_stamp(now_time)
    }
    ret = get_token_price_ratio_report(network_id, redis_key)
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
        if len(price_list) >= 2:
            last_time2 = price_list[-2]["date_time"]
            last_time1 = price_list[-1]["date_time"]
            new_time = last_time2 + 259200
            if new_time != last_time1 or new_time == handle_day_stamp(now_time):
                price_list.pop(-1)
        price_list.append(price_data)
        redis_values["price_list"] = price_list
    add_token_price_ratio_to_redis(network_id, redis_key, redis_values)


def add_token_price_ratio_to_redis(network_id, key, values):
    redis_conn = RedisProvider()
    redis_conn.begin_pipe()
    redis_conn.add_token_ratio_report(network_id, key, json.dumps(values))
    redis_conn.end_pipe()
    redis_conn.close()


def handle_token_price_report_to_redis(network_id, token_price_data):
    token_pairs = handle_token_pair(network_id)
    now_time = int(time.time())
    for token_pair in token_pairs:
        handle_token_price_ratio_report_d(network_id, token_pair, token_price_data, now_time)
        handle_token_price_ratio_report_w(network_id, token_pair, token_price_data, now_time)
        handle_token_price_ratio_report_m(network_id, token_pair, token_price_data, now_time)
        handle_token_price_ratio_report_y(network_id, token_pair, token_price_data, now_time)
        handle_token_price_ratio_report_all(network_id, token_pair, token_price_data, now_time)


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

