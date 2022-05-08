import decimal
import pymysql
import json
from datetime import datetime
from config import Cfg


class Encoder(json.JSONEncoder):
    """
    处理特殊数据类型，例如小数和时间类型
    """

    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)

        if isinstance(o, datetime):
            return o.strftime("%Y-%m-%d %H:%M:%S")

        super(Encoder, self).default(o)


def get_db_connect():
    conn = pymysql.connect(host='47.242.213.140', port=3306, user='ref', passwd='Hd2n7TKFej@C', db='mysql')
    return conn


def get_history_token_price(id_list: list) -> list:
    """
    查询历史价格
    """
    print(id_list)
    conn = get_db_connect()
    # 光标对象,设置返回结果带上字段名称
    cur = conn.cursor(cursor=pymysql.cursors.DictCursor)

    # 执行的sql语句
    # 根据token查询出当前最新的一条价格记录
    sql = "select * from(select DISTINCT(a.contract_address) ,a.symbol,a.price,a.decimal,a.create_time, " \
          "1 as float_ratio from mk_history_token_price a where a.contract_address in %s order by a.create_time desc) t " \
          "GROUP BY t.contract_address "
    # 根据token查询出24小时之前的价格记录
    sql2 = "select * from(select DISTINCT(a.contract_address) ,a.symbol,a.price,a.decimal,a.create_time, " \
           "1 as float_ratio from mk_history_token_price a where a.contract_address in %s AND a.create_time BETWEEN (" \
           "CURRENT_TIMESTAMP-interval 1445 minute) and (CURRENT_TIMESTAMP-interval 1440 minute) order by " \
           "a.create_time desc) t GROUP BY t.contract_address "
    # 进行数据查询
    cur.execute(sql, (id_list,))
    # 取出所有结果集（当前最新的价格）
    new_rows = cur.fetchall()
    cur.execute(sql2, (id_list,))
    # 取出所有结果集（24小时之前的价格记录）
    old_rows = cur.fetchall()
    # 关闭数据库链接
    conn.close()
    for new in new_rows:
        for old in old_rows:
            if new['contract_address'] in old['contract_address']:
                new_price = new['price']
                old_price = old['price']
                float_ratio = format_percentage(new_price, old_price)
                new['float_ratio'] = float_ratio

    # 转为json格式
    json_ret = json.dumps(new_rows, cls=Encoder)
    return json_ret


def add_token_price_to_db(contract_address, symbol, price, decimals):
    """
    将token价格写入mysql数据库
    """
    for token in Cfg.TOKENS[Cfg.NETWORK_ID]:
        if token["NEAR_ID"] in contract_address:
            symbol = token["SYMBOL"]


    conn = get_db_connect()
    sql = "insert into mk_history_token_price(contract_address, symbol, price, `decimal`, create_time, update_time, " \
          "`status`) values(%s,%s,%s,%s, now(), now(), 1) "
    par = (contract_address, symbol, price, decimals)
    cursor = conn.cursor()
    try:
        cursor.execute(sql, par)
        # 提交到数据库执行
        conn.commit()
    except Exception as e:
        # 发生错误时回滚
        conn.rollback()
        print(e)
    finally:
        cursor.close()


def format_percentage(new, old):
    p = 100 * (new - old) / old
    return '%.2f' % p


if __name__ == '__main__':
    print("#########MAINNET###########")
