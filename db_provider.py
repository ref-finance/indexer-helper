import decimal
import pymysql
import json
from datetime import datetime
from config import Cfg
import time
from redis_provider import RedisProvider, list_history_token_price, list_token_price


class Encoder(json.JSONEncoder):
    """
    Handle special data types, such as decimal and time types
    """

    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)

        if isinstance(o, datetime):
            return o.strftime("%Y-%m-%d %H:%M:%S")

        super(Encoder, self).default(o)


def get_db_connect(network_id: str):
    conn = pymysql.connect(
        host=Cfg.NETWORK[network_id]["DB_HOST"], 
        port=int(Cfg.NETWORK[network_id]["DB_PORT"]), 
        user=Cfg.NETWORK[network_id]["DB_UID"], 
        passwd=Cfg.NETWORK[network_id]["DB_PWD"], 
        db=Cfg.NETWORK[network_id]["DB_DSN"])
    return conn


def get_history_token_price(id_list: list) -> list:
    """
    Batch query historical price
    """
    """because 'usn' Special treatment require,'use 'dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near' 
    Price of, Record whether the input parameter is passed in 'usn'，If there is an incoming 'usn', But no incoming 
    'dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near', Then the return parameter only needs to be 
    returned 'usn', Do not return 'dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near', If both have 
    incoming,It is necessary to return the price information of two at the same time,usn_flag 1 means no incoming 'usn'
    2 means that it is passed in at the same time 'usn和dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near'
    ,3 means that only 'usn',No incoming 'dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near' """
    usn_flag = 1
    # Special treatment of USN to determine whether USN is included in the input parameter
    if "usn" in id_list:
        if "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near" in id_list:
            usn_flag = 2
        else:
            usn_flag = 3
            id_list = ['dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near' if i == 'usn' else i for i in
                       id_list]
    usdt_flag = 1
    # Special treatment of USN to determine whether USN is included in the input parameter
    if "usdt.tether-token.near" in id_list:
        if "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near" in id_list:
            usdt_flag = 2
        else:
            usdt_flag = 3
            id_list = ['dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near' if i == 'usdt.tether-token.near'
                       else i for i in id_list]

    ret = []
    history_token_prices = list_history_token_price(Cfg.NETWORK_ID, id_list)
    for token_price in history_token_prices:
        if not token_price is None:
            float_ratio = format_percentage(float(token_price['price']), float(token_price['history_price']))
            if "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near" in token_price['contract_address']:
                if 2 == usn_flag:
                    new_usn = {
                        "price": token_price['price'],
                        "history_price": token_price['history_price'],
                        "decimal": 18,
                        "symbol": "USN",
                        "float_ratio": float_ratio,
                        "timestamp": token_price['datetime'],
                        "contract_address": "usn"
                    }
                    ret.append(new_usn)
                elif 3 == usn_flag:
                    token_price['contract_address'] = "usn"
                    token_price['symbol'] = "USN"
                    token_price['decimal'] = 18

                if 2 == usdt_flag:
                    new_usdt = {
                        "price": token_price['price'],
                        "history_price": token_price['history_price'],
                        "decimal": 6,
                        "symbol": "USDt",
                        "float_ratio": float_ratio,
                        "timestamp": token_price['datetime'],
                        "contract_address": "usdt.tether-token.near"
                    }
                    ret.append(new_usdt)
                elif 3 == usdt_flag:
                    token_price['contract_address'] = "usdt.tether-token.near"
                    token_price['symbol'] = "USDt"
                    token_price['decimal'] = 6
            token_price['float_ratio'] = float_ratio
            ret.append(token_price)
    return ret


