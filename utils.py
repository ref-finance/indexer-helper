import gzip

from flask import make_response
import json
from flask import request
import requests
from db_provider import add_tx_receipt, query_tx_by_receipt
from config import Cfg

LEFT_MOST_POINT = -800000
RIGHT_MOST_POINT = 800000


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


def handle_dcl_point_bin(pool_id, point_data, slot_number, start_point, end_point, point_data_24h,
                         point_data_24h_count, token_price):
    token_decimal_data = get_token_decimal()
    ret_point_list = []
    if len(point_data) < 1:
        return ret_point_list
    total_point = end_point - start_point
    pool_id_s = pool_id.split("|")
    fee_tier = pool_id_s[-1]
    token_x = pool_id_s[0]
    token_y = pool_id_s[1]
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
            "pool_id": pool_id,
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
        current_point = 0
        for point in point_data:
            current_point = point["cp"]
            point_number = point["point"]
            if start_slot_point_number <= point_number < end_slot_point_number:
                ret_point_data["token_x"] = ret_point_data["token_x"] + float(point["tvl_x_l"])
                ret_point_data["token_y"] = ret_point_data["token_y"] + float(point["tvl_y_l"])
                ret_point_data["order_x"] = ret_point_data["order_x"] + float(point["tvl_x_o"])
                ret_point_data["order_y"] = ret_point_data["order_y"] + float(point["tvl_y_o"])
        if end_slot_point_number >= RIGHT_MOST_POINT:
            end_slot_point_number = RIGHT_MOST_POINT - 1
        liquidity_amount_x = ret_point_data["token_x"] * int("1" + "0" * token_decimal_data[token_x])
        liquidity_amount_y = ret_point_data["token_y"] * int("1" + "0" * token_decimal_data[token_y])
        if liquidity_amount_x > 0 and liquidity_amount_y == 0:
            ret_point_data["liquidity"] = compute_liquidity(start_slot_point_number, end_slot_point_number, liquidity_amount_x, liquidity_amount_y, current_point - bin_point_number)
        if liquidity_amount_x == 0 and liquidity_amount_y > 0:
            ret_point_data["liquidity"] = compute_liquidity(start_slot_point_number, end_slot_point_number, liquidity_amount_x, liquidity_amount_y, current_point + bin_point_number)
        if liquidity_amount_x > 0 and liquidity_amount_y > 0:
            ret_point_data["liquidity"] = compute_liquidity(start_slot_point_number, end_slot_point_number, liquidity_amount_x, liquidity_amount_y, current_point)
        order_amount_x = ret_point_data["order_x"] * int("1" + "0" * token_decimal_data[token_x])
        order_amount_y = ret_point_data["order_y"] * int("1" + "0" * token_decimal_data[token_y])
        if order_amount_x > 0 and order_amount_y == 0:
            ret_point_data["order_liquidity"] = compute_liquidity(start_slot_point_number, end_slot_point_number, order_amount_x, order_amount_y, current_point - bin_point_number)
        if order_amount_x == 0 and order_amount_y > 0:
            ret_point_data["order_liquidity"] = compute_liquidity(start_slot_point_number, end_slot_point_number, order_amount_x, order_amount_y, current_point + bin_point_number)
        if order_amount_x > 0 and order_amount_y > 0:
            ret_point_data["order_liquidity"] = compute_liquidity(start_slot_point_number, end_slot_point_number, order_amount_x, order_amount_y, current_point)
        for point_24h in point_data_24h:
            point_number = point_24h["point"]
            if start_slot_point_number <= point_number < end_slot_point_number:
                fee_x = float(point_24h["fee_x"]) * token_price[0]
                fee_y = float(point_24h["fee_y"]) * token_price[1]
                ret_point_data["fee"] = ret_point_data["fee"] + fee_x + fee_y
                tvl_x_l_24h = float(point_24h["tvl_x_l"]) * token_price[0] / point_data_24h_count
                tvl_y_l_24h = float(point_24h["tvl_y_l"]) * token_price[1] / point_data_24h_count
                ret_point_data["total_liquidity"] = ret_point_data["total_liquidity"] + tvl_x_l_24h + tvl_y_l_24h
        if ret_point_data["liquidity"] > 0 or ret_point_data["order_liquidity"] > 0:
            ret_point_list.append(ret_point_data)
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


