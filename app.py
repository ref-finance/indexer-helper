#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Marco'

# Import flask class
from http.client import responses
from flask import Flask
from flask import request
from flask import jsonify
import json
import logging
from indexer_provider import get_proposal_id_hash
from redis_provider import list_farms, list_top_pools, list_pools, list_token_price, list_whitelist, get_token_price, list_base_token_price
from redis_provider import list_pools_by_id_list, list_token_metadata, list_pools_by_tokens, get_pool, list_token_metadata_v2
from redis_provider import list_token_price_by_id_list, get_proposal_hash_by_id, get_24h_pool_volume, get_account_pool_assets
from redis_provider import get_dcl_pools_volume_list, get_24h_pool_volume_list, get_dcl_pools_tvl_list, get_token_price_ratio_report, get_history_token_price_report
from utils import combine_pools_info, compress_response_content, get_ip_address, pools_filter, get_tx_id, combine_dcl_pool_log, handle_dcl_point_bin, handle_point_data, handle_top_bin_fee, handle_dcl_point_bin_by_account, get_circulating_supply
from config import Cfg
from db_provider import get_history_token_price, query_limit_order_log, query_limit_order_swap, get_liquidity_pools, get_actions, query_dcl_pool_log
from db_provider import query_recent_transaction_swap, query_recent_transaction_dcl_swap, \
    query_recent_transaction_liquidity, query_recent_transaction_dcl_liquidity, query_recent_transaction_limit_order, query_dcl_points, query_dcl_points_by_account, \
    query_dcl_user_unclaimed_fee, query_dcl_user_claimed_fee, query_dcl_user_unclaimed_fee_24h, query_dcl_user_claimed_fee_24h, \
    query_dcl_user_tvl, query_dcl_user_change_log, query_burrow_log, get_history_token_price_by_token, add_orderly_trading_data
import re
# from flask_limiter import Limiter
from loguru import logger
from analysis_v2_pool_data_s3 import analysis_v2_pool_data_to_s3, analysis_v2_pool_account_data_to_s3
import time
import datetime

service_version = "20240509.01"
Welcome = 'Welcome to ref datacenter API server, version ' + service_version + ', indexer %s' % \
          Cfg.NETWORK[Cfg.NETWORK_ID]["INDEXER_HOST"][-3:]
# Instantiation, which can be regarded as fixed format
app = Flask(__name__)
# limiter = Limiter(
#     app,
#     key_func=get_ip_address,
#     default_limits=["20 per second"],
#     # storage_uri="redis://:@127.0.0.1:6379/2"
#     storage_uri="redis://:@" + Cfg.REDIS["REDIS_HOST"] + ":6379/2"
# )


@app.before_request
def before_request():
    # Processing get requests
    data = request.args
    for v in data.values():
        v = str(v).lower()
        pattern = r"(<.*?>)"
        r = re.search(pattern, v)
        if r:
            return 'Please enter the parameters of the specification!'


# route()Method is used to set the route; Similar to spring routing configuration
@app.route('/')
def hello_world():
    return Welcome


@app.route('/timestamp', methods=['GET'])
# @limiter.limit("1/5 second")
def handle_timestamp():
    import time
    return jsonify({"ts": int(time.time())})


@app.route('/latest-actions/<account_id>', methods=['GET'])
def handle_latest_actions(account_id):
    """
    get user's latest actions
    """
    json_obj = []
    try:
        ret = get_actions(Cfg.NETWORK_ID, account_id)
        json_obj = json.loads(ret)
        # for obj in json_obj:
        #     if obj[1] == "":
        #         obj[1] = get_tx_id(obj[7], Cfg.NETWORK_ID)
    except Exception as e:
        print("Exception when get_actions: ", e)

    return compress_response_content(json_obj)


@app.route('/liquidity-pools/<account_id>', methods=['GET'])
def handle_liquidity_pools(account_id):
    """
    get user's liqudity pools
    """
    if account_id == "v2.ref-finance.near":
        ip_address = get_ip_address()
        logger.info("request ip:{}", ip_address)
        return ""
    ret = []
    try:
        id_list = get_liquidity_pools(Cfg.NETWORK_ID, account_id)
        if len(id_list) > 0:
            ret = list_pools_by_id_list(Cfg.NETWORK_ID, [int(x) for x in id_list])
    except Exception as e:
        print("Exception when get_liquidity_pools: ", e)

    return compress_response_content(ret)


