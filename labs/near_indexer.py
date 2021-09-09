#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Marco'
import json
import psycopg2
import decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return "%s" % o
        super(DecimalEncoder, self).default(o)


class Cfg:
    NETWORK_ID = "MAINNET"
    NETWORK = {
        "TESTNET": {
            "INDEXER_DSN": "testnet_explorer",
            "INDEXER_UID": "public_readonly",
            "INDEXER_PWD": "nearprotocol",
            "INDEXER_HOST": "35.184.214.98",
            "INDEXER_PORT": "5432",
        },
        "MAINNET": {
            "INDEXER_DSN": "mainnet_explorer",
            "INDEXER_UID": "public_readonly",
            "INDEXER_PWD": "nearprotocol",
            "INDEXER_HOST": "104.199.89.51",
            "INDEXER_PORT": "5432",
        }
    }
        


def get_liquidity_pools(network_id: str) ->list:
    conn = psycopg2.connect(
        database=Cfg.NETWORK[network_id]["INDEXER_DSN"],
        user=Cfg.NETWORK[network_id]["INDEXER_UID"],
        password=Cfg.NETWORK[network_id]["INDEXER_PWD"],
        host=Cfg.NETWORK[network_id]["INDEXER_HOST"],
        port=Cfg.NETWORK[network_id]["INDEXER_PORT"])
    cur=conn.cursor() 

    # sql1 = (
    #     "select distinct pool_id from ( " 
    #     "select included_in_block_timestamp as timestamp, " 
    #     "convert_from(decode(args->>'args_base64', 'base64'), 'UTF8')::json->>'pool_id' as pool_id " 
    #     "from action_receipt_actions join receipts using(receipt_id) " 
    #     "where (action_kind = 'FUNCTION_CALL' and args->>'method_name' = 'add_liquidity'" 
    # )
    # sql2 = "and receiver_account_id = '%s' " % Cfg.NETWORK[network_id]["REF_CONTRACT"]
    # sql3 = "and predecessor_account_id = '%s') order by timestamp desc " % account_id 
    # sql4 = ") as report limit 100"
    # sql = "%s %s %s %s" % (sql1, sql2, sql3, sql4)

    sql = (
        "select included_in_block_timestamp as timestamp, "
        "args->>'method_name' as method_name, "
        "convert_from(decode(args->>'args_base64', 'base64'), 'UTF8')::json as params, "
        "status "
        "from action_receipt_actions join receipts using(receipt_id) join execution_outcomes using(receipt_id) "
        "where (action_kind = 'FUNCTION_CALL' and receiver_account_id = 'ref-farming.near' and args->>'method_name' = 'mft_on_transfer' and status = 'SUCCESS_VALUE') "
        "order by timestamp desc"
    )


    cur.execute(sql)
    rows = cur.fetchall()
    conn.close()

    # json_ret = json.dumps(rows, cls=DecimalEncoder)
    return rows


def get_remove(network_id: str, user: str) ->list:
    conn = psycopg2.connect(
        database=Cfg.NETWORK[network_id]["INDEXER_DSN"],
        user=Cfg.NETWORK[network_id]["INDEXER_UID"],
        password=Cfg.NETWORK[network_id]["INDEXER_PWD"],
        host=Cfg.NETWORK[network_id]["INDEXER_HOST"],
        port=Cfg.NETWORK[network_id]["INDEXER_PORT"])
    cur=conn.cursor() 

    # sql1 = (
    #     "select distinct pool_id from ( " 
    #     "select included_in_block_timestamp as timestamp, " 
    #     "convert_from(decode(args->>'args_base64', 'base64'), 'UTF8')::json->>'pool_id' as pool_id " 
    #     "from action_receipt_actions join receipts using(receipt_id) " 
    #     "where (action_kind = 'FUNCTION_CALL' and args->>'method_name' = 'add_liquidity'" 
    # )
    # sql2 = "and receiver_account_id = '%s' " % Cfg.NETWORK[network_id]["REF_CONTRACT"]
    # sql3 = "and predecessor_account_id = '%s') order by timestamp desc " % account_id 
    # sql4 = ") as report limit 100"
    # sql = "%s %s %s %s" % (sql1, sql2, sql3, sql4)

    sql = """
    select 
    originated_from_transaction_hash,
    included_in_block_timestamp as timestamp,
    args->>'method_name' as method_name,
    convert_from(decode(args->>'args_base64', 'base64'), 'UTF8')::json as params,
    status
from action_receipt_actions join receipts using(receipt_id) join execution_outcomes using(receipt_id) 
where 
    action_kind = 'FUNCTION_CALL' and 
    receiver_account_id = 'ref-finance.near' and 
    included_in_block_timestamp >= 1628939340182442322 and
    args->>'method_name' = 'remove_liquidity' and
    predecessor_account_id = 'xxxxxx' and
    status = 'SUCCESS_VALUE'
    """

    cur.execute(sql.replace('xxxxxx', user))
    rows = cur.fetchall()
    conn.close()

    # json_ret = json.dumps(rows, cls=DecimalEncoder)
    with open("%s.json" % user, "w", encoding='utf-8') as f:
        json.dump(rows, f, indent=2, ensure_ascii=False, cls=DecimalEncoder)  # 写为多行
    return rows

  

if __name__ == '__main__':
    print("#########MAINNET###########")
    records = get_remove("MAINNET", 'simeon4real.near')
    users = set()
    for record in records:
        print(record)
    print(len(records))
    print("#########End###########")

