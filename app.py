#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Marco'

# Import flask class
from http.client import responses
from flask import Flask
from flask import request
from flask import jsonify
import flask_cors
import json
import logging
from indexer_provider import get_proposal_id_hash
from redis_provider import list_farms, list_top_pools, list_pools, list_token_price, list_whitelist, get_token_price
from redis_provider import list_pools_by_id_list, list_token_metadata, list_pools_by_tokens, get_pool
from redis_provider import list_token_price_by_id_list, get_proposal_hash_by_id, get_24h_pool_volume, get_account_pool_assets
from redis_provider import get_dcl_pools_volume_list, get_24h_pool_volume_list, get_dcl_pools_tvl_list, get_token_price_ratio_report
from utils import combine_pools_info, compress_response_content, get_ip_address, pools_filter, get_tx_id
from config import Cfg
from db_provider import get_history_token_price, query_limit_order_log, query_limit_order_swap, get_liquidity_pools, get_actions, query_burrow_log, get_history_token_price_by_token
import re
from flask_limiter import Limiter
from loguru import logger


service_version = "20230912.01"
Welcome = 'Welcome to ref datacenter API server, version ' + service_version + ', indexer %s' % \
          Cfg.NETWORK[Cfg.NETWORK_ID]["INDEXER_HOST"][-3:]
# Instantiation, which can be regarded as fixed format
app = Flask(__name__)
limiter = Limiter(
    app,
    key_func=get_ip_address,
    default_limits=["20 per second"],
    storage_uri="redis://:@127.0.0.1:6379/2"
)


@app.before_request
def before_request():
    # Processing get requests
    data = request.args
    for v in data.values():
        v = str(v).lower()
        pattern = r"(<script>|</script>)|(\*|;)"
        r = re.search(pattern, v)
        if r:
            return 'Please enter the parameters of the specification!'


# route()Method is used to set the route; Similar to spring routing configuration
@app.route('/')
def hello_world():
    return Welcome


@app.route('/timestamp', methods=['GET'])
@flask_cors.cross_origin()
@limiter.limit("1/5 second")
def handle_timestamp():
    import time
    return jsonify({"ts": int(time.time())})


@app.route('/latest-actions/<account_id>', methods=['GET'])
@flask_cors.cross_origin()
def handle_latest_actions(account_id):
    """
    get user's latest actions
    """
    json_obj = []
    try:
        ret = get_actions(Cfg.NETWORK_ID, account_id)
        json_obj = json.loads(ret)
        for obj in json_obj:
            if obj[1] == "":
                obj[1] = get_tx_id(obj[7], Cfg.NETWORK_ID)
    except Exception as e:
        print("Exception when get_actions: ", e)

    return compress_response_content(json_obj)


@app.route('/liquidity-pools/<account_id>', methods=['GET'])
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
def handle_list_farms():
    """
    list_farms
    """
    ret = list_farms(Cfg.NETWORK_ID)
    return compress_response_content(ret)


@app.route('/get-token-price', methods=['GET'])
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
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


@app.route('/list-token-price-by-ids', methods=['GET'])
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
def handle_list_token():
    """
    list_token
    """
    ret = list_token_metadata(Cfg.NETWORK_ID)
    return compress_response_content(ret)


@app.route('/get-pool', methods=['GET'])
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
def handle_list_top_pools():
    """
    list_top_pools
    """

    pools = list_top_pools(Cfg.NETWORK_ID)
    prices = list_token_price(Cfg.NETWORK_ID)
    metadata = list_token_metadata(Cfg.NETWORK_ID)

    combine_pools_info(pools, prices, metadata)

    return compress_response_content(pools)


@app.route('/list-pools', methods=['GET'])
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
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
                ret[key] = {
                    "pool_id": pool["id"],
                    "token_symbol": pool["token_symbols"][0],
                    "other_token": pool["token_symbols"][1],
                    "token_decimals": [whitelist[token0]["decimals"], whitelist[token1]["decimals"]],
                    "liquidity_amounts": pool["amounts"],
                    "price_in_usd": str(float(prices[token1]) * balance1 / balance0) if token1 in prices else "N/A",
                    "price_in_other_token": str(balance1 / balance0),
                    "vol_to_other_token": pool["vol01"],
                    "vol_from_other_token": pool["vol10"],
                }

    return compress_response_content(ret)


@app.route('/list-history-token-price-by-ids', methods=['GET'])
@flask_cors.cross_origin()
def handle_history_token_price_by_ids():
    ids = request.args.get("ids", "")
    ids = ("|" + ids.lstrip("|").rstrip("|") + "|")
    id_str_list = ids.lstrip("|").rstrip("|").split("|")

    ret = get_history_token_price([str(x) for x in id_str_list])
    return compress_response_content(ret)


@app.route('/get-service-version', methods=['GET'])
@flask_cors.cross_origin()
@limiter.limit("1/second")
def get_service_version():
    return jsonify(service_version)


@app.route('/get-proposal-hash-by-id', methods=['GET'])
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
def handle_24h_pool_volume():
    pool_id = request.args.get("pool_id")
    if pool_id is None:
        return ''
    res = get_24h_pool_volume(Cfg.NETWORK_ID, pool_id)
    return compress_response_content(res)


@app.route('/get-dcl-pools-volume', methods=['GET'])
@flask_cors.cross_origin()
def handle_dcl_pools_volume():
    pool_id = request.args.get("pool_id")
    if pool_id is None:
        return ''
    res = get_dcl_pools_volume_list(Cfg.NETWORK_ID, pool_id)
    return compress_response_content(res)


@app.route('/get-24h-volume-list', methods=['GET'])
@flask_cors.cross_origin()
def handle_24h_pool_volume_list():
    res = get_24h_pool_volume_list(Cfg.NETWORK_ID)
    return compress_response_content(res)


@app.route('/get-dcl-pools-tvl-list', methods=['GET'])
@flask_cors.cross_origin()
def handle_dcl_pools_tvl_list():
    pool_id = request.args.get("pool_id")
    if pool_id is None:
        return ''
    res = get_dcl_pools_tvl_list(Cfg.NETWORK_ID, pool_id)
    return compress_response_content(res)


@app.route('/get-limit-order-log-by-account/<account_id>', methods=['GET'])
@flask_cors.cross_origin()
def get_limit_order_log_by_account(account_id):
    res = query_limit_order_log(Cfg.NETWORK_ID, account_id)
    return compress_response_content(res)


@app.route('/get-limit-order-swap-by-account/<account_id>', methods=['GET'])
@flask_cors.cross_origin()
def get_limit_order_swap_by_account(account_id):
    res = query_limit_order_swap(Cfg.NETWORK_ID, account_id)
    return compress_response_content(res)


@app.route('/get-assets-by-account', methods=['GET'])
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
def token_history_token_price_by_token():
    ids = request.args.get("ids", "")
    id_str_list = ids.split("|")
    data_time = request.args.get("data_time")
    ret = get_history_token_price_by_token(id_str_list, data_time)
    return compress_response_content(ret)


logger.add("app.log")
if __name__ == '__main__':
    app.logger.setLevel(logging.INFO)
    app.logger.info(Welcome)
    app.run(host='0.0.0.0', port=28080, debug=False)
