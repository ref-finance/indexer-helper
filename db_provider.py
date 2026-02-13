import decimal
import pymysql
import json
from datetime import datetime, timedelta
from config import Cfg
import time
from redis_provider import RedisProvider, list_history_token_price, list_token_price, get_account_pool_assets, get_pool_point_24h_by_pool_id
from data_utils import add_redis_data


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


def get_near_lake_connect(network_id: str):
    conn = pymysql.connect(
        host=Cfg.NETWORK[network_id]["NEAR_LAKE_DB_HOST"],
        port=int(Cfg.NETWORK[network_id]["NEAR_LAKE_DB_PORT"]),
        user=Cfg.NETWORK[network_id]["NEAR_LAKE_DB_UID"],
        passwd=Cfg.NETWORK[network_id]["NEAR_LAKE_DB_PWD"],
        db=Cfg.NETWORK[network_id]["NEAR_LAKE_DB_DSN"])
    return conn


def get_near_lake_dcl_connect(network_id: str):
    conn = pymysql.connect(
        host=Cfg.NETWORK[network_id]["NEAR_LAKE_DB_HOST"],
        port=int(Cfg.NETWORK[network_id]["NEAR_LAKE_DB_PORT"]),
        user=Cfg.NETWORK[network_id]["NEAR_LAKE_DB_UID"],
        passwd=Cfg.NETWORK[network_id]["NEAR_LAKE_DB_PWD"],
        db=Cfg.NETWORK[network_id]["NEAR_LAKE_DCL_DB_DSN"])
    return conn


def get_crm_db_connect(network_id: str):
    conn = pymysql.connect(
        host=Cfg.NETWORK[network_id]["DB_HOST"],
        port=int(Cfg.NETWORK[network_id]["DB_PORT"]),
        user=Cfg.NETWORK[network_id]["CRM_DB_UID"],
        passwd=Cfg.NETWORK[network_id]["CRM_DB_PWD"],
        db="crm")
    return conn


def get_burrow_connect(network_id: str):
    conn = pymysql.connect(
        host=Cfg.NETWORK[network_id]["DB_HOST"],
        port=int(Cfg.NETWORK[network_id]["DB_PORT"]),
        user=Cfg.NETWORK[network_id]["BURROW_DB_UID"],
        passwd=Cfg.NETWORK[network_id]["BURROW_DB_PWD"],
        db="burrow")
    return conn


def get_liquidity_pools(network_id, account_id):
    ret = []
    db_conn = get_db_connect(network_id)
    sql = "select DISTINCT(pool_id) as pool_id from near_lake_liquidity_pools where account_id = %s"
    cursor = db_conn.cursor()
    try:
        cursor.execute(sql, account_id)
        rows = cursor.fetchall()
        return [row[0] for row in rows if row[0]]
    except Exception as e:
        print("query liquidity pools to db error:", e)
    finally:
        cursor.close()
    return ret


def get_actions(network_id, account_id):
    json_ret = []
    db_conn = get_db_connect(network_id)
    sql = "select `timestamp`,tx_id,receiver_account_id,method_name,args,deposit,`status`,receipt_id " \
          "from near_lake_latest_actions where predecessor_account_id = %s order by `timestamp` desc limit 10"
    cursor = db_conn.cursor()
    try:
        cursor.execute(sql, account_id)
        rows = cursor.fetchall()
        json_ret = json.dumps(rows, cls=DecimalEncoder)
    except Exception as e:
        print("query liquidity pools to db error:", e)
    finally:
        cursor.close()
    return json_ret


def add_tx_receipt(data_list, network_id):
    db_conn = get_near_lake_connect(network_id)

    sql = "insert into t_tx_receipt(tx_id, receipt_id) values(%s,%s)"

    insert_data = []
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        for data in data_list:
            insert_data.append((data["tx_id"], data["receipt_id"]))

        cursor.executemany(sql, insert_data)
        db_conn.commit()

    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print("insert tx receipt log to db error:", e)
        print("insert tx receipt log to db insert_data:", insert_data)
    finally:
        cursor.close()


def query_tx_by_receipt(receipt_id, network_id):
    db_conn = get_near_lake_connect(network_id)
    sql = "SELECT tx_id FROM t_tx_receipt WHERE receipt_id = %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, receipt_id)
        tx_data = cursor.fetchone()
        if tx_data is None:
            return ""
        else:
            tx_id = tx_data["tx_id"]
            return tx_id
    except Exception as e:
        print("query tx to db error:", e)
    finally:
        cursor.close()


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
    # usn_flag = 1
    # Special treatment of USN to determine whether USN is included in the input parameter
    # if "usn" in id_list:
    #     if "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near" in id_list:
    #         usn_flag = 2
    #     else:
    #         usn_flag = 3
    #         id_list = ['dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near' if i == 'usn' else i for i in
    #                    id_list]
    # usdt_flag = 1
    # # Special treatment of USN to determine whether USN is included in the input parameter
    # if "usdt.tether-token.near" in id_list:
    #     if "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near" in id_list:
    #         usdt_flag = 2
    #     else:
    #         usdt_flag = 3
    #         id_list = ['dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near' if i == 'usdt.tether-token.near'
    #                    else i for i in id_list]
    #
    ret = []
    history_token_prices = list_history_token_price(Cfg.NETWORK_ID, id_list)
    for token_price in history_token_prices:
        if not token_price is None:
            float_ratio = format_percentage(float(token_price['price']), float(token_price['history_price']))
            # if "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near" in token_price['contract_address']:
                # if 2 == usn_flag:
                #     new_usn = {
                #         "price": token_price['price'],
                #         "history_price": token_price['history_price'],
                #         "decimal": 18,
                #         "symbol": "USN",
                #         "float_ratio": float_ratio,
                #         "timestamp": token_price['datetime'],
                #         "contract_address": "usn"
                #     }
                #     ret.append(new_usn)
                # elif 3 == usn_flag:
                #     token_price['contract_address'] = "usn"
                #     token_price['symbol'] = "USN"
                #     token_price['decimal'] = 18

                # if 2 == usdt_flag:
                #     new_usdt = {
                #         "price": token_price['price'],
                #         "history_price": token_price['history_price'],
                #         "decimal": 6,
                #         "symbol": "USDt",
                #         "float_ratio": float_ratio,
                #         "timestamp": token_price['datetime'],
                #         "contract_address": "usdt.tether-token.near"
                #     }
                #     ret.append(new_usdt)
                # elif 3 == usdt_flag:
                #     token_price['contract_address'] = "usdt.tether-token.near"
                #     token_price['symbol'] = "USDt"
                #     token_price['decimal'] = 6
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


def batch_add_history_token_price(data_list, network_id):
    now = int(time.time())
    before_time = now - (1 * 24 * 60 * 60)
    new_token_price = {}
    old_token_price = {}
    db_conn = get_db_connect(network_id)
    sql = "insert into mk_history_token_price(contract_address, symbol, price, `decimal`, create_time, update_time, " \
          "`status`, `timestamp`) values(%s,%s,%s,%s, now(), now(), 1, %s)"
    sql2 = "SELECT contract_address, AVG(price) FROM mk_history_token_price where contract_address in (%s) " \
           "and `timestamp` > '%s' group by contract_address"
    insert_data = []
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        for data in data_list:
            insert_data.append((data["contract_address"], data["symbol"], data["price"], data["decimal"], now))
            new_token_price[data["contract_address"]] = {"symbol": data["symbol"], "price": data["price"], "decimal": data["decimal"]}

        cursor.executemany(sql, insert_data)
        db_conn.commit()
        end_time = int(time.time())
        print("insert to db time:", end_time - now)
        contract_address_ids = ""
        par2 = (contract_address_ids, before_time)
        cursor.execute(sql2, par2)
        old_rows = cursor.fetchall()
        end_time1 = int(time.time())
        print("query old price time:", end_time1 - end_time)
        for old_row in old_rows:
            old_token_price[old_row["contract_address"]] = old_row["price"]
        handle_history_token_price_to_redis(now, new_token_price, old_token_price, network_id)
        end_time2 = int(time.time())
        print("add price to redis time:", end_time2 - end_time1)
    except Exception as e:
        db_conn.rollback()
        print("insert mk_history_token_price to db error:", e)
    finally:
        cursor.close()
        db_conn.close()


