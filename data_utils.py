import time
from config import Cfg
import pymysql


def get_db_connect(network_id: str):
    conn = pymysql.connect(
        host=Cfg.NETWORK[network_id]["DB_HOST"],
        port=int(Cfg.NETWORK[network_id]["DB_PORT"]),
        user=Cfg.NETWORK[network_id]["DB_UID"],
        passwd=Cfg.NETWORK[network_id]["DB_PWD"],
        db=Cfg.NETWORK[network_id]["DB_DSN"])
    return conn


def add_redis_data(network_id, key, redis_key, values):
    now_time = int(time.time())
    db_conn = get_db_connect(network_id)

    sql = "INSERT INTO t_indexer_redis_data (`key`, redis_key, redis_values, `timestamp`, created_time, updated_time) " \
          "VALUES ('%s', '%s', '%s', %s, now(), now()) ON DUPLICATE KEY UPDATE redis_values = VALUES(redis_values), " \
          "`timestamp` = VALUES(`timestamp`), created_time = VALUES(created_time), " \
          "updated_time = VALUES(updated_time)" % (key, redis_key, values, now_time)

    cursor = db_conn.cursor()
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


def get_redis_data(network_id, key, redis_key):
    db_conn = get_db_connect(network_id)
    sql = "select `redis_values` from t_indexer_redis_data where `key` = %s and redis_key = %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, (key, redis_key))
        row = cursor.fetchone()
        return row["redis_values"]
    except Exception as e:
        db_conn.rollback()
        print("query liquidation_result_info to db error:", e)
    finally:
        cursor.close()


def batch_get_redis_data(network_id, key):
    db_conn = get_db_connect(network_id)
    sql = "select redis_key, redis_values from t_indexer_redis_data where `key` = %s"
    cursor = db_conn.cursor(cursor=pymysql.cursors.DictCursor)
    try:
        cursor.execute(sql, key)
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        db_conn.rollback()
        print("query liquidation_result_info to db error:", e)
    finally:
        cursor.close()