@app.route('/list-farms', methods=['GET'])
def handle_list_farms():
    """
    list_farms
    """
    ret = list_farms(Cfg.NETWORK_ID)
    return compress_response_content(ret)


@app.route('/get-token-price', methods=['GET'])
def handle_get_token_price():
    """
    list_token_price
    """
    token_contract_id = request.args.get("token_id", "N/A")
    ret = {"token_contract_id": token_contract_id}
    # if token_contract_id == 'usn' or token_contract_id == 'usdt.tether-token.near':
    #     token_contract_id = "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near"
    ret["price"] = get_token_price(Cfg.NETWORK_ID, token_contract_id)
    if ret["price"] is None:
        ret["price"] = "N/A"
    return compress_response_content(ret)


@app.route('/list-token-price', methods=['GET'])
def handle_list_token_price():
    """
    list_token_price
    """
    ret = {}
    prices = list_token_price(Cfg.NETWORK_ID)
    for token in Cfg.TOKENS[Cfg.NETWORK_ID]:
        if token["NEAR_ID"] in prices:
            ret[token["NEAR_ID"]] = {
                "price": prices[token["NEAR_ID"]],
                "decimal": token["DECIMAL"],
                "symbol": token["SYMBOL"],
            }
    # if usdt exists, mirror its price to USN
    # if "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near" in ret:
    #     ret["usn"] = {
    #         "price": prices["dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near"],
    #         "decimal": 18,
    #         "symbol": "USN",
    #     }
    #     ret["usdt.tether-token.near"] = {
    #         "price": prices["dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near"],
    #         "decimal": 6,
    #         "symbol": "USDt",
    #     }
    # # if token.v2.ref-finance.near exists, mirror its info to rftt.tkn.near
    # if "token.v2.ref-finance.near" in ret:
    #     ret["rftt.tkn.near"] = {
    #         "price": prices["token.v2.ref-finance.near"],
    #         "decimal": 8,
    #         "symbol": "RFTT",
    #     }
    return compress_response_content(ret)


@app.route('/get-token-price-by-dapdap', methods=['GET'])
def handle_list_base_token_price():
    prices = list_base_token_price(Cfg.NETWORK_ID)
    return compress_response_content(prices)


@app.route('/list-token-price-by-ids', methods=['GET'])
def handle_list_token_price_by_ids():
    """
    list_token_price_by_ids
    """
    ids = request.args.get("ids", "")
    # ids = ("|" + ids.lstrip("|").rstrip("|") + "|").replace("|usn|",
    #                                                         "|dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near|")
    # ids = ("|" + ids.lstrip("|").rstrip("|") + "|").replace("|usdt.tether-token.near|",
    #                                                         "|dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near|")
    id_str_list = ids.lstrip("|").rstrip("|").split("|")

    prices = list_token_price_by_id_list(Cfg.NETWORK_ID, [str(x) for x in id_str_list])
    ret = ["N/A" if i is None else i for i in prices]

    return compress_response_content(ret)


@app.route('/list-token', methods=['GET'])
def handle_list_token():
    """
    list_token
    """
    ret = list_token_metadata(Cfg.NETWORK_ID)
    return compress_response_content(ret)


@app.route('/list-token-v2', methods=['GET'])
def handle_list_token_v2():
    """
    list_token
    """
    ret = list_token_metadata_v2(Cfg.NETWORK_ID)
    return compress_response_content(ret)


@app.route('/get-pool', methods=['GET'])
def handle_get_pool():
    """
    get_pool
    """
    pool_id = request.args.get("pool_id", "N/A")
    pool = get_pool(Cfg.NETWORK_ID, pool_id)

    if pool:
        prices = list_token_price(Cfg.NETWORK_ID)
        metadata = list_token_metadata(Cfg.NETWORK_ID)
        combine_pools_info([pool, ], prices, metadata)

    return compress_response_content(pool)