def handle_history_token_price_to_redis(now, new_token_price, old_token_price, network_id):
    redis_conn = RedisProvider()
    redis_conn.begin_pipe()
    for token, token_data in new_token_price.items():
        price = token_data["price"]
        symbol = token_data["symbol"]
        decimals = token_data["decimal"]
        old_price = price
        if token in old_token_price and old_token_price[token] is not None:
            old_price = old_token_price[token]

        history_token = {
            "price": price,
            "history_price": old_price,
            "symbol": symbol,
            "datetime": now,
            "contract_address": token,
            "decimal": decimals
        }
        redis_conn.add_history_token_price(network_id, token, json.dumps(history_token, cls=Encoder))
    redis_conn.end_pipe()
    redis_conn.close()


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
    db_table = "t_dcl_pools_data"
    if network_id == "MAINNET":
        db_table = "t_dcl_pools_data_mainnet"

    sql = "SELECT id, pool_id, volume_x_in, volume_y_in, volume_x_out, volume_y_out, total_order_x, total_order_y " \
          "FROM " + db_table + " WHERE id IN ( SELECT max(id) FROM " + db_table + " GROUP BY pool_id )"

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

    db_table = "t_dcl_pools_data"
    if network_id == "MAINNET":
        db_table = "t_dcl_pools_data_mainnet"

    sql = "insert into " + db_table + "(pool_id, token_x, token_y, volume_x_in, volume_y_in, volume_x_out, " \
          "volume_y_out, total_order_x, total_order_y, total_x, total_y, total_fee_x_charged, total_fee_y_charged, " \
          "volume_x_in_grow, volume_y_in_grow, volume_x_out_grow, volume_y_out_grow, total_order_x_grow, " \
          "total_order_y_grow, token_x_price, token_y_price, token_x_decimal, token_y_decimal, timestamp, create_time) " \
          "values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())"

    insert_data = []
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        token_price = get_dcl_token_price(network_id)
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
                                data["total_order_y"], data["total_x"], data["total_y"], data["total_fee_x_charged"],
                                data["total_fee_y_charged"], data["volume_x_in_grow"],
                                data["volume_y_in_grow"], data["volume_x_out_grow"], data["volume_y_out_grow"],
                                data["total_order_x_grow"], data["total_order_y_grow"], token_x_price,
                                token_y_price, token_x_decimal, token_y_decimal, now))

            pool_id = data["pool_id"] + "_" + check_point
            order_x_price = (int(data["total_x"]) - int(data["total_fee_x_charged"])) / int("1" + "0" * int(token_x_decimal)) * float(token_x_price)
            order_y_price = (int(data["total_y"]) - int(data["total_fee_y_charged"])) / int("1" + "0" * int(token_y_decimal)) * float(token_y_price)
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
    db_table = "t_dcl_pools_data"
    if network_id == "MAINNET":
        db_table = "t_dcl_pools_data_mainnet"

    sql = "SELECT pool_id, SUM(volume_x_in_grow) AS volume_x_in_grow, SUM(volume_y_in_grow) AS volume_y_in_grow, " \
          "SUM(volume_x_out_grow) AS volume_x_out_grow , SUM(volume_y_out_grow) AS volume_y_out_grow, " \
          "SUM(total_order_x_grow) AS total_order_x_grow, SUM(total_order_y_grow) AS total_order_y_grow, " \
          "token_x_price, token_y_price, token_x_decimal, token_y_decimal " \
          "FROM " + db_table + " WHERE `timestamp` >= %s GROUP BY pool_id"

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
            add_redis_data(network_id, Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_24H_KEY"], pool_data["pool_id"], str(volume))
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
            add_redis_data(network_id, Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_LIST_KEY"] + "_" + pool_data["pool_id"], pool_id, json.dumps(pool_volume_data))
            redis_conn.end_pipe()

        redis_conn.close()
    except Exception as e:
        print("add dcl_pools to redis error:", e)
    finally:
        redis_conn.close()


def add_dcl_pools_tvl_to_redis(network_id, pool_id, pool_tvl_data):
    redis_conn = RedisProvider()
    try:
        redis_conn.begin_pipe()
        redis_conn.add_dcl_pools_tvl_data(network_id, pool_tvl_data["pool_id"], pool_id, json.dumps(pool_tvl_data, cls=Encoder))
        add_redis_data(network_id, Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_TVL_LIST_KEY"] + "_" + pool_tvl_data["pool_id"], pool_id, json.dumps(pool_tvl_data, cls=Encoder))
        redis_conn.end_pipe()
        redis_conn.close()
    except Exception as e:
        print("add dcl_pools to redis error:", e)
    finally:
        redis_conn.close()


def get_dcl_token_price(network_id):
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


def query_limit_order_log(network_id, owner_id):
    db_conn = get_db_connect(network_id)
    sql = "select order_id, tx_id, receipt_id from near_lake_limit_order where type = 'order_added' and owner_id = %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, owner_id)
        limit_order_data = cursor.fetchall()
        return limit_order_data
    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print("query limit_order_log to db error:", e)
    finally:
        cursor.close()


def query_limit_order_swap(network_id, owner_id):
    db_conn = get_db_connect(network_id)
    sql = "select tx_id, token_in,token_out,pool_id,point,amount_in,amount_out,timestamp, receipt_id from " \
          "near_lake_limit_order where type = 'swap' and owner_id = %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, owner_id)
        limit_order_data = cursor.fetchall()
        return limit_order_data
    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print("query limit_order_log to db error:", e)
    finally:
        cursor.close()


def add_account_assets_data(data_list):
    now_time = int(time.time())
    db_conn = get_db_connect(Cfg.NETWORK_ID)

    sql = "insert into t_account_assets_data(type, pool_id, farm_id, account_id, tokens, token_amounts, " \
          "token_decimals, token_prices, amount, `timestamp`, create_time) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())"

    insert_data = []
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        for data in data_list:
            insert_data.append((data["type"], data["pool_id"], data["farm_id"], data["account_id"], data["tokens"],
                                data["token_amounts"], data["token_decimals"], data["token_prices"],
                                data["amount"], now_time))

        cursor.executemany(sql, insert_data)
        db_conn.commit()

    except Exception as e:
        print("insert account assets assets log to db error:", e)
        print("insert account assets assets log to db insert_data:", insert_data)
    finally:
        cursor.close()


def get_token_price():
    tokens = {}
    db_conn = get_db_connect(Cfg.NETWORK_ID)
    sql = "select contract_address,price,`decimal` from mk_history_token_price where id in " \
          "(select max(id) from mk_history_token_price group by contract_address)"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        for row in rows:
            contract_address = row["contract_address"]
            token_data = {
                "contract_address": contract_address,
                "price": row["price"],
                "decimal": row["decimal"]
            }
            tokens[contract_address] = token_data
        return tokens
    except Exception as e:
        # Rollback on error
        print(e)
    finally:
        cursor.close()


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        super(DecimalEncoder, self).default(o)


def handle_account_pool_assets_data(network_id):
    now_time = int(time.time()) - 60 * 60
    db_conn = get_db_connect(Cfg.NETWORK_ID)
    sql = "select account_id,sum(amount) as amount from t_account_assets_data where `status` = '1' group by account_id"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        for row in rows:
            handle_account_pool_assets_h_data(network_id, now_time, row)
            handle_account_pool_assets_w_data(network_id, now_time, row)
            handle_account_pool_assets_m_data(network_id, now_time, row)
            handle_account_pool_assets_all_data(network_id, now_time, row)
        update_account_pool_assets_status()
    except Exception as e:
        print(e)
    finally:
        cursor.close()


def handle_account_pool_assets_h_data(network_id, now_time, row):
    redis_key = row["account_id"] + "_h"
    amount = row["amount"]
    ret_pool_assets = get_account_pool_assets(network_id, redis_key)
    time_array = time.localtime(now_time)
    now_date_time_h = time.strftime("%Y-%m-%d %H", time_array)
    pool_assets = []
    pool_asset_data = {
        "date_itme": now_date_time_h,
        "assets": amount
    }
    if ret_pool_assets is not None:
        pool_assets = json.loads(ret_pool_assets)
        if len(pool_assets) >= 24:
            pool_assets.pop(0)
    pool_assets.append(pool_asset_data)
    add_account_pool_assets_to_redis(network_id, redis_key, json.dumps(pool_assets, cls=DecimalEncoder, ensure_ascii=False))


def handle_account_pool_assets_w_data(network_id, now_time, row):
    redis_key = row["account_id"] + "_w"
    amount = row["amount"]
    ret_pool_assets = get_account_pool_assets(network_id, redis_key)
    time_array = time.localtime(now_time)
    now_date_time_w = time.strftime("%Y-%m-%d %H", time_array)
    pool_assets = []
    pool_asset_data = {
        "date_itme": now_date_time_w,
        "assets": amount
    }
    if ret_pool_assets is not None:
        pool_assets = json.loads(ret_pool_assets)
        if len(pool_assets) >= 168:
            pool_assets.pop(0)
    pool_assets.append(pool_asset_data)
    add_account_pool_assets_to_redis(network_id, redis_key, json.dumps(pool_assets, cls=DecimalEncoder, ensure_ascii=False))


def handle_account_pool_assets_m_data(network_id, now_time, row):
    redis_key = row["account_id"] + "_m"
    amount = row["amount"]
    ret_pool_assets = get_account_pool_assets(network_id, redis_key)
    time_array = time.localtime(now_time)
    now_date_time_m = time.strftime("%Y-%m-%d", time_array)
    pool_assets = []
    pool_asset_data = {
        "date_itme": now_date_time_m,
        "assets": amount
    }
    data_flag = True
    if ret_pool_assets is not None:
        pool_assets = json.loads(ret_pool_assets)
        for asset in pool_assets:
            if now_date_time_m == asset["date_itme"]:
                data_flag = False
                asset["assets"] = amount
        if len(pool_assets) >= 30 and data_flag:
            pool_assets.pop(0)
    if data_flag:
        pool_assets.append(pool_asset_data)
    set_lst = set()
    new_pool_assets = []
    for pool in pool_assets:
        if pool["date_itme"] not in set_lst:
            set_lst.add(pool["date_itme"])
            new_pool_assets.append(pool)
    add_account_pool_assets_to_redis(network_id, redis_key, json.dumps(new_pool_assets, cls=DecimalEncoder, ensure_ascii=False))


def handle_account_pool_assets_all_data(network_id, now_time, row):
    redis_key = row["account_id"] + "_all"
    amount = row["amount"]
    ret_pool_assets = get_account_pool_assets(network_id, redis_key)
    time_array = time.localtime(now_time)
    now_date_time_all = time.strftime("%Y-%m-%d", time_array)
    pool_assets = []
    pool_asset_data = {
        "date_itme": now_date_time_all,
        "assets": amount
    }
    data_flag = True
    if ret_pool_assets is not None:
        pool_assets = json.loads(ret_pool_assets)
        for asset in pool_assets:
            if now_date_time_all == asset["date_itme"]:
                data_flag = False
                asset["assets"] = amount
    if data_flag:
        pool_assets.append(pool_asset_data)
    add_account_pool_assets_to_redis(network_id, redis_key, json.dumps(pool_assets, cls=DecimalEncoder, ensure_ascii=False))


def add_account_pool_assets_to_redis(network_id, key, values):
    redis_conn = RedisProvider()
    redis_conn.begin_pipe()
    redis_conn.add_account_pool_assets(network_id, key, values)
    add_redis_data(network_id, Cfg.NETWORK[network_id]["REDIS_ACCOUNT_POOL_ASSETS_KEY"], key, values)
    redis_conn.end_pipe()
    redis_conn.close()


def update_account_pool_assets_status():
    db_conn = get_db_connect(Cfg.NETWORK_ID)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        sql = "update t_account_assets_data set `status` = '2' where `status` = '1'"
        cursor.execute(sql)
        # Submit to database for execution
        db_conn.commit()
    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print(e)
    finally:
        cursor.close()


def query_burrow_log(network_id, account_id, page_number, page_size):
    start_number = handel_page_number(page_number, page_size)
    db_conn = get_db_connect(network_id)
    sql = "select `event`, amount, token_id, `timestamp`, '' as tx_id, receipt_id from burrow_event_log " \
          "where account_id = %s and `event` in ('borrow','decrease_collateral','deposit'," \
          "'increase_collateral','repay','withdraw_succeeded')  order by `timestamp` desc " \
          "limit %s, %s"
    sql_count = "select count(*) as total_number from burrow_event_log where account_id = %s and `event` in " \
                "('borrow','decrease_collateral','deposit','increase_collateral','repay','withdraw_succeeded')"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (account_id, start_number, page_size))
        burrow_log = cursor.fetchall()
        cursor.execute(sql_count, account_id)
        burrow_log_count = cursor.fetchone()
        return burrow_log, burrow_log_count["total_number"]
    except Exception as e:
        print("query burrow_event_log to db error:", e)
    finally:
        cursor.close()


def query_meme_burrow_log(network_id, account_id, page_number, page_size):
    start_number = handel_page_number(page_number, page_size)
    db_conn = get_db_connect(network_id)
    sql = "select `event`, amount, token_id, `timestamp`, '' as tx_id, receipt_id from meme_burrow_event_log " \
          "where account_id = %s and `event` in ('borrow','decrease_collateral','deposit'," \
          "'increase_collateral','repay','withdraw_succeeded')  order by `timestamp` desc " \
          "limit %s, %s"
    sql_count = "select count(*) as total_number from meme_burrow_event_log where account_id = %s and `event` in " \
                "('borrow','decrease_collateral','deposit','increase_collateral','repay','withdraw_succeeded')"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (account_id, start_number, page_size))
        burrow_log = cursor.fetchall()
        cursor.execute(sql_count, account_id)
        burrow_log_count = cursor.fetchone()
        return burrow_log, burrow_log_count["total_number"]
    except Exception as e:
        print("query burrow_event_log to db error:", e)
    finally:
        cursor.close()


def handel_page_number(page_number, size):
    if page_number <= 1:
        start_number = 0
    else:
        start_number = (page_number - 1) * size
    return start_number


def get_history_token_price_by_token(ids, data_time):
    db_conn = get_db_connect(Cfg.NETWORK_ID)
    token_data_list = {}
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        for token_id in ids:
            sql = "select symbol, contract_address,price,`decimal`, `timestamp` from mk_history_token_price where " \
                  "contract_address = %s and `timestamp` >= %s limit 1"
            cursor.execute(sql, (token_id, data_time))
            ret = cursor.fetchone()
            token_data = {
                "symbol": ret["symbol"],
                "contract_address": ret["contract_address"],
                "price": float(ret["price"]),
                "decimal": ret["decimal"],
                "timestamp": ret["timestamp"]
            }
            token_data_list[ret["contract_address"]] = token_data
        return token_data_list
    except Exception as e:
        # Rollback on error
        print(e)
    finally:
        cursor.close()


def query_dcl_pool_log(network_id, start_block_id, end_block_id):
    db_conn = get_db_connect(network_id)
    sql = "select * from (select tla.event_method, tla.pool_id, '' as order_id, tla.lpt_id, '' as swapper, " \
          "'' as token_in, '' as token_out, '' as amount_in, '' as amount_out, '' as created_at, '' as cancel_at, " \
          "'' as completed_at, tla.owner_id, '' as `point`, '' as sell_token, '' as buy_token, " \
          "'' as request_cancel_amount, '' as actual_cancel_amount, '' as original_amount, '' as cancel_amount, " \
          "'' as remain_amount, '' as bought_amount, '' as original_deposit_amount, '' as swap_earn_amount, " \
          "tla.left_point, tla.right_point, tla.added_amount, '' as removed_amount, tla.cur_amount, " \
          "tla.paid_token_x, tla.paid_token_y, '' as refund_token_x, '' as refund_token_y, tla.tx_id, " \
          "tla.block_id, tla.`timestamp`, tla.args,tla.predecessor_id,tla.receiver_id, tla.create_time from " \
          "t_liquidity_added tla union all select 'liquidity_removed' as event_method, tlr.pool_id, '' as order_id, " \
          "tlr.lpt_id, '' as swapper, '' as token_in, '' as token_out, '' as amount_in, '' as amount_out, " \
          "'' as created_at, '' as cancel_at, '' as completed_at, tlr.owner_id, '' as `point`, '' as sell_token, " \
          "'' as buy_token, '' as request_cancel_amount, '' as actual_cancel_amount, '' as original_amount, " \
          "'' as cancel_amount, '' as remain_amount, '' as bought_amount, '' as original_deposit_amount, " \
          "'' as swap_earn_amount, tlr.left_point, tlr.right_point, '' as added_amount, tlr.removed_amount, " \
          "tlr.cur_amount, '' as paid_token_x, '' as paid_token_y, tlr.refund_token_x, tlr.refund_token_y, " \
          "tlr.tx_id, tlr.block_id, tlr.`timestamp`, tlr.args,tlr.predecessor_id,tlr.receiver_id, create_time " \
          "from t_liquidity_removed tlr union all select 'order_added' as event_method, toa.pool_id, toa.order_id, " \
          "'' as lpt_id, '' as swapper, '' as token_in, '' as token_out, '' as amount_in, '' as amount_out, " \
          "toa.created_at, '' as cancel_at, '' as completed_at, toa.owner_id, toa.`point`, toa.sell_token, " \
          "toa.buy_token, '' as request_cancel_amount, '' as actual_cancel_amount, toa.original_amount, " \
          "'' as cancel_amount, '' as remain_amount, '' as bought_amount, toa.original_deposit_amount, " \
          "toa.swap_earn_amount, '' as left_point, '' as right_point, '' as added_amount, '' as removed_amount, " \
          "'' as cur_amount, '' as paid_token_x, '' as paid_token_y, '' as refund_token_x, '' as refund_token_y, " \
          "toa.tx_id, toa.block_id, toa.`timestamp`, toa.args,toa.predecessor_id,toa.receiver_id, create_time from " \
          "t_order_added toa union all select 'order_cancelled' as event_method, toc.pool_id, toc.order_id, " \
          "'' as lpt_id, '' as swapper, '' as token_in, '' as token_out, '' as amount_in, '' as amount_out, " \
          "toc.created_at, toc.cancel_at, '' as completed_at, toc.owner_id, toc.`point`, toc.sell_token, " \
          "toc.buy_token, toc.request_cancel_amount, toc.actual_cancel_amount, toc.original_amount, " \
          "toc.cancel_amount, toc.remain_amount, toc.bought_amount, '' as original_deposit_amount, " \
          "'' as swap_earn_amount, '' as left_point, '' as right_point, '' as added_amount, '' as removed_amount, " \
          "'' as cur_amount, '' as paid_token_x, '' as paid_token_y, '' as refund_token_x, '' as refund_token_y, " \
          "toc.tx_id, toc.block_id, toc.`timestamp`, toc.args,toc.predecessor_id,toc.receiver_id, create_time " \
          "from t_order_cancelled toc union all select 'order_completed' as event_method, tocd.pool_id, " \
          "tocd.order_id, '' as lpt_id, '' as swapper, '' as token_in, '' as token_out, '' as amount_in, " \
          "'' as amount_out, tocd.created_at, '' as cancel_at, tocd.completed_at, tocd.owner_id, tocd.`point`, " \
          "tocd.sell_token, tocd.buy_token, '' as request_cancel_amount, '' as actual_cancel_amount, " \
          "tocd.original_amount, tocd.cancel_amount, '' as remain_amount, tocd.bought_amount, " \
          "tocd.original_deposit_amount, tocd.swap_earn_amount, '' as left_point, '' as right_point, " \
          "'' as added_amount, '' as removed_amount, '' as cur_amount, '' as paid_token_x, '' as paid_token_y, " \
          "'' as refund_token_x, '' as refund_token_y, tocd.tx_id, tocd.block_id, tocd.`timestamp`, " \
          "tocd.args,tocd.predecessor_id,tocd.receiver_id, create_time from t_order_completed tocd union all " \
          "select 'swap' as event_method, '' as pool_id, '' as order_id, '' as lpt_id, ts.swapper, " \
          "ts.token_in, ts.token_out, ts.amount_in, ts.amount_out, '' as created_at, '' as cancel_at, " \
          "'' as completed_at, ts.swapper as owner_id, '' as `point`, '' as sell_token, '' as buy_token, " \
          "'' as request_cancel_amount, '' as actual_cancel_amount, '' as original_amount, '' as cancel_amount, " \
          "'' as remain_amount, '' as bought_amount, '' as original_deposit_amount, '' as swap_earn_amount, " \
          "'' as left_point, '' as right_point, '' as added_amount, '' as removed_amount, '' as cur_amount, " \
          "'' as paid_token_x, '' as paid_token_y, '' as refund_token_x, '' as refund_token_y, ts.tx_id, " \
          "ts.block_id, ts.`timestamp`, ts.args,ts.predecessor_id,ts.receiver_id, create_time from t_swap ts) as " \
          "all_data where block_id >= %s and block_id <= %s order by `timestamp`"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (start_block_id, end_block_id))
        dcl_pool_log_data = cursor.fetchall()
        return dcl_pool_log_data
    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print("query query_dcl_pool_log to db error:", e)
    finally:
        cursor.close()