def pow_128():
    return 1 << 128


def pow_96():
    return 1 << 96


def sqrt_rate_96():
    return get_sqrt_price(1)


def get_sqrt_price(point: int):
    if point > RIGHT_MOST_POINT or point < LEFT_MOST_POINT:
        print("E202_ILLEGAL_POINT")
        return None

    abs_point = point
    if point < 0:
        abs_point = -point

    value = 0x100000000000000000000000000000000
    if point & 1 != 0:
        value = 0xfffcb933bd6fad37aa2d162d1a594001

    value = update_value(abs_point, value, 0x2, 0xfff97272373d413259a46990580e213a)
    value = update_value(abs_point, value, 0x4, 0xfff2e50f5f656932ef12357cf3c7fdcc)
    value = update_value(abs_point, value, 0x8, 0xffe5caca7e10e4e61c3624eaa0941cd0)
    value = update_value(abs_point, value, 0x10, 0xffcb9843d60f6159c9db58835c926644)
    value = update_value(abs_point, value, 0x20, 0xff973b41fa98c081472e6896dfb254c0)
    value = update_value(abs_point, value, 0x40, 0xff2ea16466c96a3843ec78b326b52861)
    value = update_value(abs_point, value, 0x80, 0xfe5dee046a99a2a811c461f1969c3053)
    value = update_value(abs_point, value, 0x100, 0xfcbe86c7900a88aedcffc83b479aa3a4)
    value = update_value(abs_point, value, 0x200, 0xf987a7253ac413176f2b074cf7815e54)
    value = update_value(abs_point, value, 0x400, 0xf3392b0822b70005940c7a398e4b70f3)
    value = update_value(abs_point, value, 0x800, 0xe7159475a2c29b7443b29c7fa6e889d9)
    value = update_value(abs_point, value, 0x1000, 0xd097f3bdfd2022b8845ad8f792aa5825)
    value = update_value(abs_point, value, 0x2000, 0xa9f746462d870fdf8a65dc1f90e061e5)
    value = update_value(abs_point, value, 0x4000, 0x70d869a156d2a1b890bb3df62baf32f7)
    value = update_value(abs_point, value, 0x8000, 0x31be135f97d08fd981231505542fcfa6)
    value = update_value(abs_point, value, 0x10000, 0x9aa508b5b7a84e1c677de54f3e99bc9)
    value = update_value(abs_point, value, 0x20000, 0x5d6af8dedb81196699c329225ee604)
    value = update_value(abs_point, value, 0x40000, 0x2216e584f5fa1ea926041bedfe98)
    value = update_value(abs_point, value, 0x80000, 0x48a170391f7dc42444e8fa2)

    if point > 0:
        value = ((1 << 256) - 1) // value

    remainder = 0
    if value % (1 << 32):
        remainder = 1
    return (value >> 32) + remainder


def update_value(point, value, hex1, hex2):
    if point & hex1 != 0:
        value = value * hex2
        value = (value >> 128)
    return value


def mul_fraction_floor(number, _numerator, _denominator):
    return number * _numerator // _denominator


def get_amount_y_unit_liquidity_96(sqrt_price_l_96: int, sqrt_price_r_96: int, sqrt_rate_96: int):
    numerator = sqrt_price_r_96 - sqrt_price_l_96
    denominator = sqrt_rate_96 - pow_96()
    return mul_fraction_ceil(pow_96(), numerator, denominator)


def mul_fraction_ceil(number, _numerator, _denominator):
    res = number * _numerator // _denominator
    if number * _numerator % _denominator == 0:
        return res
    else:
        return res + 1


def get_amount_x_unit_liquidity_96(left_pt: int, right_pt: int, sqrt_price_r_96: int, sqrt_rate_96: int):
    sqrt_price_pr_pc_96 = get_sqrt_price(right_pt - left_pt + 1)
    sqrt_price_pr_pd_96 = get_sqrt_price(right_pt + 1)
    numerator = sqrt_price_pr_pc_96 - sqrt_rate_96
    denominator = sqrt_price_pr_pd_96 - sqrt_price_r_96
    return mul_fraction_ceil(pow_96(), numerator, denominator)


