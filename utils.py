import gzip
from flask import make_response
import json
from flask import request
import requests
from db_provider import add_tx_receipt, query_tx_by_receipt


def get_tx_id(receipt_id, network_id):
    tx_id = query_tx_by_receipt(receipt_id, network_id)
    if tx_id == "":
        try:
            tx_id = near_explorer_tx(receipt_id, network_id)
        except Exception as e:
            print("explorer error:", e)
            tx_id = near_block_tx(receipt_id, network_id)
    return tx_id


def near_explorer_tx(receipt_id, network_id):
    import re
    tx_receipt_data_list = []
    tx_id = ""
    tx_receipt_data = {
        "tx_id": "",
        "receipt_id": receipt_id
    }
    explorer_query_tx_id_url = "https://explorer.near.org/?query=" + receipt_id
    requests.packages.urllib3.disable_warnings()
    explorer_tx_ret = requests.get(url=explorer_query_tx_id_url, verify=False)
    explorer_tx_data = str(explorer_tx_ret.text)
    tx_ret_list = re.findall("<a class=\"(.*?)</a>", explorer_tx_data)
    if len(tx_ret_list) > 0:
        for tx_ret in tx_ret_list:
            tx_list = re.findall("href=\"/transactions/(.*?)#" + receipt_id, tx_ret)
            if len(tx_list) > 0:
                tx_id = str(tx_list[0])
        tx_receipt_data["tx_id"] = tx_id
        if tx_receipt_data["tx_id"] != "":
            tx_receipt_data_list.append(tx_receipt_data)
            add_tx_receipt(tx_receipt_data_list, network_id)
    return tx_id


def near_block_tx(receipt_id, network_id):
    tx_receipt_data_list = []
    tx_id = ""
    tx_receipt_data = {
        "tx_id": "",
        "receipt_id": receipt_id
    }
    blocks_query_tx_id_url = "https://api.nearblocks.io/v1/search/?keyword=" + receipt_id
    requests.packages.urllib3.disable_warnings()
    blocks_tx_ret = requests.get(url=blocks_query_tx_id_url, verify=False)
    blocks_tx_data = json.loads(blocks_tx_ret.text)
    for receipt in blocks_tx_data["receipts"]:
        if receipt["receipt_id"] == receipt_id:
            tx_id = receipt["originated_from_transaction_hash"]
            tx_receipt_data["tx_id"] = tx_id
            if tx_receipt_data["tx_id"] != "":
                tx_receipt_data_list.append(tx_receipt_data)
                add_tx_receipt(tx_receipt_data_list, network_id)
            else:
                print("blocks_tx_data:", blocks_tx_data)
    return tx_id


def combine_pools_info(pools, prices, metadata):
    ret_pools = []
    for pool in pools:
        tokens = pool['token_account_ids']
        token_balances = []
        token_prices = []
        token_tvls = []
        valid_token_tvl = 0
        valid_token_price = 0
        token_metadata_flag = True
        for i in range(len(tokens)):
            if metadata[tokens[i]] != "":
                token_decimals = metadata[tokens[i]]["decimals"]
                token_symbol = metadata[tokens[i]]["symbol"]
                if token_decimals is None or token_symbol is None or token_decimals == "" or token_symbol == "":
                    token_metadata_flag = False
                balance = float(pool['amounts'][i]) / (10 ** token_decimals)
            else:
                token_metadata_flag = False
                balance = 0
            # balance = float(pool['amounts'][i]) / (10 ** metadata[tokens[i]]["decimals"])
            token_balances.append(balance)
            if tokens[i] in prices:
                # record latest valid token_price
                valid_token_price = prices[tokens[i]]
                token_prices.append(valid_token_price)
                token_tvl = float(valid_token_price) * balance
                token_tvls.append(token_tvl)
                if token_tvl > 0:
                    # record latest valid token_tvl
                    valid_token_tvl = token_tvl
            else:
                token_prices.append(0)
                token_tvls.append(0)
        # sum to TVL
        tvl = 0
        for i in range(len(token_tvls)):
            token_tvl = token_tvls[i]
            if token_tvl > 0:
                tvl += token_tvl
            else:
                if pool["pool_kind"] == "SIMPLE_POOL":
                    tvl += valid_token_tvl
                elif pool["pool_kind"] == "STABLE_SWAP":
                    tvl += float(valid_token_price) * token_balances[i]
                else:
                    pass
        pool["tvl"] = str(tvl)

        if pool["pool_kind"] == "SIMPLE_POOL":
            # add token0_ref_price = token1_price * token1_balance / token0_balance 
            if token_balances[0] > 0 and token_balances[1] > 0 and tokens[1] in prices:
                pool["token0_ref_price"] = str(float(token_prices[1]) * token_balances[1] / token_balances[0])
            else:
                pool["token0_ref_price"] = "N/A"
        if token_metadata_flag:
            ret_pools.append(pool)
    pools.clear()
    for ret_pool in ret_pools:
        pools.append(ret_pool)
    pass