def add_v2_pool_data(data_list, network_id, pool_id_list):
    db_conn = get_db_connect(network_id)

    sql = "insert into dcl_pool_analysis(pool_id, point, fee_x, fee_y, l, tvl_x_l, " \
          "tvl_x_o, tvl_y_l, tvl_y_o, vol_x_in_l, vol_x_in_o, vol_x_out_l, vol_x_out_o, " \
          "vol_y_in_l, vol_y_in_o, vol_y_out_l, vol_y_out_o, p_fee_x, p_fee_y, p, cp, timestamp, create_time) " \
          "values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())"

    insert_data = []
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        for data in data_list:
            insert_data.append((data["pool_id"], data["point"], data["fee_x"], data["fee_y"], data["l"],
                                data["tvl_x_l"], data["tvl_x_o"], data["tvl_y_l"],
                                data["tvl_y_o"], data["vol_x_in_l"], data["vol_x_in_o"],
                                data["vol_x_out_l"], data["vol_x_out_o"], data["vol_y_in_l"], data["vol_y_in_o"],
                                data["vol_y_out_l"], data["vol_y_out_o"], data["p_fee_x"],
                                data["p_fee_y"], data["p"], data["cp"], data["timestamp"]))

        cursor.executemany(sql, insert_data)
        db_conn.commit()
    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print("insert v2 pool data to db error:", e)
    finally:
        cursor.close()
    handle_pool_point_data_to_redis(network_id, pool_id_list)


