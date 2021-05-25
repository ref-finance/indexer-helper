#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Marco'

"""

"""


class Cfg:
    NETWORK = {
        "TESTNET": {
            "NEAR_RPC_URL": "https://rpc.testnet.near.org",
            "FARMING_CONTRACT": "ref-farming.testnet",
            "REF_CONTRACT": "ref-finance.testnet",
            "REDIS_KEY": "FARMS_TESTNET",
            "REDIS_POOL_KEY": "POOLS_TESTNET",
            "REDIS_TOP_POOL_KEY": "TOP_POOLS_TESTNET",
            "INDEXER_DSN": "testnet_explorer",
            "INDEXER_UID": "public_readonly",
            "INDEXER_PWD": "nearprotocol",
            "INDEXER_HOST": "35.184.214.98",
            "INDEXER_PORT": "5432",
        },
        "MAINNET": {
            "NEAR_RPC_URL": "https://rpc.mainnet.near.org",
            "FARMING_CONTRACT": "ref-farming.near",
            "REF_CONTRACT": "ref-finance.near",
            "REDIS_KEY": "FARMS_MAINNET",
            "REDIS_POOL_KEY": "POOLS_MAINNET",
            "REDIS_TOP_POOL_KEY": "TOP_POOLS_MAINNET",
            "INDEXER_DSN": "mainnet_explorer",
            "INDEXER_UID": "public_readonly",
            "INDEXER_PWD": "nearprotocol",
            "INDEXER_HOST": "104.199.89.51",
            "INDEXER_PORT": "5432",
        }
    }