@app.route('/list-top-pools', methods=['GET'])
def handle_list_top_pools():
    """
    list_top_pools
    """

    pools = list_top_pools(Cfg.NETWORK_ID)
    prices = list_token_price(Cfg.NETWORK_ID)
    metadata = list_token_metadata(Cfg.NETWORK_ID)

    combine_pools_info(pools, prices, metadata)
    list_top_pools_log = []
    for pool in pools:
        pool_log = {
            "id": pool["id"],
            "token_account_ids": pool["token_account_ids"],
            "amounts": pool["amounts"],
        }
        list_top_pools_log.append(pool_log)
    # logger.info("list_top_pools_data:{}", list_top_pools_log)
    return compress_response_content(pools)


@app.route('/list-pools', methods=['GET'])
def handle_list_pools():
    """
    list_pools
    """
    tvl = request.args.get("tvl")
    amounts = request.args.get("amounts")
    pools = list_pools(Cfg.NETWORK_ID)
    prices = list_token_price(Cfg.NETWORK_ID)
    metadata = list_token_metadata(Cfg.NETWORK_ID)

    combine_pools_info(pools, prices, metadata)
    pools = pools_filter(pools, tvl, amounts)

    return compress_response_content(pools)


@app.route('/list-pools-by-tokens', methods=['GET'])
def handle_list_pools_by_tokens():
    """
    list_pools_by_tokens
    """
    token0 = request.args.get("token0", "N/A")
    token1 = request.args.get("token1", "N/A")

    pools = list_pools_by_tokens(Cfg.NETWORK_ID, token0, token1)
    prices = list_token_price(Cfg.NETWORK_ID)
    metadata = list_token_metadata(Cfg.NETWORK_ID)

    combine_pools_info(pools, prices, metadata)

    return compress_response_content(pools)


@app.route('/list-pools-by-ids', methods=['GET'])
def handle_list_pools_by_ids():
    """
    list_pools_by_ids
    """
    ids = request.args.get("ids", "")
    id_str_list = ids.split("|")

    pools = list_pools_by_id_list(Cfg.NETWORK_ID, [int(x) for x in id_str_list])
    prices = list_token_price(Cfg.NETWORK_ID)
    metadata = list_token_metadata(Cfg.NETWORK_ID)

    combine_pools_info(pools, prices, metadata)

    return compress_response_content(pools)


@app.route('/whitelisted-active-pools', methods=['GET'])
def handle_whitelisted_active_pools():
    """
    handle_whitelisted_active_pools
    """
    ret = []
    pools = list_top_pools(Cfg.NETWORK_ID)
    whitelist = list_whitelist(Cfg.NETWORK_ID)
    for pool in pools:
        if pool["pool_kind"] != "SIMPLE_POOL":
            continue
        token0, token1 = pool['token_account_ids'][0], pool['token_account_ids'][1]
        if pool["amounts"][0] == "0":
            continue
        if token0 in whitelist and token1 in whitelist:
            ret.append({
                "pool_id": pool["id"],
                "token_symbols": pool["token_symbols"],
                "token_decimals": [whitelist[token0]["decimals"], whitelist[token1]["decimals"]],
                "token_names": [whitelist[token0]["name"], whitelist[token1]["name"]],
                "liquidity_amounts": pool["amounts"],
                "vol_token0_token1": pool["vol01"],
                "vol_token1_token0": pool["vol10"],
            })

    return compress_response_content(ret)