def add_history_token_price(contract_address, symbol, price, decimals, network_id):
    """
    Write the token price to the MySQL database
    """
    for token in Cfg.TOKENS[Cfg.NETWORK_ID]:
        if token["NEAR_ID"] in contract_address:
            symbol = token["SYMBOL"]

    # Get current timestamp
    now = int(time.time())
    before_time = now - (1 * 24 * 60 * 60)
    db_conn = get_db_connect(Cfg.NETWORK_ID)
    sql = "insert into mk_history_token_price(contract_address, symbol, price, `decimal`, create_time, update_time, " \
          "`status`, `timestamp`) values(%s,%s,%s,%s, now(), now(), 1, %s) "
    par = (contract_address, symbol, price, decimals, now)
    # Query the price records 24 hours ago according to the token
    sql2 = "SELECT price FROM mk_history_token_price where contract_address = %s and `timestamp` < " \
           "%s order by from_unixtime(`timestamp`, '%%Y-%%m-%%d %%H:%%i:%%s') desc limit 1"
    par2 = (contract_address, before_time)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, par)
        # Submit to database for execution
        db_conn.commit()

        cursor.execute(sql2, par2)
        old_rows = cursor.fetchone()
        old_price = price
        if old_rows is not None:
            old_price = old_rows["price"]

        history_token = {
            "price": price,
            "history_price": old_price,
            "symbol": symbol,
            "datetime": now,
            "contract_address": contract_address,
            "decimal": decimals
        }
        redis_conn = RedisProvider()
        redis_conn.begin_pipe()
        redis_conn.add_history_token_price(network_id, contract_address, json.dumps(history_token, cls=Encoder))
        redis_conn.end_pipe()
        redis_conn.close()

    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print(e)
    finally:
        cursor.close()


def format_percentage(new, old):
    p = 100 * (new - old) / old
    return '%.2f' % p


def clear_token_price():
    now = int(time.time())
    before_time = now - (7*24*60*60)
    print("seven days ago time:", before_time)
    conn = get_db_connect(Cfg.NETWORK_ID)
    sql = "delete from mk_history_token_price where `timestamp` < %s"
    cursor = conn.cursor()
    try:
        cursor.execute(sql, before_time)
        # Submit to database for execution
        conn.commit()
    except Exception as e:
        # Rollback on error
        conn.rollback()
        print(e)
    finally:
        cursor.close()


def handle_dcl_pools(data_list, network_id):
    old_pools_data = query_dcl_pools(network_id)
    for old_pool in old_pools_data:
        for pool in data_list:
            if old_pool["pool_id"] == pool["pool_id"]:
                # print("old_pool:", old_pool["volume_x_in"])
                # print("pool:", pool["volume_x_in"])
                pool["volume_x_in_grow"] = str(int(pool["volume_x_in"]) - int(old_pool["volume_x_in"]))
                pool["volume_y_in_grow"] = str(int(pool["volume_y_in"]) - int(old_pool["volume_y_in"]))
                pool["volume_x_out_grow"] = str(int(pool["volume_x_out"]) - int(old_pool["volume_x_out"]))
                pool["volume_y_out_grow"] = str(int(pool["volume_y_out"]) - int(old_pool["volume_y_out"]))
                pool["total_order_x_grow"] = str(int(pool["total_order_x"]) - int(old_pool["total_order_x"]))
                pool["total_order_y_grow"] = str(int(pool["total_order_y"]) - int(old_pool["total_order_y"]))
    add_dcl_pools_to_db(data_list, network_id)


def query_dcl_pools(network_id):
    db_conn = get_db_connect(network_id)

    sql = "SELECT id, pool_id, volume_x_in, volume_y_in, volume_x_out, volume_y_out, total_order_x, total_order_y " \
          "FROM t_dcl_pools_data WHERE id IN ( SELECT max(id) FROM t_dcl_pools_data GROUP BY pool_id )"

    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:

        cursor.execute(sql)
        old_pools_data = cursor.fetchall()
        return old_pools_data
    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print("query dcl_pools to db error:", e)
    finally:
        cursor.close()


