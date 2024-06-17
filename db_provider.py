import decimal
import pymysql
import json
from datetime import datetime
from config import Cfg
import time
from redis_provider import RedisProvider, list_history_token_price, list_token_price, get_account_pool_assets, get_pool_point_24h_by_pool_id


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
    sql = "select DISTINCT(pool_id) as pool_id from near_lake_liquidity_pools where account_id = '%s'" % account_id
    cursor = db_conn.cursor()
    try:
        cursor.execute(sql)
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
          "from near_lake_latest_actions where predecessor_account_id = '%s' order by `timestamp` desc limit 10" % account_id
    cursor = db_conn.cursor()
    try:
        cursor.execute(sql)
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
    sql = "SELECT tx_id FROM t_tx_receipt WHERE receipt_id = '%s'" % receipt_id
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
    sql2 = "SELECT contract_address, price FROM mk_history_token_price where contract_address in (%s) " \
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
    sql = "select order_id, tx_id, receipt_id from near_lake_limit_order where type = 'order_added' and owner_id = '%s'" % owner_id
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
          "near_lake_limit_order where type = 'swap' and owner_id = '%s'" % owner_id
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
          "where account_id = '%s' and `event` in ('borrow','decrease_collateral','deposit'," \
          "'increase_collateral','repay','withdraw_succeeded')  order by `timestamp` desc " \
          "limit %s, %s" % (account_id, start_number, page_size)
    sql_count = "select count(*) as total_number from burrow_event_log where account_id = '%s' and `event` in " \
                "('borrow','decrease_collateral','deposit','increase_collateral','repay','withdraw_succeeded')" % account_id
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
        burrow_log = cursor.fetchall()
        cursor.execute(sql_count)
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
                  "contract_address = '%s' and `timestamp` >= '%s' limit 1" % (token_id, data_time)
            cursor.execute(sql)
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
    db_conn = get_near_lake_dcl_connect(network_id)
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
          "all_data where block_id >= '%s' and block_id <= '%s' order by `timestamp`" % (start_block_id, end_block_id)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
                      "sum(tvl_y_l) as tvl_y_l from dcl_pool_analysis where pool_id = '%s' " \
                      "and `timestamp` >= %s GROUP BY point order by point" % (pool_id, timestamp)
            cursor.execute(sql_24h)
            point_data_24h = cursor.fetchall()
            redis_conn.add_pool_point_24h_assets(network_id, pool_id, json.dumps(point_data_24h))
            redis_conn.add_pool_point_24h_assets(network_id, pool_id + "timestamp", now)
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
          "near_lake_swap_log where pool_id = '%s' order by `timestamp` desc limit 50" % pool_id
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
          "amount_in, amount_out from near_lake_liquidity_log where pool_id = '%s' order by `timestamp` desc limit 50" % pool_id
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
          "tla.tx_id as receipt_id from t_liquidity_added as tla where tla.pool_id = '%s' and " \
          "tla.event_method != 'liquidity_merge' group by tx_id union all select tlr.event_method as method_name, " \
          "sum(cast(tlr.refund_token_x as decimal(64, 0))) as amount_x,sum(cast(tlr.refund_token_y as decimal(64, 0))) " \
          "as amount_y, tlr.`timestamp`, tlr.tx_id as receipt_id from t_liquidity_removed as tlr where " \
          "tlr.pool_id = '%s' and tlr.removed_amount > 0 group by tx_id) as all_data" \
          " order by `timestamp` desc limit 50" % (pool_id, pool_id)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
        recent_transaction_data = cursor.fetchall()
        return recent_transaction_data
    except Exception as e:
        print("query t_liquidity_added to db error:", e)
    finally:
        cursor.close()


def query_recent_transaction_limit_order(network_id, pool_id):
    db_conn = get_db_connect(network_id)
    sql = "select all_data.method_name,all_data.sell_token,all_data.amount,all_data.point,all_data.`timestamp`, " \
          "'' as tx_id,all_data.tx_id as receipt_id from (select 'order_cancelled' as method_name, sell_token,  " \
          "actual_cancel_amount as amount, point,`timestamp`,tx_id from t_order_cancelled where pool_id = '%s' " \
          "and actual_cancel_amount != '0' union all select 'order_added' as method_name, sell_token,  " \
          "original_amount as amount, point,`timestamp`,tx_id from t_order_added where pool_id = '%s' and  " \
          "(args like '%%%%LimitOrderWithSwap%%%%' or args like '%%%%LimitOrder%%%%')) as all_data order by " \
          "all_data.`timestamp`  desc limit 50" % (pool_id, pool_id)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
        recent_transaction_data = cursor.fetchall()
        return recent_transaction_data
    except Exception as e:
        print("query recent_transaction_limit_order to db error:", e)
    finally:
        cursor.close()


def query_dcl_points(network_id, pool_id):
    db_conn = get_db_connect(network_id)
    sql = "select pool_id,point,fee_x,fee_y,l,tvl_x_l,tvl_x_o,tvl_y_l,tvl_y_o,vol_x_in_l,vol_x_in_o,vol_x_out_l," \
          "vol_x_out_o,vol_y_in_l,vol_y_in_o,vol_y_out_l,vol_y_out_o,p_fee_x,p_fee_y,p,cp,`timestamp` " \
          "from dcl_pool_analysis where pool_id = '%s' and `timestamp` >= (select `timestamp` from dcl_pool_analysis " \
          "where pool_id = '%s' order by `timestamp` desc limit 1) order by point" % (pool_id, pool_id)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
    finally:
        cursor.close()


