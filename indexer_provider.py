#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Marco'
import json
from config import Cfg
import psycopg2
import decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return "%s" % o
        super(DecimalEncoder, self).default(o)

def get_liquidity_pools(network_id: str, account_id: str) ->list:
    conn = psycopg2.connect(
        database=Cfg.NETWORK[network_id]["INDEXER_DSN"],
        user=Cfg.NETWORK[network_id]["INDEXER_UID"],
        password=Cfg.NETWORK[network_id]["INDEXER_PWD"],
        host=Cfg.NETWORK[network_id]["INDEXER_HOST"],
        port=Cfg.NETWORK[network_id]["INDEXER_PORT"])
    cur=conn.cursor() 

    sql1 = (
        "select distinct pool_id from ( " 
        "select included_in_block_timestamp as timestamp, " 
        "convert_from(decode(args->>'args_base64', 'base64'), 'UTF8')::json->>'pool_id' as pool_id " 
        "from action_receipt_actions join receipts using(receipt_id) " 
        "where (action_kind = 'FUNCTION_CALL' and args->>'method_name' = 'add_liquidity'" 
    )
    sql2 = "and receiver_account_id = '%s' " % Cfg.NETWORK[network_id]["REF_CONTRACT"]
    sql3 = """and predecessor_account_id = %s) order by timestamp desc """
    sql4 = ") as report limit 100"
    sql = "%s %s %s %s" % (sql1, sql2, sql3, sql4)

    cur.execute(sql, (account_id, ))
    rows = cur.fetchall()
    conn.close()

    return [row[0] for row in rows if row[0] ]


def get_actions(network_id, account_id):
    """
    get data from indexer
    """
    conn = psycopg2.connect(
        database=Cfg.NETWORK[network_id]["INDEXER_DSN"],
        user=Cfg.NETWORK[network_id]["INDEXER_UID"],
        password=Cfg.NETWORK[network_id]["INDEXER_PWD"],
        host=Cfg.NETWORK[network_id]["INDEXER_HOST"],
        port=Cfg.NETWORK[network_id]["INDEXER_PORT"])
    cur=conn.cursor() 

    sql1 = (
        "select " 
        "included_in_block_timestamp as timestamp, " 
        "originated_from_transaction_hash, "
        "receiver_account_id, "
        "args->>'method_name' as method_name, " 
        "args->>'args_json' as args, " 
        "args->>'deposit' as deposit, " 
        "status "
        "from action_receipt_actions join receipts using(receipt_id) "
        "join execution_outcomes using(receipt_id) " 
        "where action_kind = 'FUNCTION_CALL' and ( "
    )

    sql2 = """(predecessor_account_id = %s and """ 
    sql3 = "(receiver_account_id in ('%s', '%s', '%s', 'wrap.near') " % (Cfg.NETWORK[network_id]["REF_CONTRACT"], Cfg.NETWORK[network_id]["FARMING_CONTRACT"], Cfg.NETWORK[network_id]["XREF_CONTRACT"])
    sql4 = "or (args->'args_json'->>'receiver_id' = 'aurora' and args->>'method_name' = 'ft_transfer_call') "
    sql5 = "or (receiver_account_id = 'aurora' and args->>'method_name' = 'call') "
    sql6 = "or args->'args_json'->>'receiver_id' in ('%s', '%s'))) " % (Cfg.NETWORK[network_id]["REF_CONTRACT"], Cfg.NETWORK[network_id]["XREF_CONTRACT"])
    sql7 = "or (predecessor_account_id = 'usn' and receiver_account_id = 'usn' and  args->>'method_name' in ('buy_with_price_callback', 'sell_with_price_callback') "
    sql8 = """ and args->'args_json'->>'account' = %s )) """
    sql9 = "order by timestamp desc limit 10"
    sql = "%s %s %s %s %s %s %s %s %s" % (sql1, sql2, sql3, sql4, sql5, sql6, sql7, sql8, sql9)

    cur.execute(sql, (account_id, account_id))
    rows = cur.fetchall()
    conn.close()

    json_ret = json.dumps(rows, cls=DecimalEncoder)
    return json_ret
    

if __name__ == '__main__':
    print("#########MAINNET###########")
    # print(get_liquidity_pools("MAINNET", "reffer.near"))
    # print(get_actions("MAINNET", "reffer.near'); select version() -- "))
    # print("#########TESTNET###########")
    # print(get_liquidity_pools("TESTNET", "pika8.testnet"))
    print(get_actions("MAINNET", "sunhao.near"))