def add_dcl_pools_to_db(data_list, network_id):
    now = int(time.time())
    zero_point = int(time.time()) - int(time.time() - time.timezone) % 86400
    time_array = time.localtime(zero_point)
    check_point = time.strftime("%Y-%m-%d", time_array)
    db_conn = get_db_connect(network_id)

    sql = "insert into t_dcl_pools_data(pool_id, token_x, token_y, volume_x_in, volume_y_in, volume_x_out, " \
          "volume_y_out, total_order_x, total_order_y, total_x, total_y, volume_x_in_grow, volume_y_in_grow, " \
          "volume_x_out_grow, volume_y_out_grow, total_order_x_grow, total_order_y_grow, token_x_price, " \
          "token_y_price, token_x_decimal, token_y_decimal, timestamp, create_time) " \
          "values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())"

    insert_data = []
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        token_price = get_token_price(network_id)
        for data in data_list:
            token_x_price = 0
            token_y_price = 0
            token_x_decimal = 0
            token_y_decimal = 0
            if data["token_x"] in token_price:
                token_x_price = token_price[data["token_x"]]["price"]
                token_x_decimal = token_price[data["token_x"]]["decimal"]
            if data["token_y"] in token_price:
                token_y_price = token_price[data["token_y"]]["price"]
                token_y_decimal = token_price[data["token_y"]]["decimal"]

            insert_data.append((data["pool_id"], data["token_x"], data["token_y"], data["volume_x_in"],
                                data["volume_y_in"], data["volume_x_out"], data["volume_y_out"], data["total_order_x"],
                                data["total_order_y"], data["total_x"], data["total_y"], data["volume_x_in_grow"],
                                data["volume_y_in_grow"], data["volume_x_out_grow"], data["volume_y_out_grow"],
                                data["total_order_x_grow"], data["total_order_y_grow"], token_x_price,
                                token_y_price, token_x_decimal, token_y_decimal, now))

            pool_id = data["pool_id"] + "_" + check_point
            order_x_price = int(data["total_x"]) / int("1" + "0" * int(token_x_decimal)) * float(token_x_price)
            order_y_price = int(data["total_y"]) / int("1" + "0" * int(token_y_decimal)) * float(token_y_price)
            tvl = order_x_price + order_y_price
            pool_tvl_data = {
                "pool_id": data["pool_id"],
                "dateString": check_point,
                "tvl": str(tvl)
            }
            add_dcl_pools_tvl_to_redis(network_id, pool_id, pool_tvl_data)

        cursor.executemany(sql, insert_data)
        db_conn.commit()
        handle_dcl_pools_to_redis_data(network_id, zero_point)

    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print("insert dcl_pools to db error:", e)
        print("insert dcl_pools to db insert_data:", insert_data)
    finally:
        cursor.close()


def handle_dcl_pools_to_redis_data(network_id, zero_point):
    now = int(time.time())
    before_time = now - (1 * 24 * 60 * 60)
    db_conn = get_db_connect(network_id)

    sql = "SELECT pool_id, SUM(volume_x_in_grow) AS volume_x_in_grow, SUM(volume_y_in_grow) AS volume_y_in_grow, " \
          "SUM(volume_x_out_grow) AS volume_x_out_grow , SUM(volume_y_out_grow) AS volume_y_out_grow, " \
          "SUM(total_order_x_grow) AS total_order_x_grow, SUM(total_order_y_grow) AS total_order_y_grow, " \
          "token_x_price, token_y_price, token_x_decimal, token_y_decimal " \
          "FROM t_dcl_pools_data WHERE `timestamp` >= %s GROUP BY pool_id"

    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:

        cursor.execute(sql, before_time)
        twenty_four_hour_pools_data = cursor.fetchall()
        add_24h_dcl_pools_to_redis(network_id, twenty_four_hour_pools_data)
        cursor.execute(sql, zero_point)
        zero_point_pools_data = cursor.fetchall()
        add_list_dcl_pools_to_redis(network_id, zero_point_pools_data, zero_point)

    except Exception as e:
        print("query dcl_pools to db error:", e)
    finally:
        cursor.close()