def query_dcl_points_by_account(network_id, pool_id, account_id, start_point, end_point):
    db_conn = get_db_connect(network_id)
    sql = "select pool_id,account_id,point,l,tvl_x_l,tvl_y_l,p,`timestamp`,create_time from dcl_user_liquidity " \
          "where pool_id = '%s' and account_id = '%s' and `timestamp` >= (select max(`timestamp`) " \
          "from dcl_user_liquidity) and point >= %s and point <= %s order by point" % (pool_id, account_id, start_point, end_point)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
        point_data = cursor.fetchall()
        return point_data
    except Exception as e:
        print("query dcl_user_liquidity to db error:", e)
    finally:
        cursor.close()


def query_dcl_user_unclaimed_fee(network_id, pool_id, account_id):
    db_conn = get_db_connect(network_id)
    sql = "select unclaimed_fee_x, unclaimed_fee_y from dcl_user_liquidity_fee where pool_id = '%s' and " \
          "account_id = '%s' and `timestamp` >= (select max(`timestamp`) from dcl_user_liquidity_fee where " \
          "pool_id = '%s' and account_id = '%s')" % (pool_id, account_id, pool_id, account_id)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
    sql = "select * from dcl_user_liquidity_fee where pool_id = '%s' and account_id = '%s' and `timestamp` <= %s " \
          "order by `timestamp` desc limit 1" % (pool_id, account_id, timestamp)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
          "t_liquidity_added where pool_id = '%s' and owner_id = '%s' and event_method in( 'liquidity_append', " \
          "'liquidity_merge') union all select sum(cast(claim_fee_token_x as decimal(64, 0))) as total_fee_x, " \
          "sum(cast(claim_fee_token_y as decimal(64, 0))) as " \
          "total_fee_y from t_liquidity_removed where pool_id = '%s' and owner_id = '%s' and event_method = " \
          "'liquidity_removed') as fee" % (pool_id, account_id, pool_id, account_id)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
          "t_liquidity_added where pool_id = '%s' and owner_id = '%s' and event_method in( 'liquidity_append', " \
          "'liquidity_merge') and `timestamp` <= '%s' union all select sum(cast(claim_fee_token_x as " \
          "decimal(64, 0))) as total_fee_x, sum(cast(claim_fee_token_y as decimal(64, 0))) as total_fee_y from " \
          "t_liquidity_removed where pool_id = '%s' and owner_id = '%s' " \
          "and event_method = 'liquidity_removed' and `timestamp` <= '%s') " \
          "as fee" % (pool_id, account_id, timestamp, pool_id, account_id, timestamp)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
        recent_transaction_data = cursor.fetchall()
        return recent_transaction_data
    except Exception as e:
        print("query t_liquidity_removed to db error:", e)
    finally:
        cursor.close()


def query_dcl_user_tvl(network_id, pool_id, account_id):
    db_conn = get_db_connect(network_id)
    sql = "select sum(tvl_x_l) as tvl_x_l, sum(tvl_y_l) as tvl_y_l,`timestamp` from dcl_user_liquidity where " \
          "pool_id = '%s' and account_id = '%s' and `timestamp` >= (select max(`timestamp`) from " \
          "dcl_user_liquidity where pool_id = '%s' and account_id = '%s')" % (pool_id, account_id, pool_id, account_id)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
        point_data = cursor.fetchall()
        return point_data
    except Exception as e:
        print("query dcl_user_liquidity to db error:", e)
    finally:
        cursor.close()


def query_dcl_user_change_log(network_id, pool_id, account_id, user_token_timestamp):
    timestamp = user_token_timestamp - (1 * 24 * 60 * 60)
    db_conn = get_db_connect(network_id)
    sql = "select event_method,paid_token_x as token_x,paid_token_y as token_y,remove_token_x,remove_token_y," \
          "merge_token_x,merge_token_y,`timestamp` from t_liquidity_added where pool_id = '%s' and owner_id = '%s' " \
          "and event_method in('liquidity_append', 'liquidity_added') and `timestamp` >= '%s' " \
          "union all select event_method,refund_token_x as token_x, refund_token_y as token_y, null as remove_token_x," \
          "null as remove_token_y,null as merge_token_x,null as merge_token_y,`timestamp`  from t_liquidity_removed " \
          "where pool_id = '%s' and owner_id = '%s' and event_method = 'liquidity_removed' and removed_amount > '0' " \
          "and `timestamp` >= '%s' " \
          "order by `timestamp` desc" % (pool_id, account_id, timestamp, pool_id, account_id, timestamp)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
          "values('%s','%s',%s, now(), now())" % (key, values, now_time)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
    sql = "update liquidation_result_info set `values` = '%s' where `key` = '%s'" % (values, key)
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
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
          "where `key` = '%s'" % key
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql)
        row = cursor.fetchone()
        return row
    except Exception as e:
        db_conn.rollback()
        print("query liquidation_result_info to db error:", e)
    finally:
        cursor.close()


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

    ret_data = query_dcl_pool_log("MAINNET", "82253864", "82253911")
    print(ret_data)
    # hour_stamp = int(datetime.now().replace(minute=0, second=0, microsecond=0).timestamp())
    # timestamp = hour_stamp - (1 * 24 * 60 * 60)
    # print(timestamp)