def handle_pool_point_data_to_redis(network_id, pool_id_list):
    now = int(datetime.now().replace(minute=0, second=0, microsecond=0).timestamp())
    timestamp = now - (1 * 24 * 60 * 60)
    db_conn = get_db_connect(network_id)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    redis_conn = RedisProvider()
    redis_conn.begin_pipe()
    try:
        for pool_id in pool_id_list:
            sql_24h = "select point,sum(fee_x) as fee_x,sum(fee_y) as fee_y,sum(tvl_x_l) as tvl_x_l," \
                      "sum(tvl_y_l) as tvl_y_l from dcl_pool_analysis where pool_id = %s " \
                      "and `timestamp` >= %s GROUP BY point order by point"
            cursor.execute(sql_24h, (pool_id, timestamp))
            point_data_24h = cursor.fetchall()
            redis_conn.add_pool_point_24h_assets(network_id, pool_id, json.dumps(point_data_24h))
            add_redis_data(network_id, Cfg.NETWORK[network_id]["REDIS_POOL_POINT_24H_DATA_KEY"], pool_id, json.dumps(point_data_24h))
            redis_conn.add_pool_point_24h_assets(network_id, pool_id + "timestamp", now)
            add_redis_data(network_id, Cfg.NETWORK[network_id]["REDIS_POOL_POINT_24H_DATA_KEY"], pool_id + "timestamp", now)
    except Exception as e:
        print("query dcl_pool_analysis to db error:", e)
    finally:
        cursor.close()
        redis_conn.end_pipe()
        redis_conn.close()


def add_dcl_user_liquidity_data(data_list, network_id):
    db_conn = get_db_connect(network_id)

    sql = "insert into dcl_user_liquidity(pool_id, account_id, point, l, tvl_x_l, tvl_y_l, p, timestamp, create_time) " \
          "values(%s,%s,%s,%s,%s,%s,%s,%s, now())"

    insert_data = []
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        for data in data_list:
            insert_data.append((data["pool_id"], data["account_id"], data["point"], data["l"], data["tvl_x_l"],
                                data["tvl_y_l"], data["p"], data["timestamp"]))

        cursor.executemany(sql, insert_data)
        db_conn.commit()

    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print("insert v2 pool data to db error:", e)
    finally:
        cursor.close()


def add_dcl_user_liquidity_fee_data(data_list, network_id):
    db_conn = get_db_connect(network_id)

    sql = "insert into dcl_user_liquidity_fee(pool_id, account_id, unclaimed_fee_x, unclaimed_fee_y, timestamp, create_time) " \
          "values(%s,%s,%s,%s,%s, now())"

    insert_data = []
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        for data in data_list:
            insert_data.append((data["pool_id"], data["account_id"], data["unclaimed_fee_x"], data["unclaimed_fee_y"],
                                data["timestamp"]))

        cursor.executemany(sql, insert_data)
        db_conn.commit()

    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print("insert v2 pool data to db error:", e)
    finally:
        cursor.close()


def query_recent_transaction_swap(network_id, pool_id):
    db_conn = get_db_connect(network_id)
    sql = "select token_in, token_out, swap_in, swap_out,`timestamp`, '' as tx_id,block_hash as receipt_id from " \
          "near_lake_swap_log where pool_id = %s order by `timestamp` desc limit 50"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, pool_id)
        recent_transaction_data = cursor.fetchall()
        return recent_transaction_data
    except Exception as e:
        print("query near_lake_swap_log to db error:", e)
    finally:
        cursor.close()


def query_recent_transaction_dcl_swap(network_id, pool_id):
    db_conn = get_db_connect(network_id)
    sql = "select token_in, token_out, amount_in, amount_out,`timestamp`, '' as tx_id,tx_id as receipt_id from " \
          "t_swap where amount_in > '0' and pool_id like '%"+pool_id+"%' order by `timestamp` desc limit 50"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
        recent_transaction_data = cursor.fetchall()
        return recent_transaction_data
    except Exception as e:
        print("query t_swap to db error:", e)
    finally:
        cursor.close()


def query_recent_transaction_liquidity(network_id, pool_id):
    db_conn = get_db_connect(network_id)
    sql = "select method_name, pool_id, shares, `timestamp`, '' as tx_id, amounts,block_hash as receipt_id, " \
          "amount_in, amount_out from near_lake_liquidity_log where pool_id = %s order by `timestamp` desc limit 50"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, pool_id)
        recent_transaction_data = cursor.fetchall()
        return recent_transaction_data
    except Exception as e:
        print("query near_lake_liquidity_log to db error:", e)
    finally:
        cursor.close()


def query_recent_transaction_dcl_liquidity(network_id, pool_id):
    db_conn = get_db_connect(network_id)
    sql = "select all_data.method_name,all_data.amount_x,all_data.amount_y,all_data.`timestamp`,'' as tx_id," \
          "all_data.receipt_id from (select tla.event_method as method_name, sum(cast(tla.paid_token_x as " \
          "decimal(64, 0))) as amount_x, sum(cast(tla.paid_token_y as decimal(64, 0))) as amount_y, tla.`timestamp`, " \
          "tla.tx_id as receipt_id from t_liquidity_added as tla where tla.pool_id = %s and " \
          "tla.event_method != 'liquidity_merge' group by tla.tx_id, tla.event_method, tla.`timestamp` union all select tlr.event_method as method_name, " \
          "sum(cast(tlr.refund_token_x as decimal(64, 0))) as amount_x,sum(cast(tlr.refund_token_y as decimal(64, 0))) " \
          "as amount_y, tlr.`timestamp`, tlr.tx_id as receipt_id from t_liquidity_removed as tlr where " \
          "tlr.pool_id = %s and tlr.removed_amount > 0 group by tlr.tx_id, tlr.event_method, tlr.`timestamp`) as all_data" \
          " order by `timestamp` desc limit 50"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (pool_id, pool_id))
        recent_transaction_data = cursor.fetchall()
        return recent_transaction_data if recent_transaction_data is not None else []
    except Exception as e:
        print("query t_liquidity_added to db error:", e)
        return []
    finally:
        cursor.close()


def query_recent_transaction_limit_order(network_id, pool_id):
    db_conn = get_db_connect(network_id)
    sql = "select all_data.method_name,all_data.sell_token,all_data.amount,all_data.point,all_data.`timestamp`, " \
          "'' as tx_id,all_data.tx_id as receipt_id from (select 'order_cancelled' as method_name, sell_token,  " \
          "actual_cancel_amount as amount, point,`timestamp`,tx_id from t_order_cancelled where pool_id = %s " \
          "and actual_cancel_amount != '0' union all select 'order_added' as method_name, sell_token,  " \
          "original_amount as amount, point,`timestamp`,tx_id from t_order_added where pool_id = %s and  " \
          "(args like '%%%%LimitOrderWithSwap%%%%' or args like '%%%%LimitOrder%%%%')) as all_data order by " \
          "all_data.`timestamp`  desc limit 50"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (pool_id, pool_id))
        recent_transaction_data = cursor.fetchall()
        return recent_transaction_data
    except Exception as e:
        print("query recent_transaction_limit_order to db error:", e)
    finally:
        cursor.close()