def compute_deposit_xy_per_unit(left_point: int, right_point: int, current_point: int):
    sqrt_price_96 = get_sqrt_price(current_point)
    sqrt_price_r_96 = get_sqrt_price(right_point)
    y = 0
    if left_point < current_point:
        sqrt_price_l_96 = get_sqrt_price(left_point)
        if right_point < current_point:
            y = get_amount_y_unit_liquidity_96(sqrt_price_l_96, sqrt_price_r_96, sqrt_rate_96())
        else:
            y = get_amount_y_unit_liquidity_96(sqrt_price_l_96, sqrt_price_96, sqrt_rate_96())
    x = 0
    if right_point > current_point:
        xr_left = current_point + 1
        if left_point > current_point:
            xr_left = left_point
        x = get_amount_x_unit_liquidity_96(xr_left, right_point, sqrt_price_r_96, sqrt_rate_96())
    if left_point <= current_point < right_point:
        y += sqrt_price_96
    return x, y


def compute_liquidity(left_point: int, right_point: int, amount_x: int, amount_y: int, current_point: int):
    liquidity = ((1 << 128) - 1) // 2
    (x, y) = compute_deposit_xy_per_unit(left_point, right_point, current_point)
    if x > 0:
        xl = mul_fraction_floor(amount_x, pow_96(), x)
        if liquidity > xl:
            liquidity = xl
    if y > 0:
        yl = mul_fraction_floor(amount_y - 1, pow_96(), y)
        if liquidity > yl:
            liquidity = yl
    return liquidity


def get_token_decimal():
    token_decimal_data = {}
    for token in Cfg.TOKENS[Cfg.NETWORK_ID]:
        token_decimal_data[token["NEAR_ID"]] = token["DECIMAL"]
    return token_decimal_data


def compute_deposit_x_y(left_point: int, right_point: int, liquidity: int, current_point):
    sqrt_price_r_96 = get_sqrt_price(right_point)
    sqrt_price_96 = get_sqrt_price(current_point)
    amount_y = 0
    if left_point < current_point:
        sqrt_price_l_96 = get_sqrt_price(left_point)
        if right_point < current_point:
            amount_y = get_amount_y(liquidity, sqrt_price_l_96, sqrt_price_r_96, sqrt_rate_96(), True)
        else:
            amount_y = get_amount_y(liquidity, sqrt_price_l_96, sqrt_price_96, sqrt_rate_96(), True)

    amount_x = 0
    if right_point > current_point:
        xr_left = current_point + 1
        if left_point > current_point:
            xr_left = left_point
        amount_x = get_amount_x(liquidity, xr_left, right_point, sqrt_price_r_96, sqrt_rate_96(), True)

    if left_point <= current_point < right_point:
        amount_y += mul_fraction_ceil(liquidity, sqrt_price_96, pow_96())
        liquidity += liquidity

    return amount_x, amount_y


def get_amount_x(liquidity: int, left_pt: int, right_pt: int, sqrt_price_r_96: int, sqrt_rate_96: int, upper: bool):
    # d = 1.0001,  ∵ L = X * sqrt(P)   ∴ X(i) = L / sqrt(d ^ i)
    # sqrt(d) ^ (r - l) - 1
    # --------------------------------- = amount_x_of_unit_liquidity: the amount of token X equivalent to a unit of  c in the range
    # sqrt(d) ^ r - sqrt(d) ^ (r - 1)
    #
    # (sqrt(d) - 1) * (sqrt(d) ^ (r - l - 1) + sqrt(d) ^ (r - l - 2) + ...... + 1)
    # ----------------------------------------------------------------------------
    # (sqrt(d) - 1) * sqrt(d) ^ (r - 1))
    #
    #      1                1                             1
    # ------------ + ----------------- + ...... + -----------------
    # sqrt(d) ^ l    sqrt(d) ^ (l + 1)            sqrt(d) ^ (r - 1)
    #
    # X(l) + X(l + 1) + ...... + X(r - 1)

    # amount_x = amount_x_of_unit_liquidity * liquidity

    sqrt_price_pr_pl_96 = get_sqrt_price(right_pt - left_pt)
    sqrt_price_pr_m1_96 = mul_fraction_floor(sqrt_price_r_96, pow_96(), sqrt_rate_96)

    # using sum equation of geomitric series to compute range numbers
    numerator = sqrt_price_pr_pl_96 - pow_96()
    denominator = sqrt_price_r_96 - sqrt_price_pr_m1_96
    if not upper:
        return mul_fraction_floor(liquidity, numerator, denominator)
    else:
        return mul_fraction_ceil(liquidity, numerator, denominator)


