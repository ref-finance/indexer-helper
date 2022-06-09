import decimal
import pymysql
import json
from datetime import datetime
from config import Cfg
import time


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

    id_list = ['dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near' if i == 'usn' else i for i in id_list]
    conn = get_db_connect(Cfg.NETWORK_ID)
    # Cursor object, set the return result with field name
    cur = conn.cursor(cursor=pymysql.cursors.DictCursor)

    # Executed SQL statement
    # Query the latest price record according to the token
    sql = "select * from(select DISTINCT(a.contract_address) ,a.symbol,a.price,a.`decimal`,a.`timestamp` as datetime," \
          "1 as float_ratio from mk_history_token_price a where a.contract_address in %s " \
          "order by a.`timestamp` desc) t GROUP BY t.contract_address"
    # Query the price records 24 hours ago according to the token
    sql2 = "select * from(select DISTINCT(a.contract_address) ,a.symbol,a.price,a.decimal," \
           "from_unixtime( a.`timestamp`, '%%Y-%%m-%%d %%H:%%i:%%s' ) AS datetime, 1 as float_ratio " \
           "from mk_history_token_price a where a.contract_address in %s " \
           "AND from_unixtime( a.`timestamp`, '%%Y-%%m-%%d %%H:%%i:%%s') BETWEEN (CURRENT_TIMESTAMP-interval 1500 minute) " \
           "and (CURRENT_TIMESTAMP-interval 1440 minute) " \
           "order by from_unixtime(a.`timestamp`, '%%Y-%%m-%%d %%H:%%i:%%s') desc) t GROUP BY t.contract_address"
    # Data query
    cur.execute(sql, (id_list,))
    # Take out all result sets (current latest prices)
    new_rows = cur.fetchall()
    cur.execute(sql2, (id_list,))
    # Take out all result sets (price records 24 hours ago)
    old_rows = cur.fetchall()
    # Close database link
    conn.close()
    for new in new_rows:
        for old in old_rows:
            if new['contract_address'] in old['contract_address']:
                new_price = new['price']
                old_price = old['price']
                float_ratio = format_percentage(new_price, old_price)
                new['float_ratio'] = float_ratio
        if "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near" in new['contract_address']:
            if 2 == usn_flag:
                new_usn = {
                    "price": new['price'],
                    "decimal": 18,
                    "symbol": "USN",
                    "float_ratio": new['float_ratio'],
                    "timestamp": new['datetime'],
                    "contract_address": "usn"
                }
                new_rows.append(new_usn)
            elif 3 == usn_flag:
                new['contract_address'] = "usn"
                new['symbol'] = "USN"
                new['decimal'] = 18

    # Convert to JSON format
    json_ret = json.dumps(new_rows, cls=Encoder)
    return json_ret


def add_token_price_to_db(contract_address, symbol, price, decimals):
    """
    Write the token price to the MySQL database
    """
    for token in Cfg.TOKENS[Cfg.NETWORK_ID]:
        if token["NEAR_ID"] in contract_address:
            symbol = token["SYMBOL"]

    # Get current timestamp
    now = int(time.time())
    conn = get_db_connect(Cfg.NETWORK_ID)
    sql = "insert into mk_history_token_price(contract_address, symbol, price, `decimal`, create_time, update_time, " \
          "`status`, `timestamp`) values(%s,%s,%s,%s, now(), now(), 1, %s) "
    par = (contract_address, symbol, price, decimals, now)
    cursor = conn.cursor()
    try:
        cursor.execute(sql, par)
        # Submit to database for execution
        conn.commit()
    except Exception as e:
        # Rollback on error
        conn.rollback()
        print(e)
    finally:
        cursor.close()


def format_percentage(new, old):
    p = 100 * (new - old) / old
    return '%.2f' % p


def clear_token_price():
    now = int(time.time())
    before = now - (7*24*60*60)
    print("seven days ago time:", before)
    conn = get_db_connect(Cfg.NETWORK_ID)
    # sql = "delete from mk_history_token_price where `timestamp` < %s"
    sql = "select count(*) from mk_history_token_price where `timestamp` < %s"
    cursor = conn.cursor()
    try:
        cursor.execute(sql, before)
        # Submit to database for execution
        conn.commit()
    except Exception as e:
        # Rollback on error
        conn.rollback()
        print(e)
    finally:
        cursor.close()


if __name__ == '__main__':
    print("#########MAINNET###########")
    clear_token_price()