def query_dcl_bin_points(network_id, pool_id, bin_point_number):
    db_conn = get_db_connect(network_id)
    # 优化：使用 JOIN 替代子查询，性能更好
    sql = "SELECT pool_id,point,fee_x,fee_y,l,tvl_x_l,tvl_x_o,tvl_y_l,tvl_y_o," \
          "vol_x_in_l,vol_x_in_o,vol_x_out_l,vol_x_out_o,vol_y_in_l,vol_y_in_o," \
          "vol_y_out_l,vol_y_out_o,p_fee_x,p_fee_y,p,cp,`timestamp` " \
          "FROM dcl_pool_analysis WHERE pool_id = %s and `timestamp` = %s " \
          "and `point` >= %s and `point` <= %s ORDER BY point"
    sql1 = "select `cp`, `timestamp` from dcl_pool_analysis where pool_id = %s order by id desc limit 1"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql1, pool_id)
        cp_point_data = cursor.fetchone()
        cp_point = int(cp_point_data["cp"])
        start_point = cp_point - (bin_point_number * 10)
        end_point = cp_point + (bin_point_number * 10)
        cp_timestamp = cp_point_data["timestamp"]
        cursor.execute(sql, (pool_id, cp_timestamp, start_point, end_point))
        point_data = cursor.fetchall()
        pool_id_list = []
        point_data_timestamp = get_pool_point_24h_by_pool_id(network_id, pool_id + "timestamp")
        now = int(datetime.now().replace(minute=0, second=0, microsecond=0).timestamp())
        if point_data_timestamp is None or now - int(point_data_timestamp) > 3600:
            pool_id_list.append(pool_id)
            handle_pool_point_data_to_redis(network_id, pool_id_list)
        point_data_24h = get_pool_point_24h_by_pool_id(network_id, pool_id)
        return point_data, point_data_24h, start_point, end_point
    except Exception as e:
        print("query dcl_pool_analysis to db error:", e)
        return [], None
    finally:
        cursor.close()


def query_dcl_points(network_id, pool_id):
    db_conn = get_db_connect(network_id)
    # 优化：使用 JOIN 替代子查询，性能更好
    sql = "SELECT t1.pool_id,t1.point,t1.fee_x,t1.fee_y,t1.l,t1.tvl_x_l,t1.tvl_x_o,t1.tvl_y_l,t1.tvl_y_o," \
          "t1.vol_x_in_l,t1.vol_x_in_o,t1.vol_x_out_l,t1.vol_x_out_o,t1.vol_y_in_l,t1.vol_y_in_o," \
          "t1.vol_y_out_l,t1.vol_y_out_o,t1.p_fee_x,t1.p_fee_y,t1.p,t1.cp,t1.`timestamp` " \
          "FROM dcl_pool_analysis t1 " \
          "INNER JOIN (SELECT pool_id, MAX(`timestamp`) as max_timestamp FROM dcl_pool_analysis WHERE pool_id = %s GROUP BY pool_id) t2 " \
          "ON t1.pool_id = t2.pool_id AND t1.`timestamp` = t2.max_timestamp " \
          "WHERE t1.pool_id = %s ORDER BY t1.point"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (pool_id, pool_id))
        point_data = cursor.fetchall()
        pool_id_list = []
        point_data_timestamp = get_pool_point_24h_by_pool_id(network_id, pool_id + "timestamp")
        now = int(datetime.now().replace(minute=0, second=0, microsecond=0).timestamp())
        if point_data_timestamp is None or now - int(point_data_timestamp) > 3600:
            pool_id_list.append(pool_id)
            handle_pool_point_data_to_redis(network_id, pool_id_list)
        point_data_24h = get_pool_point_24h_by_pool_id(network_id, pool_id)
        return point_data, point_data_24h
    except Exception as e:
        print("query dcl_pool_analysis to db error:", e)
        return [], None
    finally:
        cursor.close()


def query_dcl_points_by_account(network_id, pool_id, account_id, start_point, end_point):
    db_conn = get_db_connect(network_id)
    sql = "select pool_id,account_id,point,l,tvl_x_l,tvl_y_l,p,`timestamp`,create_time from dcl_user_liquidity " \
          "where pool_id = %s and account_id = %s and `timestamp` >= (select max(`timestamp`) " \
          "from dcl_user_liquidity) and point >= %s and point <= %s order by point"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (pool_id, account_id, start_point, end_point))
        point_data = cursor.fetchall()
        return point_data
    except Exception as e:
        print("query dcl_user_liquidity to db error:", e)
    finally:
        cursor.close()


def query_dcl_user_unclaimed_fee(network_id, pool_id, account_id):
    db_conn = get_db_connect(network_id)
    sql = "select unclaimed_fee_x, unclaimed_fee_y from dcl_user_liquidity_fee where pool_id = %s and " \
          "account_id = %s and `timestamp` >= (select max(`timestamp`) from dcl_user_liquidity_fee where " \
          "pool_id = %s and account_id = %s)"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (pool_id, account_id, pool_id, account_id))
        point_data = cursor.fetchall()
        return point_data
    except Exception as e:
        print("query dcl_user_liquidity_fee to db error:", e)
    finally:
        cursor.close()


def query_dcl_user_unclaimed_fee_24h(network_id, pool_id, account_id):
    now = int(time.time())
    timestamp = now - (1 * 24 * 60 * 60)
    db_conn = get_db_connect(network_id)
    sql = "select * from dcl_user_liquidity_fee where pool_id = %s and account_id = %s and `timestamp` <= %s " \
          "order by `timestamp` desc limit 1"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (pool_id, account_id, timestamp))
        point_data = cursor.fetchall()
        return point_data
    except Exception as e:
        print("query dcl_user_liquidity_fee to db error:", e)
    finally:
        cursor.close()


def query_dcl_user_claimed_fee(network_id, pool_id, account_id):
    db_conn = get_db_connect(network_id)
    sql = "select sum(cast(total_fee_x as decimal(64, 0))) as claimed_fee_x, sum(cast(total_fee_y as " \
          "decimal(64, 0))) as claimed_fee_y from (select sum(cast(claim_fee_token_x as decimal(64, 0))) as " \
          "total_fee_x, sum(cast(claim_fee_token_y as decimal(64, 0))) as total_fee_y from " \
          "t_liquidity_added where pool_id = %s and owner_id = %s and event_method in( 'liquidity_append', " \
          "'liquidity_merge') union all select sum(cast(claim_fee_token_x as decimal(64, 0))) as total_fee_x, " \
          "sum(cast(claim_fee_token_y as decimal(64, 0))) as " \
          "total_fee_y from t_liquidity_removed where pool_id = %s and owner_id = %s and event_method = " \
          "'liquidity_removed') as fee"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (pool_id, account_id, pool_id, account_id))
        recent_transaction_data = cursor.fetchall()
        return recent_transaction_data
    except Exception as e:
        print("query t_liquidity_removed to db error:", e)
    finally:
        cursor.close()


def query_dcl_user_claimed_fee_24h(network_id, pool_id, account_id):
    now = int(time.time())
    timestamp = now - (1 * 24 * 60 * 60)
    db_conn = get_db_connect(network_id)
    sql = "select sum(cast(total_fee_x as decimal(64, 0))) as claimed_fee_x, sum(cast(total_fee_y as " \
          "decimal(64, 0))) as claimed_fee_y from (select sum(cast(claim_fee_token_x as decimal(64, 0))) as " \
          "total_fee_x, sum(cast(claim_fee_token_y as decimal(64, 0))) as total_fee_y from " \
          "t_liquidity_added where pool_id = %s and owner_id = %s and event_method in( 'liquidity_append', " \
          "'liquidity_merge') and `timestamp` <= %s union all select sum(cast(claim_fee_token_x as " \
          "decimal(64, 0))) as total_fee_x, sum(cast(claim_fee_token_y as decimal(64, 0))) as total_fee_y from " \
          "t_liquidity_removed where pool_id = %s and owner_id = %s " \
          "and event_method = 'liquidity_removed' and `timestamp` <= %s) as fee"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (pool_id, account_id, timestamp, pool_id, account_id, timestamp))
        recent_transaction_data = cursor.fetchall()
        return recent_transaction_data
    except Exception as e:
        print("query t_liquidity_removed to db error:", e)
    finally:
        cursor.close()


def query_dcl_user_tvl(network_id, pool_id, account_id):
    db_conn = get_db_connect(network_id)
    sql = "select sum(tvl_x_l) as tvl_x_l, sum(tvl_y_l) as tvl_y_l, MAX(`timestamp`) as `timestamp` from dcl_user_liquidity where " \
          "pool_id = %s and account_id = %s and `timestamp` >= (select max(`timestamp`) from " \
          "dcl_user_liquidity where pool_id = %s and account_id = %s)"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (pool_id, account_id, pool_id, account_id))
        point_data = cursor.fetchall()
        return point_data
    except Exception as e:
        print("query dcl_user_liquidity to db error:", e)
        return []
    finally:
        cursor.close()


def query_dcl_user_change_log(network_id, pool_id, account_id, user_token_timestamp):
    timestamp = user_token_timestamp - (1 * 24 * 60 * 60)
    db_conn = get_db_connect(network_id)
    sql = "select event_method,paid_token_x as token_x,paid_token_y as token_y,remove_token_x,remove_token_y," \
          "merge_token_x,merge_token_y,`timestamp` from t_liquidity_added where pool_id = %s and owner_id = %s " \
          "and event_method in('liquidity_append', 'liquidity_added') and `timestamp` >= %s " \
          "union all select event_method,refund_token_x as token_x, refund_token_y as token_y, null as remove_token_x," \
          "null as remove_token_y,null as merge_token_x,null as merge_token_y,`timestamp`  from t_liquidity_removed " \
          "where pool_id = %s and owner_id = %s and event_method = 'liquidity_removed' and removed_amount > '0' " \
          "and `timestamp` >= %s " \
          "order by `timestamp` desc"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (pool_id, account_id, timestamp, pool_id, account_id, timestamp))
        recent_transaction_data = cursor.fetchall()
        return recent_transaction_data
    except Exception as e:
        print("query t_liquidity_added to db error:", e)
    finally:
        cursor.close()


