#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Marco'
# 导入Flask类
from http.client import responses
from flask import Flask
from flask import request
from flask import jsonify
import flask_cors 
import json
import logging
from indexer_provider import get_actions
from redis_provider import list_farms, list_top_pools, list_pools, list_token_price
from config import Cfg

Welcome = 'Welcome to ref datacenter API server, version 20210520.01'
# 实例化，可视为固定格式
app = Flask(__name__)


# route()方法用于设定路由；类似spring路由配置
@app.route('/')
def hello_world():
    return Welcome


@app.route('/latest-actions/<account_id>', methods=['GET'])
@flask_cors.cross_origin()
def handle_latest_actions(account_id):
    """
    get user's latest actions
    """
    ret = get_actions(Cfg.NETWORK_ID, account_id)
    json_obj = json.loads(ret)
    return jsonify(json_obj)

@app.route('/list-farms', methods=['GET'])
@flask_cors.cross_origin()
def handle_list_farms():
    """
    list_farms
    """
    ret = list_farms(Cfg.NETWORK_ID)
    return jsonify(ret)

@app.route('/list-top-pools', methods=['GET'])
@flask_cors.cross_origin()
def handle_list_top_pools():
    """
    list_top_pools
    """
    precisions = {}
    for token in Cfg.TOKENS[Cfg.NETWORK_ID]:
        precisions[token["NEAR_ID"]] = token["DECIMAL"]
    pools = list_top_pools(Cfg.NETWORK_ID)
    prices = list_token_price(Cfg.NETWORK_ID)
    for pool in pools:
        tvl0 = 0
        tvl1 = 0
        if pool['token_account_ids'][0] in prices:
            tvl0 = float(prices[pool['token_account_ids'][0]]) * int(pool['amounts'][0]) / (10 ** precisions[pool['token_account_ids'][0]])
        if pool['token_account_ids'][1] in prices:
            tvl1 = float(prices[pool['token_account_ids'][1]]) * int(pool['amounts'][1]) / (10 ** precisions[pool['token_account_ids'][1]])
        if tvl0 > 0 and tvl1 > 0:
            pool["tvl"] = str(tvl0 + tvl1)
        elif tvl0 > 0:
            pool["tvl"] = str(tvl0 * 2)
        elif tvl1 > 0:
            pool["tvl"] = str(tvl1 * 2)
        else:
            pool["tvl"] = "0"

    return jsonify(pools)

@app.route('/list-token-price', methods=['GET'])
@flask_cors.cross_origin()
def handle_list_token_price():
    """
    list_token_price
    """
    ret = {}
    prices = list_token_price(Cfg.NETWORK_ID)
    for token in Cfg.TOKENS[Cfg.NETWORK_ID]:
        ret[token["NEAR_ID"]] = {
            "price": prices[token["NEAR_ID"]], 
            "decimal": token["DECIMAL"],
            "symbol": token["SYMBOL"],
        }
    return jsonify(ret)
    

@app.route('/list-pools', methods=['GET'])
@flask_cors.cross_origin()
def handle_list_pools():
    """
    list_pools
    """
    ret = list_pools(Cfg.NETWORK_ID)
    return jsonify(ret)


if __name__ == '__main__':
    app.logger.setLevel(logging.INFO)
    app.logger.info(Welcome)
    app.run(host='0.0.0.0', port=28080, debug=False)