@app.route('/to-coingecko', methods=['GET'])
def handle_to_coingecko():
    """
    handle_price_to_coingecko
    """
    ret = {}
    # pools = list_pools_by_id_list(Cfg.NETWORK_ID, ['1346', '1429'])
    pools = list_top_pools(Cfg.NETWORK_ID)
    prices = list_token_price(Cfg.NETWORK_ID)
    metadata = list_token_metadata(Cfg.NETWORK_ID)
    whitelist = list_whitelist(Cfg.NETWORK_ID)
    for pool in pools:
        if pool["pool_kind"] != "SIMPLE_POOL":
            continue
        token0, token1 = pool['token_account_ids'][0], pool['token_account_ids'][1]
        if pool["amounts"][0] == "0":
            continue
        if token0 in whitelist and token1 in whitelist:
            (balance0, balance1) = (
                float(pool['amounts'][0]) / (10 ** metadata[token0]["decimals"]),
                float(pool['amounts'][1]) / (10 ** metadata[token1]["decimals"])
            )
            key = "%s-%s" % (pool["token_symbols"][0], pool["token_symbols"][1])
            # add token0_ref_price = token1_price * token1_balance / token0_balance 
            if balance0 > 0 and balance1 > 0:
                vol_to_other_token = {"input": "0", "output": "0"}
                vol_from_other_token = {"input": "0", "output": "0"}
                if "vol01" in pool:
                    vol_to_other_token = pool["vol01"]
                if "vol10" in pool:
                    vol_from_other_token = pool["vol10"]
                ret[key] = {
                    "pool_id": pool["id"],
                    "token_symbol": pool["token_symbols"][0],
                    "other_token": pool["token_symbols"][1],
                    "token_decimals": [whitelist[token0]["decimals"], whitelist[token1]["decimals"]],
                    "liquidity_amounts": pool["amounts"],
                    "price_in_usd": str(float(prices[token1]) * balance1 / balance0) if token1 in prices else "N/A",
                    "price_in_other_token": str(balance1 / balance0),
                    "vol_to_other_token": vol_to_other_token,
                    "vol_from_other_token": vol_from_other_token,
                }

    return compress_response_content(ret)


@app.route('/list-history-token-price-by-ids', methods=['GET'])
def handle_history_token_price_by_ids():
    ids = request.args.get("ids", "")
    ids = ("|" + ids.lstrip("|").rstrip("|") + "|")
    id_str_list = ids.lstrip("|").rstrip("|").split("|")

    ret = get_history_token_price([str(x) for x in id_str_list])
    return compress_response_content(ret)


@app.route('/get-service-version', methods=['GET'])
# @limiter.limit("1/second")
def get_service_version():
    return jsonify(service_version)


@app.route('/get-proposal-hash-by-id', methods=['GET'])
def handle_proposal_hash():
    ret = []
    proposal_id = request.args.get("proposal_id")
    if proposal_id is None:
        return ret
    proposal_id_list = []
    ids = ("|" + proposal_id.lstrip("|").rstrip("|") + "|")
    id_str_list = ids.lstrip("|").rstrip("|").split("|")
    res = get_proposal_hash_by_id(Cfg.NETWORK_ID, id_str_list)
    for proposal in res:
        if not proposal is None:
            proposal_id_list.append(proposal["proposal_id"])
            ret.append(proposal)
    difference_set = list(set(id_str_list).difference(set(proposal_id_list)))
    if len(difference_set) > 0:
        ret += get_proposal_id_hash(Cfg.NETWORK_ID, difference_set)
    return compress_response_content(ret)


@app.route('/get-24h-volume-by-id', methods=['GET'])
def handle_24h_pool_volume():
    pool_id = request.args.get("pool_id")
    if pool_id is None:
        return ''
    res = get_24h_pool_volume(Cfg.NETWORK_ID, pool_id)
    return compress_response_content(res)


@app.route('/get-dcl-pools-volume', methods=['GET'])
def handle_dcl_pools_volume():
    pool_id = request.args.get("pool_id")
    if pool_id is None:
        return ''
    res = get_dcl_pools_volume_list(Cfg.NETWORK_ID, pool_id)
    return compress_response_content(res)


@app.route('/get-24h-volume-list', methods=['GET'])
def handle_24h_pool_volume_list():
    res = get_24h_pool_volume_list(Cfg.NETWORK_ID)
    return compress_response_content(res)


@app.route('/get-dcl-pools-tvl-list', methods=['GET'])
def handle_dcl_pools_tvl_list():
    pool_id = request.args.get("pool_id")
    if pool_id is None:
        return ''
    res = get_dcl_pools_tvl_list(Cfg.NETWORK_ID, pool_id)
    return compress_response_content(res)


@app.route('/get-limit-order-log-by-account/<account_id>', methods=['GET'])
def get_limit_order_log_by_account(account_id):
    res = query_limit_order_log(Cfg.NETWORK_ID, account_id)
    return compress_response_content(res)


