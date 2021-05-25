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
from market import get_actions
from redis_provider import list_farms, list_top_pools, list_pools
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
    ret = get_actions("%s" % Cfg.NETWORK_ID, account_id)
    json_obj = json.loads(ret)
    return jsonify(json_obj)

@app.route('/list-farms', methods=['GET'])
@flask_cors.cross_origin()
def handle_list_farms():
    """
    list_farms
    """
    ret = list_farms("%s" % Cfg.NETWORK_ID)
    return jsonify(ret)

@app.route('/list-top-pools', methods=['GET'])
@flask_cors.cross_origin()
def handle_list_top_pools():
    """
    list_farms
    """
    ret = list_top_pools("%s" % Cfg.NETWORK_ID)
    return jsonify(ret)

@app.route('/list-pools', methods=['GET'])
@flask_cors.cross_origin()
def handle_list_pools():
    """
    list_farms
    """
    ret = list_pools("%s" % Cfg.NETWORK_ID)
    return jsonify(ret)


if __name__ == '__main__':
    app.logger.setLevel(logging.INFO)
    app.logger.info(Welcome)
    app.run(host='0.0.0.0', port=28080, debug=False)
