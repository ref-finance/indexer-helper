import gzip
import time

from flask import make_response
import json
from flask import request
import requests
from db_provider import add_tx_receipt, query_tx_by_receipt
import random


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


def handle_point_data(all_point_data, start_point, end_point):
    point_data_list = []
    for point_data in all_point_data:
        if start_point <= point_data["point"] <= end_point:
            point_data_list.append(point_data)
    return point_data_list


def handle_dcl_point_bin(pool_id, point_data, slot_number, start_point, end_point, point_data_24h):
    # now = int(time.time())
    ret_point_list = []
    total_point = end_point - start_point
    fee_tier = pool_id.split("|")[-1]
    point_delta_number = 40
    if fee_tier == "100":
        point_delta_number = 1
    elif fee_tier == "400":
        point_delta_number = 8
    elif fee_tier == "2000":
        point_delta_number = 40
    elif fee_tier == "10000":
        point_delta_number = 200
    bin_point_number = point_delta_number * slot_number
    total_bin = int(total_point / bin_point_number)
    for i in range(1, total_bin + 2):
        slot_point_number = bin_point_number * i
        start_point_number = int(start_point / bin_point_number) * bin_point_number
        ret_point_data = {
            "pool_id": "",
            "point": start_point_number + slot_point_number - bin_point_number,
            "liquidity": 0,
            "token_x": 0,
            "token_y": 0,
            "order_x": 0,
            "order_y": 0,
            "order_liquidity": 0,
            "fee": 0,
            "total_liquidity": 0,
            "sort_number": i,
        }
        end_slot_point_number = start_point_number + slot_point_number
        start_slot_point_number = end_slot_point_number - bin_point_number
        for point in point_data:
            point_number = point["point"]
            if start_slot_point_number <= point_number < end_slot_point_number:
                if ret_point_data["pool_id"] == "":
                    ret_point_data["pool_id"] = point["pool_id"]
                ret_point_data["liquidity"] = ret_point_data["liquidity"] + int(point["l"])
                ret_point_data["token_x"] = ret_point_data["token_x"] + float(point["tvl_x_l"])
                ret_point_data["token_y"] = ret_point_data["token_y"] + float(point["tvl_y_l"])
                ret_point_data["order_x"] = ret_point_data["order_x"] + float(point["tvl_x_o"])
                ret_point_data["order_y"] = ret_point_data["order_y"] + float(point["tvl_y_o"])
                ret_point_data["order_liquidity"] = ret_point_data["order_liquidity"] + float(point["tvl_y_o"])
                # ret_point_data["fee"] = ret_point_data["fee"] + (float(point["fee_x"]) + float(point["fee_y"])) * float(point["p"])
                # ret_point_data["total_liquidity"] = ret_point_data["total_liquidity"] + (float(point["tvl_x_l"]) + float(point["tvl_y_l"])) * float(point["p"])
        for point_24h in point_data_24h:
            point_number = point_24h["point"]
            if start_slot_point_number <= point_number < end_slot_point_number:
                ret_point_data["fee"] = ret_point_data["fee"] + (float(point_24h["fee_x"]) + float(point_24h["fee_y"])) * float(point_24h["p"])
                ret_point_data["total_liquidity"] = ret_point_data["total_liquidity"] + (float(point_24h["tvl_x_l"]) + float(point_24h["tvl_y_l"])) / 24 * float(point_24h["p"])
        if ret_point_data["liquidity"] > 0:
            ret_point_list.append(ret_point_data)
    # end = int(time.time())
    # print("end111:", end - now)
    return ret_point_list


def handle_top_bin_fee(point_data):
    ret_point_data = {
        "total_fee": 0,
        "total_liquidity": 0,
    }
    max_fee_apr = 0
    for point in point_data:
        total_fee = point["fee"]
        total_liquidity = point["total_liquidity"]
        if total_liquidity > 0 and total_fee > 0:
            bin_fee_apr = total_fee / total_liquidity
            if bin_fee_apr > max_fee_apr:
                max_fee_apr = bin_fee_apr
                ret_point_data["total_fee"] = total_fee
                ret_point_data["total_liquidity"] = total_liquidity
    return ret_point_data