@app.route('/get-limit-order-swap-by-account/<account_id>', methods=['GET'])
def get_limit_order_swap_by_account(account_id):
    res = query_limit_order_swap(Cfg.NETWORK_ID, account_id)
    return compress_response_content(res)


@app.route('/get-assets-by-account', methods=['GET'])
def handle_assets_by_account():
    account_id = request.args.get("account_id")
    dimension = request.args.get("dimension")
    if account_id is None or dimension is None:
        return ""
    redis_key = account_id + "_" + dimension.lower()
    ret = get_account_pool_assets(Cfg.NETWORK_ID, redis_key)
    if ret is None:
        return ""
    return compress_response_content(json.loads(ret))


@app.route('/token-price-report', methods=['GET'])
def token_price_ratio_report():
    token = request.args.get("token")
    base_token = request.args.get("base_token")
    dimension = request.args.get("dimension")
    if token is None or base_token is None or dimension is None:
        return "null"
    redis_key = token + "->" + base_token + "_" + dimension.lower()
    ret = get_token_price_ratio_report(Cfg.NETWORK_ID, redis_key)
    if ret is None:
        return "null"
    return compress_response_content(json.loads(ret))


@app.route('/get-burrow-records', methods=['GET'])
def handle_burrow_records():
    account_id = request.args.get("account_id")
    page_number = request.args.get("page_number", type=int, default=1)
    page_size = request.args.get("page_size", type=int, default=10)
    if account_id is None or account_id == '':
        return ""
    burrow_log_list, count_number = query_burrow_log(Cfg.NETWORK_ID, account_id, page_number, page_size)
    if count_number % page_size == 0:
        total_page = int(count_number / page_size)
    else:
        total_page = int(count_number / page_size) + 1
    for burrow_log in burrow_log_list:
        # if burrow_log["tx_id"] is None or burrow_log["tx_id"] == "":
        #     burrow_log["tx_id"] = get_tx_id(burrow_log["receipt_id"], Cfg.NETWORK_ID)
        burrow_log["change"] = ""
        if burrow_log["event"] == "borrow":
            burrow_log["event"] = "Borrow"
        if burrow_log["event"] == "decrease_collateral":
            burrow_log["event"] = "Adjust Collateral"
            burrow_log["change"] = "decrease"
        if burrow_log["event"] == "increase_collateral":
            burrow_log["event"] = "Adjust Collateral"
            burrow_log["change"] = "increase"
        if burrow_log["event"] == "deposit":
            burrow_log["event"] = "Supply"
        if burrow_log["event"] == "withdraw_succeeded":
            burrow_log["event"] = "Withdraw"
    res = {
        "record_list": burrow_log_list,
        "page_number": page_number,
        "page_size": page_size,
        "total_page": total_page,
        "total_size": count_number,
    }
    return compress_response_content(res)


@app.route('/get-history-token-price-by-token', methods=['GET'])
def token_history_token_price_by_token():
    ids = request.args.get("ids", "")
    id_str_list = ids.split("|")
    data_time = request.args.get("data_time")
    ret = get_history_token_price_by_token(id_str_list, data_time)
    return compress_response_content(ret)


@app.route('/get-dcl-pool-log', methods=['GET'])
def handle_dcl_pool_log():
    start_block_id = request.args.get("start_block_id")
    end_block_id = request.args.get("end_block_id")
    logger.info("start_block_id:{}", start_block_id)
    logger.info("end_block_id:{}", end_block_id)
    if start_block_id is None or end_block_id is None:
        return "[]"
    ret = query_dcl_pool_log(Cfg.NETWORK_ID, start_block_id, end_block_id)
    if ret is None:
        return "[]"
    dcl_pool_log_data = combine_dcl_pool_log(ret)
    return compress_response_content(dcl_pool_log_data)


@app.route('/analysis-v2-pool-data', methods=['GET'])
def analysis_v2_pool_data():
    file_name = request.args.get("file_name")
    logger.info("pool file_name:{}", file_name)
    analysis_v2_pool_data_to_s3(file_name, Cfg.NETWORK_ID)
    return file_name