def add_orderly_trading_data(trading_data_info):
    db_conn = get_crm_db_connect(Cfg.NETWORK_ID)
    sql = "insert into t_trading(data_source, trading_type, token_in, token_out, side, `status`, order_id, " \
          "account_id, price, type, quantity, amount, executed, visible, total_fee, fee_asset, client_order_id, " \
          "average_executed_price, created_time, updated_time, `timestamp`, create_time) values(%s,%s,%s,%s,%s,%s," \
          "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())"
    par = (trading_data_info["data_source"], trading_data_info["trading_type"], trading_data_info["token_in"],
           trading_data_info["token_out"], trading_data_info["side"], trading_data_info["status"],
           trading_data_info["order_id"], trading_data_info["account_id"], trading_data_info["price"],
           trading_data_info["type"], trading_data_info["quantity"], trading_data_info["amount"],
           trading_data_info["executed"], trading_data_info["visible"], trading_data_info["total_fee"],
           trading_data_info["fee_asset"], trading_data_info["client_order_id"],
           trading_data_info["average_executed_price"], trading_data_info["created_time"],
           trading_data_info["updated_time"], trading_data_info["timestamp"])
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, par)
        db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        raise e
    finally:
        cursor.close()


def add_liquidation_result(network_id, key, values):
    now_time = int(time.time())
    db_conn = get_burrow_connect(network_id)

    sql = "insert into liquidation_result_info(`key`, `values`, `timestamp`, `created_time`, `updated_time`) " \
          "values(%s,%s,%s, now(), now())"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (key, values, now_time))
        db_conn.commit()

    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print("insert liquidation_result_info to db error:", e)
        raise e
    finally:
        cursor.close()


def update_liquidation_result(network_id, key, values):
    db_conn = get_burrow_connect(network_id)
    sql = "update liquidation_result_info set `values` = %s where `key` = %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (values, key))
        db_conn.commit()
    except Exception as e:
        # Rollback on error
        db_conn.rollback()
        print("update liquidation_result_info to db error:", e)
        raise e
    finally:
        cursor.close()


def get_liquidation_result(network_id, key):
    db_conn = get_burrow_connect(network_id)
    sql = "select `key`, `values`, `timestamp`, `created_time`, `updated_time` from liquidation_result_info " \
          "where `key` = %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, key)
        row = cursor.fetchone()
        return row
    except Exception as e:
        db_conn.rollback()
        print("query liquidation_result_info to db error:", e)
        return None
    finally:
        cursor.close()


def add_user_wallet_info(network_id, account_id, wallet_address):
    db_conn = get_db_connect(network_id)
    query_sql = "select id from t_user_wallet_info where account_id = %s and wallet_address = %s"
    sql = "insert into t_user_wallet_info(account_id, wallet_address, `created_time`, `updated_time`) " \
          "values(%s,%s, now(), now())"
    cursor = db_conn.cursor()
    try:
        cursor.execute(query_sql, (account_id, wallet_address))
        row = cursor.fetchone()
        if row is None:
            cursor.execute(sql, (account_id, wallet_address))
            db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        print("insert t_user_wallet_info to db error:", e)
        raise e
    finally:
        cursor.close()


def get_pools_volume_24h(network_id):
    db_conn = get_db_connect(network_id)
    max_time_sql = "select time from go_volume_24h_pool order by time desc limit 1"
    sql = f"select pool_id, volume_24h from go_volume_24h_pool where time = %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(max_time_sql)
        max_time_data = cursor.fetchone()
        max_time = int(max_time_data["time"])
        cursor.execute(sql, max_time)
        results = cursor.fetchall()
        return results
    except Exception as e:
        print("query multi_pools_volume_rolling_24h_sum to db error:", e)
    finally:
        cursor.close()


def query_burrow_liquidate_log(network_id, account_id, page_number, page_size):
    start_number = handel_page_number(page_number, page_size)
    db_conn = get_db_connect(network_id)
    receipt_sql = "select receipt_id from burrow_event_log where liquidation_account_id = %s and " \
                  "`event` = 'liquidate' order by `timestamp` desc limit %s, %s"
    liquidate_sql = f"select `event`, amount, token_id, `timestamp`, receipt_id, is_read, update_time, position from " \
                    f"burrow_event_log where receipt_id in ('%s') order by `timestamp` desc"
    sql_count = "select count(*) as total_number from burrow_event_log where liquidation_account_id = %s " \
                "and `event` = 'liquidate'"
    not_read_sql_count = "select count(*) as total_number from burrow_event_log where liquidation_account_id = %s " \
                         "and `event` = 'liquidate' and is_read = '0'"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(receipt_sql, (account_id, start_number, page_size))
        receipt_log = cursor.fetchall()
        receipt_ids = [entry['receipt_id'] for entry in receipt_log]
        if receipt_ids:
            receipt_ids_placeholder = "','".join(map(str, receipt_ids))
            cursor.execute(liquidate_sql % receipt_ids_placeholder)
            liquidate_log_list = cursor.fetchall()
        else:
            liquidate_log_list = []
        cursor.execute(sql_count, account_id)
        burrow_log_count = cursor.fetchone()
        cursor.execute(not_read_sql_count, account_id)
        not_read_count = cursor.fetchone()
        ret_liquidate_log = handel_liquidate_log_data(liquidate_log_list, account_id)
        return ret_liquidate_log, burrow_log_count["total_number"], not_read_count["total_number"]
    except Exception as e:
        print("query burrow_liquidate_log to db error:", e)
    finally:
        cursor.close()


def handel_liquidate_log_data(liquidate_log_list, account_id):
    liquidate_list = []
    receipt_data = {}
    for burrow_log in liquidate_log_list:
        receipt_id = burrow_log["receipt_id"]
        event = burrow_log["event"]
        timestamp = burrow_log["timestamp"]
        position = burrow_log["position"]
        time_second = int(int(timestamp) / 1000000000)
        updated_at = int(burrow_log["update_time"].timestamp())
        is_read = False if burrow_log["is_read"] == "0" else True
        if receipt_id in receipt_data:
            repaid_assets = receipt_data[receipt_id]["RepaidAssets"]
            liquidated_assets = receipt_data[receipt_id]["LiquidatedAssets"]
        else:
            repaid_assets = []
            liquidated_assets = []
            receipt_data[receipt_id] = {
                "liquidation_account_id": account_id,
                "createdAt": time_second,
                "isRead": is_read,
                "updatedAt": updated_at,
                "RepaidAssets": repaid_assets,
                "LiquidatedAssets": liquidated_assets,
                "position": position
            }
        if event == "borrow":
            repaid_assets_data = {"amount": burrow_log["amount"], "token_id": burrow_log["token_id"]}
            repaid_assets.append(repaid_assets_data)
        if event == "withdraw_started":
            liquidated_assets_data = {"amount": burrow_log["amount"], "token_id": burrow_log["token_id"]}
            liquidated_assets.append(liquidated_assets_data)
        if repaid_assets:
            receipt_data[receipt_id]["RepaidAssets"] = repaid_assets
        if liquidated_assets:
            receipt_data[receipt_id]["LiquidatedAssets"] = liquidated_assets

    for k, v in receipt_data.items():
        liquidate_data = {
            "healthFactor_after": None,
            "RepaidAssets": v["RepaidAssets"],
            "isRead": v["isRead"],
            "createdAt": v["createdAt"],
            "position": v["position"],
            "liquidation_type": "liquidate",
            "account_id": v["liquidation_account_id"],
            "healthFactor_before": None,
            "LiquidatedAssets": v["LiquidatedAssets"],
            "isDeleted": False,
            "updatedAt": v["updatedAt"],
            "receipt_id": k,
        }
        liquidate_list.append(liquidate_data)
    return liquidate_list


def update_burrow_liquidate_log(network_id, receipt_ids):
    placeholders = ','.join(['%s'] * len(receipt_ids))
    sql = f"UPDATE burrow_event_log SET is_read = '1' WHERE receipt_id IN ({placeholders})"
    db_conn = get_db_connect(network_id)
    cursor = db_conn.cursor()
    try:
        cursor.execute(sql, receipt_ids)
        db_conn.commit()
    except Exception as e:
        print("update burrow_liquidate_log to db error:", e)
    finally:
        cursor.close()


def get_whitelisted_tokens_to_db(network_id):
    token_list = []
    db_conn = get_db_connect(network_id)
    sql = f"select token_address from whitelisted_tokens"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
        results = cursor.fetchall()
        for result in results:
            token_list.append(result["token_address"])
        return token_list
    except Exception as e:
        print("query whitelisted_tokens to db error:", e)
    finally:
        cursor.close()