# def handle_top_bin_fee(pool_id, point_data, slot_number, start_point, end_point):
#     total_point = end_point - start_point
#     fee_tier = pool_id.split("|")[-1]
#     point_delta_number = 40
#     if fee_tier == "100":
#         point_delta_number = 1
#     elif fee_tier == "400":
#         point_delta_number = 8
#     elif fee_tier == "2000":
#         point_delta_number = 40
#     elif fee_tier == "10000":
#         point_delta_number = 200
#     bin_point_number = point_delta_number * slot_number
#     total_bin = int(total_point / bin_point_number)
#     ret_point_data = {
#         "total_fee": 0,
#         "total_liquidity": 0,
#     }
#     max_fee_apr = 0
#     max_total_liquidity = 0
#     for i in range(1, total_bin + 2):
#         slot_point_number = bin_point_number * i
#         start_point_number = int(start_point / bin_point_number) * bin_point_number
#         end_slot_point_number = start_point_number + slot_point_number
#         start_slot_point_number = end_slot_point_number - bin_point_number
#         total_fee = 0
#         total_liquidity = 0
#         for point in point_data:
#             point_number = point["point"]
#             if start_slot_point_number <= point_number < end_slot_point_number:
#                 total_fee = total_fee + (float(point["fee_x"]) + float(point["fee_y"])) * float(point["p"])
#                 total_liquidity = total_liquidity + (float(point["tvl_x_l"]) + float(point["tvl_y_l"])) * float(point["p"])
#         if total_liquidity > 0:
#             if total_liquidity > max_total_liquidity:
#                 max_total_liquidity = total_liquidity
#                 ret_point_data["total_liquidity"] = total_liquidity
#             bin_fee_apr = total_fee / total_liquidity
#             if bin_fee_apr > max_fee_apr:
#                 max_fee_apr = bin_fee_apr
#                 ret_point_data["total_fee"] = total_fee
#                 ret_point_data["total_liquidity"] = total_liquidity
#     return ret_point_data


def handle_dcl_point_bin_by_account(pool_id, point_data, slot_number, account_id, start_point, end_point):
    ret_point_list = []
    total_point = end_point - start_point
    fee_tier = pool_id.split("|")[-1]
    point_delta_number = 40
    if fee_tier == "100":
        point_delta_number = 1
    elif fee_tier == "400":
        point_delta_number = 8
    elif fee_tier == "2000":
        point_delta_number = 40
    elif fee_tier == "10000":
        point_delta_number = 200
    bin_point_number = point_delta_number * slot_number
    total_bin = int(total_point / bin_point_number)
    for i in range(1, total_bin + 2):
        slot_point_number = bin_point_number * i
        start_point_number = int(start_point / bin_point_number) * bin_point_number
        ret_point_data = {
            "pool_id": "",
            "account_id": account_id,
            "point": start_point_number + slot_point_number - bin_point_number,
            "liquidity": 0,
            "token_x": 0,
            "token_y": 0,
            "fee": 0,
            "total_liquidity": 0,
            "sort_number": i,
        }
        end_slot_point_number = start_point_number + slot_point_number
        start_slot_point_number = end_slot_point_number - bin_point_number
        for point in point_data:
            point_number = point["point"]
            if start_slot_point_number <= point_number < end_slot_point_number:
                if ret_point_data["pool_id"] == "":
                    ret_point_data["pool_id"] = point["pool_id"]
                ret_point_data["liquidity"] = ret_point_data["liquidity"] + int(point["l"])
                ret_point_data["token_x"] = ret_point_data["token_x"] + float(point["tvl_x_l"])
                ret_point_data["token_y"] = ret_point_data["token_y"] + float(point["tvl_y_l"])
                ret_point_data["fee"] = (ret_point_data["fee"] + (float(point["tvl_x_l"]) + float(point["tvl_y_l"])) * float(point["p"]))
                ret_point_data["total_liquidity"] = ret_point_data["total_liquidity"] + (float(point["tvl_x_l"]) + float(point["tvl_y_l"])) * float(point["p"])
        if ret_point_data["liquidity"] > 0:
            ret_point_list.append(ret_point_data)
    return ret_point_list


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