@app.route('/analysis-v2-pool-account-data', methods=['GET'])
def analysis_v2_pool_account_data():
    file_name = request.args.get("file_name")
    logger.info("account file_name:{}", file_name)
    analysis_v2_pool_account_data_to_s3(file_name, Cfg.NETWORK_ID)
    return file_name


@app.route('/get-recent-transaction-swap', methods=['GET'])
def handle_recent_transaction_swap():
    pool_id = request.args.get("pool_id")
    ret_data = []
    try:
        ret_data = query_recent_transaction_swap(Cfg.NETWORK_ID, pool_id)
        # for ret in ret_data:
        #     if ret["tx_id"] is None:
        #         ret["tx_id"] = get_tx_id(ret["block_hash"], Cfg.NETWORK_ID)
    except Exception as e:
        print("Exception when swap: ", e)
    return compress_response_content(ret_data)


@app.route('/get-recent-transaction-dcl-swap', methods=['GET'])
def handle_recent_transaction_dcl_swap():
    pool_id = request.args.get("pool_id")
    ret_data = []
    try:
        ret_data = query_recent_transaction_dcl_swap(Cfg.NETWORK_ID, pool_id)
        # for ret in ret_data:
        #     if ret["tx_id"] is None:
        #         ret["tx_id"] = get_tx_id(ret["receipt_id"], Cfg.NETWORK_ID)
    except Exception as e:
        print("Exception when dcl-swap: ", e)
    return compress_response_content(ret_data)


@app.route('/get-recent-transaction-liquidity', methods=['GET'])
def handle_recent_transaction_liquidity():
    pool_id = request.args.get("pool_id")
    ret = []
    liquidity_data_list = query_recent_transaction_liquidity(Cfg.NETWORK_ID, pool_id)
    if liquidity_data_list is None:
        return ret
    try:
        for liquidity_data in liquidity_data_list:
            amounts = str(liquidity_data["amounts"])
            if "['0', '0']" == amounts:
                amounts = str([liquidity_data["amount_in"], liquidity_data["amount_out"]])
            ret_data = {
                "method_name": liquidity_data["method_name"],
                "pool_id": liquidity_data["pool_id"],
                "shares": liquidity_data["shares"],
                "timestamp": liquidity_data["timestamp"],
                "tx_id": liquidity_data["tx_id"],
                "amounts": amounts,
                "receipt_id": liquidity_data["receipt_id"]
            }
            # if ret_data["tx_id"] is None:
            #     ret_data["tx_id"] = get_tx_id(liquidity_data["block_hash"], Cfg.NETWORK_ID)
            ret.append(ret_data)
    except Exception as e:
        print("Exception when liquidity: ", e)
    return compress_response_content(ret)


@app.route('/get-recent-transaction-dcl-liquidity', methods=['GET'])
def handle_recent_transaction_dcl_liquidity():
    pool_id = request.args.get("pool_id")
    ret_data = []
    try:
        ret_data = query_recent_transaction_dcl_liquidity(Cfg.NETWORK_ID, pool_id)
        for ret_d in ret_data:
            ret_d["amount_x"] = str(int(ret_d["amount_x"]))
            ret_d["amount_y"] = str(int(ret_d["amount_y"]))
            # if ret_d["tx_id"] is None:
            #     ret_d["tx_id"] = get_tx_id(ret_d["receipt_id"], Cfg.NETWORK_ID)
    except Exception as e:
        print("Exception when dcl-liquidity: ", e)
    return compress_response_content(ret_data)


@app.route('/get-recent-transaction-limit-order', methods=['GET'])
def handle_recent_transaction_limit_order():
    pool_id = request.args.get("pool_id")
    ret_data = []
    try:
        ret_data = query_recent_transaction_limit_order(Cfg.NETWORK_ID, pool_id)
        # for ret in ret_data:
        #     if ret["tx_id"] is None:
        #         ret["tx_id"] = get_tx_id(ret["receipt_id"], Cfg.NETWORK_ID)
    except Exception as e:
        print("Exception when limit-order: ", e)
    return compress_response_content(ret_data)