def add_24h_dcl_pools_to_redis(network_id, dcl_pools_data):
    try:
        redis_conn = RedisProvider()
        for pool_data in dcl_pools_data:
            token_x_in_price = int(pool_data["volume_x_in_grow"]) / int("1" + "0" * int(pool_data["token_x_decimal"])) * float(pool_data["token_x_price"])
            token_x_out_price = int(pool_data["volume_x_out_grow"]) / int("1" + "0" * int(pool_data["token_x_decimal"])) * float(pool_data["token_x_price"])
            token_y_in_price = int(pool_data["volume_y_in_grow"]) / int("1" + "0" * int(pool_data["token_y_decimal"])) * float(pool_data["token_y_price"])
            token_y_out_price = int(pool_data["volume_y_out_grow"]) / int("1" + "0" * int(pool_data["token_y_decimal"])) * float(pool_data["token_y_price"])
            volume_x = token_x_in_price + token_x_out_price
            volume_y = token_y_in_price + token_y_out_price
            if volume_x > volume_y:
                volume = volume_x
            else:
                volume = volume_y
            redis_conn.begin_pipe()
            redis_conn.add_twenty_four_hour_pools_data(network_id, pool_data["pool_id"], str(volume))
            redis_conn.end_pipe()

        redis_conn.close()
    except Exception as e:
        print("add dcl_pools to redis error:", e)
    finally:
        redis_conn.close()


def add_list_dcl_pools_to_redis(network_id, dcl_pools_data, zero_point):
    try:
        time_array = time.localtime(zero_point)
        check_point = time.strftime("%Y-%m-%d", time_array)
        redis_conn = RedisProvider()
        for pool_data in dcl_pools_data:
            pool_id = pool_data["pool_id"] + "_" + check_point
            token_x_in_price = int(pool_data["volume_x_in_grow"]) / int("1" + "0" * int(pool_data["token_x_decimal"])) * float(pool_data["token_x_price"])
            token_x_out_price = int(pool_data["volume_x_out_grow"]) / int("1" + "0" * int(pool_data["token_x_decimal"])) * float(pool_data["token_x_price"])
            token_y_in_price = int(pool_data["volume_y_in_grow"]) / int("1" + "0" * int(pool_data["token_y_decimal"])) * float(pool_data["token_y_price"])
            token_y_out_price = int(pool_data["volume_y_out_grow"]) / int("1" + "0" * int(pool_data["token_y_decimal"])) * float(pool_data["token_y_price"])
            volume_x = token_x_in_price + token_x_out_price
            volume_y = token_y_in_price + token_y_out_price
            if volume_x > volume_y:
                volume = volume_x
            else:
                volume = volume_y
            pool_volume_data = {
                "pool_id": pool_data["pool_id"],
                "dateString": check_point,
                "volume": str(volume)
            }
            redis_conn.begin_pipe()
            redis_conn.add_dcl_pools_data(network_id, pool_id, json.dumps(pool_volume_data, cls=Encoder), pool_data["pool_id"])
            redis_conn.end_pipe()

        redis_conn.close()
    except Exception as e:
        print("add dcl_pools to redis error:", e)
    finally:
        redis_conn.close()


def add_dcl_pools_tvl_to_redis(network_id, pool_id, pool_tvl_data):
    try:
        redis_conn = RedisProvider()
        redis_conn.begin_pipe()
        redis_conn.add_dcl_pools_tvl_data(network_id, pool_tvl_data["pool_id"], pool_id, json.dumps(pool_tvl_data, cls=Encoder))
        redis_conn.end_pipe()
        redis_conn.close()
    except Exception as e:
        print("add dcl_pools to redis error:", e)
    finally:
        redis_conn.close()


def get_token_price(network_id):
    token_price_list = {}
    prices = list_token_price(network_id)
    for token in Cfg.TOKENS[Cfg.NETWORK_ID]:
        if token["NEAR_ID"] in prices:
            token_price_list[token["NEAR_ID"]] = {
                "price": prices[token["NEAR_ID"]],
                "decimal": token["DECIMAL"],
                "symbol": token["SYMBOL"],
            }
    return token_price_list


if __name__ == '__main__':
    print("#########MAINNET###########")
    # clear_token_price()
    # add_history_token_price("ref.fakes.testnet", "ref2", 1.003, 18, "MAINNET")
    # zero_point = int(time.time()) - int(time.time() - time.timezone) % 86400
    # handle_dcl_pools_to_redis_data("TESTNET", zero_point)
    tvl_data = {
        "pool_id": "ref.fakes.testnet|usdt.fakes.testnet|2000",
        "dateString": "2022-10-24",
        "tvl": "57671.51154471094"
    }
    add_dcl_pools_tvl_to_redis("TESTNET", "ref.fakes.testnet|usdt.fakes.testnet|2000_2022-10-24", tvl_data)