def query_conversion_token_record(network_id, account_id, page_number, page_size, contract_id):
    start_number = handel_page_number(page_number, page_size)
    db_conn = get_db_connect(network_id)
    if contract_id == "orhea-token-conversion.stg.ref-dev-team.near":
        sql = "SELECT ctl.`event`, ctl.conversion_id, ctl.conversion_type, ctl.account_id, ctl.source_token_id, " \
              "ctl.target_token_id, ctl.source_amount, ctl.target_amount, ctl.start_time_ms, ctl.end_time_ms, " \
              "ctl.block_id, ctl.`timestamp`, ctl.receipt_id, 0 AS `status`,COALESCE(claims.total_claimed, '0') " \
              "AS claim_target_amount FROM conversion_token_log_stg ctl LEFT JOIN (SELECT conversion_id, account_id, " \
              "CAST(SUM(CAST(target_amount AS DECIMAL(65,0))) AS CHAR) AS total_claimed FROM " \
              "conversion_token_log_stg WHERE `event` = 'claim_succeeded' " \
              "GROUP BY conversion_id, account_id) claims ON claims.conversion_id = ctl.conversion_id " \
              "AND claims.account_id = ctl.account_id WHERE ctl.account_id = %s " \
              "AND ctl.`event` = 'create_conversion' ORDER BY ctl.`timestamp` DESC LIMIT %s, %s"
        sql_count = "select count(*) as total_number from conversion_token_log_stg " \
                    "where account_id = %s and `event` = 'create_conversion'"
    else:
        sql = "SELECT ctl.`event`, ctl.conversion_id, ctl.conversion_type, ctl.account_id, ctl.source_token_id, " \
              "ctl.target_token_id, ctl.source_amount, ctl.target_amount, ctl.start_time_ms, ctl.end_time_ms, " \
              "ctl.block_id, ctl.`timestamp`, ctl.receipt_id, 0 AS `status`,COALESCE(claims.total_claimed, '0') " \
              "AS claim_target_amount FROM conversion_token_log ctl LEFT JOIN (SELECT conversion_id, account_id, " \
              "CAST(SUM(CAST(target_amount AS DECIMAL(65,0))) AS CHAR) AS total_claimed FROM " \
              "conversion_token_log WHERE `event` = 'claim_succeeded' " \
              "GROUP BY conversion_id, account_id) claims ON claims.conversion_id = ctl.conversion_id " \
              "AND claims.account_id = ctl.account_id WHERE ctl.account_id = %s " \
              "AND ctl.`event` = 'create_conversion' ORDER BY ctl.`timestamp` DESC LIMIT %s, %s"
        sql_count = "select count(*) as total_number from conversion_token_log " \
                    "where account_id = %s and `event` = 'create_conversion'"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        now_time = int(time.time()) * 1000
        cursor.execute(sql, (account_id, start_number, page_size))
        conversion_token_log = cursor.fetchall()
        cursor.execute(sql_count, account_id)
        conversion_token_log_count = cursor.fetchone()
        for conversion_token_data in conversion_token_log:
            # status(0:锁定状态，1:可领取，2：已领取)
            end_time_ms = conversion_token_data.get("end_time_ms")
            claim_target_amount = conversion_token_data.get("claim_target_amount") or "0"
            target_amount = conversion_token_data.get("target_amount") or "0"
            if end_time_ms is not None and int(end_time_ms) <= now_time:
                if int(claim_target_amount) >= int(target_amount):
                    conversion_token_data["status"] = "2"
                else:
                    conversion_token_data["status"] = "1"
        return conversion_token_log, conversion_token_log_count["total_number"]
    except Exception as e:
        print("query query_conversion_token_record to db error:", e)
        return [], 0
    finally:
        cursor.close()


def get_token_day_data_index_number(network_id):
    db_conn = get_db_connect(network_id)
    query_sql = "select index_number from token_day_data order by index_number desc limit 1"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql)
        index_number_data = cursor.fetchone()
        if index_number_data is None:
            index_number = 0
        else:
            index_number = index_number_data["index_number"]
        return index_number
    except Exception as e:
        print("get_token_day_data_index_number to db error:", e)
    finally:
        cursor.close()
    return


def get_token_day_data_list(network_id, number, page_number, page_size):
    max_index_number = get_token_day_data_index_number(network_id)
    index_number = max_index_number - number
    start_number = handel_page_number(page_number, page_size)
    db_conn = get_db_connect(network_id)
    query_sql = "select token_id, account_id, balance, index_number, `rank`, `timestamp` from token_day_data where index_number > %s ORDER BY id DESC LIMIT %s, %s"
    sql_count = "select count(*) as total_number from token_day_data where index_number > %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql, (index_number, start_number, page_size))
        token_holders_data = cursor.fetchall()
        cursor.execute(sql_count, index_number)
        total_number_data = cursor.fetchone()
        return token_holders_data, total_number_data["total_number"]
    except Exception as e:
        print("get_token_day_data_list to db error:", e)
    finally:
        cursor.close()
    return


def get_conversion_token_day_data_index_number(network_id):
    db_conn = get_db_connect(network_id)
    query_sql = "select index_number from conversion_token_day_data order by index_number desc limit 1"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql)
        index_number_data = cursor.fetchone()
        if index_number_data is None:
            index_number = 0
        else:
            index_number = index_number_data["index_number"]
        return index_number
    except Exception as e:
        print("get_token_day_data_index_number to db error:", e)
    finally:
        cursor.close()
    return


def get_conversion_token_day_data_list(network_id, number, page_number, page_size):
    max_index_number = get_conversion_token_day_data_index_number(network_id)
    index_number = max_index_number - number
    start_number = handel_page_number(page_number, page_size)
    db_conn = get_db_connect(network_id)
    query_sql = "select token_id, account_id, balance, index_number, `rank`, target_amount, locking_duration, `type`, `timestamp` from conversion_token_day_data where index_number > %s ORDER BY id DESC LIMIT %s, %s"
    sql_count = "select count(*) as total_number from conversion_token_day_data where index_number > %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql, (index_number, start_number, page_size))
        token_holders_data = cursor.fetchall()
        cursor.execute(sql_count, index_number)
        total_number_data = cursor.fetchone()
        return token_holders_data, total_number_data["total_number"]
    except Exception as e:
        print("get_token_day_data_list to db error:", e)
    finally:
        cursor.close()
    return


def get_rhea_token_day_data_index_number(network_id):
    db_conn = get_db_connect(network_id)
    query_sql = "select index_number from rhea_token_day_data order by index_number desc limit 1"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql)
        index_number_data = cursor.fetchone()
        if index_number_data is None:
            index_number = 0
        else:
            index_number = index_number_data["index_number"]
        return index_number
    except Exception as e:
        print("get_rhea_token_day_data_index_number to db error:", e)
    finally:
        cursor.close()
    return


def get_rhea_token_day_data_list(network_id, number, page_number, page_size):
    max_index_number = get_rhea_token_day_data_index_number(network_id)
    index_number = max_index_number - number
    start_number = handel_page_number(page_number, page_size)
    db_conn = get_db_connect(network_id)
    query_sql = "select account_id, airdrop_balance, rhea_balance, stake_rhea_balance, lp_balance, lock_boost_balance, lending_balance, index_number, `timestamp` from rhea_token_day_data where index_number > %s ORDER BY id DESC LIMIT %s, %s"
    sql_count = "select count(*) as total_number from rhea_token_day_data where index_number > %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql, (index_number, start_number, page_size))
        rhea_token_day_data_list = cursor.fetchall()
        cursor.execute(sql_count, index_number)
        total_number_data = cursor.fetchone()
        return rhea_token_day_data_list, total_number_data["total_number"]
    except Exception as e:
        print("get_token_day_data_list to db error:", e)
    finally:
        cursor.close()
    return


def add_user_swap_record(network_id, account_id, is_accept_price_impact, router_path, router_type, token_in, token_out, amount_in, amount_out, slippage, tx_hash):
    db_conn = get_db_connect(network_id)
    sql = "insert into swap_record_reporting(account_id, is_accept_price_impact, router_path, router_type, " \
          "token_in, token_out, amount_in, amount_out, slippage, tx_hash, " \
          "`created_at`, `updated_at`) values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())"
    cursor = db_conn.cursor()
    try:
        cursor.execute(sql, (account_id, is_accept_price_impact, router_path, router_type, token_in, token_out, amount_in, amount_out, slippage, tx_hash))
        db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        print("insert swap_record_reporting to db error:", e)
        raise e
    finally:
        cursor.close()


def add_multichain_lending_requests(network_id, mca_id, wallet, data_list, page_display_data):
    import uuid
    batch_id = uuid.uuid4()
    db_conn = get_db_connect(network_id)
    # 使用UTC+0时区的时间
    utc_now = datetime.utcnow()
    sql = "insert into multichain_lending_requests(mca_id, `wallet`, `request`, batch_id, `sequence`, " \
          "`created_at`, `updated_at`) values(%s,%s,%s,%s,%s,%s,%s)"
    insert_sql = "insert into multichain_lending_report_data(`type`, mca_id, `wallet`, batch_id, page_display_data" \
                 ", `created_at`, `updated_at`) values(%s,%s,%s,%s,%s,%s,%s)"
    insert_data = []
    cursor = db_conn.cursor()
    try:
        i = 0
        for data in data_list:
            if isinstance(data, dict):
                data_json = json.dumps(data)
            elif isinstance(data, str):
                try:
                    json.loads(data)
                    data_json = data
                except (json.JSONDecodeError, TypeError):
                    data_json = json.dumps(data)
            else:
                data_json = json.dumps(data)
            insert_data.append((mca_id, wallet, data_json, batch_id, i, utc_now, utc_now))
            i += 1
        if len(insert_data) > 0:
            cursor.executemany(sql, insert_data)
            if page_display_data != "":
                cursor.execute(insert_sql, (1, mca_id, wallet, batch_id, page_display_data, utc_now, utc_now))
            db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        print("insert multichain_lending_requests to db error:", e)
        raise e
    finally:
        cursor.close()
    return batch_id


def add_multichain_lending_report(network_id, mca_id, wallet, request_hash, page_display_data):
    db_conn = get_db_connect(network_id)
    # 使用UTC+0时区的时间
    utc_now = datetime.utcnow()
    sql = "insert into multichain_lending_report_data(`type`, mca_id, `wallet`, request_hash, page_display_data" \
          ", `created_at`, `updated_at`) values(%s,%s,%s,%s,%s,%s,%s)"
    cursor = db_conn.cursor()
    try:
        cursor.execute(sql, (2, mca_id, wallet, request_hash, page_display_data, utc_now, utc_now))
        db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        print("insert multichain_lending_report_data to db error:", e)
        raise e
    finally:
        cursor.close()
    return request_hash


def query_multichain_lending_config(network_id):
    db_conn = get_db_connect(network_id)
    sql = "select `key`,`value` from multichain_lending_config"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
        point_data = cursor.fetchall()
        return point_data
    except Exception as e:
        print("query multichain_lending_config to db error:", e)
    finally:
        cursor.close()