@app.route('/get-dcl-points', methods=['GET'])
def handle_dcl_points():
    pool_id = request.args.get("pool_id")
    slot_number = request.args.get("slot_number", type=int, default=50)
    start_point = request.args.get("start_point", type=int, default=-800000)
    end_point = request.args.get("end_point", type=int, default=800000)
    if pool_id is None:
        return "null"
    pool_id_s = pool_id.split("|")
    token_x = pool_id_s[0]
    token_y = pool_id_s[1]
    token_list = [token_x, token_y]
    token_price = list_token_price_by_id_list(Cfg.NETWORK_ID, token_list)
    all_point_data, all_point_data_24h = query_dcl_points(Cfg.NETWORK_ID, pool_id)
    point_data = handle_point_data(all_point_data, int(start_point), int(end_point))
    point_data_24h = handle_point_data(all_point_data_24h, int(start_point), int(end_point))
    ret_point_data = handle_dcl_point_bin(pool_id, point_data, int(slot_number), int(start_point), int(end_point),
                                          point_data_24h, token_price)
    ret_data = {}
    top_bin_fee_data = handle_top_bin_fee(ret_point_data)
    ret_data["point_data"] = ret_point_data
    ret_data["top_bin_fee_data"] = top_bin_fee_data
    return compress_response_content(ret_data)


@app.route('/get-fee-by-account', methods=['GET'])
def handle_fee_by_account():
    ret_data = {}
    pool_id = request.args.get("pool_id")
    account_id = request.args.get("account_id")
    if pool_id is None or account_id is None:
        return "null"
    # unclaimed_fee_data = query_dcl_user_unclaimed_fee(Cfg.NETWORK_ID, pool_id, account_id)
    claimed_fee_data = query_dcl_user_claimed_fee(Cfg.NETWORK_ID, pool_id, account_id)
    fee_x = 0
    fee_y = 0
    # for unclaimed_fee in unclaimed_fee_data:
    #     if not unclaimed_fee["unclaimed_fee_x"] is None:
    #         fee_x = fee_x + int(unclaimed_fee["unclaimed_fee_x"])
    #     if not unclaimed_fee["unclaimed_fee_y"] is None:
    #         fee_y = fee_y + int(unclaimed_fee["unclaimed_fee_y"])
    for claimed_fee in claimed_fee_data:
        if not claimed_fee["claimed_fee_x"] is None:
            fee_x = fee_x + int(claimed_fee["claimed_fee_x"])
        if not claimed_fee["claimed_fee_y"] is None:
            fee_y = fee_y + int(claimed_fee["claimed_fee_y"])
    unclaimed_fee_data_24h = query_dcl_user_unclaimed_fee_24h(Cfg.NETWORK_ID, pool_id, account_id)
    claimed_fee_data_24h = query_dcl_user_claimed_fee_24h(Cfg.NETWORK_ID, pool_id, account_id)
    fee_x_24h = 0
    fee_y_24h = 0
    for unclaimed_fee_24h in unclaimed_fee_data_24h:
        if not unclaimed_fee_24h["unclaimed_fee_x"] is None:
            fee_x_24h = fee_x_24h + int(unclaimed_fee_24h["unclaimed_fee_x"])
        if not unclaimed_fee_24h["unclaimed_fee_y"] is None:
            fee_y_24h = fee_y_24h + int(unclaimed_fee_24h["unclaimed_fee_y"])
    for claimed_fee_24h in claimed_fee_data_24h:
        if not claimed_fee_24h["claimed_fee_x"] is None:
            fee_x_24h = fee_x_24h + int(claimed_fee_24h["claimed_fee_x"])
        if not claimed_fee_24h["claimed_fee_y"] is None:
            fee_y_24h = fee_y_24h + int(claimed_fee_24h["claimed_fee_y"])
    total_earned_fee = {
        "total_fee_x": fee_x,
        "total_fee_y": fee_y
    }
    total_fee_24h = {
        "fee_x": fee_x - fee_x_24h,
        "fee_y": fee_y - fee_y_24h,
    }
    # if total_fee_24h["fee_x"] < 0:
    #     total_fee_24h["fee_x"] = 0
    # if total_fee_24h["fee_y"] < 0:
    #     total_fee_24h["fee_y"] = 0
    user_tvl_data = query_dcl_user_tvl(Cfg.NETWORK_ID, pool_id, account_id)
    token_x = 0
    token_y = 0
    user_token_timestamp = 0
    for user_tvl in user_tvl_data:
        if not user_tvl["timestamp"] is None:
            user_token_timestamp = user_tvl["timestamp"]
            if not user_tvl["tvl_x_l"] is None:
                token_x = token_x + float(user_tvl["tvl_x_l"])
            if not user_tvl["tvl_y_l"] is None:
                token_y = token_y + float(user_tvl["tvl_y_l"])
    user_token = {
        "token_x": token_x,
        "token_y": token_y,
        "timestamp": user_token_timestamp,
    }
    change_log_data = query_dcl_user_change_log(Cfg.NETWORK_ID, pool_id, account_id, user_token_timestamp)
    ret_change_log_data = []
    for change_log in change_log_data:
        change_log_timestamp = int(int(change_log["timestamp"]) / 1000000000)
        if change_log_timestamp > user_token_timestamp:
            continue
        if change_log["token_x"] == "" or change_log["token_y"] == "":
            continue
        change_token_x = int(change_log["token_x"])
        change_token_y = int(change_log["token_y"])
        if change_log["event_method"] == "liquidity_removed":
            change_token_x = 0 - int(change_log["token_x"])
            change_token_y = 0 - int(change_log["token_y"])
        if change_log["event_method"] == "liquidity_merge":
            if change_log["remove_token_x"] == "" or change_log["merge_token_x"] == "" or change_log["remove_token_y"] == "" or change_log["merge_token_y"] == "":
                continue
            change_token_x = 0 - (int(change_log["remove_token_x"]) - int(change_log["merge_token_x"]))
            change_token_y = 0 - (int(change_log["remove_token_y"]) - int(change_log["merge_token_y"]))
        change_log = {
            "event_method": change_log["event_method"],
            "token_x": change_token_x,
            "token_y": change_token_y,
            "timestamp": change_log["timestamp"],
        }
        ret_change_log_data.append(change_log)
    ret_data["total_earned_fee"] = total_earned_fee
    ret_data["apr"] = {
        "fee_data": total_fee_24h,
        "user_token": user_token,
        "change_log_data": ret_change_log_data
    }
    return compress_response_content(ret_data)