def get_amount_y(liquidity: int, sqrt_price_l_96: int, sqrt_price_r_96: int, sqrt_rate_96: int, upper: bool):
    # d = 1.0001, ∵ L = Y / sqrt(P)   ∴ Y(i) = L * sqrt(d ^ i)
    # sqrt(d) ^ r - sqrt(d) ^ l
    # ------------------------- = amount_y_of_unit_liquidity: the amount of token Y equivalent to a unit of liquidity in the range
    # sqrt(d) - 1
    #
    # sqrt(d) ^ l * sqrt(d) ^ (r - l) - sqrt(d) ^ l
    # ----------------------------------------------
    # sqrt(d) - 1
    #
    # sqrt(d) ^ l * (sqrt(d) ^ (r - l) - 1)
    # ----------------------------------------------
    # sqrt(d) - 1
    #
    # sqrt(d) ^ l * (sqrt(d) - 1) * (sqrt(d) ^ (r - l - 1) + sqrt(d) ^ (r - l - 2) + ...... + sqrt(d) + 1)
    # ----------------------------------------------------------------------------------------------------
    # sqrt(d) - 1
    #
    # sqrt(d) ^ l + sqrt(d) ^ (l + 1) + ...... + sqrt(d) ^ (r - 1)
    #
    # Y(l) + Y(l + 1) + ...... + Y(r - 1)

    # amount_y = amount_y_of_unit_liquidity * liquidity

    # using sum equation of geomitric series to compute range numbers
    numerator = sqrt_price_r_96 - sqrt_price_l_96
    denominator = sqrt_rate_96 - pow_96()
    if not upper:
        return mul_fraction_floor(liquidity, numerator, denominator)
    else:
        return mul_fraction_ceil(liquidity, numerator, denominator)


def compute_deposit_x_y_buckup(liquidity, left_point, right_point, current_point):
    user_liquidity_y = 0
    user_liquidity_x = 0
    sqrt_price_96 = get_sqrt_price(current_point)
    sqrt_price_r_96 = get_sqrt_price(right_point)
    if left_point < current_point:
        sqrt_price_l_96 = get_sqrt_price(left_point)
        if right_point < current_point:
            user_liquidity_y = get_amount_y(liquidity, sqrt_price_l_96, sqrt_price_r_96, sqrt_rate_96(), True)
        else:
            user_liquidity_y = get_amount_y(liquidity, sqrt_price_l_96, sqrt_price_96, sqrt_rate_96(), True)

    if right_point > current_point:
        xr_left = 0
        if left_point > current_point:
            xr_left = left_point
        else:
            xr_left = current_point + 1

        user_liquidity_x = get_amount_x(liquidity, xr_left, right_point, sqrt_price_r_96, sqrt_rate_96(), True)

    if left_point <= current_point < right_point:
        user_liquidity_y += mul_fraction_ceil(liquidity, sqrt_price_96, pow_96())

    return user_liquidity_x, user_liquidity_y


if __name__ == '__main__':
    # from config import Cfg
    # from redis_provider import list_token_price, list_pools_by_id_list, list_token_metadata
    # pools = list_pools_by_id_list(Cfg.NETWORK_ID, [10, 11, 14, 79])
    # prices = list_token_price(Cfg.NETWORK_ID)
    # metadata = list_token_metadata(Cfg.NETWORK_ID)
    # combine_pools_info(pools, prices, metadata)
    # for pool in pools:
    #     print(pool)
    # pass
    liquidity_ = compute_liquidity(5160, 5240, 7404115124903830000000000000, 10555983177592727000000000000, 5214)
    print("liquidity_:", liquidity_)
    # a_x, a_y = compute_deposit_x_y_buckup(182847144196469251612398703, 5000, 5040, 5035)
    # print("x:", a_x)
    # print("y", a_y)
