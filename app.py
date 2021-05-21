#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Marco'
# 导入Flask类
from http.client import responses
from flask import Flask
from flask import request
from flask import jsonify
import logging
from market import get_actions, get_actions_testnet

Welcome = 'Welcome to ref datacenter API server, version 20210520.01'
# 实例化，可视为固定格式
app = Flask(__name__)


# route()方法用于设定路由；类似spring路由配置
@app.route('/')
def hello_world():
    return Welcome


@app.route('/latest-actions/<account_id>', methods=['GET'])
def handle_latest_actions(account_id):
    """
    get user's latest actions
    """
    ret = get_actions(account_id)
    return ret

@app.route('/latest-actions-testnet/<account_id>', methods=['GET'])
def handle_latest_actions_testnet(account_id):
    """
    get user's latest actions
    """
    ret = get_actions_testnet(account_id)
    return ret



if __name__ == '__main__':
    app.logger.setLevel(logging.INFO)
    app.logger.info(Welcome)
    app.run(host='0.0.0.0', port=28080, debug=False)