def compress_response_content(ret):
    content = gzip.compress(json.dumps(ret).encode('utf8'), 5)
    response = make_response(content)
    response.headers['Content-length'] = len(content)
    response.headers['Content-Encoding'] = 'gzip'
    return response


def get_ip_address():
    if request.headers.getlist("X-Forwarded-For"):
        ip_address = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip_address = request.remote_addr
    ip_address = ip_address.split(", ")
    return ip_address[0]


def pools_filter(pools, tvl, amounts):
    ret_pools = []
    for pool in pools:
        try:
            if not tvl is None and "" != tvl:
                if float(pool["tvl"]) <= float(tvl):
                    continue
            if not amounts is None and "" != amounts:
                amount_count = float(0)
                for amount in pool["amounts"]:
                    amount_count = amount_count + float(amount)
                if float(amount_count) <= float(amounts):
                    continue
            ret_pools.append(pool)
        except Exception as e:
            print("pools filter error:", e)
            print("error content:", pool)
            ret_pools.append(pool)
            continue

    return ret_pools


def combine_dcl_pool_log(ret):
    ret_data_list = []
    for data in ret:
        args_data = json.loads(data["args"])
        args = args_data[0]
        flag = False
        if "msg" in data["args"]:
            amount = args["amount"]
            msg = args["msg"]
            ret_msg_data = {
                "event_method": data["event_method"],
                "tx": data["tx_id"],
                # "index_in_chunk": index_data_list[mysql_data["tx_id"]]["index_in_chunk"],
                "block_no": data["block_id"],
                "operator": data["owner_id"],
                "token_contract": data["predecessor_id"],
                "receiver_id": data["receiver_id"],
                "amount": amount,
                "msg": msg
            }
            ret_data_list.append(ret_msg_data)
        else:
            ret_msg_data = {
                "event_method": data["event_method"],
                "tx": data["tx_id"],
                # "index_in_chunk": index_data_list[mysql_data["tx_id"]]["index_in_chunk"],
                "block_no": data["block_id"],
                "operator": data["owner_id"],
            }
            if "pool_id" in args:
                ret_msg_data["pool_id"] = args["pool_id"]
                flag = True
            if "lpt_id" in args:
                ret_msg_data["lpt_id"] = args["lpt_id"]
                flag = True
            if "order_id" in args:
                ret_msg_data["order_id"] = args["order_id"]
            if "amount" in args:
                ret_msg_data["amount"] = args["amount"]
                flag = True
            if "left_point" in args:
                ret_msg_data["left_point"] = args["left_point"]
                flag = True
            if "right_point" in args:
                ret_msg_data["right_point"] = args["right_point"]
                flag = True
            if "amount_x" in args:
                ret_msg_data["amount_x"] = args["amount_x"]
                flag = True
            if "amount_y" in args:
                ret_msg_data["amount_y"] = args["amount_y"]
                flag = True
            if "min_amount_x" in args:
                ret_msg_data["min_amount_x"] = args["min_amount_x"]
                flag = True
            if "min_amount_y" in args:
                ret_msg_data["min_amount_y"] = args["min_amount_y"]
                flag = True
            if flag is False:
                ret_msg_data["amount"] = "None"
            ret_data_list.append(ret_msg_data)
    return ret_data_list


if __name__ == '__main__':
    from config import Cfg
    from redis_provider import list_token_price, list_pools_by_id_list, list_token_metadata
    pools = list_pools_by_id_list(Cfg.NETWORK_ID, [10, 11, 14, 79])
    prices = list_token_price(Cfg.NETWORK_ID)
    metadata = list_token_metadata(Cfg.NETWORK_ID)
    combine_pools_info(pools, prices, metadata)
    for pool in pools:
        print(pool)
    pass