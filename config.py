#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Marco'


try:
    from rpc_info import TESTNET_RPC_URL, MAINNET_RPC_URL
except ImportError:
    TESTNET_RPC_URL= ["https://rpc.testnet.near.org", ]
    MAINNET_RPC_URL= ["https://rpc.mainnet.near.org", ]

"""

"""

class Cfg:
    NETWORK_ID = "TESTNET"
    NETWORK = {
        "TESTNET": {
            "NEAR_RPC_URL": TESTNET_RPC_URL,
            "FARMING_CONTRACT": "farm102.ref-dev.testnet",
            "REF_CONTRACT": "exchange102.ref-dev.testnet",
            "REDIS_KEY": "FARMS_TESTNET_DEV",
            "REDIS_POOL_KEY": "POOLS_TESTNET_DEV",
            "REDIS_POOL_BY_TOKEN_KEY": "POOLS_BY_TOKEN_TESTNET_DEV",
            "REDIS_TOP_POOL_KEY": "TOP_POOLS_TESTNET_DEV",
            "REDIS_TOKEN_PRICE_KEY": "TOKEN_PRICE_TESTNET_DEV",
            "REDIS_TOKEN_METADATA_KEY": "TOKEN_METADATA_TESTNET_DEV",
            "REDIS_WHITELIST_KEY": "WHITELIST_TESTNET_DEV",
            "INDEXER_DSN": "testnet_explorer",
            "INDEXER_UID": "public_readonly",
            "INDEXER_PWD": "nearprotocol",
            "INDEXER_HOST": "35.184.214.98",
            "INDEXER_PORT": "5432",
        }
    }
    TOKENS = {
        "TESTNET": [
            {"SYMBOL": "near", "NEAR_ID": "wrap.testnet", "MD_ID": "near", "DECIMAL": 24},
            {"SYMBOL": "nDAI", "NEAR_ID": "ndai.ft-fin.testnet", "MD_ID": "dai", "DECIMAL": 8},
            {"SYMBOL": "nUSDT", "NEAR_ID": "nusdt.ft-fin.testnet", "MD_ID": "tether", "DECIMAL": 6},
            {"SYMBOL": "ref", "NEAR_ID": "rft.tokenfactory.testnet", "MD_ID": "ref-finance.testnet|24|wrap.testnet", "DECIMAL": 8},
        ],
    }
    MARKET_URL = "api.coingecko.com"


if __name__ == '__main__':
    print(type(Cfg))
    print(type(Cfg.TOKENS))
    print(type(Cfg.NETWORK_ID), Cfg.NETWORK_ID)
    print(Cfg.NETWORK["TESTNET"]["NEAR_RPC_URL"])