def query_multichain_lending_history(network_id, mca_id, page_number, page_size):
    start_number = handel_page_number(page_number, page_size)
    db_conn = get_db_connect(network_id)
    query_sql = "select * from multichain_lending_report_data where mca_id = %s ORDER BY id DESC LIMIT %s, %s"
    sql_count = "select count(*) as total_number from multichain_lending_report_data where mca_id = %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql, (mca_id, start_number, page_size))
        data_list = cursor.fetchall()
        cursor.execute(sql_count, mca_id)
        total_number_data = cursor.fetchone()
        return data_list, total_number_data["total_number"]
    except Exception as e:
        print("query_multichain_lending_data to db error:", e)
    finally:
        cursor.close()
    return


def query_multichain_lending_data(network_id, batch_id):
    db_conn = get_db_connect(network_id)
    query_sql = "select * from (select * from multichain_lending_requests where `batch_id` = %s " \
                "union all select * from multichain_lending_requests_history where `batch_id` = %s) as all_data "
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql, (batch_id, batch_id))
        data_list = cursor.fetchall()
        return data_list
    except Exception as e:
        print("query_multichain_lending_data to db error:", e)
    finally:
        cursor.close()
    return


def query_multichain_lending_account(network_id, account_address):
    db_conn = get_db_connect(network_id)
    query_sql = "select * from multichain_lending_whitelist where account_address = %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql, (account_address, ))
        data_list = cursor.fetchone()
        return data_list
    except Exception as e:
        print("query multichain_lending_whitelist to db error:", e)
    finally:
        cursor.close()
    return


def query_multichain_lending_zcash_pending(network_id, minutes=10):
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        minutes = 10
    minutes = max(minutes, 1)

    time_threshold = datetime.utcnow() - timedelta(minutes=minutes)
    db_conn = get_db_connect(network_id)
    query_sql = "select * from multichain_lending_zcash_data where `status` = 0 and `created_at` >= %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql, (time_threshold,))
        return cursor.fetchall()
    except Exception as e:
        print("query multichain_lending_zcash_data to db error:", e)
    finally:
        cursor.close()
    return []


def add_multichain_lending_zcash_data(network_id, am_id, deposit_address, request_data, type_data, near_number, deposit_uuid):
    db_conn = get_db_connect(network_id)
    sql = "insert into multichain_lending_zcash_data(`ma_id`, deposit_address, request_data, `type`, near_number, " \
          "deposit_uuid, `created_at`, `updated_at`) values(%s,%s,%s,%s,%s,%s,now(),now())"
    cursor = db_conn.cursor()
    try:
        cursor.execute(sql, (am_id, deposit_address, request_data, type_data, near_number, deposit_uuid))
        db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        print("insert multichain_lending_zcash_data to db error:", e)
        raise e
    finally:
        cursor.close()


def update_multichain_lending_zcash_data(network_id, hex_data, pre_info, data_id, t_address, encryption_pubkey, mca_id, tx_hash, error_msg, status=1):
    sql = "UPDATE multichain_lending_zcash_data SET `status` = %s, `hex` = %s, pre_info = %s, t_address = %s, " \
          "public_key = %s, mca_id = %s, tx_hash = %s, error_msg = %s WHERE id = %s"
    db_conn = get_db_connect(network_id)
    cursor = db_conn.cursor()
    try:
        cursor.execute(sql, (status, hex_data, pre_info, t_address, encryption_pubkey, mca_id, tx_hash, error_msg, data_id))
        db_conn.commit()
    except Exception as e:
        print("update_multichain_lending_zcash_data to db error:", e)
    finally:
        cursor.close()


def query_multichain_lending_zcash_data(network_id, mca_id):
    db_conn = get_db_connect(network_id)
    query_sql = "select * from multichain_lending_zcash_data where deposit_address = %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql, (mca_id, ))
        ret_data = cursor.fetchone()
        return ret_data
    except Exception as e:
        print("query multichain_lending_zcash_data to db error:", e)
    finally:
        cursor.close()
    return


def update_multichain_lending_zcash_public_key(network_id, public_key, data_id):
    sql = "UPDATE multichain_lending_zcash_data SET `public_key` = %s WHERE id = %s"
    db_conn = get_db_connect(network_id)
    cursor = db_conn.cursor()
    try:
        cursor.execute(sql, (public_key, data_id))
        db_conn.commit()
    except Exception as e:
        print("update_multichain_lending_zcash_public_key to db error:", e)
    finally:
        cursor.close()


def query_multichain_lending_zcash_data_by_tx(network_id, tx_hash):
    db_conn = get_db_connect(network_id)
    query_sql = "select * from multichain_lending_zcash_data where tx_hash = %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql, (tx_hash, ))
        ret_data = cursor.fetchone()
        return ret_data
    except Exception as e:
        print("query query_multichain_lending_zcash_data_by_tx to db error:", e)
    finally:
        cursor.close()
    return


def add_multichain_lending_whitelist(network_id, account_address):
    db_conn = get_db_connect(network_id)
    query_sql = "select * from multichain_lending_whitelist where account_address = %s"
    sql = "insert into multichain_lending_whitelist(`account_address`, `created_at`, `updated_at`) values(%s, now(), now())"
    cursor = db_conn.cursor()
    try:
        cursor.execute(query_sql, (account_address,))
        account_data = cursor.fetchone()
        if account_data is None:
            cursor.execute(sql, (account_address, ))
            db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        print("insert multichain_lending_report_data to db error:", e)
        raise e
    finally:
        cursor.close()
    return account_address


def zcash_get_public_key(network_id, t_address):
    public_key = ""
    db_conn = get_db_connect(network_id)
    query_sql = "select public_key from multichain_lending_zcash_data where t_address = %s order by id desc limit 1"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql, (t_address,))
        ret_data = cursor.fetchone()
        if ret_data is not None:
            public_key = ret_data["public_key"]
    except Exception as e:
        db_conn.rollback()
        print("insert zcash_get_public_key to db error:", e)
        raise e
    finally:
        cursor.close()
    return public_key


def query_evm_mpc_call_cache(network_id, wallet, payload, proof):
    db_conn = get_db_connect(network_id)
    query_sql = "select result from evm_mpc_call_cache where wallet = %s and payload = %s and proof = %s limit 1"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql, (wallet, payload, proof))
        ret_data = cursor.fetchone()
        if ret_data is not None:
            return ret_data["result"]
        return None
    except Exception as e:
        print("query evm_mpc_call_cache to db error:", e)
        return None
    finally:
        cursor.close()
        db_conn.close()


def query_supported_chains(network_id):
    db_conn = get_db_connect(network_id)
    query_sql = "select platform, chain_index, chain_id, chain_name, dex_token_approve_address from supported_chains order by platform, id"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql)
        rows = cursor.fetchall()
        result = {}
        for row in rows:
            platform = row["platform"]
            if platform not in result:
                result[platform] = []
            result[platform].append({
                "chainIndex": row["chain_index"],
                "chainId": row["chain_id"],
                "chainName": row["chain_name"],
                "dexTokenApproveAddress": row["dex_token_approve_address"]
            })
        return result
    except Exception as e:
        print("query supported_chains to db error:", e)
        return {}
    finally:
        cursor.close()
        db_conn.close()


def check_supported_chains_expired(network_id, platform, max_age_seconds=3600):
    db_conn = get_db_connect(network_id)
    query_sql = "select created_at from supported_chains where platform = %s order by created_at desc limit 1"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(query_sql, (platform,))
        row = cursor.fetchone()
        if row is None:
            return True
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        now = datetime.utcnow()
        diff_seconds = (now - created_at).total_seconds()
        return diff_seconds > max_age_seconds
    except Exception as e:
        print("check_supported_chains_expired error:", e)
        return True
    finally:
        cursor.close()
        db_conn.close()


def refresh_supported_chains(network_id, platform, chains_list):
    db_conn = get_db_connect(network_id)
    delete_sql = "delete from supported_chains where platform = %s"
    insert_sql = "insert into supported_chains(platform, chain_index, chain_id, chain_name, " \
                 "dex_token_approve_address, created_at, updated_at) values(%s, %s, %s, %s, %s, now(), now())"
    cursor = db_conn.cursor()
    try:
        cursor.execute(delete_sql, (platform,))
        insert_data = []
        for chain in chains_list:
            insert_data.append((
                platform,
                chain.get("chainIndex", ""),
                chain.get("chainId", ""),
                chain.get("chainName", ""),
                chain.get("dexTokenApproveAddress", "")
            ))
        if insert_data:
            cursor.executemany(insert_sql, insert_data)
        db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        print("refresh_supported_chains to db error:", e)
        raise e
    finally:
        cursor.close()
        db_conn.close()


def add_evm_mpc_call_cache(network_id, wallet, payload, proof, result):
    db_conn = get_db_connect(network_id)
    sql = "insert into evm_mpc_call_cache(wallet, payload, proof, result, created_at, updated_at) " \
          "values(%s, %s, %s, %s, now(), now())"
    cursor = db_conn.cursor()
    try:
        cursor.execute(sql, (wallet, payload, proof, result))
        db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        print("insert evm_mpc_call_cache to db error:", e)
        raise e
    finally:
        cursor.close()
        db_conn.close()


if __name__ == '__main__':
    print("#########MAINNET###########")
    # clear_token_price()
    # add_history_token_price("ref.fakes.testnet", "ref2", 1.003, 18, "MAINNET")
    # handle_account_pool_assets_data("MAINNET")
    # now_time = int(time.time())
    # row = {
    #     "account_id": "juaner.near",
    #     "amount": 10
    # }
    # handle_account_pool_assets_m_data("MAINNET", now_time, row)

    # ret_data = query_dcl_pool_log("MAINNET", "82253864", "82253911")
    # print(ret_data)

    # hour_stamp = int(datetime.now().replace(minute=0, second=0, microsecond=0).timestamp())
    # timestamp = hour_stamp - (1 * 24 * 60 * 60)
    # print(timestamp)

    add_redis_data("MAINNET", "test", "test6", "6")
