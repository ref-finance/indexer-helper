#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Marco'
import json
from config import Cfg
import psycopg2
import decimal
import time
import requests
from redis_provider import RedisProvider
from config import Cfg
from psycopg2.extras import RealDictCursor

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
        "where (action_kind = 'FUNCTION_CALL' and args->>'method_name' in ('add_liquidity', 'add_stable_liquidity')"
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

    now_time = int(time.time())
    old_time = (now_time - (30 * 24 * 60 * 60)) * 1000000000

    sql1 = (
            "SELECT "
            "included_in_block_timestamp as timestamp, "
            "originated_from_transaction_hash, "
            "receiver_account_id, "
            "args->>'method_name' AS method_name, "
            "args->>'args_json' AS args, "
            "args->>'deposit' AS deposit, "
            "status FROM (SELECT * FROM action_receipt_actions WHERE action_kind = 'FUNCTION_CALL' "
            "AND receipt_included_in_block_timestamp > %s "
            "AND receipt_predecessor_account_id = '%s' ) AS ara "
            "JOIN receipts USING ( receipt_id ) "
            "JOIN execution_outcomes USING ( receipt_id ) " % (old_time, account_id)
    )

    sql2 = """WHERE predecessor_account_id = %s """
    sql3 = "AND (receiver_account_id IN ('%s', '%s', '%s', 'wrap.near', '%s', '%s', '%s') " % (Cfg.NETWORK[network_id]["REF_CONTRACT"], Cfg.NETWORK[network_id]["FARMING_CONTRACT"], Cfg.NETWORK[network_id]["XREF_CONTRACT"], Cfg.NETWORK[network_id]["BOOSTFARM_CONTRACT"], Cfg.NETWORK[network_id]["USN_CONTRACT"], Cfg.NETWORK[network_id]["DCL_CONTRACT"])
    sql4 = "OR (args->'args_json'->>'receiver_id' IN ('aurora', '%s') AND args->>'method_name' = 'ft_transfer_call') " % Cfg.NETWORK[network_id]["USN_CONTRACT"]
    sql5 = "OR (receiver_account_id = 'aurora' AND args->>'method_name' = 'call') "
    sql6 = "OR args->'args_json'->>'receiver_id' IN ('%s', '%s', '%s')) " % (Cfg.NETWORK[network_id]["REF_CONTRACT"], Cfg.NETWORK[network_id]["XREF_CONTRACT"], Cfg.NETWORK[network_id]["DCL_CONTRACT"])
    sql7 = "order by timestamp desc limit 10"
    sql = "%s %s %s %s %s %s %s" % (sql1, sql2, sql3, sql4, sql5, sql6, sql7)

    print("get_actions sql:", sql)
    cur.execute(sql, (account_id, ))
    rows = cur.fetchall()
    conn.close()

    json_ret = json.dumps(rows, cls=DecimalEncoder)
    return json_ret


def get_proposal_id_hash(network_id, id_list):
    proposal_res_data = []
    url = Cfg.REFSUBGRAPH_URL
    id_list = str(id_list).replace("'", """\"""")
    query = """query {
                proposalCreates(where: {proposal_id_in: """ + id_list + """}) {
                proposal_id
                receipt_id
                }
            }"""
    ret = requests.post(url, json={'query': query}).content
    ret_json = json.loads(ret)
    proposal_data = ret_json["data"]["proposalCreates"]
    receipt_id_str = ""
    if len(proposal_data) > 0:
        for proposal in proposal_data:
            receipt_id_str += "'" + (proposal["receipt_id"]) + "',"
            proposal_res = {
                                "proposal_id": proposal["proposal_id"],
                                "receipt_id": proposal["receipt_id"],
                                "transaction_hash": ""
                            }
            proposal_res_data.append(proposal_res)
        conn = psycopg2.connect(
            database=Cfg.NETWORK[network_id]["INDEXER_DSN"],
            user=Cfg.NETWORK[network_id]["INDEXER_UID"],
            password=Cfg.NETWORK[network_id]["INDEXER_PWD"],
            host=Cfg.NETWORK[network_id]["INDEXER_HOST"],
            port=Cfg.NETWORK[network_id]["INDEXER_PORT"])
        cur = conn.cursor(cursor_factory=RealDictCursor)
        sql = "select receipt_id, originated_from_transaction_hash from receipts where receipt_id in (%s)" % receipt_id_str[:-1]
        cur.execute(sql)
        rows = cur.fetchall()
        conn.close()
        for proposal_pg in rows:
            for proposal_ret in proposal_res_data:
                if proposal_pg["receipt_id"] in proposal_ret["receipt_id"]:
                    proposal_ret["transaction_hash"] = proposal_pg["originated_from_transaction_hash"]

        redis_conn = RedisProvider()
        redis_conn.begin_pipe()
        for pps in proposal_res_data:
            if not pps["transaction_hash"] is "":
                redis_conn.add_proposal_id_hash(network_id, pps["proposal_id"], json.dumps(pps))
        redis_conn.end_pipe()
        redis_conn.close()
    return proposal_res_data


if __name__ == '__main__':
    print("#########MAINNET###########")
    # print(get_liquidity_pools("MAINNET", "reffer.near"))
    print(get_actions("MAINNET", "juaner.near"))
    # print("#########TESTNET###########")
    # print(get_liquidity_pools("TESTNET", "pika8.testnet"))
    print(get_proposal_id_hash("TESTNET"))