@app.route('/get-dcl-points-by-account', methods=['GET'])
def handle_dcl_points_by_account():
    pool_id = request.args.get("pool_id")
    slot_number = request.args.get("slot_number", type=int, default=50)
    start_point = request.args.get("start_point", type=int, default=-800000)
    end_point = request.args.get("end_point", type=int, default=800000)
    account_id = request.args.get("account_id")
    if pool_id is None or account_id is None:
        return "null"
    point_data = query_dcl_points_by_account(Cfg.NETWORK_ID, pool_id, account_id, int(start_point), int(end_point))
    ret_point_data = handle_dcl_point_bin_by_account(pool_id, point_data, int(slot_number), account_id, int(start_point), int(end_point))
    return compress_response_content(ret_point_data)


@app.route('/total_supply', methods=['GET'])
def handle_total_supple():
    ret = "99990506.142591673655212239"
    return ret


@app.route('/circulating_supply', methods=['GET'])
def handle_circulating_supply():
    ret = get_circulating_supply()
    return ret


@app.route('/history-token-price-report', methods=['GET'])
def history_token_price_report():
    token = request.args.get("token")
    base_token = request.args.get("base_token")
    redis_key = token + "->" + base_token
    ret = get_history_token_price_report(Cfg.NETWORK_ID, redis_key)
    if ret is None:
        return "null"
    return compress_response_content(json.loads(ret))


current_date = datetime.datetime.now().strftime("%Y-%m-%d")
log_file = "app-%s.log" % current_date
logger.add(log_file)
if __name__ == '__main__':
    app.logger.setLevel(logging.INFO)
    app.logger.info(Welcome)
    app.run(host='0.0.0.0', port=28080, debug=False)
